from app.agents.context import AgentContext
from app.agents.llm_provider import LLMProvider
from app.agents.schemas import IntentSchema


async def extract_intent(context: AgentContext, provider: LLMProvider) -> IntentSchema:
    """
    Extracts the user's intent, entities, constraints, capabilities, and ambiguities
    from the current conversation context. This operation never executes tools directly.
    """
    system_instruction = (
        "You are an expert intent extraction engine. Given a user query and recent history, "
        "extract the core intent, entities, constraints, required capabilities (such as 'calendar', "
        "'contacts', 'email', 'reminders', 'search', 'documents'), and any ambiguities. "
        "If the request is ambiguous (e.g. 'schedule a meeting with Rahul' but there are multiple Rahuls, "
        "or 'cancel it' but it's not clear what 'it' is), list those ambiguities explicitly in the ambiguities field.\n"
        "Set routing_decision to 'DIRECT_EXECUTION' if the request can be completed with a single tool call or simple inquiry. "
        "Set routing_decision to 'MULTI_STEP_PLAN' if the request requires multiple dependent tools, background actions, or complex workflows."
    )

    history_lines = []
    for msg in context.recent_messages:
        role = msg.get("role", "user")
        content = msg.get("content", "")
        history_lines.append(f"{role.capitalize()}: {content}")
    history_str = "\n".join(history_lines)

    prompt = (
        f"User Timezone: {context.timezone}\n"
        f"Recent History:\n{history_str}\n\n"
        f"Current User Query: {context.message}\n"
        f"{context.enriched_context}\n"
    )

    # Use the structured generation to enforce pydantic validation on the output
    intent = await provider.generate_structured(
        prompt=prompt,
        schema=IntentSchema,
        system_instruction=system_instruction,
    )
    return intent
