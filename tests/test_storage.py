"""Тесты загрузки аудио в S3 (boto3 замокан, сети нет)."""

from pathlib import Path

import pytest
from botocore.exceptions import ClientError
from pytest_mock import MockerFixture

from worker.storage import upload_audio

VIDEO_ID = "dQw4w9WgXcQ"
PRESIGNED_URL = f"https://s3.local/audio/1/{VIDEO_ID}.mp3?signature=xyz"


class TestUploadAudio:
    async def test_upload_returns_url_and_deletes_file(
        self, mocker: MockerFixture, tmp_path: Path
    ) -> None:
        fake_file = tmp_path / "test.mp3"
        fake_file.write_bytes(b"fake audio data")

        mock_client = mocker.MagicMock()
        mock_client.generate_presigned_url.return_value = PRESIGNED_URL
        mocker.patch("worker.storage.boto3.client", return_value=mock_client)

        url = await upload_audio(fake_file, user_id=1, video_id=VIDEO_ID)

        # Ссылка вернулась та, что «сгенерировал» S3
        assert url == PRESIGNED_URL
        # Временный файл удалён
        assert not fake_file.exists()
        # Ключ идемпотентный: строго по video_id, без случайного uuid
        args, _ = mock_client.upload_file.call_args
        assert args[2] == f"audio/1/{VIDEO_ID}.mp3"

    async def test_upload_error_keeps_file(self, mocker: MockerFixture, tmp_path: Path) -> None:
        fake_file = tmp_path / "test.mp3"
        fake_file.write_bytes(b"fake audio data")

        mock_client = mocker.MagicMock()
        mock_client.upload_file.side_effect = ClientError(
            {"Error": {"Code": "NoSuchBucket", "Message": "bucket not found"}},
            "UploadFile",
        )
        mocker.patch("worker.storage.boto3.client", return_value=mock_client)

        with pytest.raises(ClientError):
            await upload_audio(fake_file, user_id=1, video_id=VIDEO_ID)

        # При ошибке файл НЕ удаляется
        assert fake_file.exists()

    async def test_key_is_idempotent(self, mocker: MockerFixture, tmp_path: Path) -> None:
        """Повторная загрузка того же видео даёт тот же ключ (защита от сирот)."""
        mock_client = mocker.MagicMock()
        mock_client.generate_presigned_url.return_value = PRESIGNED_URL
        mocker.patch("worker.storage.boto3.client", return_value=mock_client)

        keys = []
        for _ in range(2):
            fake_file = tmp_path / "test.mp3"
            fake_file.write_bytes(b"fake audio data")
            await upload_audio(fake_file, user_id=1, video_id=VIDEO_ID)
            args, _ = mock_client.upload_file.call_args
            keys.append(args[2])

        assert keys[0] == keys[1]
