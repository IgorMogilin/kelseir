from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.models import User


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
