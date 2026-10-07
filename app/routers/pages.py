"""Основные страницы приложения: онбординг, дашборд, модули органов, чек-ин, дыхание, настройки."""

from __future__ import annotations

from datetime import date, datetime, timedelta

from fastapi import APIRouter, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy import select

from ..config import HABIT_REPLACEMENTS, LAPSE_SEVERITIES
from ..core.engagement import habit_totals
from ..core.organs import ORGANS_BY_KEY
from ..core.recovery import ORGAN_WEIGHTS, humanize_hours
from ..db import utcnow
from ..deps import CurrentUser, SessionDep
from ..models import CheckIn, LapseEvent, Profile
from ..services import (
    all_checkins,
    build_report,
    calculator_for,
    checkin_for_day,
    compute_points,
    engagement_for,
    factors_from_profile,
    recent_checkins,
)
from ..templating import templates

router = APIRouter(tags=["pages"])


# ---------------------------------------------------------------------------
# Вспомогательное
# ---------------------------------------------------------------------------
def _to_float(value: object, default: float = 0.0) -> float:
    try:
        text = str(value).strip().replace(",", ".")
        return float(text) if text else default
    except (TypeError, ValueError):
        return default


def _to_int(value: object, default: int = 0) -> int:
    try:
        text = str(value).strip()
        return int(float(text)) if text else default
    except (TypeError, ValueError):
        return default


def _to_float_or_none(value: object) -> float | None:
    text = str(value or "").strip().replace(",", ".")
    if not text:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def _to_int_or_none(value: object) -> int | None:
    value_f = _to_float_or_none(value)
    return int(value_f) if value_f is not None else None


def _clamp(value: int, low: int, high: int) -> int:
    return max(low, min(high, value))


def parse_local_datetime(local_value: str, offset_minutes: int) -> datetime | None:
    """Преобразовать значение <input type="datetime-local"> в наивное UTC.

    ``offset_minutes`` — то, что возвращает JS ``getTimezoneOffset()``:
    для UTC+3 это -180.
    """
    text = (local_value or "").strip()
    if not text:
        return None
    for fmt in ("%Y-%m-%dT%H:%M", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d"):
        try:
            local_dt = datetime.strptime(text, fmt)
        except ValueError:
            continue
        return local_dt + timedelta(minutes=offset_minutes)
    return None


def _require_user(user, request: Request):
    if user is None:
        return RedirectResponse(
            f"/login?next={request.url.path}", status_code=status.HTTP_303_SEE_OTHER
        )
    return None


# ---------------------------------------------------------------------------
# Лендинг
# ---------------------------------------------------------------------------
@router.get("/")
def index(request: Request, user: CurrentUser, session: SessionDep):
    if user is None:
        return templates.TemplateResponse(request, "landing.html", {"user": None})
    if user.profile is None or not user.profile.onboarding_completed:
        return RedirectResponse("/onboarding", status_code=status.HTTP_303_SEE_OTHER)
    return dashboard(request, user, session)


# ---------------------------------------------------------------------------
# Онбординг
# ---------------------------------------------------------------------------
@router.get("/onboarding")
def onboarding_form(request: Request, user: CurrentUser):
    if user is None:
        return RedirectResponse("/login?next=/onboarding", status_code=status.HTTP_303_SEE_OTHER)
    profile = user.profile
    return templates.TemplateResponse(
        request,
        "onboarding.html",
        {
            "user": user,
            "profile": profile,
            "quit_at_utc": profile.quit_at if profile else None,
            "step": request.query_params.get("step", "1"),
        },
    )


@router.post("/onboarding")
async def onboarding_submit(request: Request, user: CurrentUser, session: SessionDep):
    redirect = _require_user(user, request)
    if redirect:
        return redirect

    form = await request.form()
    profile = user.profile
    if profile is None:
        profile = Profile(user_id=user.id)
        session.add(profile)
        session.flush()

    offset = _to_int(form.get("tz_offset"), 0)
    quit_at = parse_local_datetime(str(form.get("quit_at_local", "")), offset)

    profile.quit_at = quit_at or profile.quit_at or utcnow()
    profile.vape_years = max(0.0, _to_float(form.get("vape_years"), 0.0))
    profile.pods_per_day = max(0.0, _to_float(form.get("pods_per_day"), 0.0))
    profile.nicotine_strength = max(0.0, _to_float(form.get("nicotine_strength"), 20.0))
    profile.nicotine_type = str(form.get("nicotine_type") or "salt")[:16]
    profile.pod_volume_ml = max(0.5, _to_float(form.get("pod_volume_ml"), 2.0))

    profile.age = _to_int_or_none(form.get("age"))
    profile.sex = (str(form.get("sex")) or None) if form.get("sex") else None
    profile.height_cm = _to_float_or_none(form.get("height_cm"))
    profile.weight_kg = _to_float_or_none(form.get("weight_kg"))
    profile.activity = str(form.get("activity") or "moderate")[:16]

    conditions = [str(v) for v in form.getlist("chronic") if str(v).strip()]
    profile.chronic_conditions = conditions

    profile.onboarding_completed = True
    session.commit()

    return RedirectResponse("/?welcome=1", status_code=status.HTTP_303_SEE_OTHER)


# ---------------------------------------------------------------------------
# Дашборд
# ---------------------------------------------------------------------------
def _chart_rows(rows: list[CheckIn], days: int = 21) -> list[dict]:
    """Данные для графика динамики тяги и настроения."""
    by_day = {r.day: r for r in rows}
    today = date.today()
    out: list[dict] = []
    for i in range(days - 1, -1, -1):
        day = today - timedelta(days=i)
        row = by_day.get(day)
        out.append(
            {
                "day": day.isoformat(),
                "label": day.strftime("%d.%m"),
                "craving": row.craving if row else None,
                "mood": row.mood if row else None,
                "sleep": row.sleep_hours if row else None,
            }
        )
    return out


@router.get("/dashboard")
def dashboard(request: Request, user: CurrentUser, session: SessionDep):
    if user is None:
        return RedirectResponse("/login?next=/dashboard", status_code=status.HTTP_303_SEE_OTHER)
    if user.profile is None or not user.profile.onboarding_completed:
        return RedirectResponse("/onboarding", status_code=status.HTTP_303_SEE_OTHER)

    report = build_report(user)
    today_row = checkin_for_day(session, user.id, date.today())
    achievements, notifications = engagement_for(session, user, report)
    calc = calculator_for(user)

    next_events = calc.upcoming_events(report.progress.effective_hours, utcnow(), limit=6)
    rows = recent_checkins(session, user.id, days=21)

    # Прогноз ближайших 7 дней по каждому модулю.
    forecast = [
        {"organ": o, "next_week": min(100.0, o.percent + o.trend_7d)} for o in report.organs
    ]

    context = {
        "user": user,
        "profile": user.profile,
        "report": report,
        "progress": report.progress,
        "today_checkin": today_row,
        "achievements": achievements,
        "unlocked_count": sum(1 for a in achievements if a.unlocked),
        "notifications": notifications,
        "next_events": next_events,
        "chart_rows": _chart_rows(rows),
        "habit_replacements": HABIT_REPLACEMENTS,
        "forecast": forecast,
        "report_json": {
            "overall": report.percent_int,
            "phase": report.phase.key,
            "organs": {o.key: o.percent_int for o in report.organs},
        },
        "now_utc": utcnow(),
        "lapse_flash": request.query_params.get("lapse"),
        "welcome": request.query_params.get("welcome"),
    }
    if context["lapse_flash"]:
        context["lapse_retained"] = report.progress.last_lapse_retained_pct
        context["lapse_label"] = report.progress.last_lapse_label
        context["lapse_keep_pct"] = report.percent_int
    return templates.TemplateResponse(request, "dashboard.html", context)


# ---------------------------------------------------------------------------
# Модули органов
# ---------------------------------------------------------------------------
def _organ_context(request: Request, user, key: str, *, partial: bool):
    module = ORGANS_BY_KEY.get(key)
    if module is None:
        return None
    report = build_report(user)
    status = next((o for o in report.organs if o.key == key), None)
    if status is None:
        return None
    timeline = [
        {
            "milestone": m,
            "reached": report.progress.effective_hours * report.speed_factor >= m.hours,
            "eta_hours": max(0.0, m.hours / report.speed_factor - report.progress.effective_hours),
        }
        for m in module.milestones
    ]
    next_index = next((i for i, row in enumerate(timeline) if not row["reached"]), len(timeline) - 1)
    context = {
        "user": user,
        "status": status,
        "module": module,
        "timeline": timeline,
        "next_index": next_index,
        "report": report,
        "progress": report.progress,
        "speed_factor": report.speed_factor,
        "speed_notes": report.speed_notes,
        "weight": ORGAN_WEIGHTS.get(key, 0.1),
        "partial": partial,
    }
    if partial:
        context["humanize_hours"] = humanize_hours
    return context


@router.get("/organ/{key}", response_class=HTMLResponse)
def organ_page(request: Request, user: CurrentUser, key: str):
    if user is None:
        return RedirectResponse(f"/login?next=/organ/{key}", status_code=status.HTTP_303_SEE_OTHER)
    context = _organ_context(request, user, key, partial=False)
    if context is None:
        return RedirectResponse("/dashboard", status_code=status.HTTP_303_SEE_OTHER)
    return templates.TemplateResponse(request, "organ.html", context)


@router.get("/organ/{key}/card", response_class=HTMLResponse)
def organ_card(request: Request, user: CurrentUser, key: str):
    """Фрагмент для модального окна (подгружается fetch-запросом)."""
    if user is None:
        return HTMLResponse('<p class="muted">Требуется вход в приложение.</p>', status_code=401)
    context = _organ_context(request, user, key, partial=True)
    if context is None:
        return HTMLResponse('<p class="muted">Модуль не найден.</p>', status_code=404)
    return templates.TemplateResponse(request, "partials/organ_card.html", context)


# ---------------------------------------------------------------------------
# Срыв
# ---------------------------------------------------------------------------
@router.post("/lapse")
async def record_lapse(request: Request, user: CurrentUser, session: SessionDep):
    redirect = _require_user(user, request)
    if redirect:
        return redirect

    form = await request.form()
    severity = str(form.get("severity") or "episode")
    if severity not in {s for s, _ in LAPSE_SEVERITIES}:
        severity = "episode"

    session.add(
        LapseEvent(
            user_id=user.id,
            occurred_at=utcnow(),
            severity=severity,
            note=str(form.get("note") or "")[:500],
        )
    )
    session.commit()
    return RedirectResponse("/?lapse=1", status_code=status.HTTP_303_SEE_OTHER)


@router.post("/lapse/{lapse_id}/delete")
def delete_lapse(request: Request, user: CurrentUser, session: SessionDep, lapse_id: int):
    redirect = _require_user(user, request)
    if redirect:
        return redirect
    row = session.get(LapseEvent, lapse_id)
    if row is not None and row.user_id == user.id:
        session.delete(row)
        session.commit()
    return RedirectResponse("/dashboard", status_code=status.HTTP_303_SEE_OTHER)


@router.post("/restart")
async def restart_timer(request: Request, user: CurrentUser, session: SessionDep):
    """Полный перезапуск таймера — осознанное действие, отдельное от «Я сорвался»."""
    redirect = _require_user(user, request)
    if redirect:
        return redirect
    if user.profile is not None:
        user.profile.quit_at = utcnow()
        for row in list(user.lapses):
            session.delete(row)
        session.commit()
    return RedirectResponse("/dashboard", status_code=status.HTTP_303_SEE_OTHER)


# ---------------------------------------------------------------------------
# Чек-ин
# ---------------------------------------------------------------------------
@router.get("/checkin")
def checkin_page(request: Request, user: CurrentUser, session: SessionDep):
    if user is None:
        return RedirectResponse("/login?next=/checkin", status_code=status.HTTP_303_SEE_OTHER)
    if user.profile is None or not user.profile.onboarding_completed:
        return RedirectResponse("/onboarding", status_code=status.HTTP_303_SEE_OTHER)

    today_row = checkin_for_day(session, user.id, date.today())
    rows = all_checkins(session, user.id)
    totals = habit_totals([r.day for r in rows], rows)
    return templates.TemplateResponse(
        request,
        "checkin.html",
        {
            "user": user,
            "today": date.today(),
            "checkin": today_row,
            "totals": totals,
            "saved": request.query_params.get("saved"),
            "recent": rows[-14:][::-1],
        },
    )


@router.post("/checkin")
async def checkin_submit(request: Request, user: CurrentUser, session: SessionDep):
    redirect = _require_user(user, request)
    if redirect:
        return redirect

    form = await request.form()

    # Дата определяется по локальным часам клиента.
    local_day = str(form.get("local_date") or "").strip()
    try:
        day = date.fromisoformat(local_day) if local_day else date.today()
    except ValueError:
        day = date.today()

    values = {
        "mood": _clamp(_to_int(form.get("mood"), 5), 1, 10),
        "craving": _clamp(_to_int(form.get("craving"), 5), 1, 10),
        "sleep_hours": max(0.0, min(24.0, _to_float(form.get("sleep_hours"), 0.0))),
        "sleep_quality": _clamp(_to_int(form.get("sleep_quality"), 3), 1, 5),
        "water_glasses": _clamp(_to_int(form.get("water_glasses"), 0), 0, 30),
        "activity_minutes": _clamp(_to_int(form.get("activity_minutes"), 0), 0, 600),
        "breathing_sessions": _clamp(_to_int(form.get("breathing_sessions"), 0), 0, 50),
        "note": str(form.get("note") or "")[:1000],
    }
    values["points"] = compute_points(
        mood=values["mood"],
        craving=values["craving"],
        sleep_hours=values["sleep_hours"],
        sleep_quality=values["sleep_quality"],
        water_glasses=values["water_glasses"],
        activity_minutes=values["activity_minutes"],
        breathing_sessions=values["breathing_sessions"],
    )

    row = checkin_for_day(session, user.id, day)
    if row is None:
        row = CheckIn(user_id=user.id, day=day)
        session.add(row)
    for key, value in values.items():
        setattr(row, key, value)
    session.commit()

    return RedirectResponse("/checkin?saved=1", status_code=status.HTTP_303_SEE_OTHER)


# ---------------------------------------------------------------------------
# Дыхание и замена ритуала
# ---------------------------------------------------------------------------
@router.get("/breathing")
def breathing_page(request: Request, user: CurrentUser, session: SessionDep):
    if user is None:
        return RedirectResponse("/login?next=/breathing", status_code=status.HTTP_303_SEE_OTHER)
    today_row = checkin_for_day(session, user.id, date.today()) if user else None
    return templates.TemplateResponse(
        request,
        "breathing.html",
        {
            "user": user,
            "today_checkin": today_row,
            "habit_replacements": HABIT_REPLACEMENTS,
        },
    )


# ---------------------------------------------------------------------------
# Настройки
# ---------------------------------------------------------------------------
@router.get("/settings")
def settings_page(request: Request, user: CurrentUser, session: SessionDep):
    if user is None:
        return RedirectResponse("/login?next=/settings", status_code=status.HTTP_303_SEE_OTHER)
    rows = list(user.lapses)
    return templates.TemplateResponse(
        request,
        "settings.html",
        {
            "user": user,
            "profile": user.profile,
            "lapses": rows[::-1],
            "factors": factors_from_profile(user.profile),
            "saved": request.query_params.get("saved"),
        },
    )


@router.post("/settings")
async def settings_submit(request: Request, user: CurrentUser, session: SessionDep):
    redirect = _require_user(user, request)
    if redirect:
        return redirect

    form = await request.form()
    profile = user.profile
    if profile is None:
        profile = Profile(user_id=user.id)
        session.add(profile)
        session.flush()

    profile.vape_years = max(0.0, _to_float(form.get("vape_years"), profile.vape_years))
    profile.pods_per_day = max(0.0, _to_float(form.get("pods_per_day"), profile.pods_per_day))
    profile.nicotine_strength = max(0.0, _to_float(form.get("nicotine_strength"), profile.nicotine_strength))
    profile.nicotine_type = str(form.get("nicotine_type") or profile.nicotine_type)[:16]
    profile.age = _to_int_or_none(form.get("age"))
    profile.sex = (str(form.get("sex")) or None) if form.get("sex") else None
    profile.height_cm = _to_float_or_none(form.get("height_cm"))
    profile.weight_kg = _to_float_or_none(form.get("weight_kg"))
    profile.activity = str(form.get("activity") or profile.activity)[:16]
    profile.chronic_conditions = [str(v) for v in form.getlist("chronic") if str(v).strip()]

    name = str(form.get("display_name") or "").strip()
    if name:
        user.display_name = name[:120]

    session.commit()
    return RedirectResponse("/settings?saved=1", status_code=status.HTTP_303_SEE_OTHER)


__all__ = ["router", "parse_local_datetime"]
