from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class IntentSchema(BaseModel):
    model_config = ConfigDict(extra="forbid")

    intent: str = Field(
        description="The identified core intent of the user (e.g., schedule_meeting, query_calendar, create_reminder, generic_chat)"
    )
    confidence: float = Field(description="Confidence score of the intent classification (0.0 to 1.0)")
    entities: dict[str, Any] = Field(
        default_factory=dict, description="Extracted entities such as name, date, time, query_string"
    )
    constraints: list[str] = Field(
        default_factory=list,
        description="Extracted constraints or requirements (e.g., 'morning only', 'exclude weekend')",
    )
    required_capabilities: list[str] = Field(
        default_factory=list,
        description="Required system capabilities/modules (e.g., calendar, contacts, email, reminders, search, documents)",
    )
    ambiguities: list[str] = Field(
        default_factory=list,
        description="Any critical missing information or ambiguity preventing deterministic execution",
    )
    routing_decision: str = Field(
        description="Must be 'DIRECT_EXECUTION' for simple single-step tools or 'MULTI_STEP_PLAN' for complex workflows requiring dependent steps or recovery."
    )


class PlanStepSchema(BaseModel):
    model_config = ConfigDict(extra="forbid")

    step_id: str = Field(description="Unique identifier for the step (e.g. 'step_1')")
    tool_name: str = Field(description="The exact name of the tool to be executed")
    arguments: dict[str, Any] = Field(default_factory=dict, description="Concrete arguments / inputs for the tool call")
    depends_on: list[str] = Field(
        default_factory=list, description="List of step_ids that must complete successfully before this step starts"
    )
    execution_mode: str = Field(description="Execution mode, must be either 'sequential' or 'parallel'")
    risk_level: str = Field(description="Risk level of the tool, must be one of: 'LOW', 'MEDIUM', 'HIGH', 'CRITICAL'")


class PlanSchema(BaseModel):
    model_config = ConfigDict(extra="forbid")

    goal: str = Field(description="A clear description of what this plan aims to achieve")
    steps: list[PlanStepSchema] = Field(description="DAG list of plan steps to execute")
