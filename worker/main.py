import asyncio
import shutil
import tempfile
from pathlib import Path
from typing import Any

from sqlalchemy.exc import IntegrityError
from taskiq import TaskiqEvents, TaskiqState
from taskiq_redis import RedisStreamBroker

from core.config import settings
from core.db import AsyncSessionLocal
from core.logger import logger, setup_logger
from core.repositories import DownloadHistoryRepository, UserRepository
from worker.downloader import (
    AgeRestrictedError,
    DurationLimitError,
    GeoBlockedError,
    PrivateVideoError,
    VideoMetadata,
    extract_metadata,
)
from worker.downloader import (
    download_audio as download_audio_file,
)
from worker.storage import upload_audio

setup_logger()
broker = RedisStreamBroker(url=settings.redis_broker_url)

# Ошибки, при которых повторять попытку бессмысленно:
# проблема в самом видео, и со временем она не исчезнет.
_FINAL_ERRORS: tuple[type[Exception], ...] = (
    PrivateVideoError,
    AgeRestrictedError,
    GeoBlockedError,
    DurationLimitError,
)
MAX_ATTEMPTS = 3
RETRY_BASE_DELAY = 2
RETRY_MAX_DELAY = 60


@broker.on_event(TaskiqEvents.WORKER_STARTUP)
async def startup(state: TaskiqState) -> None:
    """Вызывается один раз, когда воркер стартует."""
    if shutil.which("ffmpeg") is None or shutil.which("ffprobe") is None:
        logger.error("ffmpeg/ffprobe не найдены в PATH — скачивание работать не будет")
        raise RuntimeError("ffmpeg/ffprobe не установлены")
    logger.info("Воркер запущен, слушаю очередь...")


@broker.on_event(TaskiqEvents.WORKER_SHUTDOWN)
async def shutdown(state: TaskiqState) -> None:
    """Вызывается при корректной остановке воркера (Ctrl+C / SIGTERM)."""
    logger.info("Воркер остановлен.")


async def _notify_bot(chat_id: int, ok: bool, **payload: Any) -> None:
    """ЗАГЛУШКА! Потом тут будет код системы уведомлений бота."""
    if ok:
        logger.info("→ бот, чат {}: готово, {}", chat_id, payload.get("s3_url"))
    else:
        logger.warning("→ бот, чат {}: ошибка, {}", chat_id, payload.get("error"))


async def _save_history(user_id: int, youtube_url: str, s3_url: str, file_size: int) -> None:
    """Атомарно сохранить результат пайплайна."""
    async with AsyncSessionLocal() as session:
        user_repo = UserRepository(session)
        if await user_repo.get_by_telegram_id(user_id) is None:
            try:
                async with session.begin_nested():
                    await user_repo.create(telegram_id=user_id)
            except IntegrityError:
                pass
        history_repo = DownloadHistoryRepository(session)
        await history_repo.create(
            user_id=user_id, youtube_url=youtube_url, s3_url=s3_url, file_size=file_size
        )
        await session.commit()


async def _run_pipeline(user_id: int, youtube_url: str, metadata: VideoMetadata) -> str:
    """Одна полная попытка с метаданными."""
    with tempfile.TemporaryDirectory(prefix="kelseir_") as tmp_dir:
        file_path = await download_audio_file(youtube_url, dest_dir=Path(tmp_dir))
        file_size = file_path.stat().st_size
        logger.info("Файл скачан: {} ({} байт)", file_path.name, file_size)
        s3_url = await upload_audio(file_path, user_id, metadata.video_id)
        logger.info("Файл загружен в S3")
    await _save_history(user_id, youtube_url, s3_url, file_size)
    logger.info("История записана в БД")
    return s3_url


@broker.task
async def final_download_audio(user_id: int, youtube_url: str, chat_id: int) -> None:
    """Скачивает аудио с YT и сохраняет результат."""
    logger.info("Задача стартовала: user={} url={}", user_id, youtube_url)

    metadata: VideoMetadata | None = None
    for attempt in range(1, MAX_ATTEMPTS + 1):
        try:
            if metadata is None:
                metadata = await extract_metadata(youtube_url)
                logger.info(
                    "Метаданные: «{}» ({} с, автор: {})",
                    metadata.title,
                    metadata.duration,
                    metadata.uploader,
                )
            s3_url = await _run_pipeline(user_id, youtube_url, metadata)
        except _FINAL_ERRORS as ex:
            logger.error("Фатальная ошибка, ретрай не нужен: {}", ex)
            await _notify_bot(chat_id, ok=False, error=str(ex))
            raise
        except Exception as ex:
            if attempt == MAX_ATTEMPTS:
                logger.error("Попытка {}/{} последняя: {}", attempt, MAX_ATTEMPTS, ex)
                await _notify_bot(chat_id, ok=False, error=str(ex))
                raise
            delay = min(RETRY_BASE_DELAY**attempt, RETRY_MAX_DELAY)
            logger.warning(
                "Попытка {}/{} упала: {}. Повтор через {} с",
                attempt,
                MAX_ATTEMPTS,
                ex,
                delay,
            )
            await asyncio.sleep(delay)
        else:
            logger.info("Задача выполнена с попытки {}", attempt)
            await _notify_bot(chat_id, ok=True, s3_url=s3_url)
            return
