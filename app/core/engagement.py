"""Достижения и мотивационные уведомления.

Правила подобраны так, чтобы подкреплять прогресс и никогда не наказывать
за срыв: все достижения привязаны к накопленному «эквивалентному чистому
времени», а не к текущей непрерывной серии.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta

from .recovery import OverallStatus, humanize_hours

DAY = 24.0


@dataclass(frozen=True)
class Achievement:
    key: str
    title: str
    detail: str
    emoji: str
    progress: float  # 0..1
    unlocked: bool


@dataclass(frozen=True)
class HabitTotals:
    checkin_days: int = 0
    water_glasses: int = 0
    activity_minutes: int = 0
    breathing_sessions: int = 0
    longest_checkin_streak: int = 0


def habit_totals(days: list[date], checkins) -> HabitTotals:
    """Агрегировать чек-ины. ``checkins`` — итерируемое объектов CheckIn."""
    rows = list(checkins)
    if not rows:
        return HabitTotals()

    ordered = sorted({c.day for c in rows})
    best = 0
    run = 0
    prev: date | None = None
    for d in ordered:
        run = run + 1 if prev is not None and (d - prev).days == 1 else 1
        best = max(best, run)
        prev = d

    return HabitTotals(
        checkin_days=len(ordered),
        water_glasses=sum(int(c.water_glasses or 0) for c in rows),
        activity_minutes=sum(int(c.activity_minutes or 0) for c in rows),
        breathing_sessions=sum(int(c.breathing_sessions or 0) for c in rows),
        longest_checkin_streak=best,
    )


def _time_achievement(key: str, emoji: str, title: str, detail: str, hours_needed: float, have: float) -> Achievement:
    return Achievement(
        key=key,
        title=title,
        detail=detail,
        emoji=emoji,
        progress=min(1.0, have / hours_needed) if hours_needed else 1.0,
        unlocked=have >= hours_needed,
    )


def _count_achievement(key: str, emoji: str, title: str, detail: str, needed: float, have: float) -> Achievement:
    return Achievement(
        key=key,
        title=title,
        detail=detail,
        emoji=emoji,
        progress=min(1.0, have / needed) if needed else 1.0,
        unlocked=have >= needed,
    )


TIME_BADGES: tuple[tuple[str, str, str, str, float], ...] = (
    ("h24", "⏱️", "Первые сутки", "Никотин выведен из организма, пик отмены впереди, но он конечен.", 24),
    ("h72", "🌤️", "72 часа", "Котинин выведен полностью. Дальше становится легче, а не тяжелее.", 72),
    ("d7", "🟠", "Первая неделя", "Начало регенерации: реснички эпителия и эндотелий включаются в работу.", 7 * DAY),
    ("d14", "🌿", "Две недели", "Кровообращение улучшается, тяга становится реже и короче.", 14 * DAY),
    ("d30", "🟡", "Месяц", "Никотиновые рецепторы вернулись к уровню некурящего человека.", 30 * DAY),
    ("d90", "💪", "Три месяца", "Реснички лёгких восстановлены, оральный ритуал почти угас.", 90 * DAY),
    ("d180", "🟢", "Полгода", "Значительное улучшение: органы работают как у некурящего.", 180 * DAY),
    ("d365", "🏆", "Год", "Риск ишемической болезни сердца вдвое ниже, чем у продолжающего вейпить.", 365 * DAY),
)


def achievements_for(report: OverallStatus, totals: HabitTotals) -> list[Achievement]:
    have = report.progress.effective_hours
    items = [
        _time_achievement(key, emoji, title, detail, need, have)
        for key, emoji, title, detail, need in TIME_BADGES
    ]
    items += [
        _count_achievement("water10", "💧", "10 стаканов воды", "Гидратация помогает выводить метаболиты никотина.", 10, totals.water_glasses),
        _count_achievement("water100", "🌊", "100 стаканов воды", "Устойчивая привычка пить воду вместо перерыва на вейп.", 100, totals.water_glasses),
        _count_achievement("breath10", "🌬️", "10 дыхательных практик", "4-7-8 — ваш рабочий инструмент против острой тяги.", 10, totals.breathing_sessions),
        _count_achievement("move300", "🏃", "300 минут активности", "Кардио тренирует лёгкие и сосуды.", 300, totals.activity_minutes),
        _count_achievement("checkin7", "📅", "7 чек-инов подряд", "Наблюдение за состоянием — половина успеха.", 7, totals.longest_checkin_streak),
    ]
    return items


# ---------------------------------------------------------------------------
# Уведомления
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class Notification:
    kind: str  # motivational | warning | info
    title: str
    body: str
    action: str = ""
    action_href: str = ""


def build_notifications(
    report: OverallStatus,
    *,
    today_checkin=None,
    today: date | None = None,
) -> list[Notification]:
    """Сформировать ленту уведомлений по текущему состоянию.

    Мотивационные — по достигнутым рубежам, предупреждающие — по триггерам
    самочувствия из чек-ина.
    """
    today = today or date.today()
    notes: list[Notification] = []
    progress = report.progress

    # 1. Рубежи, пройденные за последние сутки.
    for organ in report.organs:
        if organ.reached is None:
            continue
        gap_hours = progress.effective_hours - organ.reached.hours / max(report.speed_factor, 1e-6)
        if 0 <= gap_hours <= 24:
            notes.append(
                Notification(
                    kind="motivational",
                    title=f"{organ.emoji} {organ.reached.title}",
                    body=(
                        f"{organ.name}: {organ.reached.detail} "
                        f"Восстановление по этому модулю — {organ.percent_int}%."
                    ),
                    action="Открыть модуль",
                    action_href=f"/organ/{organ.key}",
                )
            )

    # 2. Сильнейший модуль — позитивное подкрепление.
    strongest = report.strongest
    notes.append(
        Notification(
            kind="motivational",
            title=f"{strongest.emoji} {strongest.short}: {strongest.percent_int}% восстановления",
            body=(
                f"Сейчас быстрее всего восстанавливается модуль «{strongest.name}». "
                f"За следующую неделю прогноз +{strongest.trend_7d:.1f} п.п."
            ),
            action="Посмотреть",
            action_href=f"/organ/{strongest.key}",
        )
    )

    # 3. Триггеры из чек-ина.
    if today_checkin is not None:
        if today_checkin.craving >= 7:
            notes.append(
                Notification(
                    kind="warning",
                    title="Высокий уровень тяги",
                    body=(
                        "Тяга — это волна на 3–5 минут, а не приказ. Сделайте 4 цикла дыхания 4-7-8 "
                        "или выпейте стакан холодной воды: пик пройдёт без затяжки."
                    ),
                    action="Дыхание 4-7-8",
                    action_href="/breathing",
                )
            )
        if today_checkin.mood <= 3:
            notes.append(
                Notification(
                    kind="warning",
                    title="Настроение ниже обычного",
                    body=(
                        "Снижение настроения в первые недели — следствие перестройки дофаминовой системы, "
                        "а не вашей слабости. Прогресс никуда не делся: "
                        f"{report.percent_int}% уже пройдено."
                    ),
                    action="Что происходит с мозгом",
                    action_href="/organ/brain",
                )
            )
        if 0 < today_checkin.sleep_hours < 6:
            notes.append(
                Notification(
                    kind="warning",
                    title="Короткий сон",
                    body=(
                        "Никотин ломает быстрые фазы сна, и на восстановление нужно время. "
                        "Попробуйте лечь на 30 минут раньше и убрать вечерние триггеры."
                    ),
                    action="Модуль сна",
                    action_href="/organ/sleep",
                )
            )
        if today_checkin.water_glasses < 6:
            notes.append(
                Notification(
                    kind="info",
                    title="Меньше 6 стаканов воды",
                    body="Вода помогает слизистой и ускоряет выведение метаболитов никотина.",
                    action="Отметить чек-ин",
                    action_href="/checkin",
                )
            )
        if today_checkin.breathing_sessions == 0 and today_checkin.craving >= 5:
            notes.append(
                Notification(
                    kind="info",
                    title="Ещё не было дыхательной практики",
                    body="Одна сессия 4-7-8 занимает около 2 минут и заметно снижает тягу.",
                    action="Начать",
                    action_href="/breathing",
                )
            )
        if today_checkin.day != today:
            notes.append(
                Notification(
                    kind="info",
                    title="Отметьте сегодняшнее состояние",
                    body="Ежедневный чек-ин занимает 20 секунд и показывает динамику тяги и сна.",
                    action="Заполнить",
                    action_href="/checkin",
                )
            )
    else:
        notes.append(
            Notification(
                kind="info",
                title="Отметьте сегодняшнее состояние",
                body="Ежедневный чек-ин занимает 20 секунд и показывает динамику тяги и сна.",
                action="Заполнить",
                action_href="/checkin",
            )
        )

    # 4. Сколько осталось до ближайшего рубежа.
    nearest = min(
        (o for o in report.organs if o.hours_to_next is not None),
        key=lambda o: o.hours_to_next or float("inf"),
        default=None,
    )
    if nearest is not None and nearest.upcoming is not None and nearest.hours_to_next is not None:
        notes.append(
            Notification(
                kind="info",
                title=f"Следующий рубеж: {nearest.upcoming.title}",
                body=(
                    f"{nearest.emoji} {nearest.name} — через {humanize_hours(nearest.hours_to_next)} "
                    f"({nearest.upcoming.percent}% восстановления)."
                ),
                action="Открыть модуль",
                action_href=f"/organ/{nearest.key}",
            )
        )

    return notes
