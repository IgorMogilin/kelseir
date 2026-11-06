import asyncio
from dataclasses import dataclass
from typing import Any

import yt_dlp
from yt_dlp.utils import DownloadError

from core.config import settings

__all__ = [
    "DurationLimitError",
    "MetadataExtractionError",
    "PrivateVideoError",
    "VideoMetadata",
    "VideoUnavailableError",
    "extract_metadata",
]

_YDL_OPTS: dict[str, Any] = {
    "quiet": True,          # не спамить в stdout
    "no_warnings": True,
    "noplaylist": True,     # ссылка на плейлист не должна скачивать весь плейлист
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
    if "Private video" in message:
        return PrivateVideoError(url, "видео приватное")
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
