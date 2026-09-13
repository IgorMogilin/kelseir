import sys

from loguru import logger

from core.config import settings


def setup_logger() -> None:
    """Настройка loguru для всего приложения."""
    logger.remove()

    level = settings.LOG_LEVEL.upper()

    if settings.ENVIRONMENT == "production":
        logger.add(
            sys.stdout,
            level=level,
            serialize=True,
            backtrace=True,
            diagnose=False,
        )
    else:
        log_format = (
            "<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | "
            "<level>{level: <8}</level> | "
            "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - "
            "<level>{message}</level>"
        )
        logger.add(
            sys.stdout,
            level=level,
            format=log_format,
            colorize=True,
            backtrace=True,
            diagnose=True,
        )


__all__ = ["logger", "setup_logger"]
