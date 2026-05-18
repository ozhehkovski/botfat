from collections.abc import AsyncIterator

from sqlalchemy import inspect, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import get_settings
from app.models import Base


settings = get_settings()
engine = create_async_engine(settings.database_url, future=True, echo=False)
SessionLocal = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


async def init_db() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        await conn.run_sync(_run_startup_migrations)


async def get_session() -> AsyncIterator[AsyncSession]:
    async with SessionLocal() as session:
        yield session


def _run_startup_migrations(sync_conn) -> None:
    inspector = inspect(sync_conn)
    table_names = set(inspector.get_table_names())
    if "users" in table_names:
        user_columns = {column["name"] for column in inspector.get_columns("users")}
        if "reminder_enabled" not in user_columns:
            sync_conn.execute(
                text("ALTER TABLE users ADD COLUMN reminder_enabled BOOLEAN DEFAULT 1 NOT NULL")
            )
    if "meal_entries" in table_names:
        meal_entry_columns = {column["name"] for column in inspector.get_columns("meal_entries")}
        if "total_fiber" not in meal_entry_columns:
            sync_conn.execute(text("ALTER TABLE meal_entries ADD COLUMN total_fiber FLOAT"))
    if "meal_items" in table_names:
        meal_item_columns = {column["name"] for column in inspector.get_columns("meal_items")}
        if "fiber" not in meal_item_columns:
            sync_conn.execute(text("ALTER TABLE meal_items ADD COLUMN fiber FLOAT"))
    if "daily_summaries" in table_names:
        summary_columns = {column["name"] for column in inspector.get_columns("daily_summaries")}
        if "total_fiber" not in summary_columns:
            sync_conn.execute(text("ALTER TABLE daily_summaries ADD COLUMN total_fiber FLOAT"))
