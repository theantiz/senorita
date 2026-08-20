from unittest.mock import patch

import pytest
from httpx import AsyncClient


@pytest.fixture
def mock_embed_text():
    with patch("app.services.memory_service.embed_text") as mock:
        # Mock pgvector embedding format (list of floats)
        mock.return_value = [0.1] * 3072
        yield mock


@pytest.mark.asyncio
async def test_memory_crud_and_search(client: AsyncClient, mock_embed_text):
    # 1. Login to get token
    login_res = await client.post("/api/v1/auth/login", json={"name": "test_memory_user"})
    token = login_res.json()["token"]
    headers = {"Authorization": f"Bearer {token}"}

    # 2. Create memory
    memory_data = {
        "content": "User loves chocolate",
        "memory_type": "preference",
        "source_ref": "chat",
        "importance_score": 0.8,
    }
    create_res = await client.post("/api/v1/memory", json=memory_data, headers=headers)
    assert create_res.status_code == 200
    memory = create_res.json()
    assert memory["content"] == memory_data["content"]
    memory_id = memory["id"]

    # 3. Search memory (triggers mock_embed_text)
    search_res = await client.get("/api/v1/memory?search=chocolate", headers=headers)
    assert search_res.status_code == 200
    results = search_res.json()
    assert len(results) >= 1
    assert any(m["id"] == memory_id for m in results)

    # 4. Lock memory
    lock_res = await client.patch(f"/api/v1/memory/{memory_id}", json={"locked": True}, headers=headers)
    assert lock_res.status_code == 200
    assert lock_res.json()["locked"] == True

    # 5. Delete memory
    del_res = await client.delete(f"/api/v1/memory/{memory_id}", headers=headers)
    assert del_res.status_code == 200

    # 6. Delete again should fail
    del_res2 = await client.delete(f"/api/v1/memory/{memory_id}", headers=headers)
    assert del_res2.status_code == 404
