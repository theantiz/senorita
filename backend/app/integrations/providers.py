from __future__ import annotations

from typing import Any, Protocol

import httpx
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

from app.core.crypto import decrypt
from app.db.models import Integration


class EmailProvider(Protocol):
    async def search(self, integration: Integration, query: str, limit: int = 10) -> dict[str, Any]: ...

    async def get_message(
        self, integration: Integration, message_id: str, *, format: str = "full"
    ) -> dict[str, Any]: ...

    async def create_draft(self, integration: Integration, raw_message: str) -> dict[str, Any]: ...

    async def send_draft(self, integration: Integration, draft_id: str) -> dict[str, Any]: ...


class CalendarProvider(Protocol):
    async def list_events(self, integration: Integration, **kwargs: Any) -> dict[str, Any]: ...

    async def create_event(self, integration: Integration, **kwargs: Any) -> dict[str, Any]: ...


class MessagingProvider(Protocol):
    async def search(self, integration: Integration, query: str, limit: int = 10) -> dict[str, Any]: ...

    async def send_message(self, integration: Integration, channel_id: str, message: str) -> dict[str, Any]: ...


class SearchProvider(Protocol):
    async def search(self, query: str, **kwargs: Any) -> dict[str, Any]: ...


class DocumentProvider(Protocol):
    async def get_document(self, document_id: str, **kwargs: Any) -> dict[str, Any]: ...

    async def search(self, query: str, **kwargs: Any) -> dict[str, Any]: ...


class GmailEmailProvider:
    def _service(self, integration: Integration):
        if not integration.access_token_encrypted:
            raise ValueError("Gmail is connected but has no usable access token.")
        access_token = decrypt(integration.access_token_encrypted)
        creds = Credentials(token=access_token)
        return build("gmail", "v1", credentials=creds, cache_discovery=False)

    async def search(self, integration: Integration, query: str, limit: int = 10) -> dict[str, Any]:
        service = self._service(integration)
        return await _to_thread(
            lambda: service.users().messages().list(userId="me", q=query, maxResults=limit).execute()
        )

    async def get_message(self, integration: Integration, message_id: str, *, format: str = "full") -> dict[str, Any]:
        service = self._service(integration)
        return await _to_thread(
            lambda: service.users().messages().get(userId="me", id=message_id, format=format).execute()
        )

    async def create_draft(self, integration: Integration, raw_message: str) -> dict[str, Any]:
        service = self._service(integration)
        return await _to_thread(
            lambda: service.users().drafts().create(userId="me", body={"message": {"raw": raw_message}}).execute()
        )

    async def send_draft(self, integration: Integration, draft_id: str) -> dict[str, Any]:
        service = self._service(integration)
        return await _to_thread(lambda: service.users().drafts().send(userId="me", body={"id": draft_id}).execute())


class SlackMessagingProvider:
    async def search(self, integration: Integration, query: str, limit: int = 10) -> dict[str, Any]:
        if not integration.access_token_encrypted:
            raise ValueError("Slack is connected but has no usable access token.")
        access_token = decrypt(integration.access_token_encrypted)
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.get(
                "https://slack.com/api/search.messages",
                headers={"Authorization": f"Bearer {access_token}"},
                params={"query": query, "count": limit},
            )
            response.raise_for_status()
            return response.json()

    async def send_message(self, integration: Integration, channel_id: str, message: str) -> dict[str, Any]:
        if not integration.access_token_encrypted:
            raise ValueError("Slack is connected but has no usable access token.")
        access_token = decrypt(integration.access_token_encrypted)
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.post(
                "https://slack.com/api/chat.postMessage",
                headers={"Authorization": f"Bearer {access_token}"},
                json={"channel": channel_id, "text": message},
            )
            response.raise_for_status()
            return response.json()


async def _to_thread(callable_):
    import asyncio

    return await asyncio.to_thread(callable_)


_EMAIL_PROVIDERS: dict[str, EmailProvider] = {"gmail": GmailEmailProvider()}
_MESSAGING_PROVIDERS: dict[str, MessagingProvider] = {"slack": SlackMessagingProvider()}


def get_email_provider(provider: str) -> EmailProvider:
    return _EMAIL_PROVIDERS[provider]


def get_messaging_provider(provider: str) -> MessagingProvider:
    return _MESSAGING_PROVIDERS[provider]
