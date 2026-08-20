import uuid

import pytest
from httpx import AsyncClient

from app.db.models import MemoryEntry


@pytest.mark.asyncio
async def test_memory_isolation(client: AsyncClient):
    # User A
    login_a = await client.post("/api/v1/auth/login", json={"name": "user_a"})
    token_a = login_a.json()["token"]
    headers_a = {"Authorization": f"Bearer {token_a}"}

    # User B
    login_b = await client.post("/api/v1/auth/login", json={"name": "user_b"})
    token_b = login_b.json()["token"]
    headers_b = {"Authorization": f"Bearer {token_b}"}

    # A creates memory
    res_a = await client.post(
        "/api/v1/memory",
        json={"content": "A secret", "memory_type": "context", "confidence": "HIGH"},
        headers=headers_a,
    )
    mem_id = res_a.json()["id"]

    # B tries to get it
    res_get_b = await client.get("/api/v1/memory", headers=headers_b)
    assert not any(m["id"] == mem_id for m in res_get_b.json())

    # B tries to delete it
    res_del_b = await client.delete(f"/api/v1/memory/{mem_id}", headers=headers_b)
    assert res_del_b.status_code == 404

    # B tries to patch it
    res_patch_b = await client.patch(f"/api/v1/memory/{mem_id}", json={"locked": True}, headers=headers_b)
    assert res_patch_b.status_code == 404
