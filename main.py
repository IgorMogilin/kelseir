from core.config import settings
from core.logger import logger, setup_logger

setup_logger()


def main() -> None:
    print("Direct print: script is running!")  # Явная проверка вызова
    logger.info(
        "Application starting | env={} | level={}",
        settings.ENVIRONMENT,
        settings.LOG_LEVEL,
    )
    logger.warning("Test warning log | user_id={} | action={}", 12345, "download")


if __name__ == "__main__":
    main()
