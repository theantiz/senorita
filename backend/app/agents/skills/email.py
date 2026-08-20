from app.agents.skills.base import Skill, SkillRegistry

email_skill = Skill(
    name="EmailSkill",
    description="Handles email communication and follow-ups.",
    tools=["gmail.search_emails", "gmail.send_email", "gmail.create_draft", "gmail.reply_to_email"],
    triggers=["EmailReceived", "ImportantEmailReceived", "EmailUnanswered"],
    default_permissions={
        "gmail.search_emails": "FULL_AUTO",
        "gmail.send_email": "CONFIRM",
        "gmail.create_draft": "TRUSTED",
        "gmail.reply_to_email": "CONFIRM"
    }
)

SkillRegistry.register(email_skill)
