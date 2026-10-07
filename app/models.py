"""ORM-модели: пользователь, анамнез, срывы, ежедневные чек-ины, подписки на push."""

from __future__ import annotations

import json
from datetime import date, datetime
from typing import Any

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
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base, utcnow


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    display_name: Mapped[str] = mapped_column(String(120), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)

    profile: Mapped["Profile | None"] = relationship(
        back_populates="user", uselist=False, cascade="all, delete-orphan"
    )
    lapses: Mapped[list["LapseEvent"]] = relationship(
        back_populates="user", cascade="all, delete-orphan", order_by="LapseEvent.occurred_at"
    )
    checkins: Mapped[list["CheckIn"]] = relationship(
        back_populates="user", cascade="all, delete-orphan", order_by="CheckIn.day"
    )


class Profile(Base):
    """Анамнез, собранный на онбординге."""

    __tablename__ = "profiles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), unique=True)

    # Старт таймера
    quit_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=utcnow)

    # Стаж и доза
    vape_years: Mapped[float] = mapped_column(Float, default=0.0)
    pods_per_day: Mapped[float] = mapped_column(Float, default=0.0)
    nicotine_strength: Mapped[float] = mapped_column(Float, default=20.0)
    nicotine_type: Mapped[str] = mapped_column(String(16), default="salt")
    pod_volume_ml: Mapped[float] = mapped_column(Float, default=2.0)

    # Базовые параметры
    age: Mapped[int | None] = mapped_column(Integer, nullable=True)
    sex: Mapped[str | None] = mapped_column(String(16), nullable=True)
    height_cm: Mapped[float | None] = mapped_column(Float, nullable=True)
    weight_kg: Mapped[float | None] = mapped_column(Float, nullable=True)
    activity: Mapped[str] = mapped_column(String(16), default="moderate")
    chronic_json: Mapped[str] = mapped_column(Text, default="[]")

    onboarding_completed: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)

    user: Mapped[User] = relationship(back_populates="profile")

    # -- convenience --------------------------------------------------------
    @property
    def chronic_conditions(self) -> list[str]:
        try:
            value = json.loads(self.chronic_json or "[]")
        except (ValueError, TypeError):
            return []
        return [str(v) for v in value] if isinstance(value, list) else []

    @chronic_conditions.setter
    def chronic_conditions(self, values: list[str]) -> None:
        self.chronic_json = json.dumps(sorted(set(values)), ensure_ascii=False)

    @property
    def bmi(self) -> float | None:
        if not self.height_cm or not self.weight_kg or self.height_cm <= 0:
            return None
        meters = self.height_cm / 100.0
        return round(self.weight_kg / (meters * meters), 1)


class LapseEvent(Base):
    """Зафиксированный срыв. Прогресс никогда не обнуляется полностью."""

    __tablename__ = "lapse_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    occurred_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)
    severity: Mapped[str] = mapped_column(String(16), default="episode")
    note: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)

    user: Mapped[User] = relationship(back_populates="lapses")


class CheckIn(Base):
    """Ежедневный чек-ин самочувствия и здоровых привычек."""

    __tablename__ = "checkins"
    __table_args__ = (UniqueConstraint("user_id", "day", name="uq_checkin_user_day"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    day: Mapped[date] = mapped_column(Date, nullable=False)

    mood: Mapped[int] = mapped_column(Integer, default=5)          # 1..10
    craving: Mapped[int] = mapped_column(Integer, default=5)       # 1..10
    sleep_hours: Mapped[float] = mapped_column(Float, default=0.0)
    sleep_quality: Mapped[int] = mapped_column(Integer, default=3)  # 1..5
    water_glasses: Mapped[int] = mapped_column(Integer, default=0)
    activity_minutes: Mapped[int] = mapped_column(Integer, default=0)
    breathing_sessions: Mapped[int] = mapped_column(Integer, default=0)
    note: Mapped[str] = mapped_column(Text, default="")

    points: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)

    user: Mapped[User] = relationship(back_populates="checkins")


class PushSubscription(Base):
    """Подписка Web Push (отправка требует настроенных VAPID-ключей)."""

    __tablename__ = "push_subscriptions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    endpoint: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    payload_json: Mapped[str] = mapped_column(Text, default="{}")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)

    @property
    def payload(self) -> dict[str, Any]:
        try:
            return json.loads(self.payload_json or "{}")
        except (ValueError, TypeError):
            return {}
