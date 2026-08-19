from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.tool_registry import discover_tools_for_message, execute_tool, get_tool_registry
from app.agents.tool_system.validation import SchemaValidationError, ToolArgumentValidator
from app.api.deps import get_current_user, get_db
from app.db.models import User

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
    args = dict(request.arguments)
    if request.confirmed:
        args["_confirmed"] = True
    return await execute_tool(session, current_user.id, name, args)
