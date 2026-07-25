"""
services/conversation_service.py

Channel-agnostic conversation façade.

All inbound messages — regardless of origin (WhatsApp, SMS, Slack, etc.) —
are routed through this single service. It bridges the queue model
(IncomingMessage) to the AI orchestrator (handle_message) without the
orchestrator needing to know anything about channels.

Adding a new channel requires zero changes to this file.
"""

import logging
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import User, IncomingMessage
from agents.orchestrator import handle_message

logger = logging.getLogger(__name__)


async def handle_incoming(
    session: AsyncSession,
    user: User,
    incoming: IncomingMessage,
) -> str:
    """
    Process a single IncomingMessage through the Señorita AI orchestrator.

    Uses the full context pipeline already built into handle_message:
    - Semantic memory retrieval (pgvector)
    - Contact awareness
    - Conversation history (last 10 turns)
    - Tool calling (reminders, tasks, calendar, email, etc.)
    - Implicit memory capture

    Args:
        session:  Active AsyncSession (shared with the processor worker).
        user:     The User record the message belongs to.
        incoming: The IncomingMessage queue row being processed.

    Returns:
        The AI-generated reply text string, ready to be sent back via
        the appropriate channel sender.

    Raises:
        Exception: Any error from the orchestrator bubbles up so the
                   processor worker can mark the row as 'error'.
    """
    logger.info(
        f"ConversationService: handling {incoming.channel} message "
        f"from {incoming.sender_id} for user {user.id}"
    )

    reply = await handle_message(
        session=session,
        user=user,
        message_text=incoming.content,
    )

    logger.info(
        f"ConversationService: reply generated ({len(reply)} chars) "
        f"for {incoming.channel}/{incoming.sender_id}"
    )
    return reply
