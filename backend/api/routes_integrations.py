from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from uuid import UUID
from pydantic import BaseModel
import logging

from db.session import get_db
from db.models import User, Integration
from schemas.integration import IntegrationRead, IntegrationUpdatePermissions
from core.security import get_current_user
from core.crypto import encrypt, decrypt
from integrations.base import get_adapter

logger = logging.getLogger(__name__)




router = APIRouter(prefix="/integrations", tags=["integrations"])

SUPPORTED_PROVIDERS = [
    "gmail",
    "slack",
    "google_calendar",
    "outlook",
    "apple_calendar",
    "google_drive",
    "linkedin"
]

@router.get("", response_model=list[IntegrationRead])
async def list_integrations(
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Lists connection status and permissions per provider for the current user.
    If a provider is not connected, returns a placeholder with status 'disconnected'.
    """
    stmt = select(Integration).where(Integration.user_id == current_user.id)
    result = await session.execute(stmt)
    existing_integrations = {i.provider: i for i in result.scalars().all()}

    integrations_list = []
    for provider in SUPPORTED_PROVIDERS:
        if provider in existing_integrations:
            integrations_list.append(existing_integrations[provider])
        else:
            # Create a transient Integration object (not persisted) for the response
            integrations_list.append(
                Integration(
                    user_id=current_user.id,
                    provider=provider,
                    status="disconnected",
                    scopes=[],
                    permissions={},
                    access_token_encrypted=None,
                    refresh_token_encrypted=None,
                    token_expires_at=None,
                    last_synced_at=None
                )
            )
    return integrations_list

@router.get("/{provider}/connect")
async def get_connect_url(
    provider: str,
    state: str = Query("default_state"),
    current_user: User = Depends(get_current_user)
):
    """
    Returns the OAuth URL to redirect the user to.
    """
    if provider not in SUPPORTED_PROVIDERS:
        raise HTTPException(status_code=400, detail=f"Unsupported provider: {provider}")

    try:
        adapter = get_adapter(provider)
        oauth_url = adapter.get_oauth_url(state)
        return {"url": oauth_url}
    except ValueError as e:
        raise HTTPException(status_code=501, detail=str(e))
    except Exception as e:
        logger.error(f"Error getting connect URL for {provider}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.get("/{provider}/callback")
async def oauth_callback(
    provider: str,
    code: str,
    state: str = "default_state",
    session: AsyncSession = Depends(get_db),
):
    """
    OAuth redirect target. Exchanges authorization code for tokens,
    encrypts and stores them, and sets status to 'connected'.

    NOTE: This route intentionally has NO Bearer auth dependency —
    Google's browser redirect does not carry our Authorization header.
    The user is identified via the `state` parameter, which is set to
    "{provider}:{user_id}:{timestamp}" by the frontend's handleConnect.
    """
    if provider not in SUPPORTED_PROVIDERS:
        raise HTTPException(status_code=400, detail=f"Unsupported provider: {provider}")

    # ── Resolve user from state ───────────────────────────────────────────────
    # Expected format: "{provider}:{user_id}:{timestamp}"
    parts = state.split(":")
    if len(parts) < 2:
        raise HTTPException(
            status_code=400,
            detail="Invalid OAuth state parameter — missing user_id segment."
        )
    raw_user_id = parts[1]
    try:
        user_uuid = UUID(raw_user_id)
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid user_id in OAuth state: {raw_user_id}"
        )

    stmt_user = select(User).where(User.id == user_uuid)
    result_user = await session.execute(stmt_user)
    current_user = result_user.scalars().first()
    if not current_user:
        raise HTTPException(status_code=404, detail="User not found for this OAuth session.")

    try:
        adapter = get_adapter(provider)
        token_data = await adapter.exchange_code_for_tokens(code)

        # Encrypt the retrieved tokens
        access_token_enc = encrypt(token_data.get("access_token"))
        refresh_token_enc = encrypt(token_data.get("refresh_token"))

        # Find existing integration or create a new one
        stmt = select(Integration).where(
            Integration.user_id == current_user.id,
            Integration.provider == provider
        )
        result = await session.execute(stmt)
        integration = result.scalars().first()

        # Build provider-specific default permissions.
        # For Slack we also stash workspace metadata needed for webhook routing.
        if provider == "slack":
            default_permissions = {
                "read": True,
                "send_automatically": False,
                "team_id": token_data.get("team_id", ""),
                "bot_user_id": token_data.get("bot_user_id", ""),
            }
        else:
            default_permissions = {
                "read": True,
                "draft": True,
                "send_automatically": False,
            }

        if integration:
            integration.status = "connected"
            integration.scopes = token_data.get("scopes", [])
            integration.access_token_encrypted = access_token_enc
            if refresh_token_enc:
                integration.refresh_token_encrypted = refresh_token_enc
            integration.token_expires_at = token_data.get("expires_at")
            integration.permissions = default_permissions
        else:
            integration = Integration(
                user_id=current_user.id,
                provider=provider,
                status="connected",
                scopes=token_data.get("scopes", []),
                permissions=default_permissions,
                access_token_encrypted=access_token_enc,
                refresh_token_encrypted=refresh_token_enc,
                token_expires_at=token_data.get("expires_at")
            )
            session.add(integration)

        await session.commit()
        await session.refresh(integration)

        # Redirect the user back to the connections UI
        return RedirectResponse(url="http://localhost:3000/connections")
    except ValueError as e:
        raise HTTPException(status_code=501, detail=str(e))
    except Exception as e:
        logger.error(f"OAuth callback failed for {provider}: {e}")
        raise HTTPException(status_code=500, detail="OAuth authentication failed")




@router.patch("/{provider}/permissions", response_model=IntegrationRead)
async def update_permissions(
    provider: str,
    permissions_in: IntegrationUpdatePermissions,
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Updates the capability toggles for the provider integration.
    """
    if provider not in SUPPORTED_PROVIDERS:
        raise HTTPException(status_code=400, detail=f"Unsupported provider: {provider}")

    stmt = select(Integration).where(
        Integration.user_id == current_user.id,
        Integration.provider == provider
    )
    result = await session.execute(stmt)
    integration = result.scalars().first()

    if not integration:
        raise HTTPException(status_code=404, detail="Integration not found or not connected")

    # Update only the permissions dictionary
    integration.permissions = permissions_in.permissions
    await session.commit()
    await session.refresh(integration)
    return integration

@router.delete("/{provider}")
async def disconnect_integration(
    provider: str,
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Revokes local tokens (deletes stored credentials, resets status to 'disconnected').
    Calls the provider's token revocation endpoint where applicable.
    """
    if provider not in SUPPORTED_PROVIDERS:
        raise HTTPException(status_code=400, detail=f"Unsupported provider: {provider}")

    stmt = select(Integration).where(
        Integration.user_id == current_user.id,
        Integration.provider == provider
    )
    result = await session.execute(stmt)
    integration = result.scalars().first()

    if not integration:
        raise HTTPException(status_code=404, detail="Integration not found")

    # Call provider's token revocation endpoint if implemented
    try:
        adapter = get_adapter(provider)
        # Decrypt tokens to pass to revoke if needed
        # (Though revoke_tokens gets the row object, it can decrypt it internally)
        await adapter.revoke_tokens(integration)
    except Exception as e:
        logger.warning(f"Failed to revoke tokens at provider {provider}: {e}")

    # Completely delete the integration row to revoke locally
    await session.delete(integration)
    await session.commit()

    return {"ok": True, "message": f"Successfully disconnected {provider}"}
