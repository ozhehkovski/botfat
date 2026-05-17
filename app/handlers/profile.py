from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

from app.database import SessionLocal
from app.repositories.users import UsersRepository


router = Router()


@router.message(Command("profile"))
async def cmd_profile(message: Message) -> None:
    async with SessionLocal() as session:
        users_repo = UsersRepository(session)
        user = await users_repo.get_by_telegram_id(message.from_user.id)
        if user is None or not user.onboarding_completed:
            await message.answer("Сначала нужно настроить профиль. Укажи свой вес в кг.")
            return

        summary_status = "включено" if user.summary_enabled else "выключено"
        reminder_status = "включены" if user.reminder_enabled else "выключены"
        await message.answer(
            "Профиль:\n\n"
            f"Вес: {user.weight_kg} кг\n"
            f"Рост: {user.height_cm} см\n"
            f"Лимит калорий: {user.daily_calorie_limit} ккал\n"
            f"Цель по белку: {user.daily_protein_goal} г\n"
            f"Часовой пояс: {user.timezone}\n"
            f"Вечернее саммари: {summary_status} в {user.summary_hour}:00\n"
            f"Напоминания: {reminder_status} в 08:00, 15:00 и 20:00"
        )
