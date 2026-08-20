import asyncio
import json
import logging
import uuid
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload

from app.agents.context import AgentContext
from app.agents.llm_provider import GeminiProvider, LLMProvider
from app.agents.tool_registry import execute_tool
from app.db.models.plan import AgentPlan, AgentPlanStep

logger = logging.getLogger(__name__)

class PlanExecutionError(Exception):
    pass


class PlanExecutor:
    """
    Phase 3E: Evaluates and orchestrates the DAG steps of an AgentPlan.
    Handles Just-In-Time argument evaluation and parallel/sequential tool dispatch.
    """

    def __init__(self, session: AsyncSession, run_id: uuid.UUID, provider: LLMProvider | None = None):
        self.session = session
        self.run_id = run_id
        self.provider = provider or GeminiProvider()

    async def run(self) -> str:  # noqa: C901
        """
        Executes the run until it reaches a terminal state or requires confirmation.
        Returns the final status of the run.
        """
        from app.agents.events import record_and_publish_event
        from app.db.models.run import AgentRun

        stmt = select(AgentRun).options(selectinload(AgentRun.plan).selectinload(AgentPlan.steps)).where(AgentRun.id == self.run_id)
        result = await self.session.execute(stmt)
        run = result.scalar_one_or_none()

        if not run:
            raise PlanExecutionError("Run not found.")

        if run.status in ("COMPLETED", "FAILED", "CANCELLED", "EXPIRED"):
            return run.status

        plan = run.plan
        if not plan:
            # Direct execution case handled outside of PlanExecutor
            return run.status

        if run.status == "CREATED":
            run.status = "RUNNING"
            plan.status = "RUNNING"
            await self.session.commit()
            await record_and_publish_event(self.session, self.run_id, "agent.started", "running", "Agent run started", plan.id)

        while True:
            # Refresh to get latest states
            await self.session.refresh(plan, ["steps"])
            await self.session.refresh(run)

            if run.status == "CANCELLED":
                plan.status = "CANCELLED"
                await self.session.commit()
                await record_and_publish_event(self.session, self.run_id, "agent.cancelled", "cancelled", "Agent run cancelled", plan.id)
                return run.status

            ready_steps = self._get_ready_steps(plan)

            if not ready_steps:
                # If no steps are ready, evaluate termination
                if self._is_plan_completed(plan):
                    plan.status = "COMPLETED"
                    run.status = "COMPLETED"
                    await self.session.commit()
                    await record_and_publish_event(self.session, self.run_id, "agent.completed", "completed", "All steps completed successfully.", plan.id)
                    return run.status

                if self._is_plan_failed(plan):
                    plan.status = "FAILED"
                    run.status = "FAILED"
                    await self.session.commit()
                    await record_and_publish_event(self.session, self.run_id, "agent.failed", "failed", "One or more plan steps failed.", plan.id)
                    return run.status

                break

            tasks = []
            for step in ready_steps:
                step.status = "RUNNING"
                self.session.add(step)
                await record_and_publish_event(self.session, self.run_id, "agent.step_started", "running", f"Running {step.tool_name}", plan.id, step.step_id)
                tasks.append(self._execute_step(run.user_id, plan, step))

            await self.session.commit()

            results = await asyncio.gather(*tasks, return_exceptions=True)

            needs_pause = False
            for step, result in zip(ready_steps, results, strict=False):
                if isinstance(result, Exception):
                    logger.error(f"Step {step.step_id} failed: {result}")
                    step.status = "FAILED"
                    await record_and_publish_event(self.session, self.run_id, "agent.step_failed", "failed", f"Failed: {result}", plan.id, step.step_id)
                else:
                    error_data = result.get("error")

                    if error_data and error_data.get("code") == "confirmation_required":
                        step.status = "PENDING"
                        needs_pause = True
                        await record_and_publish_event(self.session, self.run_id, "agent.waiting_confirmation", "waiting_confirmation", f"Confirmation required for {step.tool_name}", plan.id, step.step_id, metadata_payload=result)
                    elif error_data:
                        step.status = "FAILED"
                        await record_and_publish_event(self.session, self.run_id, "agent.step_failed", "failed", f"Failed: {error_data.get('message')}", plan.id, step.step_id)
                    else:
                        step.status = "SUCCESS"
                        await record_and_publish_event(self.session, self.run_id, "agent.step_completed", "success", f"Completed {step.tool_name}", plan.id, step.step_id)

                self.session.add(step)

            await self.session.commit()

            if needs_pause:
                plan.status = "WAITING_FOR_CONFIRMATION"
                run.status = "WAITING_FOR_CONFIRMATION"
                await self.session.commit()
                return run.status

        return run.status

    def _get_ready_steps(self, plan: AgentPlan) -> list[AgentPlanStep]:
        """Finds all CREATED or PENDING steps where all dependencies are SUCCESS."""
        ready = []
        # Create a lookup for quick status checking
        step_status = {s.step_id: s.status for s in plan.steps}

        for step in plan.steps:
            if step.status not in ("CREATED", "PENDING"):
                continue

            deps_met = True
            for dep in step.depends_on:
                if step_status.get(dep) != "SUCCESS":
                    deps_met = False
                    break

            if deps_met:
                ready.append(step)

        # If we have sequential steps, they should technically not run in parallel with others
        # To strictly honor execution_mode="SEQUENTIAL", if we find one, we just return it alone.
        for step in ready:
            if step.execution_mode == "SEQUENTIAL":
                return [step]

        return ready

    def _is_plan_completed(self, plan: AgentPlan) -> bool:
        return all(s.status == "SUCCESS" for s in plan.steps)

    def _is_plan_failed(self, plan: AgentPlan) -> bool:
        return any(s.status == "FAILED" for s in plan.steps)

    async def _execute_step(self, user_id: uuid.UUID, plan: AgentPlan, step: AgentPlanStep) -> dict[str, Any]:
        """
        Performs Just-In-Time argument evaluation and executes the tool.
        """
        # We would ideally fetch the invocation result from the db if we linked it.
        # For Phase 3E, we will assume JIT can just rely on the orchestrator's implicit history
        # or we just execute the tool with the arguments provided by the planner.

        # JIT LLM Call:
        args_str = json.dumps(step.arguments)
        if "$" in args_str:
            sys_inst = (
                "You are a Just-In-Time argument evaluator. Replace any string values that start with '$' "
                "(e.g., '$step_1.result') with the actual value from the preceding steps context. "
                "Output ONLY a valid JSON object matching the exact arguments structure, but with the variables resolved."
            )

            # Simple context serialization
            context_data = {prior.step_id: "success" for prior in plan.steps if prior.status == "SUCCESS"}

            try:
                from google.genai import types
                jit_response = await self.provider.generate(
                    system_instruction=sys_inst,
                    contents=[
                        types.Content(role="user", parts=[
                            types.Part.from_text(f"Prior Context: {json.dumps(context_data)}\n\nResolve: {args_str}")
                        ])
                    ]
                )
                if jit_response:
                    resolved_args = json.loads(jit_response)
                    if isinstance(resolved_args, dict):
                        step.arguments = resolved_args
            except Exception as e:
                logger.warning(f"JIT Evaluation failed: {e}")

        # Execute tool
        try:
            result = await execute_tool(self.session, user_id, step.tool_name, step.arguments)
            return result
        except Exception as e:
            return {"error": {"code": "exception", "message": str(e)}}
