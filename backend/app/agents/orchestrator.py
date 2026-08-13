from datetime import datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import ActionLog, Contact, Conversation, Task, User

try:
    from zoneinfo import ZoneInfo
except ImportError:
    from backports.zoneinfo import ZoneInfo
import asyncio
import json

from google.genai import types

from app.agents.gemini_client import get_client, start_chat
from app.agents.prompts import build_system_instruction
from app.agents.tool_registry import SENORITA_TOOLS, execute_tool
from app.core.config import settings
from app.core.logger import logger
from app.core.state import get_pause_state
from app.db.session import async_session_factory
from app.memory.embeddings import embed_text
from app.memory.retrieval import search_similar_memory


async def _implicit_capture_routine(user_id: UUID, message_text: str, final_text: str, sensitivity: str, timezone_str: str):
    if sensitivity == 'off' or get_pause_state():
        return

    try:
        user_tz = ZoneInfo(timezone_str)
    except Exception:
        user_tz = ZoneInfo("UTC")
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
        text = response.text.strip()
        if text.startswith("```json"):
            text = text[7:-3]
        elif text.startswith("```"):
            text = text[3:-3]
        data = json.loads(text)

        has_fact = data.get("has_fact")
        confidence = float(data.get("confidence", 0.0))
        fact = data.get("fact")
        category = data.get("category", "context")

        if not has_fact or not fact:
            return

        if sensitivity == 'conservative' and confidence < 0.8:
            return

        async with async_session_factory() as session:
            if category == 'promise':
                subject = data.get("subject")
                contact_name = data.get("contact_name")
                due_at_str = data.get("due_at")

                contact_id = None
                if contact_name:
                    stmt = select(Contact).where(Contact.user_id == user_id, Contact.name.ilike(f"%{contact_name}%"))
                    result = await session.execute(stmt)
                    contacts = result.scalars().all()
                    if len(contacts) == 1:
                        contact_id = contacts[0].id

                task_due = None
                if due_at_str:
                    try:
                        task_due = datetime.fromisoformat(due_at_str.replace("Z", "+00:00"))
                    except Exception:
                        pass

                if subject:
                    task = Task(
                        user_id=user_id,
                        title=subject,
                        description="[Auto-captured from conversation]",
                        due_at=task_due,
                        contact_id=contact_id
                    )
                    session.add(task)

            from db.models import MemoryEntry
            embedding = await embed_text(fact, task_type="RETRIEVAL_DOCUMENT")
            mem = MemoryEntry(
                user_id=user_id,
                content=fact,
                category=category,
                source_ref='implicit_capture',
                embedding=embedding
            )
            session.add(mem)
            await session.commit()
    except Exception as e:
        logger.error(f"Implicit capture failed: {e}")


async def handle_message(session: AsyncSession, user: User, message_text: str) -> str:
    # a. Embed message_text
    query_embedding = await embed_text(message_text, task_type="RETRIEVAL_QUERY")

    # b. Search similar memory for top-5 context
    memories = await search_similar_memory(session, user.id, query_embedding, top_k=5)

    # c. Fetch the user's contacts
    stmt_contacts = select(Contact).where(Contact.user_id == user.id)
    res_contacts = await session.execute(stmt_contacts)
    contacts = list(res_contacts.scalars().all())

    # d. Fetch the last 10 conversation rows
    stmt_conv = (
        select(Conversation)
        .where(Conversation.user_id == user.id)
        .order_by(Conversation.created_at.desc())
        .limit(10)
    )
    res_conv = await session.execute(stmt_conv)
    conv_history = list(res_conv.scalars().all())

    previous_interaction_id = None
    for c in conv_history:
        if c.gemini_interaction_id:
            previous_interaction_id = c.gemini_interaction_id
            break

    new_interaction_id = previous_interaction_id

    # e. Build system instruction
    sys_inst = build_system_instruction(user, memories, contacts)

    # f. Build the initial contents list.
    #    We use a stateless generate_content loop so that the full model response
    #    (including thought parts and thought_signature) is preserved across tool
    #    call iterations — the stateful chat object strips thought parts when we
    #    manually inject history, which causes the 400 INVALID_ARGUMENT error on
    #    thinking models like gemini-3.1-flash-lite.
    contents: list[types.Content] = []

    # Inject prior text turns for context (no thought parts needed for old turns)
    conv_history.reverse()  # chronological order
    for c in conv_history:
        role = "user" if c.role == "user" else "model"
        contents.append(types.Content(role=role, parts=[types.Part.from_text(text=c.content)]))

    # Append the current user message
    contents.append(types.Content(role="user", parts=[types.Part.from_text(text=message_text)]))

    client = get_client()
    config = types.GenerateContentConfig(
        tools=SENORITA_TOOLS,
        system_instruction=sys_inst,
        automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True)
    )

    # g. Stateless agentic loop — up to 5 tool-call rounds
    for _ in range(6):  # 1 initial call + up to 5 tool-call rounds
        from google.genai.errors import ClientError

        response = None
        for attempt in range(3):
            try:
                response = await client.aio.models.generate_content(
                    model=settings.GEMINI_MODEL,
                    contents=contents,
                    config=config,
                )
                break
            except ClientError as e:
                if "thought_signature" in str(e) and attempt < 2:
                    logger.warning(f"Model dropped thought_signature, retrying ({attempt+1}/3)...")
                    await asyncio.sleep(0.5)
                else:
                    raise
            except Exception:
                raise

        if not response:
            raise RuntimeError("Failed to generate content after 3 retries due to thought_signature validation errors.")

        function_calls = response.function_calls
        if not function_calls:
            if response.candidates:
                contents.append(response.candidates[0].content)
            break

        # Tools were called. To bypass thought_signature validation bug in google-genai,
        # we format the model's tool calls and results as text history instead of native FunctionCall parts.
        try:
            model_text = response.text
        except ValueError:
            model_text = ""
        model_text = model_text or "I am using my tools to fulfill the request."
        contents.append(types.Content(role="model", parts=[types.Part.from_text(text=model_text)]))

        # Execute all tool calls and collect function responses
        text_responses = []
        for fc in function_calls:
            fn_name = fc.name
            args = fc.args

            action = ActionLog(
                user_id=user.id,
                action_type=fn_name,
                payload=args,
                result="pending"
            )
            session.add(action)
            await session.flush()

            tool_res = await execute_tool(session, user.id, fn_name, args)

            action.result = "failed" if "error" in tool_res else "success"
            await session.commit()

            text_responses.append(f"Tool `{fn_name}` was called with args: {json.dumps(args)}\nResult: {json.dumps(tool_res)}")

        # Append function responses as a user turn so the model sees the results
        contents.append(types.Content(role="user", parts=[types.Part.from_text(text="\n\n".join(text_responses))]))

    # h. Persist to conversations table
    final_text = response.text or ""

    session.add(Conversation(
        user_id=user.id,
        gemini_interaction_id=new_interaction_id,
        role="user",
        content=message_text,
    ))
    session.add(Conversation(
        user_id=user.id,
        gemini_interaction_id=new_interaction_id,
        role="assistant",
        content=final_text,
    ))
    await session.commit()

    # Implicit capture trigger
    asyncio.create_task(
        _implicit_capture_routine(
            user_id=user.id,
            message_text=message_text,
            final_text=final_text,
            sensitivity=user.memory_capture_sensitivity,
            timezone_str=user.timezone
        )
    )

    return final_text
