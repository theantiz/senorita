import asyncio
import logging
from typing import Callable, Awaitable
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.models.user import User

logger = logging.getLogger(__name__)

class EventBus:
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance.handlers = {}
        return cls._instance

    def subscribe(self, event_type: str, handler: Callable[[AsyncSession, User, dict], Awaitable[None]]):
        if event_type not in self.handlers:
            self.handlers[event_type] = []
        self.handlers[event_type].append(handler)
        
    async def publish(self, session: AsyncSession, user: User, event_type: str, event_data: dict):
        logger.info(f"Event published: {event_type} for user {user.id}")
        from app.events.trigger_engine import process_event
        asyncio.create_task(process_event(session, user, event_type, event_data))
        if event_type in self.handlers:
            for handler in self.handlers[event_type]:
                try:
                    await handler(session, user, event_data)
                except Exception as e:
                    logger.error(f"Error handling event {event_type}: {e}")

bus = EventBus()
