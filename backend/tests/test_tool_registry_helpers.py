import base64
from uuid import uuid4

import pytest

from app.agents.tool_registry import (
    ToolInputError,
    _bounded_limit,
    _decode_gmail_body,
    _normalize_choice,
    _parse_uuid,
    _require_text,
)

pytestmark = pytest.mark.no_db


def test_require_text_strips_and_rejects_blank_values():
    assert _require_text("  hello  ", "title") == "hello"

    with pytest.raises(ToolInputError):
        _require_text("   ", "title")


def test_bounded_limit_defaults_and_caps_values():
    assert _bounded_limit(None) == 10
    assert _bounded_limit(0) == 10
    assert _bounded_limit(500) == 50
    assert _bounded_limit("7") == 7


def test_normalize_choice_reports_allowed_values():
    assert _normalize_choice("Quick", "depth", {"quick", "thorough"}) == "quick"

    with pytest.raises(ToolInputError, match="quick"):
        _normalize_choice("slow", "depth", {"quick", "thorough"})


def test_parse_uuid_accepts_valid_uuid_only():
    value = uuid4()
    assert _parse_uuid(str(value), "document_id") == value

    with pytest.raises(ToolInputError):
        _parse_uuid("not-a-uuid", "document_id")


def test_decode_gmail_body_walks_nested_plain_text_parts():
    encoded = base64.urlsafe_b64encode(b"hello from gmail").decode().rstrip("=")
    payload = {
        "mimeType": "multipart/alternative",
        "parts": [
            {"mimeType": "text/html", "body": {"data": base64.urlsafe_b64encode(b"<p>skip</p>").decode()}},
            {"mimeType": "text/plain", "body": {"data": encoded}},
        ],
    }

    assert _decode_gmail_body(payload) == "hello from gmail"
