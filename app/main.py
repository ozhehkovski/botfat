import asyncio
import logging

from app.bot import create_bot, create_dispatcher, setup_bot_commands
from app.database import init_db
from app.services.scheduler import SummaryScheduler


async def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    )
    await init_db()
    bot = create_bot()
    await setup_bot_commands(bot)
    dp = create_dispatcher()
    scheduler = SummaryScheduler(bot)
    scheduler.start()
    try:
        await dp.start_polling(bot)
    finally:
        await scheduler.shutdown()
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
