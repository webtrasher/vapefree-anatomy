"""Тесты ядра расчёта восстановления."""

from __future__ import annotations

from datetime import datetime, timedelta

import pytest

from app.core.organs import ANATOMY_KEYS, ORGAN_MODULES, ORGANS_BY_KEY, SYSTEM_KEYS
from app.core.recovery import (
    CURVES,
    ORGAN_WEIGHTS,
    PHASES,
    RECOVERY_FLOOR,
    HealthRecoveryCalculator,
    Lapse,
    PersonalFactors,
    RecoveryCurve,
    compute_progress,
    humanize_hours,
    phase_for_hours,
)
from app.core.sources import SOURCES

NOW = datetime(2026, 3, 1, 12, 0, 0)

HOUR_POINTS = [
    20 / 60, 1, 2, 4, 8, 12, 24, 48, 72,
    7 * 24, 14 * 24, 30 * 24, 90 * 24, 180 * 24, 365 * 24, 5 * 365 * 24,
]


# ---------------------------------------------------------------------------
# Данные об органах
# ---------------------------------------------------------------------------
def test_every_module_has_increasing_milestones():
    for module in ORGAN_MODULES:
        hours = [m.hours for m in module.milestones]
        percents = [m.percent for m in module.milestones]
        assert hours == sorted(hours), f"{module.key}: опорные точки не по возрастанию"
        assert len(set(hours)) == len(hours), f"{module.key}: дублирующиеся часы"
        assert percents == sorted(percents), f"{module.key}: проценты не возрастают"
        assert percents[0] > 0 and percents[-1] <= 100
        assert module.what_we_show, f"{module.key}: не заполнено what_we_show"
        assert module.vape_specific, f"{module.key}: нет пояснения про вейпинг"


def test_all_cited_sources_exist():
    for module in ORGAN_MODULES:
        for key in module.sources:
            assert key in SOURCES, f"{module.key}: неизвестный источник {key!r}"
        for milestone in module.milestones:
            for key in milestone.sources:
                assert key in SOURCES, f"{module.key}/{milestone.title}: неизвестный источник {key!r}"


def test_organ_registry_is_consistent():
    keys = {m.key for m in ORGAN_MODULES}
    assert set(ORGANS_BY_KEY) == keys
    assert set(CURVES) == keys
    assert set(ANATOMY_KEYS).isdisjoint(SYSTEM_KEYS)
    assert set(ANATOMY_KEYS) | set(SYSTEM_KEYS) == keys
    assert set(ORGAN_WEIGHTS) == keys
    assert sum(ORGAN_WEIGHTS.values()) == pytest.approx(1.0)


# ---------------------------------------------------------------------------
# Кривая
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("key", sorted(ORGANS_BY_KEY))
def test_curve_is_monotone_and_bounded(key: str):
    curve = CURVES[key]
    previous = -1.0
    for hours in [0, 0.001, 0.1, *HOUR_POINTS, 10 * 365 * 24, 50 * 365 * 24]:
        value = curve.percent_at(hours)
        assert 0.0 <= value <= 100.0, f"{key}: {value} вне диапазона при {hours} ч"
        assert value >= previous - 1e-9, f"{key}: кривая не монотонна при {hours} ч"
        previous = value
    assert curve.percent_at(0) == 0.0


@pytest.mark.parametrize("key", sorted(ORGANS_BY_KEY))
def test_curve_hits_declared_milestones(key: str):
    curve = CURVES[key]
    for milestone in ORGANS_BY_KEY[key].milestones:
        assert curve.percent_at(milestone.hours) == pytest.approx(milestone.percent, abs=0.01)


@pytest.mark.parametrize("key", sorted(ORGANS_BY_KEY))
def test_curve_inverse_roundtrip(key: str):
    curve = CURVES[key]
    for percent in (5, 25, 50, 75, 90):
        if percent > curve.milestones[-1].percent:
            continue
        hours = curve.hours_for_percent(percent)
        assert curve.percent_at(hours) == pytest.approx(percent, abs=0.05)


def test_curve_rejects_invalid_input():
    with pytest.raises(ValueError):
        RecoveryCurve(())


# ---------------------------------------------------------------------------
# Личные факторы
# ---------------------------------------------------------------------------
def test_speed_factor_stays_in_bounds():
    extremes = [
        PersonalFactors(age=80, bmi=42, chronic_conditions=("copd", "heart", "diabetes", "asthma"),
                        vape_years=20, pods_per_day=5, nicotine_strength=50, activity="low"),
        PersonalFactors(age=19, bmi=20, vape_years=0.2, pods_per_day=0.2, nicotine_strength=3, activity="high"),
    ]
    for factors in extremes:
        assert 0.65 <= factors.speed_factor <= 1.15


def test_speed_factor_direction():
    young_healthy = PersonalFactors(age=22, bmi=22, vape_years=1, pods_per_day=0.5,
                                    nicotine_strength=6, activity="high")
    older_heavy = PersonalFactors(age=64, bmi=34, chronic_conditions=("hypertension", "copd"),
                                  vape_years=8, pods_per_day=3, nicotine_strength=40, activity="low")
    assert young_healthy.speed_factor > 1.0
    assert older_heavy.speed_factor < 1.0
    assert young_healthy.speed_factor > older_heavy.speed_factor


def test_daily_nicotine_estimate():
    factors = PersonalFactors(pods_per_day=2, pod_volume_ml=2.0, nicotine_strength=25)
    assert factors.daily_nicotine_mg == pytest.approx(100.0)


# ---------------------------------------------------------------------------
# Срывы
# ---------------------------------------------------------------------------
def test_no_lapses_means_full_clean_time():
    started = NOW - timedelta(days=10)
    progress = compute_progress(started, NOW, [])
    assert progress.effective_hours == pytest.approx(240.0)
    assert progress.current_streak_hours == pytest.approx(240.0)
    assert progress.lapse_count == 0
    assert progress.last_lapse_retained_pct is None


def test_single_lapse_never_zeroes_progress():
    started = NOW - timedelta(days=40)
    lapse = Lapse(at=NOW - timedelta(days=1), severity="day")
    progress = compute_progress(started, NOW, [lapse])

    assert progress.effective_hours > 0
    assert progress.effective_hours < 40 * 24
    # Сохраняется не меньше 65% от достигнутого максимума
    assert progress.effective_hours >= RECOVERY_FLOOR * 40 * 24 - 1e-6
    assert progress.current_streak_hours == pytest.approx(24.0)
    assert progress.lapse_count == 1
    assert progress.last_lapse_retained_pct == pytest.approx(78.0, abs=0.5)
    assert progress.last_lapse_label == "возврат к вейпу на день и больше"


def test_lapse_severity_ordering():
    started = NOW - timedelta(days=30)
    results = {}
    for severity in ("puff", "episode", "day"):
        lapse = Lapse(at=NOW - timedelta(days=2), severity=severity)
        results[severity] = compute_progress(started, NOW, [lapse]).effective_hours
    assert results["puff"] > results["episode"] > results["day"]


def test_multiple_lapses_keep_longest_streak():
    started = NOW - timedelta(days=60)
    lapses = [
        Lapse(at=NOW - timedelta(days=50), severity="puff"),
        Lapse(at=NOW - timedelta(days=20), severity="episode"),
        Lapse(at=NOW - timedelta(days=3), severity="puff"),
    ]
    progress = compute_progress(started, NOW, lapses)
    assert progress.lapse_count == 3
    assert progress.longest_streak_hours == pytest.approx(30 * 24)
    assert progress.current_streak_hours == pytest.approx(72.0)
    assert progress.effective_hours < progress.total_wall_hours


def test_lapses_before_start_are_ignored():
    started = NOW - timedelta(days=5)
    stale = Lapse(at=started - timedelta(days=30), severity="day")
    progress = compute_progress(started, NOW, [stale])
    assert progress.lapse_count == 0
    assert progress.effective_hours == pytest.approx(120.0)


# ---------------------------------------------------------------------------
# Фазы
# ---------------------------------------------------------------------------
@pytest.mark.parametrize(
    "hours,expected",
    [
        (0, "acute"),
        (6 * 24, "acute"),
        (7 * 24, "regeneration"),
        (27 * 24, "regeneration"),
        (28 * 24, "active"),
        (179 * 24, "active"),
        (180 * 24, "restored"),
        (5000 * 24, "restored"),
    ],
)
def test_phase_boundaries(hours: float, expected: str):
    assert phase_for_hours(hours).key == expected


def test_phases_are_contiguous():
    for earlier, later in zip(PHASES, PHASES[1:]):
        assert earlier.max_hours == later.min_hours
    assert PHASES[-1].max_hours is None
    assert PHASES[0].min_hours == 0.0


# ---------------------------------------------------------------------------
# Калькулятор
# ---------------------------------------------------------------------------
def test_snapshot_covers_all_modules_and_weights():
    calc = HealthRecoveryCalculator()
    report = calc.snapshot(90 * 24, NOW)
    assert len(report.organs) == len(ORGAN_MODULES)
    assert len(report.anatomy) == len(ANATOMY_KEYS)
    assert len(report.systems) == len(SYSTEM_KEYS)
    assert 0 <= report.percent <= 100
    assert report.strongest.percent >= report.weakest.percent


def test_personal_factor_slows_recovery():
    fast = HealthRecoveryCalculator(PersonalFactors(age=22, bmi=22, activity="high"))
    slow = HealthRecoveryCalculator(
        PersonalFactors(age=70, bmi=35, chronic_conditions=("copd", "heart", "diabetes"),
                        vape_years=10, pods_per_day=4, activity="low")
    )
    fast_report = fast.snapshot(30 * 24, NOW)
    slow_report = slow.snapshot(30 * 24, NOW)
    assert fast_report.percent > slow_report.percent


def test_next_milestone_and_eta():
    calc = HealthRecoveryCalculator()
    status = calc.organ_status("lungs", 48.0, NOW)
    assert status.upcoming is not None
    assert status.hours_to_next is not None and status.hours_to_next > 0
    assert status.next_eta is not None and status.next_eta > NOW
    assert status.reached is not None


def test_upcoming_events_sorted():
    calc = HealthRecoveryCalculator()
    events = calc.upcoming_events(24.0, NOW, limit=6)
    assert events
    hours = [row[3] for row in events]
    assert hours == sorted(hours)
    assert len(events) <= 6


def test_full_report_uses_lapse_history():
    calc = HealthRecoveryCalculator()
    started = NOW - timedelta(days=30)
    clean = calc.full_report(started, NOW, [])
    lapsed = calc.full_report(started, NOW, [Lapse(at=NOW - timedelta(days=1), severity="day")])
    assert lapsed.percent < clean.percent
    assert lapsed.percent > 0
    assert lapsed.progress.lapse_count == 1


def test_humanize_hours_formats_units():
    assert "мин" in humanize_hours(0.5)
    assert humanize_hours(10).endswith("ч")
    assert humanize_hours(72).endswith("дн")
    assert humanize_hours(24 * 90).endswith("мес")
    assert humanize_hours(24 * 800).endswith("г")
