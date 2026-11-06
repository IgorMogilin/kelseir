from pathlib import Path

import pytest
from pytest_mock import MockerFixture

from worker.storage import upload_audio


class TestUploadAudio:
    async def test_upload_returns_url_and_deletes_file(
        self, mocker: MockerFixture, tmp_path: Path
    ) -> None:
        fake_file = tmp_path / "test.mp3"
        fake_file.write_bytes(b"fake audio data")

        mock_client = mocker.MagicMock()
        mock_client.generate_presigned_url.return_value = (
            "https://s3.local/audio/1/abc.mp3?signature=xyz"
        )
        mocker.patch("worker.storage.boto3.client", return_value=mock_client)

        url = await upload_audio(fake_file, user_id=1)

        # Ссылка вернулась та, что «сгенерировал» S3
        assert url == "https://s3.local/audio/1/abc.mp3?signature=xyz"
        # Временный файл удалён
        assert not fake_file.exists()
        # Ключ в правильном формате
        args, _ = mock_client.upload_file.call_args
        key = args[2]
        assert key.startswith("audio/1/")
        assert key.endswith(".mp3")

    async def test_upload_error_keeps_file(self, mocker: MockerFixture, tmp_path: Path) -> None:
        from botocore.exceptions import ClientError

        fake_file = tmp_path / "test.mp3"
        fake_file.write_bytes(b"fake audio data")

        mock_client = mocker.MagicMock()
        mock_client.upload_file.side_effect = ClientError(
            {"Error": {"Code": "NoSuchBucket", "Message": "bucket not found"}},
            "UploadFile",
        )
        mocker.patch("worker.storage.boto3.client", return_value=mock_client)

        with pytest.raises(ClientError):
            await upload_audio(fake_file, user_id=1)

        # При ошибке файл НЕ удаляется
        assert fake_file.exists()
