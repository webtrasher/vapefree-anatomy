"""Ядро приложения: расчёт восстановления, данные об органах, источники."""

from .organs import ANATOMY_KEYS, ORGAN_MODULES, ORGANS_BY_KEY, SYSTEM_KEYS, OrganModule
from .recovery import (
    CURVES,
    PHASES,
    HealthRecoveryCalculator,
    Lapse,
    OrganStatus,
    OverallStatus,
    PersonalFactors,
    ProgressState,
    RecoveryCurve,
    compute_progress,
    humanize_hours,
    phase_for_hours,
)
from .sources import SOURCES, Source, citation

__all__ = [
    "ANATOMY_KEYS",
    "CURVES",
    "ORGAN_MODULES",
    "ORGANS_BY_KEY",
    "PHASES",
    "SOURCES",
    "SYSTEM_KEYS",
    "HealthRecoveryCalculator",
    "Lapse",
    "OrganModule",
    "OrganStatus",
    "OverallStatus",
    "PersonalFactors",
    "ProgressState",
    "RecoveryCurve",
    "Source",
    "citation",
    "compute_progress",
    "humanize_hours",
    "phase_for_hours",
]
