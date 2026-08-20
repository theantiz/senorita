import pytest

from app.agents.plan_validator import PlanValidationError, validate_plan
from app.agents.schemas import PlanSchema, PlanStepSchema

pytestmark = pytest.mark.no_db


def test_valid_plan_passes_validation():
    # A simple DAG: step_1 -> step_2 (sequential)
    plan = PlanSchema(
        goal="Fetch contact and send email",
        steps=[
            PlanStepSchema(
                step_id="step_1",
                tool_name="find_contact",
                arguments={"name": "Rahul"},
                depends_on=[],
                execution_mode="sequential",
                risk_level="LOW"
            ),
            PlanStepSchema(
                step_id="step_2",
                tool_name="send_email",
                arguments={"to": "rahul@example.com", "subject": "hi"},
                depends_on=["step_1"],
                execution_mode="sequential",
                risk_level="HIGH"
            )
        ]
    )
    # Should not raise any validation error
    validate_plan(plan)


def test_plan_with_invalid_tool_fails():
    plan = PlanSchema(
        goal="Run non-existent tool",
        steps=[
            PlanStepSchema(
                step_id="step_1",
                tool_name="non_existent_tool_xyz",
                arguments={},
                depends_on=[],
                execution_mode="sequential",
                risk_level="LOW"
            )
        ]
    )
    with pytest.raises(PlanValidationError) as excinfo:
        validate_plan(plan)
    assert "non-existent tool" in str(excinfo.value)


def test_plan_with_circular_dependency_fails():
    # Cyclic: step_1 -> step_2 -> step_1
    plan = PlanSchema(
        goal="Circular steps",
        steps=[
            PlanStepSchema(
                step_id="step_1",
                tool_name="find_contact",
                arguments={"name": "Rahul"},
                depends_on=["step_2"],
                execution_mode="sequential",
                risk_level="LOW"
            ),
            PlanStepSchema(
                step_id="step_2",
                tool_name="send_email",
                arguments={},
                depends_on=["step_1"],
                execution_mode="sequential",
                risk_level="HIGH"
            )
        ]
    )
    with pytest.raises(PlanValidationError) as excinfo:
        validate_plan(plan)
    assert "circular dependency" in str(excinfo.value)


def test_plan_with_self_dependency_fails():
    plan = PlanSchema(
        goal="Self dependency",
        steps=[
            PlanStepSchema(
                step_id="step_1",
                tool_name="find_contact",
                arguments={"name": "Rahul"},
                depends_on=["step_1"],
                execution_mode="sequential",
                risk_level="LOW"
            )
        ]
    )
    with pytest.raises(PlanValidationError) as excinfo:
        validate_plan(plan)
    assert "cannot depend on itself" in str(excinfo.value)


def test_plan_with_invalid_execution_mode_fails():
    plan = PlanSchema(
        goal="Invalid execution mode",
        steps=[
            PlanStepSchema(
                step_id="step_1",
                tool_name="find_contact",
                arguments={"name": "Rahul"},
                depends_on=[],
                execution_mode="invalid_mode",
                risk_level="LOW"
            )
        ]
    )
    with pytest.raises(PlanValidationError) as excinfo:
        validate_plan(plan)
    assert "execution_mode" in str(excinfo.value)
