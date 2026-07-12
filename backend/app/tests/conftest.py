"""Shared test fixtures."""
import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.security import hash_password
from app.db.base import Base
from app.db.models.user import User
from app.db.session import get_db
from app.main import app

# ── In-memory SQLite for tests ────────────────────────────────────────────────
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"


@pytest_asyncio.fixture(scope="session")
async def engine():
    eng = create_async_engine(TEST_DATABASE_URL, echo=False)
    async with eng.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield eng
    async with eng.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await eng.dispose()


@pytest_asyncio.fixture
async def db_session(engine):
    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with session_factory() as session:
        yield session
        await session.rollback()


@pytest_asyncio.fixture
async def client(db_session: AsyncSession):
    """HTTP test client with DB override."""

    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c
    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def superuser(db_session: AsyncSession) -> User:
    user = User(
        username="admin",
        hashed_password=hash_password("Admin123!"),
        role="admin",
        is_active=True,
        is_superuser=True,
    )
    db_session.add(user)
    await db_session.flush()
    return user


@pytest_asyncio.fixture
async def regular_user(db_session: AsyncSession) -> User:
    user = User(
        username="user",
        hashed_password=hash_password("User123!"),
        role="viewer",
        is_active=True,
        is_superuser=False,
    )
    db_session.add(user)
    await db_session.flush()
    return user


@pytest_asyncio.fixture
async def superuser_token(client, superuser: User) -> str:
    response = await client.post(
        "/api/v1/auth/login",
        json={"username": "admin", "password": "Admin123!"},
    )
    return response.json()["access_token"]


@pytest_asyncio.fixture
async def user_token(client, regular_user: User) -> str:
    response = await client.post(
        "/api/v1/auth/login",
        json={"username": "user", "password": "User123!"},
    )
    return response.json()["access_token"]
