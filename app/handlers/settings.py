from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message

from app.database import SessionLocal
from app.keyboards import settings_keyboard
from app.repositories.meals import MealsRepository
from app.repositories.users import UsersRepository
from app.states import BotStates


router = Router()


@router.message(Command("settings"))
async def cmd_settings(message: Message) -> None:
    async with SessionLocal() as session:
        users_repo = UsersRepository(session)
        user = await users_repo.get_by_telegram_id(message.from_user.id)
        if user is None or not user.onboarding_completed:
            await message.answer("Сначала нужно настроить профиль. Укажи свой вес в кг.")
            return
        await message.answer(
            "Что хочешь изменить?",
            reply_markup=settings_keyboard(user.summary_enabled, user.reminder_enabled),
        )


@router.callback_query(F.data.startswith("settings:"))
async def settings_callback(callback: CallbackQuery) -> None:
    async with SessionLocal() as session:
        users_repo = UsersRepository(session)
        meals_repo = MealsRepository(session)
        user = await users_repo.get_by_telegram_id(callback.from_user.id)
        if user is None:
            await callback.answer()
            return

        action = callback.data.split(":", 1)[1]
        if action == "summary_toggle":
            user.summary_enabled = not user.summary_enabled
            await session.commit()
            await callback.message.edit_text(
                "Настройки обновлены.",
                reply_markup=settings_keyboard(user.summary_enabled, user.reminder_enabled),
            )
        elif action == "reminder_toggle":
            user.reminder_enabled = not user.reminder_enabled
            await session.commit()
            await callback.message.edit_text(
                "Настройки обновлены.",
                reply_markup=settings_keyboard(user.summary_enabled, user.reminder_enabled),
            )
        else:
            state_map = {
                "weight": (BotStates.SETTINGS_WEIGHT, "Укажи новый вес в кг."),
                "height": (BotStates.SETTINGS_HEIGHT, "Укажи новый рост в см."),
                "calories": (BotStates.SETTINGS_CALORIES, "Укажи новый дневной лимит калорий."),
                "protein": (BotStates.SETTINGS_PROTEIN, "Укажи новую цель по белку в граммах."),
            }
            state_name, prompt = state_map[action]
            await meals_repo.save_state(callback.from_user.id, state_name, {})
            await session.commit()
            await callback.message.answer(prompt)
        await callback.answer()
