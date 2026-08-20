import asyncio
import os
import subprocess
import sys
import uuid
from collections.abc import Callable
from pathlib import Path

import asyncpg
import pytest

BACKEND_DIR = Path(__file__).resolve().parents[1]
DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_PORT = os.environ.get("DB_PORT", "5433")
DB_USER = os.environ.get("POSTGRES_USER", "senorita")
DB_PASS = os.environ.get("POSTGRES_PASSWORD", "senorita")
HEAD_REVISION = "b6a4df3e91c2"

EXPECTED_TABLES = {
    "action_log",
    "auth_tokens",
    "briefings",
    "calendar_events",
    "contacts",
    "conversations",
    "document_chunks",
    "documents",
    "email_messages",
    "integrations",
    "memory_entries",
    "message_modes",
    "notification_log",
    "reminders",
    "slack_messages",
    "tasks",
    "tool_confirmations",
    "tool_idempotency_keys",
    "tool_invocations",
    "users",
}
EXPECTED_CONSTRAINTS = {
    "action_result_check",
    "check_message_mode_channel",
    "check_message_mode_mode",
    "check_message_mode_scope",
    "chk_briefings_type",
    "chk_calendar_events_source",
    "chk_email_direction",
    "chk_integrations_provider",
    "chk_integrations_status",
    "chk_tool_confirmations_risk_level",
    "chk_tool_confirmations_status",
    "chk_tool_idempotency_keys_status",
    "chk_tool_invocations_risk_level",
    "chk_tool_invocations_status",
    "chk_users_briefing_detail_level",
    "chk_users_eod_briefing_detail_level",
    "chk_users_memory_capture_sensitivity",
    "conversation_role_check",
    "memory_category_check",
    "reminder_type_check",
    "uq_calendar_events_user_google_event_id",
    "uq_message_mode",
    "uq_tool_idempotency_user_key_hash",
}


def _database_url(database: str, *, async_driver: bool = False) -> str:
    scheme = "postgresql+asyncpg" if async_driver else "postgresql"
    return f"{scheme}://{DB_USER}:{DB_PASS}@{DB_HOST}:{DB_PORT}/{database}"


async def _create_database(database: str) -> None:
    try:
        conn = await asyncpg.connect(_database_url("postgres"))
    except (OSError, asyncpg.PostgresError) as exc:
        pytest.skip(f"Postgres migration test database is unavailable: {exc}")

    try:
        await conn.execute(f'DROP DATABASE IF EXISTS "{database}"')
        await conn.execute(f'CREATE DATABASE "{database}"')
    finally:
        await conn.close()


async def _drop_database(database: str) -> None:
    conn = await asyncpg.connect(_database_url("postgres"))
    try:
        await conn.execute(
            "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname = $1",
            database,
        )
        await conn.execute(f'DROP DATABASE IF EXISTS "{database}"')
    finally:
        await conn.close()


def _run_with_database(callback: Callable[[str], None]) -> None:
    database = f"senorita_migration_{uuid.uuid4().hex[:12]}"
    asyncio.run(_create_database(database))
    try:
        callback(database)
    finally:
        asyncio.run(_drop_database(database))


def _run_alembic(database: str, *args: str) -> None:
    env = os.environ.copy()
    env.update(
        {
            "DATABASE_URL": _database_url(database, async_driver=True),
            "ENCRYPTION_KEY": "test-encryption-key",
            "GEMINI_API_KEY": "test-gemini-key",
            "SECRET_KEY": "test-secret-key",
            "TESTING": "1",
        }
    )
    result = subprocess.run(
        [sys.executable, "-m", "alembic", *args],
        cwd=BACKEND_DIR,
        env=env,
        capture_output=True,
        text=True,
        timeout=90,
    )
    assert result.returncode == 0, result.stdout + result.stderr


async def _fetch_schema_state(database: str) -> dict[str, object]:
    conn = await asyncpg.connect(_database_url(database))
    try:
        rows = await conn.fetch(
            """
            SELECT table_name
            FROM information_schema.tables
            WHERE table_schema = 'public'
              AND table_type = 'BASE TABLE'
            """
        )
        constraints = await conn.fetch(
            """
            SELECT conname
            FROM pg_constraint
            WHERE connamespace = 'public'::regnamespace
            """
        )
        extensions = await conn.fetch("SELECT extname FROM pg_extension")
        vector_columns = await conn.fetch(
            """
            SELECT c.relname AS table_name, a.attname AS column_name,
                   format_type(a.atttypid, a.atttypmod) AS data_type
            FROM pg_attribute a
            JOIN pg_class c ON c.oid = a.attrelid
            JOIN pg_namespace n ON n.oid = c.relnamespace
            WHERE n.nspname = 'public'
              AND c.relname IN ('memory_entries', 'document_chunks')
              AND a.attname = 'embedding'
              AND NOT a.attisdropped
            """
        )
        version = await conn.fetchval("SELECT version_num FROM alembic_version")
    finally:
        await conn.close()

    return {
        "constraints": {row["conname"] for row in constraints},
        "extensions": {row["extname"] for row in extensions},
        "tables": {row["table_name"] for row in rows},
        "version": version,
        "vector_columns": {(row["table_name"], row["column_name"], row["data_type"]) for row in vector_columns},
    }


def _assert_head_schema(database: str) -> None:
    schema = asyncio.run(_fetch_schema_state(database))

    assert schema["version"] == HEAD_REVISION
    assert EXPECTED_TABLES <= schema["tables"]
    assert EXPECTED_CONSTRAINTS <= schema["constraints"]
    assert {"pgcrypto", "vector"} <= schema["extensions"]
    assert ("memory_entries", "embedding", "vector(3072)") in schema["vector_columns"]
    assert ("document_chunks", "embedding", "vector(3072)") in schema["vector_columns"]


async def _fetch_public_tables(database: str) -> set[str]:
    conn = await asyncpg.connect(_database_url(database))
    try:
        rows = await conn.fetch(
            """
            SELECT table_name
            FROM information_schema.tables
            WHERE table_schema = 'public'
              AND table_type = 'BASE TABLE'
            """
        )
    finally:
        await conn.close()
    return {row["table_name"] for row in rows}


@pytest.mark.no_db
def test_alembic_upgrade_head_on_fresh_database() -> None:
    def exercise(database: str) -> None:
        _run_alembic(database, "upgrade", "head")
        _assert_head_schema(database)

        _run_alembic(database, "downgrade", "base")
        assert not (EXPECTED_TABLES & asyncio.run(_fetch_public_tables(database)))

        _run_alembic(database, "upgrade", "head")
        _assert_head_schema(database)

    _run_with_database(exercise)


@pytest.mark.no_db
def test_alembic_upgrade_from_phase_2_head_preserves_existing_database() -> None:
    def exercise(database: str) -> None:
        _run_alembic(database, "upgrade", "8f2c7b91d4a1")
        _run_alembic(database, "upgrade", "head")
        _assert_head_schema(database)

    _run_with_database(exercise)
