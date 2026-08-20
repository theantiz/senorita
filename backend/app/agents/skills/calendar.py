from app.agents.skills.base import Skill, SkillRegistry

meeting_skill = Skill(
    name="MeetingSkill",
    description="Handles calendar events and meeting preparation.",
    tools=["calendar.list_events", "calendar.create_event", "calendar.update_event", "calendar.delete_event", "gmail.search_emails", "memory.search_memories", "contacts.search_contacts"],
    triggers=["MeetingCreated", "MeetingUpdated", "MeetingStartingSoon"],
    default_permissions={
        "calendar.*": "FULL_AUTO",
        "gmail.search_emails": "FULL_AUTO",
        "memory.*": "FULL_AUTO"
    }
)

SkillRegistry.register(meeting_skill)
