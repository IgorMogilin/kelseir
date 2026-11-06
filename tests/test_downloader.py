from pathlib import Path
from typing import Any

import pytest
from pytest_mock import MockerFixture
from yt_dlp.utils import DownloadError

from core.config import settings
from worker.downloader import (
    AgeRestrictedError,
    DurationLimitError,
    GeoBlockedError,
    PrivateVideoError,
    VideoMetadata,
    VideoUnavailableError,
    download_audio,
    extract_metadata,
)

URL = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"

VALID_INFO: dict[str, Any] = {
    "id": "dQw4w9WgXcQ",
    "title": "Never Gonna Give You Up",
    "duration": 213,
    "uploader": "Rick Astley",
}


def _patch_ydl(mocker: MockerFixture) -> Any:
    """Подменяет YoutubeDL и возвращает мок, с которым работает код."""
    ydl_cls = mocker.patch("worker.downloader.yt_dlp.YoutubeDL")
    return ydl_cls.return_value.__enter__.return_value


class TestExtractMetadata:
    async def test_valid_url_returns_metadata(self, mocker: MockerFixture) -> None:
        ydl = _patch_ydl(mocker)
        ydl.extract_info.return_value = VALID_INFO

        metadata = await extract_metadata(URL)

        assert metadata == VideoMetadata(
            video_id="dQw4w9WgXcQ",
            title="Never Gonna Give You Up",
            duration=213,
            uploader="Rick Astley",
        )
        ydl.extract_info.assert_called_once_with(URL, download=False)

    async def test_video_longer_than_limit_raises(self, mocker: MockerFixture) -> None:
        mocker.patch.object(settings, "MAX_VIDEO_DURATION", 120)
        ydl = _patch_ydl(mocker)
        ydl.extract_info.return_value = {**VALID_INFO, "duration": 300}

        with pytest.raises(DurationLimitError):
            await extract_metadata(URL)

    async def test_video_at_limit_is_allowed(self, mocker: MockerFixture) -> None:
        mocker.patch.object(settings, "MAX_VIDEO_DURATION", 300)
        ydl = _patch_ydl(mocker)
        ydl.extract_info.return_value = {**VALID_INFO, "duration": 300}

        metadata = await extract_metadata(URL)

        assert metadata.duration == 300

    async def test_private_video_raises(self, mocker: MockerFixture) -> None:
        ydl = _patch_ydl(mocker)
        ydl.extract_info.side_effect = DownloadError(
            "Private video. Sign in if you've been granted access to this video."
        )

        with pytest.raises(PrivateVideoError) as exc_info:
            await extract_metadata(URL)

        assert exc_info.value.__cause__ is not None  # цепочка исключений сохранена

    async def test_unavailable_video_raises(self, mocker: MockerFixture) -> None:
        ydl = _patch_ydl(mocker)
        ydl.extract_info.side_effect = DownloadError("Video unavailable")

        with pytest.raises(VideoUnavailableError):
            await extract_metadata(URL)


class TestDownloadAudio:
    async def test_returns_mp3_path(self, mocker: MockerFixture, tmp_path: Path) -> None:
        fake_mp3 = tmp_path / "test123.mp3"
        fake_mp3.touch()
        mocker.patch("worker.downloader._download_sync", return_value=fake_mp3)

        result = await download_audio(URL, dest_dir=tmp_path)

        assert result == fake_mp3

    async def test_age_restricted_raises(self, mocker: MockerFixture, tmp_path: Path) -> None:
        mocker.patch(
            "worker.downloader._download_sync",
            side_effect=DownloadError("Sign in to confirm your age"),
        )

        with pytest.raises(AgeRestrictedError):
            await download_audio(URL, dest_dir=tmp_path)

    async def test_geo_blocked_raises(self, mocker: MockerFixture, tmp_path: Path) -> None:
        mocker.patch(
            "worker.downloader._download_sync",
            side_effect=DownloadError(
                "The uploader has not made this video available in your country"
            ),
        )

        with pytest.raises(GeoBlockedError):
            await download_audio(URL, dest_dir=tmp_path)

    async def test_unavailable_raises(self, mocker: MockerFixture, tmp_path: Path) -> None:
        mocker.patch(
            "worker.downloader._download_sync",
            side_effect=DownloadError("Video unavailable"),
        )

        with pytest.raises(VideoUnavailableError):
            await download_audio(URL, dest_dir=tmp_path)
