"""Тесты задачи download_audio: ретраи, пайплайн, запись в БД."""

from collections.abc import AsyncIterator
from pathlib import Path
from unittest.mock import AsyncMock

import pytest
import pytest_asyncio
from pytest_mock import MockerFixture
from sqlalchemy import Connection, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from core.db import Base
from core.models import DownloadHistory, User
from core.repositories import UserRepository
from worker import main as worker_main
from worker.downloader import PrivateVideoError, VideoMetadata

URL = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
S3_URL = "https://s3.local/audio/1/dQw4w9WgXcQ.mp3?sig=x"
META = VideoMetadata(video_id="dQw4w9WgXcQ", title="Тест", duration=100, uploader="Автор")


def _create_tables(conn: Connection) -> None:
    Base.metadata.create_all(bind=conn)


@pytest.fixture(autouse=True)
def no_delay(mocker: MockerFixture) -> None:
    """Ретраи без реальных пауз."""
    mocker.patch.object(worker_main, "RETRY_BASE_DELAY", 0)


@pytest.fixture(autouse=True)
def meta(mocker: MockerFixture) -> AsyncMock:
    """Метаданные без похода в YouTube."""
    mock = AsyncMock(return_value=META)
    mocker.patch.object(worker_main, "extract_metadata", new=mock)
    return mock


@pytest.fixture
def pipeline(mocker: MockerFixture) -> AsyncMock:
    mock = AsyncMock(return_value=S3_URL)
    mocker.patch.object(worker_main, "_run_pipeline", new=mock)
    return mock


@pytest.fixture
def notify(mocker: MockerFixture) -> AsyncMock:
    mock = AsyncMock()
    mocker.patch.object(worker_main, "_notify_bot", new=mock)
    return mock


class TestDownloadAudioTask:
    async def test_success(self, pipeline: AsyncMock, notify: AsyncMock) -> None:
        await worker_main.final_download_audio(user_id=1, youtube_url=URL, chat_id=42)

        pipeline.assert_awaited_once_with(1, URL, META)
        notify.assert_awaited_once()
        assert notify.call_args is not None
        assert notify.call_args.kwargs["ok"] is True

    async def test_retries_transient(
        self, pipeline: AsyncMock, notify: AsyncMock, meta: AsyncMock
    ) -> None:
        pipeline.side_effect = [ConnectionError("сеть"), TimeoutError("таймаут"), S3_URL]

        await worker_main.final_download_audio(user_id=1, youtube_url=URL, chat_id=42)

        assert pipeline.await_count == 3
        meta.assert_awaited_once()  # метаданные не перезапрашивались
        assert notify.call_args is not None
        assert notify.call_args.kwargs["ok"] is True

    async def test_fatal_not_retried(self, pipeline: AsyncMock, notify: AsyncMock) -> None:
        pipeline.side_effect = PrivateVideoError(URL, "приватное")

        with pytest.raises(PrivateVideoError):
            await worker_main.final_download_audio(user_id=1, youtube_url=URL, chat_id=42)

        pipeline.assert_awaited_once()
        assert notify.call_args is not None
        assert notify.call_args.kwargs["ok"] is False

    async def test_gives_up(self, pipeline: AsyncMock, notify: AsyncMock) -> None:
        pipeline.side_effect = ConnectionError("сеть лежит")

        with pytest.raises(ConnectionError):
            await worker_main.final_download_audio(user_id=1, youtube_url=URL, chat_id=42)

        assert pipeline.await_count == worker_main.MAX_ATTEMPTS
        assert notify.call_args is not None
        assert notify.call_args.kwargs["ok"] is False

    async def test_fatal_at_metadata(
        self, pipeline: AsyncMock, notify: AsyncMock, mocker: MockerFixture
    ) -> None:
        mocker.patch.object(
            worker_main,
            "extract_metadata",
            new=AsyncMock(side_effect=PrivateVideoError(URL, "приватное")),
        )

        with pytest.raises(PrivateVideoError):
            await worker_main.final_download_audio(user_id=1, youtube_url=URL, chat_id=42)

        pipeline.assert_not_awaited()
        notify.assert_awaited_once()


class TestRunPipeline:
    async def test_happy_path(self, mocker: MockerFixture) -> None:
        async def fake_download(url: str, dest_dir: Path) -> Path:
            file_path = dest_dir / "dQw4w9WgXcQ.mp3"
            file_path.write_bytes(b"audio-bytes")  # 11 байт
            return file_path

        mocker.patch.object(worker_main, "download_audio_file", new=fake_download)
        upload = AsyncMock(return_value=S3_URL)
        mocker.patch.object(worker_main, "upload_audio", new=upload)
        save = AsyncMock()
        mocker.patch.object(worker_main, "_save_history", new=save)

        result = await worker_main._run_pipeline(7, URL, META)

        assert result == S3_URL
        upload.assert_awaited_once()
        assert upload.call_args is not None
        assert upload.call_args.args[1:] == (7, META.video_id)
        save.assert_awaited_once_with(7, URL, S3_URL, 11)


class TestSaveHistory:
    @pytest_asyncio.fixture
    async def db(self, mocker: MockerFixture) -> AsyncIterator[async_sessionmaker[AsyncSession]]:
        """In-memory SQLite вместо боевой БД."""
        engine = create_async_engine("sqlite+aiosqlite:///:memory:")
        async with engine.begin() as conn:
            await conn.run_sync(_create_tables)
        factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
        mocker.patch.object(worker_main, "AsyncSessionLocal", new=factory)
        yield factory
        await engine.dispose()

    async def test_creates_user_and_history(self, db: async_sessionmaker[AsyncSession]) -> None:
        await worker_main._save_history(123, URL, S3_URL, 99)

        async with db() as session:
            users = list((await session.execute(select(User))).scalars().all())
            history = list((await session.execute(select(DownloadHistory))).scalars().all())

        assert [u.telegram_id for u in users] == [123]
        assert len(history) == 1
        assert history[0].file_size == 99

    async def test_user_not_duplicated(self, db: async_sessionmaker[AsyncSession]) -> None:
        await worker_main._save_history(123, URL, "s1", 1)
        await worker_main._save_history(123, URL, "s2", 2)

        async with db() as session:
            users = list((await session.execute(select(User))).scalars().all())
            history = list((await session.execute(select(DownloadHistory))).scalars().all())

        assert len(users) == 1
        assert len(history) == 2

    async def test_race_on_user_creation(
        self, db: async_sessionmaker[AsyncSession], mocker: MockerFixture
    ) -> None:
        # «параллельная задача» уже создала пользователя
        async with db() as session:
            session.add(User(telegram_id=123))
            await session.commit()

        # наша проверка его «не видит» и лезет создавать
        mocker.patch.object(UserRepository, "get_by_telegram_id", new=AsyncMock(return_value=None))

        await worker_main._save_history(123, URL, S3_URL, 1)

        async with db() as session:
            history = list((await session.execute(select(DownloadHistory))).scalars().all())

        assert len(history) == 1


class TestNotifyBot:
    async def test_both_outcomes(self) -> None:
        await worker_main._notify_bot(1, ok=True, s3_url=S3_URL)
        await worker_main._notify_bot(1, ok=False, error="boom")
