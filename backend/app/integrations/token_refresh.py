import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import select

from app.core.crypto import encrypt
from app.db.models import Integration, NotificationLog
from app.db.session import async_session_factory
from app.integrations.base import get_adapter
from app.workers.notifications.dispatch import dispatch_notification

logger = logging.getLogger(__name__)

async def refresh_expired_tokens() -> None:
    """
    Background worker job that runs periodically (every 30 mins).
    Checks all 'connected' integrations expiring within the next hour,
    and refreshes them via their provider adapters.
    """
    logger.info("Starting background token refresh job...")
    now = datetime.now(timezone.utc)
    one_hour_later = now + timedelta(hours=1)

    async with async_session_factory() as session:
        # Fetch integrations expiring in the next hour that are currently connected
        stmt = select(Integration).where(
            Integration.status == "connected",
            Integration.token_expires_at <= one_hour_later
        )
        result = await session.execute(stmt)
        integrations_to_refresh = result.scalars().all()

        if not integrations_to_refresh:
            logger.info("No integrations require token refresh at this time.")
            return

        logger.info(f"Found {len(integrations_to_refresh)} integration(s) to refresh.")

        for integration in integrations_to_refresh:
            provider = integration.provider
            logger.info(f"Attempting to refresh token for user {integration.user_id}, provider {provider}")

            try:
                adapter = get_adapter(provider)
                # Call adapter to refresh tokens
                refreshed_data = await adapter.refresh_access_token(integration)

                # Encrypt new credentials
                access_token_enc = encrypt(refreshed_data.get("access_token"))
                refresh_token_enc = encrypt(refreshed_data.get("refresh_token"))

                # Update integration state
                integration.access_token_encrypted = access_token_enc
                if refresh_token_enc:
                    integration.refresh_token_encrypted = refresh_token_enc
                if refreshed_data.get("expires_at"):
                    integration.token_expires_at = refreshed_data.get("expires_at")

                integration.status = "connected"
                logger.info(f"Successfully refreshed token for {provider}")

            except Exception as e:
                logger.error(f"Failed to refresh token for provider {provider}: {e}")

                # Update status to token_expired on failure
                integration.status = "token_expired"

                # Log notification in the database & dispatch to desktop
                message = f"Your {provider.upper()} integration credentials have expired. Please reconnect."
                notification = NotificationLog(
                    user_id=integration.user_id,
                    trigger_type="integration_token_expired",
                    message=message
                )
                session.add(notification)

                # Dispatch standard notification
                try:
                    await dispatch_notification(
                        title="Integration Expired",
                        message=message,
                        payload={
                            "provider": provider,
                            "trigger_type": "integration_token_expired"
                        }
                    )
                except Exception as dispatch_err:
                    logger.error(f"Failed to dispatch expiration notification: {dispatch_err}")

        # Commit all changes to the database
        await session.commit()
        logger.info("Background token refresh job completed.")
