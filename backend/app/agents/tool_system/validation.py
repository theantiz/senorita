from __future__ import annotations

from typing import Any


class SchemaValidationError(ValueError):
    pass


class ToolArgumentValidator:
    def validate(self, schema: dict[str, Any], arguments: dict[str, Any]) -> dict[str, Any]:
        if not isinstance(arguments, dict):
            raise SchemaValidationError("Tool arguments must be an object.")

        properties = schema.get("properties", {})
        required = set(schema.get("required", []))
        additional_allowed = schema.get("additionalProperties", False)

        unknown = set(arguments) - set(properties)
        if unknown and not additional_allowed:
            raise SchemaValidationError(f"Unknown argument(s): {', '.join(sorted(unknown))}.")

        missing = required - {key for key, value in arguments.items() if value is not None}
        if missing:
            raise SchemaValidationError(f"Missing required argument(s): {', '.join(sorted(missing))}.")

        for key, value in arguments.items():
            if value is None or key not in properties:
                continue
            expected_type = properties[key].get("type")
            if expected_type and not self._matches_type(value, expected_type):
                raise SchemaValidationError(f"`{key}` must be {expected_type}.")

        return arguments

    def _matches_type(self, value: Any, expected_type: str) -> bool:
        if expected_type == "string":
            return isinstance(value, str)
        if expected_type == "integer":
            return isinstance(value, int) and not isinstance(value, bool)
        if expected_type == "number":
            return isinstance(value, int | float) and not isinstance(value, bool)
        if expected_type == "boolean":
            return isinstance(value, bool)
        if expected_type == "object":
            return isinstance(value, dict)
        if expected_type == "array":
            return isinstance(value, list)
        return True
