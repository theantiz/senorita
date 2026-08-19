from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class ToolError:
    code: str
    message: str
    retryable: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {"code": self.code, "message": self.message, "retryable": self.retryable}


@dataclass(frozen=True)
class ToolResult:
    success: bool
    tool: str
    data: Any = None
    error: ToolError | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        payload = {
            "success": self.success,
            "tool": self.tool,
            "data": self.data,
            "error": self.error.to_dict() if self.error else None,
            "metadata": self.metadata,
        }
        if isinstance(self.data, dict):
            if self.data.get("ambiguous"):
                payload["ambiguous"] = True
            if self.data.get("refused"):
                payload["refused"] = True
        return payload

    @classmethod
    def ok(cls, tool: str, data: Any, metadata: dict[str, Any] | None = None) -> "ToolResult":
        return cls(success=True, tool=tool, data=data, metadata=metadata or {})

    @classmethod
    def fail(
        cls,
        tool: str,
        code: str,
        message: str,
        *,
        retryable: bool = False,
        data: Any = None,
        metadata: dict[str, Any] | None = None,
    ) -> "ToolResult":
        return cls(
            success=False,
            tool=tool,
            data=data,
            error=ToolError(code=code, message=message, retryable=retryable),
            metadata=metadata or {},
        )
