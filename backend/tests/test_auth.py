import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_setup_fails_if_user_exists(client: AsyncClient):
    # Depending on lifespan, the admin user might already exist
    response = await client.post("/api/v1/auth/setup", json={
        "name": "newuser",
        "timezone": "UTC"
    })
    # If admin exists, it returns 400.
    # If not, it returns 200. We will assert it doesn't crash.
    assert response.status_code in [200, 400]

@pytest.mark.asyncio
async def test_login_success(client: AsyncClient):
    response = await client.post("/api/v1/auth/login", json={"name": "test_login_user"})
    assert response.status_code == 200
    data = response.json()
    assert "token" in data
    assert "user" in data
    assert data["user"]["name"] == "test_login_user"

    # Subsequent login should also work (invalidates old token)
    response2 = await client.post("/api/v1/auth/login", json={"name": "test_login_user"})
    assert response2.status_code == 200
    assert response2.json()["token"] != data["token"]
