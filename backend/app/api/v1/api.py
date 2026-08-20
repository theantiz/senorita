from fastapi import APIRouter

from app.api.v1.endpoints import (
    goals,
    autonomy,
    feedback,
    activity,
    agent,
    auth,
    briefings,
    calendar,
    chat,
    contacts,
    health,
    integrations,
    memory,
    message_modes,
    notifications,
    plans,
    preferences,
    reminders,
    slack,
    system,
    tasks,
    tools,
)

api_router = APIRouter()

api_router.include_router(health.router)
api_router.include_router(auth.router)
api_router.include_router(contacts.router)
api_router.include_router(tasks.router)
api_router.include_router(tools.router)
api_router.include_router(reminders.router)
api_router.include_router(calendar.router)
api_router.include_router(memory.router)
api_router.include_router(activity.router)
api_router.include_router(chat.router)
api_router.include_router(system.router)
api_router.include_router(integrations.router)
api_router.include_router(slack.router)
api_router.include_router(message_modes.router)
api_router.include_router(briefings.router)
api_router.include_router(notifications.router)
api_router.include_router(plans.router)
api_router.include_router(agent.router, prefix="/agent", tags=["agent"])
api_router.include_router(preferences.router, prefix="/preferences", tags=["preferences"])

api_router.include_router(goals.router, prefix="/goals", tags=["goals"])
api_router.include_router(autonomy.router, prefix="/autonomy", tags=["autonomy"])
api_router.include_router(feedback.router, prefix="/feedback", tags=["feedback"])
