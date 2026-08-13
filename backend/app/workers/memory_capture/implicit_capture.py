"""Implicit memory capture — automatically extracts key info from conversations (T4.2)."""

import asyncio
from datetime import datetime, timedelta, timezone

from app.core.config import settings


async def capture_implicit_memories():
    """Analyze recent conversations and extract memorable facts."""
    try:
        import httpx
        async with httpx.AsyncClient() as client:
            # Get recent conversations
            # This is a stub — in production would use embeddings + NLP
            pass
    except Exception:
        pass


async def run_implicit_capture():
    """Background loop for implicit memory extraction."""
    while True:
        await capture_implicit_memories()
        await asyncio.sleep(3600)  # Once per hour


def start_implicit_capture():
    """Start implicit memory capture in background."""
    import asyncio
    loop = asyncio.get_event_loop()
    loop.create_task(run_implicit_capture())

