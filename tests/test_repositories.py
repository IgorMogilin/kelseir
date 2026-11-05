from collections.abc import AsyncIterator

import pytest_asyncio
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from core.db import Base
from core.repositories import DownloadHistoryRepository, UserRepository


@pytest_asyncio.fixture
async def async_engine() -> AsyncIterator[AsyncEngine]:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest_asyncio.fixture
async def session(async_engine: AsyncEngine) -> AsyncIterator[AsyncSession]:
    factory = async_sessionmaker(
        async_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )
    async with factory() as session:
        yield session


class TestUserRepository:
    async def test_create(self, session: AsyncSession) -> None:
        repo = UserRepository(session)
        user = await repo.create(telegram_id=123456789, username="testuser")

        assert user.telegram_id == 123456789
        assert user.username == "testuser"
        assert user.created_at is not None

    async def test_get_by_telegram_id_found(self, session: AsyncSession) -> None:
        repo = UserRepository(session)
        await repo.create(telegram_id=123456789, username="testuser")

        user = await repo.get_by_telegram_id(123456789)
        assert user is not None
        assert user.telegram_id == 123456789
        assert user.username == "testuser"

    async def test_get_by_telegram_id_not_found(self, session: AsyncSession) -> None:
        repo = UserRepository(session)
        user = await repo.get_by_telegram_id(999999999)
        assert user is None


class TestDownloadHistoryRepository:
    async def test_create(self, session: AsyncSession) -> None:
        user_repo = UserRepository(session)
        user = await user_repo.create(telegram_id=123456789)

        history_repo = DownloadHistoryRepository(session)
        record = await history_repo.create(
            user_id=user.telegram_id,
            youtube_url="https://youtube.com/watch?v=test",
            s3_url="https://s3.example.com/file.mp3",
            file_size=1024,
        )

        assert record.user_id == 123456789
        assert record.youtube_url == "https://youtube.com/watch?v=test"
        assert record.s3_url == "https://s3.example.com/file.mp3"
        assert record.file_size == 1024
        assert record.created_at is not None

    async def test_get_by_user_id(self, session: AsyncSession) -> None:
        user_repo = UserRepository(session)
        user = await user_repo.create(telegram_id=123456789)

        history_repo = DownloadHistoryRepository(session)
        await history_repo.create(
            user_id=user.telegram_id,
            youtube_url="https://youtube.com/watch?v=1",
        )
        await history_repo.create(
            user_id=user.telegram_id,
            youtube_url="https://youtube.com/watch?v=2",
        )

        records = await history_repo.get_by_user_id(user.telegram_id)
        assert len(records) == 2

    async def test_get_by_user_id_empty(self, session: AsyncSession) -> None:
        history_repo = DownloadHistoryRepository(session)
        records = await history_repo.get_by_user_id(999999999)
        assert records == []
