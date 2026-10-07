"""Алгоритм расчёта восстановления.

Модель состоит из четырёх частей:

1. ``RecoveryCurve`` — монотонная интерполяция опорных точек модуля органа
   в логарифмическом времени. Восстановление идёт быстро в первые часы и
   замедляется на длинной дистанции, что соответствует и физиологии, и
   опубликованным таймлайнам ВОЗ/CDC.
2. ``PersonalFactors`` — поправка скорости восстановления на возраст, ИМТ,
   хронические заболевания, стаж и дозу никотина, физическую активность.
3. ``effective_clean_hours`` — свёртка истории срывов: прогресс никогда не
   обнуляется, а лишь частично откатывается (без «наказания»).
4. ``HealthRecoveryCalculator`` — сборка снимка состояния по всем органам.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import datetime, timedelta

from .organs import (
    ANATOMY_KEYS,
    ORGAN_MODULES,
    ORGANS_BY_KEY,
    SYSTEM_KEYS,
    Milestone,
    OrganModule,
)

DAY = 24.0
HOUR = 1.0

#: Масштаб логарифмического времени (в часах).
LOG_SCALE_HOURS = 1.0

#: Скорость асимптотического приближения к 100% после последней опорной точки.
TAIL_K = 0.8

#: Вклад модулей в общий индекс восстановления.
ORGAN_WEIGHTS: dict[str, float] = {
    "lungs": 0.24,
    "heart": 0.20,
    "vessels": 0.18,
    "brain": 0.18,
    "blood": 0.09,
    "mouth": 0.05,
    "sleep": 0.06,
}


# ---------------------------------------------------------------------------
# Фазы
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class Phase:
    key: str
    label: str
    emoji: str
    color: str
    soft_color: str
    min_hours: float
    max_hours: float | None
    description: str


PHASES: tuple[Phase, ...] = (
    Phase(
        key="acute",
        label="Острая фаза отмены",
        emoji="🔴",
        color="#C97F7F",
        soft_color="#F6E4E4",
        min_hours=0.0,
        max_hours=7 * DAY,
        description=(
            "Организм перестраивается без никотина. Возможны тяга, раздражительность "
            "и плохой сон — это нормальная часть процесса, а не признак неудачи."
        ),
    ),
    Phase(
        key="regeneration",
        label="Начало регенерации",
        emoji="🟠",
        color="#D69A63",
        soft_color="#FAEDE0",
        min_hours=7 * DAY,
        max_hours=28 * DAY,
        description=(
            "Пик физической отмены позади. Реснички эпителия и эндотелий начинают "
            "восстанавливаться, тяга становится реже."
        ),
    ),
    Phase(
        key="active",
        label="Активное восстановление функций",
        emoji="🟡",
        color="#C4B062",
        soft_color="#F7F2DC",
        min_hours=28 * DAY,
        max_hours=180 * DAY,
        description=(
            "Функции органов возвращаются: лёгкие очищаются, сосуды становятся "
            "эластичнее, сон и настроение выравниваются."
        ),
    ),
    Phase(
        key="restored",
        label="Значительное улучшение / норма",
        emoji="🟢",
        color="#7FB894",
        soft_color="#E3F1E8",
        min_hours=180 * DAY,
        max_hours=None,
        description=(
            "Показатели близки к уровню человека, который никогда не употреблял никотин. "
            "Дальнейшее снижение рисков продолжается годами."
        ),
    ),
)


def phase_for_hours(hours: float) -> Phase:
    """Определить фазу по числу часов воздержания."""
    hours = max(0.0, hours)
    for phase in PHASES:
        if phase.max_hours is None or hours < phase.max_hours:
            return phase
    return PHASES[-1]


# ---------------------------------------------------------------------------
# Кривая восстановления
# ---------------------------------------------------------------------------
def _u(hours: float) -> float:
    """Логарифмическая ось времени."""
    return math.log1p(max(0.0, hours) / LOG_SCALE_HOURS)


class RecoveryCurve:
    """Монотонная интерполяция опорных точек по логарифмическому времени."""

    __slots__ = ("milestones", "_u", "_p")

    def __init__(self, milestones: tuple[Milestone, ...]) -> None:
        if not milestones:
            raise ValueError("Нужна хотя бы одна опорная точка")
        ordered = tuple(sorted(milestones, key=lambda m: m.hours))
        percents = [m.percent for m in ordered]
        if percents != sorted(percents):
            raise ValueError("Проценты опорных точек должны возрастать")
        self.milestones = ordered
        self._u = [_u(m.hours) for m in ordered]
        self._p = percents

    def percent_at(self, hours: float) -> float:
        """Процент восстановления для заданного числа часов."""
        hours = max(0.0, float(hours))
        u = _u(hours)
        us, ps = self._u, self._p

        if u <= us[0]:
            # От нуля до первой опорной точки — линейно по лог-оси.
            if us[0] <= 0:
                return ps[0]
            return max(0.0, min(ps[0], ps[0] * (u / us[0])))

        for i in range(1, len(us)):
            if u <= us[i]:
                span = us[i] - us[i - 1]
                if span <= 0:
                    return ps[i]
                k = (u - us[i - 1]) / span
                return ps[i - 1] + (ps[i] - ps[i - 1]) * k

        # Хвост: асимптотическое приближение к 100%.
        tail = 100.0 - (100.0 - ps[-1]) * math.exp(-(u - us[-1]) / TAIL_K)
        return min(100.0, tail)

    def hours_for_percent(self, percent: float) -> float:
        """Обратная задача: сколько часов нужно для заданного процента."""
        percent = max(0.0, min(100.0, percent))
        us, ps = self._u, self._p
        if percent <= 0:
            return 0.0
        if percent <= ps[0]:
            if ps[0] <= 0:
                return 0.0
            return math.expm1(us[0] * (percent / ps[0]))
        for i in range(1, len(ps)):
            if percent <= ps[i]:
                span = ps[i] - ps[i - 1]
                if span <= 0:
                    return math.expm1(us[i])
                k = (percent - ps[i - 1]) / span
                return math.expm1(us[i - 1] + (us[i] - us[i - 1]) * k)
        # Хвост
        if ps[-1] >= 100:
            return math.expm1(us[-1])
        ratio = (100.0 - percent) / (100.0 - ps[-1])
        if ratio <= 0:
            return math.expm1(us[-1])
        return math.expm1(us[-1] - TAIL_K * math.log(ratio))


CURVES: dict[str, RecoveryCurve] = {o.key: RecoveryCurve(o.milestones) for o in ORGAN_MODULES}


# ---------------------------------------------------------------------------
# Персональные факторы
# ---------------------------------------------------------------------------
SEVERITY_LABELS = {
    "puff": "одна затяжка",
    "episode": "короткий эпизод",
    "day": "возврат к вейпу на день и больше",
}

SEVERITY_PENALTY = {
    "puff": 0.03,
    "episode": 0.10,
    "day": 0.22,
}

#: Даже при самом тяжёлом срыве сохраняется не меньше этой доли прогресса.
RECOVERY_FLOOR = 0.65


@dataclass
class PersonalFactors:
    """Анамнез, влияющий на скорость восстановления."""

    age: int | None = None
    sex: str | None = None
    bmi: float | None = None
    chronic_conditions: tuple[str, ...] = ()
    vape_years: float = 0.0
    pods_per_day: float = 0.0
    nicotine_strength: float = 20.0  # мг/мл
    activity: str = "moderate"  # low | moderate | high
    pod_volume_ml: float = 2.0

    @property
    def daily_nicotine_mg(self) -> float:
        """Оценка суточной дозы никотина, мг."""
        return max(0.0, self.pods_per_day) * self.pod_volume_ml * max(0.0, self.nicotine_strength)

    @property
    def speed_factor(self) -> float:
        """Множитель скорости восстановления. >1 — быстрее, <1 — медленнее."""
        f = 1.0

        age = self.age
        if age is not None:
            if age < 30:
                f += 0.05
            elif age < 45:
                f += 0.0
            elif age < 60:
                f -= 0.05
            else:
                f -= 0.10

        bmi = self.bmi
        if bmi is not None:
            if bmi < 25:
                f += 0.03
            elif bmi < 30:
                f += 0.0
            else:
                f -= 0.07

        f -= min(0.12, 0.03 * len(self.chronic_conditions))

        f += {"low": -0.04, "moderate": 0.0, "high": 0.05}.get(self.activity, 0.0)

        daily = self.daily_nicotine_mg
        if daily >= 40:
            f -= 0.05
        elif daily >= 20:
            f -= 0.02
        elif daily > 0:
            f += 0.02

        if self.vape_years >= 5:
            f -= 0.04
        elif self.vape_years >= 2:
            f -= 0.02
        elif self.vape_years > 0:
            f += 0.02

        return max(0.65, min(1.15, round(f, 4)))

    @property
    def speed_notes(self) -> list[str]:
        """Человекочитаемое объяснение поправки."""
        notes: list[str] = []
        if self.age is not None:
            if self.age < 30:
                notes.append("возраст до 30 лет ускоряет восстановление")
            elif self.age >= 60:
                notes.append("возраст 60+ замедляет восстановление")
        if self.bmi is not None and self.bmi >= 30:
            notes.append("ИМТ 30+ замедляет восстановление")
        if self.chronic_conditions:
            notes.append(f"хронические заболевания ({len(self.chronic_conditions)}) замедляют восстановление")
        if self.activity == "high":
            notes.append("высокая физическая активность ускоряет восстановление")
        elif self.activity == "low":
            notes.append("низкая физическая активность замедляет восстановление")
        if self.daily_nicotine_mg >= 40:
            notes.append("высокая суточная доза никотина замедляет восстановление")
        if self.vape_years >= 5:
            notes.append("стаж 5+ лет замедляет восстановление")
        return notes


# ---------------------------------------------------------------------------
# История срывов
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class Lapse:
    """Зафиксированный срыв."""

    at: datetime
    severity: str = "episode"
    note: str = ""

    @property
    def penalty(self) -> float:
        return SEVERITY_PENALTY.get(self.severity, SEVERITY_PENALTY["episode"])

    @property
    def label(self) -> str:
        return SEVERITY_LABELS.get(self.severity, self.severity)


@dataclass
class ProgressState:
    """Результат свёртки истории: сколько «чистого» времени заработано."""

    effective_hours: float
    current_streak_hours: float
    longest_streak_hours: float
    total_wall_hours: float
    lapse_count: int
    last_lapse_at: datetime | None
    last_lapse_retained_pct: float | None
    last_lapse_label: str | None


def compute_progress(
    started_at: datetime,
    now: datetime,
    lapses: list[Lapse] | None = None,
) -> ProgressState:
    """Свернуть историю воздержания в набор метрик.

    Срыв не обнуляет прогресс: он умножает накопленное «эквивалентное чистое
    время» на (1 - штраф), но никогда не опускает его ниже ``RECOVERY_FLOOR``
    от достигнутого максимума.
    """
    events = sorted(lapses or [], key=lambda x: x.at)
    events = [e for e in events if e.at >= started_at]

    eff = 0.0
    peak = 0.0
    cursor = started_at
    longest = 0.0
    last_retained: float | None = None
    last_label: str | None = None

    for event in events:
        length = max(0.0, (event.at - cursor).total_seconds() / 3600.0)
        eff += length
        longest = max(longest, length)
        peak = max(peak, eff)

        before = eff
        eff = eff * (1.0 - event.penalty)
        if peak > 0:
            eff = max(eff, RECOVERY_FLOOR * peak)
        last_retained = (eff / before * 100.0) if before > 0 else 100.0
        last_label = event.label
        cursor = event.at

    final_length = max(0.0, (now - cursor).total_seconds() / 3600.0)
    eff += final_length
    longest = max(longest, final_length)

    total_wall = max(0.0, (now - started_at).total_seconds() / 3600.0)

    return ProgressState(
        effective_hours=eff,
        current_streak_hours=final_length,
        longest_streak_hours=longest,
        total_wall_hours=total_wall,
        lapse_count=len(events),
        last_lapse_at=events[-1].at if events else None,
        last_lapse_retained_pct=last_retained,
        last_lapse_label=last_label,
    )


# ---------------------------------------------------------------------------
# Снимок по органам
# ---------------------------------------------------------------------------
@dataclass
class OrganStatus:
    key: str
    name: str
    short: str
    emoji: str
    headline: str
    percent: float
    phase: Phase
    color: str
    reached: Milestone | None
    upcoming: Milestone | None
    hours_to_next: float | None
    next_eta: datetime | None
    trend_7d: float
    what_we_show: tuple[str, ...]
    vape_specific: str
    ritual_note: str
    sources: tuple[str, ...]
    is_anatomy: bool

    @property
    def percent_int(self) -> int:
        return int(round(self.percent))

    @property
    def band(self) -> str:
        """Грубая полоса для CSS-класса."""
        return self.phase.key


@dataclass
class OverallStatus:
    percent: float
    phase: Phase
    organs: list[OrganStatus]
    anatomy: list[OrganStatus]
    systems: list[OrganStatus]
    progress: ProgressState
    speed_factor: float
    speed_notes: list[str] = field(default_factory=list)

    @property
    def percent_int(self) -> int:
        return int(round(self.percent))

    @property
    def weakest(self) -> OrganStatus:
        return min(self.organs, key=lambda o: o.percent)

    @property
    def strongest(self) -> OrganStatus:
        return max(self.organs, key=lambda o: o.percent)


def _format_eta(hours: float) -> str:
    if hours < 1:
        return f"{int(round(hours * 60))} мин"
    if hours < 48:
        return f"{int(round(hours))} ч"
    days = hours / 24
    if days < 60:
        return f"{int(round(days))} дн"
    months = days / 30.44
    if months < 24:
        return f"{int(round(months))} мес"
    return f"{days / 365.25:.1f} г"


class HealthRecoveryCalculator:
    """Главный калькулятор восстановления."""

    def __init__(self, factors: PersonalFactors | None = None) -> None:
        self.factors = factors or PersonalFactors()
        self.speed = self.factors.speed_factor

    # -- отдельный орган ----------------------------------------------------
    def organ_status(self, key: str, effective_hours: float, now: datetime) -> OrganStatus:
        module: OrganModule = ORGANS_BY_KEY[key]
        curve = CURVES[key]
        effective_hours = max(0.0, effective_hours)

        t_eff = effective_hours * self.speed
        percent = curve.percent_at(t_eff)

        reached = module.milestone_reached(t_eff)
        upcoming = module.next_milestone(t_eff)

        hours_to_next: float | None = None
        next_eta: datetime | None = None
        if upcoming is not None:
            needed_eff = upcoming.hours / self.speed
            hours_to_next = max(0.0, needed_eff - effective_hours)
            next_eta = now + timedelta(hours=hours_to_next)

        trend = curve.percent_at(t_eff + 7 * DAY * self.speed) - percent

        return OrganStatus(
            key=module.key,
            name=module.name,
            short=module.short,
            emoji=module.emoji,
            headline=module.headline,
            percent=percent,
            phase=phase_for_hours(t_eff),
            color=phase_for_hours(t_eff).color,
            reached=reached,
            upcoming=upcoming,
            hours_to_next=hours_to_next,
            next_eta=next_eta,
            trend_7d=trend,
            what_we_show=module.what_we_show,
            vape_specific=module.vape_specific,
            ritual_note=module.ritual_note,
            sources=module.sources,
            is_anatomy=module.key in ANATOMY_KEYS,
        )

    # -- полный снимок ------------------------------------------------------
    def snapshot(
        self,
        effective_hours: float,
        now: datetime,
        keys: tuple[str, ...] | None = None,
    ) -> OverallStatus:
        keys = keys or tuple(ORGANS_BY_KEY)
        statuses = [self.organ_status(k, effective_hours, now) for k in keys]

        total_weight = sum(ORGAN_WEIGHTS.get(s.key, 0.1) for s in statuses) or 1.0
        overall = sum(s.percent * ORGAN_WEIGHTS.get(s.key, 0.1) for s in statuses) / total_weight

        return OverallStatus(
            percent=overall,
            phase=phase_for_hours(effective_hours * self.speed),
            organs=statuses,
            anatomy=[s for s in statuses if s.is_anatomy],
            systems=[s for s in statuses if not s.is_anatomy],
            progress=ProgressState(
                effective_hours=effective_hours,
                current_streak_hours=effective_hours,
                longest_streak_hours=effective_hours,
                total_wall_hours=effective_hours,
                lapse_count=0,
                last_lapse_at=None,
                last_lapse_retained_pct=None,
                last_lapse_label=None,
            ),
            speed_factor=self.speed,
            speed_notes=self.factors.speed_notes,
        )

    # -- удобная сборка из истории -----------------------------------------
    def full_report(
        self,
        started_at: datetime,
        now: datetime,
        lapses: list[Lapse] | None = None,
    ) -> OverallStatus:
        progress = compute_progress(started_at, now, lapses)
        report = self.snapshot(progress.effective_hours, now)
        report.progress = progress
        return report

    # -- вспомогательное ----------------------------------------------------
    def upcoming_events(
        self,
        effective_hours: float,
        now: datetime,
        limit: int = 5,
        keys: tuple[str, ...] | None = None,
    ) -> list[tuple[OrganStatus, Milestone, datetime, float]]:
        """Ближайшие будущие опорные точки по всем модулям."""
        rows: list[tuple[OrganStatus, Milestone, datetime, float]] = []
        for key in keys or tuple(ORGANS_BY_KEY):
            status = self.organ_status(key, effective_hours, now)
            if status.upcoming is None or status.next_eta is None:
                continue
            rows.append((status, status.upcoming, status.next_eta, status.hours_to_next or 0.0))
        rows.sort(key=lambda r: r[3])
        return rows[:limit]


def humanize_hours(hours: float) -> str:
    """Публичная обёртка для форматирования длительности."""
    return _format_eta(hours)


def anatomy_keys() -> tuple[str, ...]:
    return ANATOMY_KEYS


def system_keys() -> tuple[str, ...]:
    return SYSTEM_KEYS
