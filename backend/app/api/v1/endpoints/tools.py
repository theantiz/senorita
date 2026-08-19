from datetime import datetime
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Body, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.tool_registry import discover_tools_for_message, execute_tool, get_tool_executor, get_tool_registry
from app.agents.tool_system.context import ToolContext
from app.agents.tool_system.persistence import ToolPersistence, utcnow
from app.agents.tool_system.validation import SchemaValidationError, ToolArgumentValidator
from app.api.deps import get_current_user, get_db
from app.db.models import ToolConfirmation, User

router = APIRouter(prefix="/tools", tags=["tools"])


class ToolSearchRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    query: str = Field(min_length=1, max_length=1_000)
    limit: int = Field(default=12, ge=1, le=50)


class ToolValidateRequest(BaseModel):
    arguments: dict[str, Any] = Field(default_factory=dict)


class ToolExecuteRequest(BaseModel):
    arguments: dict[str, Any] = Field(default_factory=dict)
    confirmed: bool = False
    idempotency_key: str | None = Field(default=None, min_length=1, max_length=300)


class ToolConfirmationResponse(BaseModel):
    id: UUID
    user_id: UUID
    conversation_id: str | None
    tool_invocation_id: UUID
    tool_name: str
    risk_level: str
    summary: str
    arguments_preview: dict[str, Any]
    status: str
    created_at: datetime
    expires_at: datetime
    approved_at: datetime | None
    rejected_at: datetime | None


def _confirmation_response(confirmation: ToolConfirmation) -> ToolConfirmationResponse:
    return ToolConfirmationResponse(
        id=confirmation.id,
        user_id=confirmation.user_id,
        conversation_id=confirmation.conversation_id,
        tool_invocation_id=confirmation.tool_invocation_id,
        tool_name=confirmation.tool_name,
        risk_level=confirmation.risk_level,
        summary=confirmation.summary,
        arguments_preview=confirmation.arguments_preview,
        status=confirmation.status,
        created_at=confirmation.created_at,
        expires_at=confirmation.expires_at,
        approved_at=confirmation.approved_at,
        rejected_at=confirmation.rejected_at,
    )


@router.get("")
async def list_tools(_current_user: User = Depends(get_current_user)):
    return {"tools": get_tool_registry().inventory()}


@router.get("/categories")
async def list_tool_categories(_current_user: User = Depends(get_current_user)):
    return {"categories": get_tool_registry().categories()}


@router.post("/search")
async def search_tools(request: ToolSearchRequest, _current_user: User = Depends(get_current_user)):
    tool_names = discover_tools_for_message(request.query, limit=request.limit)
    registry = get_tool_registry()
    return {"tools": [registry.get(name).to_inventory_row() for name in tool_names if registry.get(name)]}


@router.get("/health")
async def tool_health(_current_user: User = Depends(get_current_user)):
    registry = get_tool_registry()
    return {"count": len(registry.all()), "tools": registry.inventory()}


@router.get("/confirmations")
async def list_confirmations(
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await session.execute(
        select(ToolConfirmation)
        .where(ToolConfirmation.user_id == current_user.id)
        .order_by(ToolConfirmation.created_at.desc())
        .limit(100)
    )
    return {"confirmations": [_confirmation_response(row) for row in result.scalars().all()]}


@router.get("/confirmations/{confirmation_id}")
async def get_confirmation(
    confirmation_id: UUID,
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    confirmation = await ToolPersistence().get_confirmation_for_user(session, current_user.id, confirmation_id)
    if not confirmation:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Confirmation not found.")
    return _confirmation_response(confirmation)


@router.post("/confirmations/{confirmation_id}/approve")
async def approve_confirmation(
    confirmation_id: UUID,
    request_body: dict[str, Any] | None = Body(default=None),
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if request_body:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Approval cannot include new tool arguments.",
        )
    persistence = ToolPersistence()
    confirmation = await persistence.get_confirmation_for_user(session, current_user.id, confirmation_id, lock=True)
    if not confirmation:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Confirmation not found.")
    if confirmation.status != "PENDING":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Confirmation is already {confirmation.status.lower()}.",
        )

    now = utcnow()
    invocation = await persistence.get_invocation_for_update(session, confirmation.tool_invocation_id, current_user.id)
    if not invocation or invocation.confirmation_id != confirmation.id:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Confirmation is not linked to a valid invocation."
        )
    if confirmation.expires_at <= now:
        confirmation.status = "EXPIRED"
        invocation.status = "EXPIRED"
        if invocation.idempotency_key_hash:
            record = await persistence.get_idempotency_record_by_hash(
                session, current_user.id, invocation.idempotency_key_hash, lock=True
            )
            if record:
                record.status = "EXPIRED"
        await session.flush()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Confirmation has expired.")
    if invocation.status != "WAITING_CONFIRMATION":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Tool invocation is not waiting for confirmation."
        )

    confirmation.status = "APPROVED"
    confirmation.approved_at = now
    await session.flush()

    context = ToolContext(
        user_id=current_user.id,
        conversation_id=invocation.conversation_id,
        request_id=invocation.request_id,
    )
    result = await get_tool_executor().execute(
        session,
        context,
        invocation.tool_name,
        dict(invocation.arguments_snapshot),
        confirmed=True,
        confirmation_id=str(confirmation.id),
        existing_invocation_id=invocation.id,
    )
    return result.to_dict()


@router.post("/confirmations/{confirmation_id}/reject")
async def reject_confirmation(
    confirmation_id: UUID,
    request_body: dict[str, Any] | None = Body(default=None),
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if request_body:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Rejection cannot include new tool arguments.",
        )
    persistence = ToolPersistence()
    confirmation = await persistence.get_confirmation_for_user(session, current_user.id, confirmation_id, lock=True)
    if not confirmation:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Confirmation not found.")
    if confirmation.status != "PENDING":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Confirmation is already {confirmation.status.lower()}.",
        )
    invocation = await persistence.get_invocation_for_update(session, confirmation.tool_invocation_id, current_user.id)
    if invocation:
        invocation.status = "CANCELLED"
        if invocation.idempotency_key_hash:
            record = await persistence.get_idempotency_record_by_hash(
                session, current_user.id, invocation.idempotency_key_hash, lock=True
            )
            if record:
                record.status = "CANCELLED"
    confirmation.status = "REJECTED"
    confirmation.rejected_at = utcnow()
    await session.flush()
    return _confirmation_response(confirmation)


@router.get("/{name}")
async def get_tool(name: str, _current_user: User = Depends(get_current_user)):
    definition = get_tool_registry().get(name)
    if not definition:
        return {"error": "Tool not found."}
    data = definition.to_inventory_row()
    data["description"] = definition.description
    data["input_schema"] = definition.input_schema
    data["dependencies"] = list(definition.dependencies)
    data["side_effects"] = list(definition.side_effects)
    return data


@router.post("/{name}/validate")
async def validate_tool(name: str, request: ToolValidateRequest, _current_user: User = Depends(get_current_user)):
    definition = get_tool_registry().get(name)
    if not definition:
        return {"valid": False, "error": {"code": "unknown_tool", "message": "Tool not found."}}
    try:
        ToolArgumentValidator().validate(definition.input_schema, request.arguments)
    except SchemaValidationError as exc:
        return {"valid": False, "error": {"code": "invalid_input", "message": str(exc)}}
    return {"valid": True}


@router.post("/{name}/execute")
async def execute_tool_endpoint(
    name: str,
    request: ToolExecuteRequest,
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if request.confirmed:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Use /tools/confirmations/{id}/approve to approve the original invocation.",
        )
    args = dict(request.arguments)
    if request.idempotency_key:
        args["_idempotency_key"] = request.idempotency_key
    return await execute_tool(session, current_user.id, name, args)
