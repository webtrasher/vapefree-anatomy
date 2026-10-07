"""Настройка Jinja2: общие переменные, фильтры, форматирование."""

from __future__ import annotations

from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path

from fastapi.templating import Jinja2Templates
from markupsafe import Markup

from .config import (
    ACTIVITY_LEVELS,
    APP_DIR,
    APP_NAME,
    APP_TAGLINE,
    BREATHING_PATTERN,
    CHRONIC_CONDITIONS,
    HABIT_REPLACEMENTS,
    LAPSE_SEVERITIES,
    MEDICAL_DISCLAIMER,
    NICOTINE_TYPES,
    SEX_OPTIONS,
)
from .core.recovery import PHASES, humanize_hours
from .core.sources import SOURCES, citation

templates = Jinja2Templates(directory=str(APP_DIR / "templates"))


def iso_utc(value: datetime | None) -> str:
    """Наивное UTC-время -> строка ISO 8601 с Z (для JS)."""
    if value is None:
        return ""
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def plural_ru(number: float, one: str, few: str, many: str) -> str:
    """Русское склонение: 1 день / 2 дня / 5 дней."""
    n = abs(int(number)) % 100
    if 11 <= n <= 14:
        return many
    n %= 10
    if n == 1:
        return one
    if 2 <= n <= 4:
        return few
    return many


def format_duration(hours: float) -> str:
    """Длительность в человекочитаемом виде."""
    hours = max(0.0, float(hours))
    if hours < 1:
        return f"{int(round(hours * 60))} {plural_ru(hours * 60, 'минута', 'минуты', 'минут')}"
    if hours < 48:
        return f"{int(hours)} {plural_ru(hours, 'час', 'часа', 'часов')}"
    days = hours / 24
    if days < 60:
        return f"{int(days)} {plural_ru(days, 'день', 'дня', 'дней')}"
    months = days / 30.44
    rounded = int(round(months))
    if rounded < 24:
        return f"{rounded} {plural_ru(rounded, 'месяц', 'месяца', 'месяцев')}"
    years = days / 365.25
    return f"{years:.1f} {plural_ru(years, 'год', 'года', 'лет')}"


def split_timer(hours: float) -> dict[str, int]:
    """Разложить часы в дни/часы/минуты/секунды для таймера."""
    total_seconds = int(max(0.0, hours) * 3600)
    days, rem = divmod(total_seconds, 86400)
    hrs, rem = divmod(rem, 3600)
    minutes, seconds = divmod(rem, 60)
    return {"days": days, "hours": hrs, "minutes": minutes, "seconds": seconds}


templates.env.filters["iso_utc"] = iso_utc
templates.env.filters["plural_ru"] = plural_ru
templates.env.filters["duration"] = format_duration


@lru_cache(maxsize=1)
def _body_svg_markup() -> Markup:
    """Инлайн SVG-схемы тела (единый источник — app/static/img/body-map.svg)."""
    path: Path = APP_DIR / "static" / "img" / "body-map.svg"
    if not path.exists():
        return Markup(
            '<p class="muted">Схема тела не сгенерирована. '
            "Выполните <code>python tools/build_body_svg.py</code>.</p>"
        )
    return Markup(path.read_text(encoding="utf-8"))


def body_svg() -> Markup:
    return _body_svg_markup()


templates.env.globals.update(
    APP_NAME=APP_NAME,
    APP_TAGLINE=APP_TAGLINE,
    MEDICAL_DISCLAIMER=MEDICAL_DISCLAIMER,
    PHASES=PHASES,
    ACTIVITY_LEVELS=ACTIVITY_LEVELS,
    SEX_OPTIONS=SEX_OPTIONS,
    NICOTINE_TYPES=NICOTINE_TYPES,
    CHRONIC_CONDITIONS=CHRONIC_CONDITIONS,
    LAPSE_SEVERITIES=LAPSE_SEVERITIES,
    BREATHING_PATTERN=BREATHING_PATTERN,
    HABIT_REPLACEMENTS=HABIT_REPLACEMENTS,
    humanize_hours=humanize_hours,
    format_duration=format_duration,
    split_timer=split_timer,
    body_svg=body_svg,
    citation=citation,
    SOURCES=SOURCES,
)
