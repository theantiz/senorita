import asyncio
import json
import os
from datetime import datetime
from typing import Any
from uuid import UUID
from zoneinfo import ZoneInfo

from google.genai import types
from google.genai.errors import ClientError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.gemini_client import get_client, start_chat
from app.agents.prompts import build_system_instruction
from app.agents.tool_registry import SENORITA_TOOLS, discover_tools_for_message, execute_tool, gemini_tools_for_names
from app.agents.tool_system.persistence import redact_sensitive_arguments

AGENT_MAX_EXECUTION_TIME = int(os.environ.get("AGENT_MAX_EXECUTION_TIME", "600"))

from app.core.config import settings
from app.core.logger import logger
from app.core.state import get_pause_state
from app.db.models import ActionLog, Contact, Conversation, Task, User
from app.db.session import async_session_factory
from app.memory.embeddings import embed_text
from app.memory.retrieval import search_similar_memory

MAX_CONTEXT_MESSAGES = 10
MAX_TOOL_ROUNDS = 5
MODEL_RETRY_ATTEMPTS = 3
TOOL_RESULT_CHAR_LIMIT = 12_000


def _zone_info_or_utc(timezone_str: str | None) -> ZoneInfo:
    try:
        return ZoneInfo(timezone_str or "UTC")
    except Exception:
        return ZoneInfo("UTC")


def _strip_json_fence(text: str) -> str:
    text = text.strip()
    if text.startswith("```json"):
        return text[7:].removesuffix("```").strip()
    if text.startswith("```"):
        return text[3:].removesuffix("```").strip()
    return text


def _response_text(response: Any) -> str:
    try:
        return (response.text or "").strip()
    except ValueError:
        return ""


def _compact_json_for_model(value: Any, max_chars: int = TOOL_RESULT_CHAR_LIMIT) -> str:
    text = json.dumps(value, default=str, ensure_ascii=False)
    if len(text) <= max_chars:
        return text
    return f"{text[:max_chars]}... [truncated {len(text) - max_chars} chars]"


async def _call_model_with_retries(client: Any, contents: list[Any], config: types.GenerateContentConfig) -> Any:
    for attempt in range(MODEL_RETRY_ATTEMPTS):
        try:
            return await client.aio.models.generate_content(
                model=settings.GEMINI_MODEL,
                contents=contents,
                config=config,
            )
        except ClientError as exc:
            if "thought_signature" in str(exc) and attempt < MODEL_RETRY_ATTEMPTS - 1:
                logger.warning("Model dropped thought_signature, retrying (%s/%s)", attempt + 1, MODEL_RETRY_ATTEMPTS)
                await asyncio.sleep(0.5)
                continue
            raise

    raise RuntimeError("Failed to generate content after retries.")


async def _safe_memory_context(session: AsyncSession, user_id: UUID, message_text: str):
    try:
        query_embedding = await embed_text(message_text, task_type="RETRIEVAL_QUERY")
        if not query_embedding:
            return []
        return await search_similar_memory(session, user_id, query_embedding, top_k=5)
    except Exception:
        logger.warning("Memory retrieval failed; continuing without retrieved context", exc_info=True)
        return []


async def _fetch_contacts(session: AsyncSession, user_id: UUID) -> list[Contact]:
    result = await session.execute(select(Contact).where(Contact.user_id == user_id))
    return list(result.scalars().all())


async def _fetch_conversation_history(session: AsyncSession, user_id: UUID) -> list[Conversation]:
    stmt = (
        select(Conversation)
        .where(Conversation.user_id == user_id)
        .order_by(Conversation.created_at.desc())
        .limit(MAX_CONTEXT_MESSAGES)
    )
    result = await session.execute(stmt)
    return list(result.scalars().all())


def _previous_interaction_id(history: list[Conversation]) -> str | None:
    for conversation in history:
        if conversation.gemini_interaction_id:
            return conversation.gemini_interaction_id
    return None


def _build_contents(history: list[Conversation], message_text: str) -> list[Any]:
    contents: list[Any] = []
    for conversation in reversed(history):
        role = "user" if conversation.role == "user" else "model"
        contents.append(types.Content(role=role, parts=[types.Part.from_text(text=conversation.content)]))
    contents.append(types.Content(role="user", parts=[types.Part.from_text(text=message_text)]))
    return contents


async def _record_tool_result(
    session: AsyncSession,
    user_id: UUID,
    function_name: str,
    args: dict,
    tool_result: dict[str, Any],
) -> None:
    result = "failed" if tool_result.get("error") else "success"
    session.add(
        ActionLog(
            user_id=user_id,
            action_type=function_name,
            payload=redact_sensitive_arguments(args),
            result=result,
        )
    )
    await session.commit()


async def _execute_tool_calls_for_model(session: AsyncSession, user_id: UUID, function_calls: list[Any]) -> str:
    text_responses = []
    for function_call in function_calls:
        function_name = function_call.name or ""
        args = function_call.args or {}

        tool_result = await execute_tool(session, user_id, function_name, args)

        await _record_tool_result(session, user_id, function_name, args, tool_result)
        text_responses.append(
            f"Tool `{function_name}` was called with args: {_compact_json_for_model(args)}\n"
            f"Result: {_compact_json_for_model(tool_result)}"
        )

    return "\n\n".join(text_responses)


async def _resolve_contact_id(session: AsyncSession, user_id: UUID, contact_name: str | None) -> UUID | None:
    if not contact_name:
        return None
    stmt = select(Contact).where(Contact.user_id == user_id, Contact.name.ilike(f"%{contact_name}%"))
    result = await session.execute(stmt)
    contacts = result.scalars().all()
    return contacts[0].id if len(contacts) == 1 else None


def _parse_optional_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


async def _maybe_create_promise_task(session: AsyncSession, user_id: UUID, capture: dict[str, Any]) -> None:
    if capture.get("category") != "promise":
        return

    subject = capture.get("subject")
    if not subject:
        return

    contact_id = await _resolve_contact_id(session, user_id, capture.get("contact_name"))
    task = Task(
        user_id=user_id,
        title=subject,
        description="[Auto-captured from conversation]",
        due_at=_parse_optional_datetime(capture.get("due_at")),
        contact_id=contact_id,
    )
    session.add(task)


async def _implicit_capture_routine(
    user_id: UUID, message_text: str, final_text: str, sensitivity: str, timezone_str: str
):
    if sensitivity == "off" or get_pause_state():
        return

    user_tz = _zone_info_or_utc(timezone_str)
    current_time_iso = datetime.now(user_tz).isoformat()

    prompt = f"""Analyze the following exchange. Did the user mention a durable fact about their life worth remembering that wasn't already explicitly stored?
If yes, extract it as a single sentence. Return ONLY a JSON object with:
'has_fact': boolean,
'fact': string (the sentence),
'category': string (one of: person, preference, date, promise, context),
'confidence': float (0.0 to 1.0)
If category is 'promise', also extract:
'subject': string (what the user promised to do),
'contact_name': string or null (who they promised it to or about),
'due_at': string or null (resolve any relative due date like 'tomorrow' into an ISO 8601 timestamp using the current date: {current_time_iso}. If a date/time is not clearly specified, leave as null)

User: {message_text}
Assistant: {final_text}
"""
    try:
        chat = start_chat()
        response = await chat.send_message(prompt)
        data = json.loads(_strip_json_fence(response.text or ""))

        has_fact = data.get("has_fact")
        confidence = float(data.get("confidence", 0.0))
        fact = data.get("fact")
        category = data.get("category", "context")

        if not has_fact or not fact:
            return

        if sensitivity == "conservative" and confidence < 0.8:
            return

        async with async_session_factory() as session:
            await _maybe_create_promise_task(session, user_id, data)

            from app.db.models import MemoryEntry

            embedding = await embed_text(fact, task_type="RETRIEVAL_DOCUMENT")
            mem = MemoryEntry(
                user_id=user_id,
                content=fact,
                category=category,
                source_ref="implicit_capture",
                confidence=confidence,
                embedding=embedding,
            )
            session.add(mem)
            await session.commit()
    except Exception:
        logger.warning("Implicit capture failed", exc_info=True)


async def handle_message(session: AsyncSession, user: User, message_text: str) -> str:  # noqa: C901
    from app.agents.context import AgentContext
    from app.agents.context_builder import build_context
    from app.agents.executor import PlanExecutor
    from app.agents.intent import extract_intent
    from app.agents.llm_provider import GeminiProvider
    from app.agents.plan_validator import PlanValidationError, validate_plan
    from app.agents.planner import generate_plan
    from app.agents.tool_registry import get_tool_registry
    from app.agents.tool_system.planner import ToolPlanner
    from app.db.models.plan import AgentPlan, AgentPlanStep
    from app.db.models.run import AgentRun

    message_text = message_text.strip()
    conv_history = await _fetch_conversation_history(session, user.id)
    new_interaction_id = _previous_interaction_id(conv_history)

    # 1. Build Base Context
    context = AgentContext(
        user_id=str(user.id),
        conversation_id=new_interaction_id,
        request_id=new_interaction_id or "",
        message=message_text,
        timezone=user.timezone,
        recent_messages=[{"role": msg.role, "content": msg.content} for msg in conv_history[-5:]],
    )
    provider = GeminiProvider()

    # 2. Extract Intent
    intent = await extract_intent(context, provider)
    context.intent = intent

    # 3. Build Enriched Context via ContextBuilder
    context = await build_context(session, user, context)

    sys_inst = build_system_instruction(user) + "\n" + context.enriched_context

    if intent.ambiguities:
        final_text = "I need a bit more clarification, baby: " + " ".join(intent.ambiguities)
    elif intent.routing_decision == "MULTI_STEP_PLAN":
        # 3. Complex Request -> Plan
        planner = ToolPlanner(get_tool_registry())
        discovered_tool_names = planner.discover(message_text, intent=intent)

        # Get raw definitions to pass to prompt
        registry = get_tool_registry()
        available_tools_info = [
            {"name": t.name, "description": t.description, "risk_level": t.risk_level.name}
            for t in registry.enabled()
            if t.name in discovered_tool_names
        ]

        plan = await generate_plan(context, intent, available_tools_info, provider)

        try:
            validate_plan(plan)

            # Persist Plan to Database
            db_plan = AgentPlan(user_id=user.id, conversation_id=new_interaction_id, goal=plan.goal, status="CREATED")
            session.add(db_plan)
            await session.flush()

            for step in plan.steps:
                db_step = AgentPlanStep(
                    plan_id=db_plan.id,
                    step_id=step.step_id,
                    tool_name=step.tool_name,
                    arguments=step.arguments,
                    depends_on=step.depends_on,
                    execution_mode=step.execution_mode,
                    risk_level=step.risk_level,
                    status="CREATED",
                )
                session.add(db_step)

            # Persist Run
            db_run = AgentRun(
                user_id=user.id,
                conversation_id=new_interaction_id,
                plan_id=db_plan.id,
                status="CREATED",
            )
            session.add(db_run)
            await session.commit()

            # Start Background Execution
            import asyncio
            import os

            from app.db.session import async_session_factory

            async def _bg_executor(run_id):
                try:
                    async with async_session_factory() as bg_session:
                        executor = PlanExecutor(bg_session, run_id, GeminiProvider())
                        try:
                            await asyncio.wait_for(executor.run(), timeout=AGENT_MAX_EXECUTION_TIME)
                        except asyncio.TimeoutError:
                            from sqlalchemy import select

                            from app.agents.events import record_and_publish_event
                            from app.db.models.run import AgentRun

                            stmt = select(AgentRun).where(AgentRun.id == run_id)
                            res = await bg_session.execute(stmt)
                            run = res.scalar_one_or_none()
                            if run:
                                run.status = "FAILED"
                                await bg_session.commit()
                                await record_and_publish_event(
                                    bg_session, run.id, "agent.failed", "failed", "Execution timed out.", run.plan_id
                                )
                except Exception as e:
                    logger.error(f"Background execution failed: {e}")

            asyncio.create_task(_bg_executor(db_run.id))

            final_text = f"I've started a background plan for you, baby. (Run ID: {db_run.id})"

        except PlanValidationError as e:
            logger.warning(f"Plan validation failed: {e}")
            final_text = f"I tried to make a plan for that, baby, but it wasn't safe to execute. {str(e)}"
    else:
        # 4. Simple Request -> Direct Execution Fallback
        # Persist Run without a plan
        db_run = AgentRun(
            user_id=user.id,
            conversation_id=new_interaction_id,
            status="CREATED",
        )
        session.add(db_run)
        await session.commit()

        final_text = f"I've started a background run for you, baby. (Run ID: {db_run.id})"

        import asyncio

        from app.db.session import async_session_factory

        async def _bg_direct_executor(run_id, msg_text, sys_instruction, contents_list, interaction_id):
            try:
                async with async_session_factory() as bg_session:
                    from sqlalchemy import select

                    from app.agents.events import record_and_publish_event
                    from app.db.models.run import AgentRun

                    stmt = select(AgentRun).where(AgentRun.id == run_id)
                    res = await bg_session.execute(stmt)
                    run = res.scalar_one()

                    run.status = "RUNNING"
                    await bg_session.commit()
                    await record_and_publish_event(bg_session, run.id, "agent.started", "running", "Agent run started")

                    client = get_client()
                    discovered_tool_names = discover_tools_for_message(msg_text)
                    available_tools = gemini_tools_for_names(discovered_tool_names)
                    config = types.GenerateContentConfig(
                        tools=available_tools,
                        system_instruction=sys_instruction,
                        automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
                    )

                    response = None
                    for round_index in range(MAX_TOOL_ROUNDS + 1):
                        response = await _call_model_with_retries(client, contents_list, config)

                        function_calls = response.function_calls
                        if not function_calls:
                            if response.candidates:
                                contents_list.append(response.candidates[0].content)
                            break

                        if round_index >= MAX_TOOL_ROUNDS:
                            break

                        model_text = _response_text(response) or "I am using my tools to fulfill the request."
                        contents_list.append(types.Content(role="model", parts=[types.Part.from_text(text=model_text)]))

                        await record_and_publish_event(
                            bg_session, run.id, "agent.step_started", "running", f"Running {len(function_calls)} tools"
                        )

                        tool_response_text = await _execute_tool_calls_for_model(bg_session, user.id, function_calls)
                        contents_list.append(
                            types.Content(role="user", parts=[types.Part.from_text(text=tool_response_text)])
                        )

                    final_out = _response_text(response) if response else "I couldn't generate a response."

                    run.status = "COMPLETED"
                    await bg_session.commit()
                    await record_and_publish_event(bg_session, run.id, "agent.completed", "completed", final_out)

                    # Finalize Conversation for background run
                    bg_session.add(
                        Conversation(
                            user_id=user.id, gemini_interaction_id=interaction_id, role="assistant", content=final_out
                        )
                    )
                    await bg_session.commit()

                    await _implicit_capture_routine(
                        user_id=user.id,
                        message_text=msg_text,
                        final_text=final_out,
                        sensitivity=user.memory_capture_sensitivity,
                        timezone_str=user.timezone,
                    )
            except Exception as e:
                logger.error(f"Direct execution background failed: {e}")

        contents = _build_contents(conv_history, message_text)

        async def _timeout_wrapper():
            try:
                await asyncio.wait_for(
                    _bg_direct_executor(db_run.id, message_text, sys_inst, contents, new_interaction_id),
                    timeout=AGENT_MAX_EXECUTION_TIME,
                )
            except asyncio.TimeoutError:
                async with async_session_factory() as bg_session:
                    from sqlalchemy import select

                    from app.agents.events import record_and_publish_event
                    from app.db.models.run import AgentRun

                    stmt = select(AgentRun).where(AgentRun.id == db_run.id)
                    res = await bg_session.execute(stmt)
                    run = res.scalar_one_or_none()
                    if run:
                        run.status = "FAILED"
                        await bg_session.commit()
                        await record_and_publish_event(
                            bg_session, run.id, "agent.failed", "failed", "Execution timed out."
                        )

        asyncio.create_task(_timeout_wrapper())

    # Finalize Conversation for the initial user message
    session.add(
        Conversation(user_id=user.id, gemini_interaction_id=new_interaction_id, role="user", content=message_text)
    )
    await session.commit()

    return final_text
