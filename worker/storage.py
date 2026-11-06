import asyncio
import uuid
from pathlib import Path

import boto3
from botocore.exceptions import BotoCoreError, ClientError

from core.config import settings
from core.logger import logger

__all__ = ["upload_audio"]


def _upload_and_presign(file_path: Path, key: str) -> str:
    """Блокирующая функция дял загрузки ссылки и подписи ссылки"""
    client = boto3.client(
        "s3",
        endpoint_url=settings.S3_ENDPOINT_URL,
        aws_access_key_id=settings.S3_ACCESS_KEY_ID,
        aws_secret_access_key=settings.S3_SECRET_ACCESS_KEY,
    )
    client.upload_file(str(file_path), settings.S3_BUCKET_NAME, key)
    url: str = client.generate_presigned_url(
        "get_object",
        Params={"Bucket": settings.S3_BUCKET_NAME, "Key": key},
        ExpiresIn=3600,
    )
    return url


async def upload_audio(file_path: Path, user_id: int) -> str:
    """Асинх-ая обертка для функции выше. Загружает файл и отдает ссылку."""
    key = f"audio/{user_id}/{uuid.uuid4().hex}.mp3"
    try:
        url = await asyncio.to_thread(_upload_and_presign, file_path, key)
    except (ClientError, BotoCoreError) as e:
        logger.error(f"Не удалось загрузить файл в S3: {e}")
        raise
    file_path.unlink(missing_ok=True)
    return url
