import asyncio
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yt_dlp
from yt_dlp.utils import DownloadError

from core.config import settings
from core.logger import logger

__all__ = [
    "AgeRestrictedError",
    "DurationLimitError",
    "GeoBlockedError",
    "MetadataExtractionError",
    "PrivateVideoError",
    "VideoMetadata",
    "VideoUnavailableError",
    "download_audio",
    "extract_metadata",
]

_YDL_OPTS: dict[str, Any] = {
    "quiet": True,  # не спамить в stdout
    "no_warnings": True,
    "noplaylist": True,  # ссылка на плейлист не должна скачивать весь плейлист
    "socket_timeout": 15,
}


# --- Ошибки ---


class MetadataExtractionError(Exception):
    """Базовая ошибка извлечения метаданных."""

    def __init__(self, url: str, reason: str) -> None:
        self.url = url
        self.reason = reason
        super().__init__(f"{reason}: {url}")


class PrivateVideoError(MetadataExtractionError):
    """Видео приватное — доступа к нему нет."""


class VideoUnavailableError(MetadataExtractionError):
    """Видео удалено или недоступно."""


class DurationLimitError(MetadataExtractionError):
    """Видео длиннее разрешённого лимита."""


class AgeRestrictedError(MetadataExtractionError):
    """Видео с возрастным ограничением — нужен вход в аккаунт."""


class GeoBlockedError(MetadataExtractionError):
    """Видео недоступно в текущем регионе (гео-блок)."""


# --- Модель данных ---


@dataclass(frozen=True, slots=True)
class VideoMetadata:
    """Метаданные, нужные для скачивания и ответа пользователю."""

    video_id: str
    title: str
    duration: int  # секунды
    uploader: str


# --- Внутренние функции ---


def _fetch_info(url: str) -> dict[str, Any]:
    """Синхронный (блокирующий) запрос метаданных у yt-dlp."""
    with yt_dlp.YoutubeDL(_YDL_OPTS) as ydl:
        info: dict[str, Any] = ydl.extract_info(url, download=False)
        return info


def _map_download_error(url: str, exc: DownloadError) -> MetadataExtractionError:
    """Превращает сырую ошибку yt-dlp в наши доменные ошибки."""
    message = str(exc)
    lowered = message.lower()

    if "private video" in lowered:
        return PrivateVideoError(url, "видео приватное")
    if "confirm your age" in lowered:
        return AgeRestrictedError(url, "видео с возрастным ограничением")
    if "your country" in lowered or "geo blocked" in lowered:
        return GeoBlockedError(url, "видео недоступно в вашем регионе")
    return VideoUnavailableError(url, message)


def _build_metadata(url: str, info: dict[str, Any]) -> VideoMetadata:
    duration = int(info.get("duration") or 0)

    limit = settings.MAX_VIDEO_DURATION
    if duration > limit:
        raise DurationLimitError(url, f"длительность {duration} c превышает лимит {limit} c")

    return VideoMetadata(
        video_id=str(info.get("id", "")),
        title=str(info.get("title", "")),
        duration=duration,
        uploader=str(info.get("uploader") or info.get("channel") or "Неизвестный автор"),
    )


# --- Публичное API ---


async def extract_metadata(url: str) -> VideoMetadata:
    """Извлечь метаданные видео без скачивания файла.

    Для приватного/удалённого видео бросает PrivateVideoError /
    VideoUnavailableError, для слишком длинного — DurationLimitError.
    """
    try:
        info = await asyncio.to_thread(_fetch_info, url)
    except DownloadError as exc:
        raise _map_download_error(url, exc) from exc

    if not info:
        raise VideoUnavailableError(url, "yt-dlp вернул пустой ответ")

    return _build_metadata(url, info)


# --- Скачивание файла ---


_MP3_QUALITY = "192"


def _download_sync(url: str, dest_dir: Path) -> Path:
    """Блокирующее скачивание + конвертация в mp3 (вызывается в потоке)."""
    opts: dict[str, Any] = {
        **_YDL_OPTS,
        "format": "bestaudio/best",
        "outtmpl": str(dest_dir / "%(id)s.%(ext)s"),
        "postprocessors": [
            {
                "key": "FFmpegExtractAudio",  # конвертация в mp3 через ffmpeg
                "preferredcodec": "mp3",
                "preferredquality": _MP3_QUALITY,
            },
            {
                "key": "FFmpegMetadata",  # вшивает теги (название, автор и т.д.)
            },
        ],
    }
    with yt_dlp.YoutubeDL(opts) as ydl:
        ydl.download([url])

    mp3_files = list(dest_dir.glob("*.mp3"))
    if not mp3_files:
        raise VideoUnavailableError(url, "скачивание завершилось, но mp3 не появился")
    return mp3_files[0]


async def download_audio(url: str, dest_dir: Path | None = None) -> Path:
    """Скачать аудио, сконвертировать в mp3 и вшить метаданные.

    Возвращает путь к готовому mp3. Если dest_dir не передан, создаётся
    свежая временная директория. Удаление файла/директории — зона
    ответственности вызывающего кода (позже это будет таска в воркере).

    Бросает PrivateVideoError / AgeRestrictedError / GeoBlockedError /
    VideoUnavailableError при неудаче.
    """
    if dest_dir is None:
        dest_dir = Path(tempfile.mkdtemp(prefix="kelseir_"))
    dest_dir.mkdir(parents=True, exist_ok=True)

    try:
        return await asyncio.to_thread(_download_sync, url, dest_dir)
    except DownloadError as exc:
        logger.error("Не удалось скачать {}: {}", url, exc)
        raise _map_download_error(url, exc) from exc
