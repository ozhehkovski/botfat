# Calories Bot

Telegram-бот для учета калорий, БЖУ, клетчатки и дневника питания на `aiogram 3`, `SQLite`, `SQLAlchemy async` и `OpenAI API`.

## Запуск

1. Создай `.env` на основе `.env.example`.
2. Заполни `TELEGRAM_BOT_TOKEN` и `OPENAI_API_KEY`.
3. Запусти:

```bash
docker compose up -d --build
```

## Полезные команды

Запустить логи:

```bash
docker compose logs -f bot
```

Остановить сервис:

```bash
docker compose down
```

## Команды бота

- `/start` — запуск и onboarding
- `/add` — добавить прием пищи
- `/done` — завершить добавление текущего приема пищи
- `/today` — сводка за сегодня
- `/yesterday` — сводка за вчера
- `/profile` — показать профиль
- `/settings` — изменить настройки
- `/cancel` — отменить текущее действие
- `/delete_last` — удалить последнюю запись
- `/help` — помощь

## Хранение данных

- SQLite база: `data/calories_bot.sqlite3`
- Фото: `data/photos/<telegram_id>/<YYYY-MM-DD>/`

## Что умеет MVP

- onboarding пользователя
- добавление еды текстом и фото
- до 5 фото на прием пищи
- анализ через OpenAI API
- уточняющие вопросы, если данных недостаточно
- подтверждение перед сохранением
- правка результата свободным текстом
- сводки за сегодня и вчера
- учет клетчатки в каждом приеме пищи и дневных сводках
- вечернее саммари в 21:00 по timezone пользователя
- напоминания в 08:00, 15:00 и 20:00 по timezone пользователя
- мягкое удаление последней записи

## Архитектура

- `app/handlers` — Telegram-слой
- `app/services` — бизнес-логика и интеграции
- `app/repositories` — работа с БД
- `app/models.py` — SQLAlchemy-модели
- `app/database.py` — engine, session, auto-create таблиц

Структура отделяет Telegram-хендлеры от бизнес-логики, поэтому позже SQLite можно заменить на PostgreSQL с минимальными изменениями в конфиге и инфраструктуре.
