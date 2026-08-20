"""
integrations/slack.py

SlackIntegrationAdapter — OAuth 2.0 flow using Slack's standard OAuth v2.

OAuth scopes requested:
  channels:history, channels:read, groups:history, im:history, im:write,
  chat:write, users:read

The Slack Events API is webhook-based (not polling). This adapter handles
the OAuth code exchange and token management only. Real-time event ingestion
is handled by the webhook route in api/routes_slack.py.
"""

import logging
from datetime import datetime, timedelta, timezone

import httpx

from app.core.config import settings
from app.integrations.base import IntegrationAdapter, register_adapter

logger = logging.getLogger(__name__)

SLACK_OAUTH_URL = "https://slack.com/oauth/v2/authorize"
SLACK_TOKEN_URL = "https://api.slack.com/api/oauth.v2.access"
SLACK_REVOKE_URL = "https://api.slack.com/api/auth.revoke"

# Scopes required for DMs + channel history + posting
SCOPES = [
    "channels:history",
    "channels:read",
    "groups:history",
    "im:history",
    "im:write",
    "chat:write",
    "users:read",
]


class SlackIntegrationAdapter(IntegrationAdapter):
    def __init__(self):
        self.client_id = settings.SLACK_CLIENT_ID
        self.client_secret = settings.SLACK_CLIENT_SECRET
        self.redirect_uri = settings.SLACK_REDIRECT_URI

    def get_oauth_url(self, state: str) -> str:
        if not self.client_id:
            raise ValueError("SLACK_CLIENT_ID not set in environment.")
        scope_str = ",".join(SCOPES)
        return (
            f"{SLACK_OAUTH_URL}"
            f"?client_id={self.client_id}"
            f"&scope={scope_str}"
            f"&redirect_uri={self.redirect_uri}"
            f"&state={state}"
        )

    async def exchange_code_for_tokens(self, code: str) -> dict:
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                SLACK_TOKEN_URL,
                data={
                    "client_id": self.client_id,
                    "client_secret": self.client_secret,
                    "code": code,
                    "redirect_uri": self.redirect_uri,
                },
            )
            resp.raise_for_status()
            data = resp.json()

        if not data.get("ok"):
            raise ValueError(f"Slack token exchange failed: {data.get('error')}")

        # Slack bot tokens don't expire in the traditional sense — they're valid
        # until revoked. We store a far-future expires_at so the token-valid
        # check doesn't force unnecessary refreshes.
        expires_at = datetime.now(timezone.utc) + timedelta(days=3650)

        # Slack returns authed_user.access_token (user token) and access_token
        # (bot token). We store the bot token as primary; user token as refresh.
        bot_token = data.get("access_token", "")
        user_token = data.get("authed_user", {}).get("access_token", "")

        granted_scopes = data.get("scope", "").split(",")

        return {
            "access_token": bot_token,
            "refresh_token": user_token or None,
            "expires_at": expires_at,
            "scopes": granted_scopes,
            # Stash team/workspace info in extras for use in webhook verification
            "team_id": data.get("team", {}).get("id", ""),
            "bot_user_id": data.get("bot_user_id", ""),
        }

    async def refresh_access_token(self, integration) -> dict:
        # Slack tokens don't expire — nothing to refresh. Return as-is.
        logger.info("Slack token refresh called but Slack tokens do not expire. Skipping.")
        return {}

    def is_token_valid(self, integration) -> bool:
        # Slack bot tokens are valid until revoked.
        return integration.status == "connected" and bool(integration.access_token_encrypted)

    async def revoke_tokens(self, integration) -> None:
        from core.crypto import decrypt

        token = decrypt(integration.access_token_encrypted)
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                SLACK_REVOKE_URL,
                headers={"Authorization": f"Bearer {token}"},
            )
            if not resp.json().get("ok"):
                logger.warning(f"Slack token revoke returned not-ok: {resp.json()}")


register_adapter("slack", SlackIntegrationAdapter())
