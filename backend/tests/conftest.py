import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import asyncpg
import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

# Set test environment variables before importing app
os.environ["SECRET_KEY"] = "test-secret-key"
os.environ["GEMINI_API_KEY"] = "test-gemini-key"
os.environ["TESTING"] = "1"

from app.db.base import Base  # noqa: E402
from app.db.session import get_db  # noqa: E402
from app.main import app  # noqa: E402

# Assuming docker-compose is running with port 5433 or local postgres on 5432
DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_PORT = os.environ.get("DB_PORT", "5432")
DB_USER = os.environ.get("POSTGRES_USER", "senorita")
DB_PASS = os.environ.get("POSTGRES_PASSWORD", "senorita")
DB_NAME = "senorita_test"

TEST_DATABASE_URL = f"postgresql+asyncpg://{DB_USER}:{DB_PASS}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
DEFAULT_DB_URL = f"postgresql://{DB_USER}:{DB_PASS}@{DB_HOST}:{DB_PORT}/postgres"

test_engine = create_async_engine(TEST_DATABASE_URL, echo=False, future=True, poolclass=NullPool)
test_async_session_factory = async_sessionmaker(test_engine, class_=AsyncSession, expire_on_commit=False)


async def override_get_db():
    async with test_async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


app.dependency_overrides[get_db] = override_get_db


@pytest_asyncio.fixture(scope="session")
async def _test_db():
    # 1. Connect to default DB and create test DB
    try:
        sys_conn = await asyncpg.connect(DEFAULT_DB_URL)
        await sys_conn.execute(f"DROP DATABASE IF EXISTS {DB_NAME}")
        await sys_conn.execute(f"CREATE DATABASE {DB_NAME}")
        await sys_conn.close()
    except Exception as e:
        pytest.skip(f"Postgres test database is unavailable: {e}")

    # 2. Connect to test DB and create vector extension
    try:
        test_conn = await asyncpg.connect(f"postgresql://{DB_USER}:{DB_PASS}@{DB_HOST}:{DB_PORT}/{DB_NAME}")
        await test_conn.execute("CREATE EXTENSION IF NOT EXISTS vector;")
        await test_conn.close()
    except Exception as e:
        print(f"Failed to create extension: {e}")

    # 3. Create tables
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    yield

    # 4. Drop tables
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest.fixture(autouse=True)
def setup_db(request: pytest.FixtureRequest):
    if "no_db" in request.node.keywords:
        return

    request.getfixturevalue("_test_db")


@pytest_asyncio.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest_asyncio.fixture
async def db_session():
    async with test_async_session_factory() as session:
        yield session


@pytest.fixture
def mock_gemini(mocker):
    return mocker.patch("google.genai.Client")
