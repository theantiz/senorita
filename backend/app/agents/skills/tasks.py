from app.agents.skills.base import Skill, SkillRegistry

task_skill = Skill(
    name="TaskSkill",
    description="Handles task tracking and goal management.",
    tools=["create_task", "list_tasks", "update_task", "complete_task", "delete_task"],
    triggers=["TaskCreated", "TaskOverdue", "TaskCompleted", "DeadlineApproaching", "GoalProgressChanged"],
    default_permissions={
        "create_task": "TRUSTED",
        "list_tasks": "FULL_AUTO",
        "update_task": "TRUSTED",
        "complete_task": "TRUSTED",
        "delete_task": "CONFIRM"
    }
)

SkillRegistry.register(task_skill)
