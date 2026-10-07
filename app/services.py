"""Связующий слой: ORM-модели -> калькулятор восстановления и обратно."""

from __future__ import annotations

from datetime import date, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from .core.engagement import HabitTotals, achievements_for, build_notifications, habit_totals
from .core.recovery import (
    HealthRecoveryCalculator,
    Lapse,
    OverallStatus,
    PersonalFactors,
)
from .db import utcnow
from .models import CheckIn, LapseEvent, Profile, User


def factors_from_profile(profile: Profile | None) -> PersonalFactors:
    """Собрать персональные факторы из анамнеза."""
    if profile is None:
        return PersonalFactors()
    return PersonalFactors(
        age=profile.age,
        sex=profile.sex,
        bmi=profile.bmi,
        chronic_conditions=tuple(profile.chronic_conditions),
        vape_years=float(profile.vape_years or 0.0),
        pods_per_day=float(profile.pods_per_day or 0.0),
        nicotine_strength=float(profile.nicotine_strength or 0.0),
        activity=profile.activity or "moderate",
        pod_volume_ml=float(profile.pod_volume_ml or 2.0),
    )


def lapses_from_db(events: list[LapseEvent]) -> list[Lapse]:
    return [Lapse(at=e.occurred_at, severity=e.severity, note=e.note or "") for e in events]


def build_report(user: User, now: datetime | None = None) -> OverallStatus:
    """Полный отчёт по состоянию пользователя."""
    now = now or utcnow()
    profile = user.profile
    started_at = profile.quit_at if profile is not None else now
    calc = HealthRecoveryCalculator(factors_from_profile(profile))
    return calc.full_report(started_at, now, lapses_from_db(list(user.lapses)))


def calculator_for(user: User) -> HealthRecoveryCalculator:
    return HealthRecoveryCalculator(factors_from_profile(user.profile))


def latest_checkin(session: Session, user_id: int, day: date | None = None) -> CheckIn | None:
    stmt = select(CheckIn).where(CheckIn.user_id == user_id)
    if day is not None:
        stmt = stmt.where(CheckIn.day == day)
    else:
        stmt = stmt.order_by(CheckIn.day.desc()).limit(1)
    return session.execute(stmt).scalar_one_or_none()


def checkin_for_day(session: Session, user_id: int, day: date) -> CheckIn | None:
    return session.execute(
        select(CheckIn).where(CheckIn.user_id == user_id, CheckIn.day == day)
    ).scalar_one_or_none()


def recent_checkins(session: Session, user_id: int, days: int = 30) -> list[CheckIn]:
    since = date.today() - timedelta(days=days)
    return list(
        session.execute(
            select(CheckIn)
            .where(CheckIn.user_id == user_id, CheckIn.day >= since)
            .order_by(CheckIn.day)
        ).scalars()
    )


def all_checkins(session: Session, user_id: int) -> list[CheckIn]:
    return list(
        session.execute(
            select(CheckIn).where(CheckIn.user_id == user_id).order_by(CheckIn.day)
        ).scalars()
    )


def compute_points(
    *,
    mood: int,
    craving: int,
    sleep_hours: float,
    sleep_quality: int,
    water_glasses: int,
    activity_minutes: int,
    breathing_sessions: int,
) -> int:
    """Геймификация: баллы за заботу о теле, без наказаний."""
    points = 5
    points += min(max(water_glasses, 0), 12)
    points += min(max(activity_minutes, 0), 60) // 10 * 2
    points += max(breathing_sessions, 0) * 3
    points += max(0, min(sleep_quality, 5))
    if sleep_hours >= 7:
        points += 3
    elif sleep_hours >= 6:
        points += 1
    return int(points)


def totals_for(session: Session, user_id: int) -> HabitTotals:
    return habit_totals([c.day for c in all_checkins(session, user_id)], all_checkins(session, user_id))


def engagement_for(
    session: Session,
    user: User,
    report: OverallStatus,
    today: date | None = None,
) -> tuple[list, list]:
    """Достижения и уведомления для текущего состояния."""
    today = today or date.today()
    rows = all_checkins(session, user.id)
    totals = habit_totals([c.day for c in rows], rows)
    today_row = next((c for c in rows if c.day == today), None)
    return (
        achievements_for(report, totals),
        build_notifications(report, today_checkin=today_row, today=today),
    )


def create_default_profile(session: Session, user: User, quit_at: datetime | None = None) -> Profile:
    profile = Profile(user_id=user.id, quit_at=quit_at or utcnow())
    session.add(profile)
    session.flush()
    return profile
