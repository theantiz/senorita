from typing import Any

from app.agents.context import AgentContext
from app.agents.llm_provider import LLMProvider
from app.agents.schemas import IntentSchema, PlanSchema


async def generate_plan(
    context: AgentContext,
    intent: IntentSchema,
    available_tools: list[dict[str, Any]],
    provider: LLMProvider,
) -> PlanSchema:
    """
    Generates a multi-step execution plan (DAG) based on the context, intent, and available tools.
    """
    system_instruction = (
        "You are a highly competent AI planner. Break down the user's intent into a structured "
        "Directed Acyclic Graph (DAG) of step executions. For each step, determine step_id, tool_name, "
        "arguments, depends_on dependencies, execution_mode ('sequential' or 'parallel'), and risk_level. "
        "Only generate steps using tools that exist in the provided 'Available Tools' list. "
        "Do not invent tools. Independent steps should have no depends_on to execute concurrently."
    )

    tools_str = "\n".join(
        [
            f"- {t.get('name', '')}: {t.get('description', '')} (Risk: {t.get('risk_level', 'LOW')})"
            for t in available_tools
        ]
    )

    prompt = (
        f"Goal: {intent.intent}\n"
        f"Entities/Constraints: {intent.entities} | {intent.constraints}\n\n"
        f"Available Tools:\n{tools_str}\n\n"
        f"Original User Request: {context.message}\n"
        f"{context.enriched_context}\n"
    )

    plan = await provider.generate_structured(
        prompt=prompt,
        schema=PlanSchema,
        system_instruction=system_instruction,
    )
    return plan
