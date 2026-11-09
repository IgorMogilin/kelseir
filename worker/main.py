from taskiq import TaskiqEvents, TaskiqState
from taskiq_redis import RedisStreamBroker

from core.config import settings
from core.logger import logger, setup_logger

setup_logger()
broker = RedisStreamBroker(url=settings.redis_broker_url)


@broker.on_event(TaskiqEvents.WORKER_STARTUP)
async def startup(state: TaskiqState) -> None:
    """Вызывается один раз, когда воркер стартует."""
    logger.info("Воркер запущен, слушаю очередь...")


@broker.on_event(TaskiqEvents.WORKER_SHUTDOWN)
async def shutdown(state: TaskiqState) -> None:
    """Вызывается при корректной остановке воркера (Ctrl+C / SIGTERM)."""
    logger.info("Воркер остановлен.")


@broker.task
async def test_task(message: str) -> None:
    """Тестовая задача для проверки, что очередь работает."""
    logger.info("Получена задача: {}", message)
