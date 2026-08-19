import asyncio
import time
from datetime import timedelta
from uuid import UUID, uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.agents.tool_system import (
    ConfirmationPolicy,
    RiskLevel,
    ToolContext,
    ToolDefinition,
    ToolExecutor,
    ToolPermission,
)
from app.agents.tool_system.persistence import utcnow
from app.agents.tool_system.registry import ToolRegistry
from app.db.models import AuthToken, Contact, Reminder, Task, ToolConfirmation, ToolIdempotencyKey, ToolInvocation, User
from tests.conftest import test_engine

pytestmark = pytest.mark.no_db


@pytest.fixture(scope="module", autouse=True)
async def _tool_system_tables():
    tables = [
        User.__table__,
        AuthToken.__table__,
        Contact.__table__,
        Reminder.__table__,
        Task.__table__,
        ToolInvocation.__table__,
        ToolConfirmation.__table__,
        ToolIdempotencyKey.__table__,
    ]
    try:
        async with test_engine.begin() as conn:
            await conn.run_sync(lambda sync_conn: User.metadata.drop_all(sync_conn, tables=reversed(tables)))
            await conn.run_sync(lambda sync_conn: User.metadata.create_all(sync_conn, tables=tables))
        yield
    except Exception as exc:
        pytest.skip(f"Postgres tool-system test database is unavailable: {exc}")
    finally:
        try:
            async with test_engine.begin() as conn:
                await conn.run_sync(lambda sync_conn: User.metadata.drop_all(sync_conn, tables=reversed(tables)))
        except Exception:
            pass


async def _side_effect_handler(session, user_id, title: str):
    return {"id": str(uuid4()), "title": title, "user_id": str(user_id)}


def _side_effect_definition() -> ToolDefinition:
    return ToolDefinition(
        name="create_once",
        description="Create once.",
        category="test",
        subcategory="unit",
        input_schema={
            "type": "object",
            "properties": {"title": {"type": "string"}},
            "required": ["title"],
            "additionalProperties": False,
        },
        required_permissions=(ToolPermission.WRITE,),
        risk_level=RiskLevel.LOW,
        side_effects=("creates_task",),
        idempotent=False,
    )


@pytest.mark.asyncio
async def test_idempotency_key_replays_original_result(db_session):
    calls = 0

    async def create_once_handler(session, user_id, title: str):
        nonlocal calls
        calls += 1
        await asyncio.sleep(0)
        return {"id": str(uuid4()), "title": title, "calls": calls}

    user = User(name="tool-idempotency-user", timezone="UTC")
    db_session.add(user)
    await db_session.flush()

    registry = ToolRegistry()
    registry.register(_side_effect_definition(), create_once_handler)
    executor = ToolExecutor(registry)
    context = ToolContext(user_id=user.id, idempotency_key="same-key")

    first = await executor.execute(db_session, context, "create_once", {"title": "Ship it"})
    second = await executor.execute(db_session, context, "create_once", {"title": "Ship it"})

    records = (
        (await db_session.execute(select(ToolIdempotencyKey).where(ToolIdempotencyKey.user_id == user.id)))
        .scalars()
        .all()
    )
    invocations = (
        (await db_session.execute(select(ToolInvocation).where(ToolInvocation.user_id == user.id))).scalars().all()
    )
    assert calls == 1
    assert first.success is True
    assert second.success is True
    assert second.data == first.data
    assert len(records) == 1
    assert len(invocations) == 1


@pytest.mark.asyncio
async def test_idempotency_key_rejects_different_arguments(db_session):
    user = User(name="tool-idempotency-conflict-user", timezone="UTC")
    db_session.add(user)
    await db_session.flush()

    registry = ToolRegistry()
    registry.register(_side_effect_definition(), _side_effect_handler)
    executor = ToolExecutor(registry)
    context = ToolContext(user_id=user.id, idempotency_key="same-key")

    first = await executor.execute(db_session, context, "create_once", {"title": "First"})
    second = await executor.execute(db_session, context, "create_once", {"title": "Second"})

    assert first.success is True
    assert second.success is False
    assert second.error.code == "idempotency_conflict"


@pytest.mark.asyncio
async def test_failed_and_denied_invocations_are_persisted(db_session):
    user = User(name="tool-failure-audit-user", timezone="UTC")
    db_session.add(user)
    await db_session.flush()

    registry = ToolRegistry()
    registry.register(_side_effect_definition(), _side_effect_handler)
    executor = ToolExecutor(registry)

    invalid = await executor.execute(db_session, ToolContext(user_id=user.id), "create_once", {})
    denied = await executor.execute(
        db_session,
        ToolContext(user_id=user.id, permissions={"WRITE": ConfirmationPolicy.NEVER_ALLOW.value}),
        "create_once",
        {"title": "Nope"},
    )
    unknown = await executor.execute(db_session, ToolContext(user_id=user.id), "missing_tool", {"api_key": "secret"})

    rows = (await db_session.execute(select(ToolInvocation).where(ToolInvocation.user_id == user.id))).scalars().all()
    assert invalid.error.code == "invalid_input"
    assert denied.error.code == "permission_denied"
    assert unknown.error.code == "unknown_tool"
    assert sorted(row.error_code for row in rows) == ["invalid_input", "permission_denied", "unknown_tool"]
    assert next(row for row in rows if row.tool_name == "missing_tool").arguments_snapshot["api_key"] == "[REDACTED]"


@pytest.mark.asyncio
async def test_confirmation_api_approves_exact_invocation_once(client: AsyncClient):
    login = await client.post("/api/v1/auth/login", json={"name": "tool_confirmation_user"})
    token = login.json()["token"]
    headers = {"Authorization": f"Bearer {token}"}

    execute = await client.post(
        "/api/v1/tools/delete_task/execute",
        headers=headers,
        json={"arguments": {"task_id": str(uuid4())}},
    )
    assert execute.status_code == 200
    data = execute.json()
    assert data["error"]["code"] == "confirmation_required"
    confirmation_id = data["metadata"]["confirmation_id"]

    listed = await client.get("/api/v1/tools/confirmations", headers=headers)
    assert listed.status_code == 200
    assert any(row["id"] == confirmation_id for row in listed.json()["confirmations"])

    approved = await client.post(f"/api/v1/tools/confirmations/{confirmation_id}/approve", headers=headers)
    assert approved.status_code == 200
    assert approved.json()["error"]["code"] == "Task not found."

    approved_again = await client.post(f"/api/v1/tools/confirmations/{confirmation_id}/approve", headers=headers)
    assert approved_again.status_code == 409


@pytest.mark.asyncio
async def test_confirmation_api_rejects_argument_override_attempt(client: AsyncClient):
    login = await client.post("/api/v1/auth/login", json={"name": f"tool_override_user_{uuid4()}"})
    headers = {"Authorization": f"Bearer {login.json()['token']}"}

    execute = await client.post(
        "/api/v1/tools/delete_task/execute",
        headers=headers,
        json={"arguments": {"task_id": str(uuid4())}},
    )
    confirmation_id = execute.json()["metadata"]["confirmation_id"]

    approved = await client.post(
        f"/api/v1/tools/confirmations/{confirmation_id}/approve",
        headers=headers,
        json={"arguments": {"task_id": str(uuid4())}},
    )
    assert approved.status_code == 400


@pytest.mark.asyncio
async def test_confirmation_api_enforces_cross_user_isolation(client: AsyncClient):
    user_a = await client.post("/api/v1/auth/login", json={"name": f"tool_user_a_{uuid4()}"})
    headers_a = {"Authorization": f"Bearer {user_a.json()['token']}"}
    user_b = await client.post("/api/v1/auth/login", json={"name": f"tool_user_b_{uuid4()}"})
    headers_b = {"Authorization": f"Bearer {user_b.json()['token']}"}

    execute = await client.post(
        "/api/v1/tools/delete_task/execute",
        headers=headers_a,
        json={"arguments": {"task_id": str(uuid4())}},
    )
    confirmation_id = execute.json()["metadata"]["confirmation_id"]

    read = await client.get(f"/api/v1/tools/confirmations/{confirmation_id}", headers=headers_b)
    approve = await client.post(f"/api/v1/tools/confirmations/{confirmation_id}/approve", headers=headers_b)
    reject = await client.post(f"/api/v1/tools/confirmations/{confirmation_id}/reject", headers=headers_b)
    listed = await client.get("/api/v1/tools/confirmations", headers=headers_b)

    assert read.status_code == 404
    assert approve.status_code == 404
    assert reject.status_code == 404
    assert all(row["id"] != confirmation_id for row in listed.json()["confirmations"])


@pytest.mark.asyncio
async def test_expired_confirmation_cannot_execute(client: AsyncClient, db_session):
    login = await client.post("/api/v1/auth/login", json={"name": f"tool_expired_user_{uuid4()}"})
    headers = {"Authorization": f"Bearer {login.json()['token']}"}

    execute = await client.post(
        "/api/v1/tools/delete_task/execute",
        headers=headers,
        json={"arguments": {"task_id": str(uuid4())}},
    )
    confirmation_id = execute.json()["metadata"]["confirmation_id"]
    confirmation = (
        await db_session.execute(select(ToolConfirmation).where(ToolConfirmation.id == confirmation_id))
    ).scalar_one()
    confirmation.expires_at = utcnow() - timedelta(minutes=1)
    await db_session.commit()

    approved = await client.post(f"/api/v1/tools/confirmations/{confirmation_id}/approve", headers=headers)
    assert approved.status_code == 409
    assert approved.json()["detail"] == "Confirmation has expired."


@pytest.mark.asyncio
async def test_concurrent_confirmation_approval_executes_once(client: AsyncClient, db_session):
    login = await client.post("/api/v1/auth/login", json={"name": f"tool_race_user_{uuid4()}"})
    user_id = UUID(login.json()["user"]["id"])
    headers = {"Authorization": f"Bearer {login.json()['token']}"}

    create = await client.post(
        "/api/v1/tools/create_task/execute",
        headers=headers,
        json={"arguments": {"title": f"Race target {uuid4()}"}},
    )
    task_id = UUID(create.json()["data"]["id"])
    execute = await client.post(
        "/api/v1/tools/delete_task/execute",
        headers=headers,
        json={"arguments": {"task_id": str(task_id)}},
    )
    confirmation_id = execute.json()["metadata"]["confirmation_id"]

    responses = await asyncio.gather(
        *[client.post(f"/api/v1/tools/confirmations/{confirmation_id}/approve", headers=headers) for _ in range(10)]
    )
    statuses = [response.status_code for response in responses]
    remaining = (
        (await db_session.execute(select(Task).where(Task.user_id == user_id, Task.id == task_id))).scalars().all()
    )

    assert statuses.count(200) == 1
    assert statuses.count(409) == 9
    assert remaining == []


@pytest.mark.asyncio
async def test_concurrent_idempotency_executes_once(client: AsyncClient, db_session):
    login = await client.post("/api/v1/auth/login", json={"name": f"tool_idempotency_race_user_{uuid4()}"})
    user_id = UUID(login.json()["user"]["id"])
    headers = {"Authorization": f"Bearer {login.json()['token']}"}
    title = f"Idempotent create {uuid4()}"

    responses = await asyncio.gather(
        *[
            client.post(
                "/api/v1/tools/create_task/execute",
                headers=headers,
                json={"arguments": {"title": title}, "idempotency_key": "create-once"},
            )
            for _ in range(5)
        ]
    )
    payloads = [response.json() for response in responses]
    tasks = (await db_session.execute(select(Task).where(Task.user_id == user_id, Task.title == title))).scalars().all()

    assert all(response.status_code == 200 for response in responses)
    assert all(payload["success"] for payload in payloads)
    assert len({payload["data"]["id"] for payload in payloads}) == 1
    assert len(tasks) == 1


@pytest.mark.asyncio
async def test_confirmation_plus_idempotency_reuses_one_confirmation(client: AsyncClient, db_session):
    login = await client.post("/api/v1/auth/login", json={"name": f"tool_confirm_idem_user_{uuid4()}"})
    user_id = UUID(login.json()["user"]["id"])
    headers = {"Authorization": f"Bearer {login.json()['token']}"}

    create = await client.post(
        "/api/v1/tools/create_task/execute",
        headers=headers,
        json={"arguments": {"title": f"Confirm idem target {uuid4()}"}},
    )
    task_id = UUID(create.json()["data"]["id"])

    initial = await asyncio.gather(
        *[
            client.post(
                "/api/v1/tools/delete_task/execute",
                headers=headers,
                json={"arguments": {"task_id": str(task_id)}, "idempotency_key": "confirm-delete-once"},
            )
            for _ in range(5)
        ]
    )
    confirmation_ids = {response.json()["metadata"]["confirmation_id"] for response in initial}
    assert len(confirmation_ids) == 1
    confirmation_id = confirmation_ids.pop()

    approvals = await asyncio.gather(
        *[client.post(f"/api/v1/tools/confirmations/{confirmation_id}/approve", headers=headers) for _ in range(5)]
    )
    remaining = (
        (await db_session.execute(select(Task).where(Task.user_id == user_id, Task.id == task_id))).scalars().all()
    )

    assert [response.status_code for response in approvals].count(200) == 1
    assert [response.status_code for response in approvals].count(409) == 4
    assert remaining == []


@pytest.mark.asyncio
async def test_lightweight_tool_system_load_paths(client: AsyncClient, db_session):
    login = await client.post("/api/v1/auth/login", json={"name": f"tool_load_user_{uuid4()}"})
    user_id = UUID(login.json()["user"]["id"])
    headers = {"Authorization": f"Bearer {login.json()['token']}"}

    read_start = time.perf_counter()
    read_responses = await asyncio.gather(
        *[
            client.post(
                "/api/v1/tools/list_tasks/execute",
                headers=headers,
                json={"arguments": {"limit": 5}},
            )
            for _ in range(100)
        ]
    )
    read_duration_ms = round((time.perf_counter() - read_start) * 1000)

    create = await client.post(
        "/api/v1/tools/create_task/execute",
        headers=headers,
        json={"arguments": {"title": f"Load delete target {uuid4()}"}},
    )
    task_id = UUID(create.json()["data"]["id"])
    execute = await client.post(
        "/api/v1/tools/delete_task/execute",
        headers=headers,
        json={"arguments": {"task_id": str(task_id)}},
    )
    confirmation_id = execute.json()["metadata"]["confirmation_id"]

    approval_start = time.perf_counter()
    approval_responses = await asyncio.gather(
        *[client.post(f"/api/v1/tools/confirmations/{confirmation_id}/approve", headers=headers) for _ in range(50)]
    )
    approval_duration_ms = round((time.perf_counter() - approval_start) * 1000)

    title = f"Load idempotency target {uuid4()}"
    idempotency_start = time.perf_counter()
    idempotency_responses = await asyncio.gather(
        *[
            client.post(
                "/api/v1/tools/create_task/execute",
                headers=headers,
                json={"arguments": {"title": title}, "idempotency_key": "load-create-once"},
            )
            for _ in range(50)
        ]
    )
    idempotency_duration_ms = round((time.perf_counter() - idempotency_start) * 1000)

    created_tasks = (
        (await db_session.execute(select(Task).where(Task.user_id == user_id, Task.title == title))).scalars().all()
    )
    idempotency_payloads = [response.json() for response in idempotency_responses]

    print(
        "LOAD_METRICS "
        f"read_100_ms={read_duration_ms} "
        f"approval_50_ms={approval_duration_ms} "
        f"idempotency_50_ms={idempotency_duration_ms}"
    )

    assert all(response.status_code == 200 for response in read_responses), read_duration_ms
    assert [response.status_code for response in approval_responses].count(200) == 1, approval_duration_ms
    assert [response.status_code for response in approval_responses].count(409) == 49, approval_duration_ms
    assert all(response.status_code == 200 for response in idempotency_responses), idempotency_duration_ms
    assert len({payload["data"]["id"] for payload in idempotency_payloads}) == 1
    assert len(created_tasks) == 1
