"""
integrations/whatsapp.py

WhatsApp Business API (Meta Cloud API) integration adapter.

Two distinct responsibilities live here:
1. WhatsAppIntegrationAdapter — fulfils the IntegrationAdapter interface so the
   existing /api/v1/integrations/{provider} routes work correctly. WhatsApp
   uses permanent tokens rather than OAuth, so the OAuth-specific methods
   raise NotImplementedError.

2. WhatsAppSender — thin stateless class that actually POSTs to the Meta
   Graph API. Used by the processor worker to deliver AI replies.

Multi-tenancy design:
  Each Integration row for provider='whatsapp' stores its Meta phone_number_id
  inside the `permissions` JSONB column as {"phone_number_id": "...", ...}.
  The access_token is stored encrypted in `access_token_encrypted` (same
  pattern as Gmail). This means different users can own different Meta numbers
  without any code change.
"""

import hashlib
import hmac
import logging
from datetime import datetime, timezone, timedelta

import httpx

from integrations.base import IntegrationAdapter, register_adapter

logger = logging.getLogger(__name__)

META_GRAPH_API_VERSION = "v19.0"
META_GRAPH_BASE = f"https://graph.facebook.com/{META_GRAPH_API_VERSION}"


# ─────────────────────────────────────────────────────────────────────────────
# HMAC-SHA256 signature verification
# ─────────────────────────────────────────────────────────────────────────────

def verify_webhook_signature(payload_body: bytes, signature_header: str, app_secret: str) -> bool:
    """
    Verify the X-Hub-Signature-256 header Meta sends with every webhook POST.
    signature_header is of the form  'sha256=<hex_digest>'.
    Returns True if the HMAC matches, False otherwise.
    """
    if not signature_header or not signature_header.startswith("sha256="):
        return False
    expected = hmac.new(
        app_secret.encode("utf-8"),
        payload_body,
        hashlib.sha256
    ).hexdigest()
    received = signature_header[len("sha256="):]
    return hmac.compare_digest(expected, received)


# ─────────────────────────────────────────────────────────────────────────────
# WhatsApp sender — used by the processor worker
# ─────────────────────────────────────────────────────────────────────────────

class WhatsAppSender:
    """
    Thin wrapper around the Meta Cloud API send-message endpoint.
    Stateless — pass credentials per call so it works for any tenant.
    """

    async def send(
        self,
        to_phone: str,
        text: str,
        access_token: str,
        phone_number_id: str,
    ) -> dict:
        """
        Send a text reply to `to_phone` from the business number identified by
        `phone_number_id` using `access_token`.

        Returns the raw Meta API JSON response on success.
        Raises httpx.HTTPStatusError on failure (4xx/5xx).
        """
        url = f"{META_GRAPH_BASE}/{phone_number_id}/messages"
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
        }
        payload = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": to_phone,
            "type": "text",
            "text": {"preview_url": False, "body": text},
        }

        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(url, headers=headers, json=payload)
            resp.raise_for_status()
            logger.info(f"WhatsApp reply sent to {to_phone}: {resp.status_code}")
            return resp.json()


# Shared singleton used by the processor worker
whatsapp_sender = WhatsAppSender()


# ─────────────────────────────────────────────────────────────────────────────
# Integration adapter (satisfies the adapter registry interface)
# ─────────────────────────────────────────────────────────────────────────────

class WhatsAppIntegrationAdapter(IntegrationAdapter):
    """
    WhatsApp does not use OAuth — credentials are permanent Meta tokens
    configured manually by the user and stored encrypted in the DB.

    The OAuth-flow methods raise ValueError so the integrations UI can
    detect this and show a manual-setup guide instead of an OAuth redirect.
    """

    def get_oauth_url(self, state: str) -> str:
        raise ValueError(
            "WhatsApp uses a permanent access token, not OAuth. "
            "Please set WHATSAPP_ACCESS_TOKEN and WHATSAPP_PHONE_NUMBER_ID "
            "in your .env file and save them via the integrations setup page."
        )

    async def exchange_code_for_tokens(self, code: str) -> dict:
        raise NotImplementedError("WhatsApp does not use OAuth code exchange.")

    async def refresh_access_token(self, integration) -> dict:
        raise NotImplementedError(
            "WhatsApp access tokens are permanent and do not require refresh."
        )

    def is_token_valid(self, integration) -> bool:
        """
        For WhatsApp, validity is determined by whether the integration row
        exists with status='connected' and a non-empty access_token_encrypted.
        Token expiry is not applicable.
        """
        return (
            integration.status == "connected"
            and bool(integration.access_token_encrypted)
        )

    async def revoke_tokens(self, integration) -> None:
        """
        WhatsApp permanent tokens cannot be revoked via API.
        We simply clear the stored credentials in the DB (done by the
        disconnect endpoint in routes_integrations.py).
        """
        logger.info(
            f"WhatsApp integration for user {integration.user_id} disconnected. "
            "Token cleared from DB. Revocation at Meta must be done manually "
            "via https://developers.facebook.com."
        )


register_adapter("whatsapp", WhatsAppIntegrationAdapter())
