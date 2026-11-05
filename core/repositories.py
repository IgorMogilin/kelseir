from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.models import DownloadHistory, User


class UserRepository:
    """Репозиторий для работы с таблицей пользователей."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_by_telegram_id(self, telegram_id: int) -> User | None:
        """Поиск пользователя по telegram_id."""
        stmt = select(User).where(User.telegram_id == telegram_id)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def create(self, telegram_id: int, username: str | None = None) -> User:
        """Создание нового пользователя."""
        new_user = User(telegram_id=telegram_id, username=username)
        self.session.add(new_user)
        await self.session.flush()
        await self.session.refresh(new_user)
        return new_user


class DownloadHistoryRepository:
    """Репозиторий для работы с таблицей истории загрузок."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(
        self,
        user_id: int,
        youtube_url: str,
        s3_url: str | None = None,
        file_size: int | None = None,
    ) -> DownloadHistory:
        """Создание записи истории загрузки."""
        record = DownloadHistory(
            user_id=user_id,
            youtube_url=youtube_url,
            s3_url=s3_url,
            file_size=file_size,
        )
        self.session.add(record)
        await self.session.flush()
        await self.session.refresh(record)
        return record

    async def get_by_user_id(self, user_id: int) -> list[DownloadHistory]:
        """Поиск истории загрузок по user_id."""
        stmt = (
            select(DownloadHistory)
            .where(DownloadHistory.user_id == user_id)
            .order_by(DownloadHistory.created_at.desc())
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())
