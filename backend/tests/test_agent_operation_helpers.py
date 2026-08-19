import pytest

from app.agents.orchestrator import _compact_json_for_model, _strip_json_fence
from app.memory.embeddings import embed_text

pytestmark = pytest.mark.no_db


def test_strip_json_fence_handles_plain_and_fenced_json():
    assert _strip_json_fence('{"ok": true}') == '{"ok": true}'
    assert _strip_json_fence('```json\n{"ok": true}\n```') == '{"ok": true}'
    assert _strip_json_fence('```\n{"ok": true}\n```') == '{"ok": true}'


def test_compact_json_for_model_truncates_large_payloads():
    compact = _compact_json_for_model({"value": "x" * 40}, max_chars=20)

    assert compact.startswith('{"value": "xxxxxxxxx')
    assert "[truncated" in compact


async def test_embed_text_returns_empty_vector_for_blank_text():
    assert await embed_text("   ", task_type="RETRIEVAL_QUERY") == []
