from aiogram import Router
from aiogram.filters import CommandStart
from aiogram.types import Message

from app.database import SessionLocal
from app.repositories.meals import MealsRepository
from app.repositories.users import UsersRepository
from app.states import BotStates


router = Router()


@router.message(CommandStart())
async def cmd_start(message: Message) -> None:
    async with SessionLocal() as session:
        users_repo = UsersRepository(session)
        meals_repo = MealsRepository(session)
        user = await users_repo.create_or_update_telegram_user(
            telegram_id=message.from_user.id,
            username=message.from_user.username,
            first_name=message.from_user.first_name,
            last_name=message.from_user.last_name,
        )

        if user.onboarding_completed:
            await meals_repo.clear_state(message.from_user.id)
            await session.commit()
            await message.answer(
                "Бот уже настроен.\n\n"
                "Команды:\n"
                "/add — добавить прием пищи\n"
                "/today — сводка за сегодня\n"
                "/yesterday — сводка за вчера\n"
                "/profile — профиль\n"
                "/settings — настройки\n"
                "/delete_last — удалить последнюю запись\n"
                "/help — помощь"
            )
            return

        await meals_repo.save_state(message.from_user.id, BotStates.ONBOARDING_WEIGHT, {})
        await session.commit()
        await message.answer("Укажи свой вес в кг.")
