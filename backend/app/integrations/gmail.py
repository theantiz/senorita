import os
from datetime import datetime, timedelta, timezone

import httpx
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build

from app.core.config import settings
from app.integrations.base import IntegrationAdapter, register_adapter

SCOPES = [
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/gmail.compose",
    "https://www.googleapis.com/auth/gmail.send",
    "https://www.googleapis.com/auth/calendar.readonly",
    "https://www.googleapis.com/auth/calendar.events",
]

CALENDAR_SCOPES = {
    "https://www.googleapis.com/auth/calendar.readonly",
    "https://www.googleapis.com/auth/calendar.events",
}

def has_calendar_scopes(scopes: list[str] | None) -> bool:
    return CALENDAR_SCOPES.issubset(set(scopes or []))

class GmailIntegrationAdapter(IntegrationAdapter):
    def __init__(self):
        self.client_id = settings.GMAIL_CLIENT_ID
        self.client_secret = settings.GMAIL_CLIENT_SECRET
        self.redirect_uri = settings.GMAIL_REDIRECT_URI

    def _get_client_config(self) -> dict:
        return {
            "web": {
                "client_id": self.client_id,
                "client_secret": self.client_secret,
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
                "redirect_uris": [self.redirect_uri]
            }
        }

    def get_oauth_url(self, state: str) -> str:
        if not self.client_id or not self.client_secret:
            raise ValueError("GMAIL_CLIENT_ID or GMAIL_CLIENT_SECRET not set in environment.")

        flow = Flow.from_client_config(
            self._get_client_config(),
            scopes=SCOPES,
            state=state
        )
        flow.redirect_uri = self.redirect_uri

        auth_url, _ = flow.authorization_url(
            access_type="offline",
            include_granted_scopes="true",
            prompt="consent"
        )
        return auth_url

    async def exchange_code_for_tokens(self, code: str) -> dict:
        flow = Flow.from_client_config(
            self._get_client_config(),
            scopes=SCOPES
        )
        flow.redirect_uri = self.redirect_uri

        import logging
        logger = logging.getLogger(__name__)
        logger.info(f"Attempting token exchange with GMAIL_CLIENT_ID: {self.client_id}")

        async with httpx.AsyncClient() as client:
            resp = await client.post(
                "https://oauth2.googleapis.com/token",
                data={
                    "client_id": self.client_id,
                    "client_secret": self.client_secret,
                    "code": code,
                    "grant_type": "authorization_code",
                    "redirect_uri": self.redirect_uri
                }
            )
            try:
                resp.raise_for_status()
            except httpx.HTTPStatusError as e:
                logger.error(f"Google Token Exchange Error - Client ID: {self.client_id}")
                logger.error(f"Google Response Body: {e.response.text}")
                raise
            data = resp.json()

            expires_in = data.get("expires_in", 3599)
            expires_at = datetime.now(timezone.utc) + timedelta(seconds=expires_in)

            return {
                "access_token": data["access_token"],
                "refresh_token": data.get("refresh_token"),
                "expires_at": expires_at,
                "scopes": data.get("scope", "").split()
            }

    async def refresh_access_token(self, integration) -> dict:
        if not integration.refresh_token_encrypted:
            raise ValueError("No refresh token available to refresh access token.")

        import logging

        from core.crypto import decrypt
        logger = logging.getLogger(__name__)

        refresh_token = decrypt(integration.refresh_token_encrypted)

        logger.info(f"Attempting token refresh with GMAIL_CLIENT_ID: {self.client_id}")

        async with httpx.AsyncClient() as client:
            resp = await client.post(
                "https://oauth2.googleapis.com/token",
                data={
                    "client_id": self.client_id,
                    "client_secret": self.client_secret,
                    "refresh_token": refresh_token,
                    "grant_type": "refresh_token"
                }
            )
            try:
                resp.raise_for_status()
            except httpx.HTTPStatusError as e:
                logger.error(f"Google Token Refresh Error - Client ID: {self.client_id}")
                logger.error(f"Google Response Body: {e.response.text}")
                raise
            data = resp.json()

            expires_in = data.get("expires_in", 3599)
            expires_at = datetime.now(timezone.utc) + timedelta(seconds=expires_in)

            return {
                "access_token": data["access_token"],
                "refresh_token": data.get("refresh_token", refresh_token),
                "expires_at": expires_at,
            }

    def is_token_valid(self, integration) -> bool:
        if not integration.token_expires_at:
            return False
        # Add 1 minute buffer
        return datetime.now(timezone.utc) + timedelta(minutes=1) < integration.token_expires_at

register_adapter("gmail", GmailIntegrationAdapter())

