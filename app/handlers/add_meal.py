from __future__ import annotations

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message

from app.config import get_settings
from app.database import SessionLocal
from app.keyboards import add_meal_keyboard, delete_confirmation_keyboard, meal_confirmation_keyboard
from app.repositories.meals import MealsRepository
from app.repositories.users import UsersRepository
from app.services.image_storage import ImageStorageService
from app.services.meal_analyzer import MealAnalyzerService, RateLimitExceededError
from app.services.openai_service import InvalidOpenAIResponseError, OpenAIService
from app.states import BotStates
from app.utils.validators import parse_calories, parse_height, parse_protein, parse_weight


router = Router()


def _new_draft() -> dict:
    return {"texts": [], "photos": [], "analysis": None, "clarification": None}


def _source_type_from_draft(draft: dict) -> str:
    has_text = bool(draft.get("texts"))
    has_photo = bool(draft.get("photos"))
    if has_text and has_photo:
        return "mixed"
    if has_photo:
        return "photo"
    return "text"


def _render_analysis(analysis: dict) -> str:
    lines = ["Я распознал:\n", analysis.get("meal_title") or "Без названия", "\n", "Состав:"]
    for item in analysis.get("items", []):
        quantity = item.get("quantity")
        quantity_text = f"{quantity:g}" if isinstance(quantity, (int, float)) else "?"
        lines.extend(
            [
                f"• {item['name']} — {quantity_text} {item.get('unit') or ''}".rstrip(),
                f"{item.get('calories', 0):.0f} ккал / Б: {item.get('protein', 0):.0f} г / "
                f"Ж: {item.get('fat', 0):.0f} г / У: {item.get('carbs', 0):.0f} г",
                "",
            ]
        )
    lines.extend(
        [
            "Итого:",
            f"{analysis['total']['calories']:.0f} ккал",
            f"Б: {analysis['total']['protein']:.0f} г / "
            f"Ж: {analysis['total']['fat']:.0f} г / У: {analysis['total']['carbs']:.0f} г",
            "",
            f"Точность: примерно {round((analysis.get('confidence') or 0) * 100)}%",
            "",
            "Комментарий:",
            analysis.get("notes") or "Оценка примерная.",
            "",
            "Сохранить?",
        ]
    )
    return "\n".join(lines)


async def _ensure_onboarded(message: Message) -> bool:
    async with SessionLocal() as session:
        users_repo = UsersRepository(session)
        user = await users_repo.get_by_telegram_id(message.from_user.id)
        if user and user.onboarding_completed:
            return True
    await message.answer("Сначала нужно настроить профиль. Укажи свой вес в кг.")
    return False


@router.message(Command("add"))
async def cmd_add(message: Message) -> None:
    if not await _ensure_onboarded(message):
        return
    async with SessionLocal() as session:
        meals_repo = MealsRepository(session)
        await meals_repo.save_state(
            message.from_user.id,
            BotStates.MEAL_COLLECTING,
            {"draft": _new_draft()},
        )
        await session.commit()
        await message.answer(
            "Отправь описание еды, одно или несколько фото. Можно добавить подпись к фото. "
            "Когда закончишь — нажми ‘Готово’ или отправь /done.",
            reply_markup=add_meal_keyboard(),
        )


@router.message(Command("done"))
async def cmd_done(message: Message) -> None:
    if not await _ensure_onboarded(message):
        return
    await _finish_meal_collection(message)


@router.message(Command("cancel"))
async def cmd_cancel(message: Message) -> None:
    async with SessionLocal() as session:
        meals_repo = MealsRepository(session)
        await meals_repo.clear_state(message.from_user.id)
        await session.commit()
    await message.answer("Текущее действие отменено.")


@router.message(Command("delete_last"))
async def cmd_delete_last(message: Message) -> None:
    if not await _ensure_onboarded(message):
        return
    async with SessionLocal() as session:
        users_repo = UsersRepository(session)
        meals_repo = MealsRepository(session)
        user = await users_repo.get_by_telegram_id(message.from_user.id)
        meal = await meals_repo.get_last_confirmed_meal(user.id)
        if meal is None:
            await message.answer("Нет сохраненных записей для удаления.")
            return

        await meals_repo.save_state(
            message.from_user.id,
            BotStates.DELETE_CONFIRM,
            {"meal_id": meal.id},
        )
        await session.commit()
        await message.answer(
            f"Удалить последнюю запись?\n\n{meal.meal_title or 'Прием пищи'}\n"
            f"{meal.total_calories or 0:.0f} ккал / Б: {meal.total_protein or 0:.0f} г / "
            f"Ж: {meal.total_fat or 0:.0f} г / У: {meal.total_carbs or 0:.0f} г",
            reply_markup=delete_confirmation_keyboard(),
        )


@router.callback_query(F.data == "meal:done")
async def callback_done(callback: CallbackQuery) -> None:
    await _finish_meal_collection(callback.message, callback.from_user.id)
    await callback.answer()


@router.callback_query(F.data == "meal:cancel")
async def callback_cancel(callback: CallbackQuery) -> None:
    async with SessionLocal() as session:
        meals_repo = MealsRepository(session)
        await meals_repo.clear_state(callback.from_user.id)
        await session.commit()
    await callback.message.answer("Текущее действие отменено.")
    await callback.answer()


@router.callback_query(F.data == "meal:confirm")
async def callback_confirm(callback: CallbackQuery) -> None:
    async with SessionLocal() as session:
        users_repo = UsersRepository(session)
        meals_repo = MealsRepository(session)
        user = await users_repo.get_by_telegram_id(callback.from_user.id)
        state, data = await meals_repo.get_state(callback.from_user.id)
        if state not in {BotStates.MEAL_COLLECTING, BotStates.MEAL_CLARIFICATION, BotStates.MEAL_REVISION}:
            await callback.answer()
            return
        analysis = data.get("analysis")
        draft = data.get("draft", _new_draft())
        if not analysis:
            await callback.answer("Нет данных для сохранения.", show_alert=True)
            return

        meal = await meals_repo.create_confirmed_meal(
            user_id=user.id,
            source_type=_source_type_from_draft(draft),
            original_text="\n".join(draft.get("texts", [])) or None,
            analysis=analysis,
            photos=draft.get("photos", []),
        )
        await meals_repo.clear_state(callback.from_user.id)
        await session.commit()
        await callback.message.answer(
            f"Сохранено.\n\n{meal.meal_title or 'Прием пищи'}\n"
            f"{meal.total_calories or 0:.0f} ккал / Б: {meal.total_protein or 0:.0f} г / "
            f"Ж: {meal.total_fat or 0:.0f} г / У: {meal.total_carbs or 0:.0f} г"
        )
        await callback.answer()


@router.callback_query(F.data == "meal:revise")
async def callback_revise(callback: CallbackQuery) -> None:
    async with SessionLocal() as session:
        meals_repo = MealsRepository(session)
        state, data = await meals_repo.get_state(callback.from_user.id)
        if not data.get("analysis"):
            await callback.answer("Нет данных для редактирования.", show_alert=True)
            return
        await meals_repo.save_state(callback.from_user.id, BotStates.MEAL_REVISION, data)
        await session.commit()
    await callback.message.answer(
        "Напиши, что нужно изменить. Например: ‘курицы было 150 г, риса 200 г’ "
        "или ‘калорий 650, белков 40, жиров 20, углеводов 70’."
    )
    await callback.answer()


@router.callback_query(F.data == "delete:confirm")
async def callback_delete_confirm(callback: CallbackQuery) -> None:
    async with SessionLocal() as session:
        users_repo = UsersRepository(session)
        meals_repo = MealsRepository(session)
        user = await users_repo.get_by_telegram_id(callback.from_user.id)
        state, data = await meals_repo.get_state(callback.from_user.id)
        if state != BotStates.DELETE_CONFIRM:
            await callback.answer()
            return
        meal = await meals_repo.get_last_confirmed_meal(user.id)
        if meal and meal.id == data.get("meal_id"):
            await meals_repo.soft_delete_meal(meal)
        await meals_repo.clear_state(callback.from_user.id)
        await session.commit()
    await callback.message.answer("Последняя запись помечена как удаленная.")
    await callback.answer()


@router.callback_query(F.data == "delete:cancel")
async def callback_delete_cancel(callback: CallbackQuery) -> None:
    async with SessionLocal() as session:
        meals_repo = MealsRepository(session)
        await meals_repo.clear_state(callback.from_user.id)
        await session.commit()
    await callback.message.answer("Удаление отменено.")
    await callback.answer()


@router.message(F.photo)
async def handle_user_photo(message: Message) -> None:
    await _handle_user_input(message)


@router.message(F.text & ~F.text.startswith("/"))
async def handle_user_text(message: Message) -> None:
    await _handle_user_input(message)


async def _handle_user_input(message: Message) -> None:
    async with SessionLocal() as session:
        users_repo = UsersRepository(session)
        meals_repo = MealsRepository(session)
        user = await users_repo.create_or_update_telegram_user(
            telegram_id=message.from_user.id,
            username=message.from_user.username,
            first_name=message.from_user.first_name,
            last_name=message.from_user.last_name,
        )
        state, data = await meals_repo.get_state(message.from_user.id)

        if state and state.startswith("onboarding_"):
            await _handle_onboarding_step(message, session, users_repo, meals_repo, user, state)
            return

        if state and state.startswith("settings_"):
            await _handle_settings_step(message, session, users_repo, meals_repo, user, state)
            return

        if not user.onboarding_completed:
            await meals_repo.save_state(message.from_user.id, BotStates.ONBOARDING_WEIGHT, {})
            await session.commit()
            await message.answer("Сначала нужно настроить профиль. Укажи свой вес в кг.")
            return

        if state == BotStates.MEAL_CLARIFICATION:
            await _handle_clarification(message, session, user, data)
            return

        if state == BotStates.MEAL_REVISION:
            await _handle_revision(message, session, user, data)
            return

        had_existing_draft = state == BotStates.MEAL_COLLECTING and bool(data.get("draft"))
        if state != BotStates.MEAL_COLLECTING:
            data = {"draft": _new_draft()}
            state = BotStates.MEAL_COLLECTING

        draft = data.get("draft", _new_draft())
        if message.text:
            draft["texts"].append(message.text.strip())
        if message.photo:
            settings = get_settings()
            if len(draft["photos"]) >= settings.max_photos_per_meal:
                await message.answer("Можно добавить максимум 5 фото на один прием пищи.")
                return
            largest_photo = message.photo[-1]
            if largest_photo.file_size and largest_photo.file_size > settings.max_photo_size_bytes:
                await message.answer("Фото слишком большое. Отправь изображение меньшего размера.")
                return
            storage = ImageStorageService()
            local_path = await storage.save_telegram_photo(
                bot=message.bot,
                telegram_id=message.from_user.id,
                file_id=largest_photo.file_id,
            )
            draft["photos"].append(
                {"telegram_file_id": largest_photo.file_id, "local_path": local_path}
            )
            if message.caption:
                draft["texts"].append(message.caption.strip())

        await meals_repo.save_state(message.from_user.id, BotStates.MEAL_COLLECTING, {"draft": draft})
        await session.commit()

        if not had_existing_draft:
            await message.answer(
                "Похоже, это прием пищи. Я начал черновик. "
                "Можешь добавить еще текст или фото, а потом нажать Готово.",
                reply_markup=add_meal_keyboard(),
            )


async def _handle_onboarding_step(message, session, users_repo, meals_repo, user, state: str) -> None:
    validators = {
        BotStates.ONBOARDING_WEIGHT: (
            parse_weight,
            "weight_kg",
            BotStates.ONBOARDING_HEIGHT,
            "Укажи свой рост в см.",
            "Вес должен быть числом от 20 до 300 кг. Попробуй еще раз.",
        ),
        BotStates.ONBOARDING_HEIGHT: (
            parse_height,
            "height_cm",
            BotStates.ONBOARDING_CALORIES,
            "Укажи дневной лимит калорий.",
            "Рост должен быть числом от 80 до 250 см. Попробуй еще раз.",
        ),
        BotStates.ONBOARDING_CALORIES: (
            parse_calories,
            "daily_calorie_limit",
            BotStates.ONBOARDING_PROTEIN,
            "Сколько белка в день ты хочешь получать? Укажи в граммах.",
            "Лимит калорий должен быть числом от 500 до 10000. Попробуй еще раз.",
        ),
        BotStates.ONBOARDING_PROTEIN: (
            parse_protein,
            "daily_protein_goal",
            None,
            "Готово! Теперь ты можешь добавлять еду через /add, фото или текст.",
            "Цель по белку должна быть числом от 10 до 400 г. Попробуй еще раз.",
        ),
    }
    parser, field_name, next_state, success_message, error_message = validators[state]
    try:
        parsed = parser(message.text or "")
    except (TypeError, ValueError):
        await message.answer(error_message)
        return

    setattr(user, field_name, parsed)
    if next_state is None:
        user.onboarding_completed = True
        await meals_repo.clear_state(message.from_user.id)
    else:
        await meals_repo.save_state(message.from_user.id, next_state, {})
    await session.commit()
    await message.answer(success_message)


async def _handle_settings_step(message, session, users_repo, meals_repo, user, state: str) -> None:
    mapping = {
        BotStates.SETTINGS_WEIGHT: (parse_weight, "weight_kg", "Вес обновлен."),
        BotStates.SETTINGS_HEIGHT: (parse_height, "height_cm", "Рост обновлен."),
        BotStates.SETTINGS_CALORIES: (parse_calories, "daily_calorie_limit", "Лимит калорий обновлен."),
        BotStates.SETTINGS_PROTEIN: (parse_protein, "daily_protein_goal", "Цель по белку обновлена."),
    }
    parser, field_name, success_message = mapping[state]
    try:
        parsed = parser(message.text or "")
    except (TypeError, ValueError):
        prompts = {
            BotStates.SETTINGS_WEIGHT: "Нужно число от 20 до 300 кг. Попробуй еще раз.",
            BotStates.SETTINGS_HEIGHT: "Нужно число от 80 до 250 см. Попробуй еще раз.",
            BotStates.SETTINGS_CALORIES: "Нужно число от 500 до 10000. Попробуй еще раз.",
            BotStates.SETTINGS_PROTEIN: "Нужно число от 10 до 400 г. Попробуй еще раз.",
        }
        await message.answer(prompts[state])
        return

    await users_repo.update_profile(user, **{field_name: parsed})
    await meals_repo.clear_state(message.from_user.id)
    await session.commit()
    await message.answer(success_message)


async def _finish_meal_collection(message: Message, telegram_id: int | None = None) -> None:
    actor_telegram_id = telegram_id or message.from_user.id
    async with SessionLocal() as session:
        users_repo = UsersRepository(session)
        meals_repo = MealsRepository(session)
        user = await users_repo.get_by_telegram_id(actor_telegram_id)
        state, data = await meals_repo.get_state(actor_telegram_id)
        draft = data.get("draft", {})
        if state != BotStates.MEAL_COLLECTING or (not draft.get("texts") and not draft.get("photos")):
            await message.answer("Сначала отправь описание еды или фото.")
            return

        analyzer = MealAnalyzerService(meals_repo, OpenAIService())
        try:
            result = await analyzer.analyze_meal(
                user_id=user.id,
                text="\n".join(draft.get("texts", [])) or None,
                image_paths=[photo["local_path"] for photo in draft.get("photos", [])],
                profile_context={
                    "weight_kg": user.weight_kg,
                    "height_cm": user.height_cm,
                    "daily_calorie_limit": user.daily_calorie_limit,
                    "daily_protein_goal": user.daily_protein_goal,
                    "timezone": user.timezone,
                },
            )
        except RateLimitExceededError:
            await message.answer("Лимит анализов на час исчерпан. Попробуй чуть позже.")
            return
        except InvalidOpenAIResponseError:
            await session.commit()
            await message.answer("Не удалось разобрать результат анализа. Попробуй отправить описание текстом.")
            return
        except Exception:
            await message.answer("Не удалось обработать еду. Попробуй еще раз чуть позже.")
            await session.commit()
            return

        if result.get("needs_clarification"):
            await meals_repo.save_state(
                message.from_user.id,
                BotStates.MEAL_CLARIFICATION,
                {"draft": draft, "analysis": result},
            )
            await session.commit()
            await message.answer(result.get("clarification_question") or "Нужно уточнение по порции.")
            return

        await meals_repo.save_state(
            actor_telegram_id,
            BotStates.MEAL_COLLECTING,
            {"draft": draft, "analysis": result},
        )
        await session.commit()
        await message.answer(_render_analysis(result), reply_markup=meal_confirmation_keyboard())


async def _handle_clarification(message: Message, session, user, data: dict) -> None:
    if not message.text:
        await message.answer("Напиши ответ текстом, чтобы я смог уточнить расчет.")
        return
    draft = data.get("draft", _new_draft())
    analyzer = MealAnalyzerService(MealsRepository(session), OpenAIService())
    try:
        result = await analyzer.analyze_meal(
            user_id=user.id,
            text="\n".join(draft.get("texts", [])) or None,
            image_paths=[photo["local_path"] for photo in draft.get("photos", [])],
            profile_context={
                "weight_kg": user.weight_kg,
                "height_cm": user.height_cm,
                "daily_calorie_limit": user.daily_calorie_limit,
                "daily_protein_goal": user.daily_protein_goal,
                "timezone": user.timezone,
            },
            clarification=message.text,
        )
    except RateLimitExceededError:
        await message.answer("Лимит анализов на час исчерпан. Попробуй чуть позже.")
        return
    except InvalidOpenAIResponseError:
        await session.commit()
        await message.answer("Не удалось разобрать результат анализа. Попробуй отправить описание текстом.")
        return
    except Exception:
        await message.answer("Не удалось обработать еду. Попробуй еще раз чуть позже.")
        await session.commit()
        return

    if result.get("needs_clarification"):
        await message.answer(result.get("clarification_question") or "Нужно еще одно уточнение.")
        await MealsRepository(session).save_state(
            message.from_user.id,
            BotStates.MEAL_CLARIFICATION,
            {"draft": draft, "analysis": result},
        )
        await session.commit()
        return

    await MealsRepository(session).save_state(
        message.from_user.id,
        BotStates.MEAL_COLLECTING,
        {"draft": draft, "analysis": result},
    )
    await session.commit()
    await message.answer(_render_analysis(result), reply_markup=meal_confirmation_keyboard())


async def _handle_revision(message: Message, session, user, data: dict) -> None:
    if not message.text:
        await message.answer("Напиши правку текстом, чтобы я обновил расчет.")
        return
    analysis = data.get("analysis")
    draft = data.get("draft", _new_draft())
    if not analysis:
        await message.answer("Нет результата для редактирования.")
        return
    analyzer = MealAnalyzerService(MealsRepository(session), OpenAIService())
    try:
        result = await analyzer.revise_meal(user.id, analysis, message.text or "")
    except RateLimitExceededError:
        await message.answer("Лимит анализов на час исчерпан. Попробуй чуть позже.")
        return
    except InvalidOpenAIResponseError:
        await session.commit()
        await message.answer("Не удалось разобрать результат анализа. Попробуй отправить описание текстом.")
        return
    except Exception:
        await message.answer("Не удалось разобрать результат анализа. Попробуй отправить описание текстом.")
        await session.commit()
        return

    await MealsRepository(session).save_state(
        message.from_user.id,
        BotStates.MEAL_COLLECTING,
        {"draft": draft, "analysis": result},
    )
    await session.commit()
    await message.answer(_render_analysis(result), reply_markup=meal_confirmation_keyboard())
