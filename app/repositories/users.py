from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models import User


class UsersRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.settings = get_settings()

    async def get_by_telegram_id(self, telegram_id: int) -> User | None:
        result = await self.session.execute(select(User).where(User.telegram_id == telegram_id))
        return result.scalar_one_or_none()

    async def create_or_update_telegram_user(
        self,
        telegram_id: int,
        username: str | None,
        first_name: str | None,
        last_name: str | None,
    ) -> User:
        user = await self.get_by_telegram_id(telegram_id)
        if user is None:
            user = User(
                telegram_id=telegram_id,
                username=username,
                first_name=first_name,
                last_name=last_name,
                timezone=self.settings.default_timezone,
                summary_hour=self.settings.summary_send_hour,
            )
            self.session.add(user)
        else:
            user.username = username
            user.first_name = first_name
            user.last_name = last_name
        await self.session.flush()
        return user

    async def update_profile(self, user: User, **fields) -> User:
        for key, value in fields.items():
            setattr(user, key, value)
        await self.session.flush()
        return user

    async def list_summary_enabled_users(self) -> list[User]:
        result = await self.session.execute(
            select(User).where(User.summary_enabled.is_(True), User.onboarding_completed.is_(True))
        )
        return list(result.scalars().all())

    async def list_reminder_enabled_users(self) -> list[User]:
        result = await self.session.execute(
            select(User).where(User.reminder_enabled.is_(True), User.onboarding_completed.is_(True))
        )
        return list(result.scalars().all())
