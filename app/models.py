from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


class User(Base, TimestampMixin):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    telegram_id: Mapped[int] = mapped_column(Integer, unique=True, nullable=False, index=True)
    username: Mapped[str | None] = mapped_column(String(255))
    first_name: Mapped[str | None] = mapped_column(String(255))
    last_name: Mapped[str | None] = mapped_column(String(255))
    weight_kg: Mapped[float | None] = mapped_column(Float)
    height_cm: Mapped[float | None] = mapped_column(Float)
    daily_calorie_limit: Mapped[int | None] = mapped_column(Integer)
    daily_protein_goal: Mapped[int | None] = mapped_column(Integer)
    timezone: Mapped[str] = mapped_column(String(64), default="Europe/Warsaw", nullable=False)
    language: Mapped[str] = mapped_column(String(8), default="ru", nullable=False)
    summary_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    reminder_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    summary_hour: Mapped[int] = mapped_column(Integer, default=21, nullable=False)
    onboarding_completed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    meal_entries: Mapped[list[MealEntry]] = relationship(back_populates="user")


class MealEntry(Base, TimestampMixin):
    __tablename__ = "meal_entries"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    meal_title: Mapped[str | None] = mapped_column(String(255))
    source_type: Mapped[str | None] = mapped_column(String(32))
    original_text: Mapped[str | None] = mapped_column(Text)
    total_calories: Mapped[float | None] = mapped_column(Float)
    total_protein: Mapped[float | None] = mapped_column(Float)
    total_fat: Mapped[float | None] = mapped_column(Float)
    total_carbs: Mapped[float | None] = mapped_column(Float)
    total_fiber: Mapped[float | None] = mapped_column(Float)
    confidence: Mapped[float | None] = mapped_column(Float)
    status: Mapped[str] = mapped_column(String(32), default="draft", nullable=False, index=True)
    openai_raw_response: Mapped[str | None] = mapped_column(Text)
    notes: Mapped[str | None] = mapped_column(Text)

    user: Mapped[User] = relationship(back_populates="meal_entries")
    items: Mapped[list[MealItem]] = relationship(
        back_populates="meal_entry", cascade="all, delete-orphan"
    )
    photos: Mapped[list[MealPhoto]] = relationship(
        back_populates="meal_entry", cascade="all, delete-orphan"
    )


class MealItem(Base):
    __tablename__ = "meal_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    meal_entry_id: Mapped[int] = mapped_column(ForeignKey("meal_entries.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    quantity: Mapped[float | None] = mapped_column(Float)
    unit: Mapped[str | None] = mapped_column(String(32))
    calories: Mapped[float | None] = mapped_column(Float)
    protein: Mapped[float | None] = mapped_column(Float)
    fat: Mapped[float | None] = mapped_column(Float)
    carbs: Mapped[float | None] = mapped_column(Float)
    fiber: Mapped[float | None] = mapped_column(Float)
    notes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    meal_entry: Mapped[MealEntry] = relationship(back_populates="items")


class MealPhoto(Base):
    __tablename__ = "meal_photos"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    meal_entry_id: Mapped[int | None] = mapped_column(ForeignKey("meal_entries.id"))
    telegram_file_id: Mapped[str | None] = mapped_column(String(255))
    local_path: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    meal_entry: Mapped[MealEntry | None] = relationship(back_populates="photos")


class DailySummary(Base):
    __tablename__ = "daily_summaries"
    __table_args__ = (UniqueConstraint("user_id", "summary_date", name="uq_user_summary_date"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    summary_date: Mapped[date] = mapped_column(Date, nullable=False)
    total_calories: Mapped[float | None] = mapped_column(Float)
    total_protein: Mapped[float | None] = mapped_column(Float)
    total_fat: Mapped[float | None] = mapped_column(Float)
    total_carbs: Mapped[float | None] = mapped_column(Float)
    total_fiber: Mapped[float | None] = mapped_column(Float)
    calorie_limit: Mapped[int | None] = mapped_column(Integer)
    protein_goal: Mapped[int | None] = mapped_column(Integer)
    summary_text: Mapped[str | None] = mapped_column(Text)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class ReminderLog(Base):
    __tablename__ = "reminder_logs"
    __table_args__ = (
        UniqueConstraint("user_id", "reminder_date", "reminder_hour", name="uq_user_reminder_slot"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    reminder_date: Mapped[date] = mapped_column(Date, nullable=False)
    reminder_hour: Mapped[int] = mapped_column(Integer, nullable=False)
    sent_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class OpenAILog(Base):
    __tablename__ = "openai_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    meal_entry_id: Mapped[int | None] = mapped_column(ForeignKey("meal_entries.id"))
    request_payload: Mapped[str | None] = mapped_column(Text)
    response_payload: Mapped[str | None] = mapped_column(Text)
    model: Mapped[str | None] = mapped_column(String(128))
    input_tokens: Mapped[int | None] = mapped_column(Integer)
    output_tokens: Mapped[int | None] = mapped_column(Integer)
    cost: Mapped[float | None] = mapped_column(Float)
    error: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class UserState(Base):
    __tablename__ = "user_states"

    telegram_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    state: Mapped[str | None] = mapped_column(String(128))
    data_json: Mapped[str | None] = mapped_column(Text)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )
