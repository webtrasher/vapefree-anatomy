"""JSON API: живое состояние таймера, отметка дыхательных практик, push-подписки."""

from __future__ import annotations

import json
from datetime import date

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from sqlalchemy import select

from ..db import utcnow
from ..deps import CurrentUser, SessionDep
from ..models import CheckIn, PushSubscription
from ..services import build_report, checkin_for_day, compute_points
from ..templating import format_duration, split_timer

router = APIRouter(prefix="/api", tags=["api"])


@router.get("/state")
def state(user: CurrentUser, session: SessionDep):
    """Текущее состояние для живого таймера и карты тела."""
    if user is None:
        return JSONResponse({"authenticated": False}, status_code=401)

    report = build_report(user)
    progress = report.progress
    return {
        "authenticated": True,
        "now": utcnow().isoformat() + "Z",
        "quit_at": user.profile.quit_at.isoformat() + "Z" if user.profile else None,
        "streak_hours": round(progress.current_streak_hours, 4),
        "effective_hours": round(progress.effective_hours, 4),
        "longest_streak_hours": round(progress.longest_streak_hours, 4),
        "timers": {
            "effective": split_timer(progress.effective_hours),
            "streak": split_timer(progress.current_streak_hours),
            "effective_text": format_duration(progress.effective_hours),
            "streak_text": format_duration(progress.current_streak_hours),
        },
        "overall": report.percent_int,
        "phase": {
            "key": report.phase.key,
            "label": report.phase.label,
            "emoji": report.phase.emoji,
            "color": report.phase.color,
            "description": report.phase.description,
        },
        "speed_factor": report.speed_factor,
        "lapses": progress.lapse_count,
        "organs": {
            o.key: {
                "percent": o.percent_int,
                "phase": o.phase.key,
                "color": o.phase.color,
                "hours_to_next": round(o.hours_to_next, 2) if o.hours_to_next is not None else None,
                "next_title": o.upcoming.title if o.upcoming else None,
                "next_percent": o.upcoming.percent if o.upcoming else None,
            }
            for o in report.organs
        },
    }


@router.post("/breathing/complete")
async def breathing_complete(request: Request, user: CurrentUser, session: SessionDep):
    """Отметить завершённую дыхательную практику в сегодняшнем чек-ине."""
    if user is None:
        return JSONResponse({"ok": False, "error": "auth"}, status_code=401)

    payload: dict = {}
    try:
        payload = await request.json()
    except Exception:  # noqa: BLE001 — тело может быть пустым
        payload = {}

    raw_day = str(payload.get("local_date") or "").strip()
    try:
        day = date.fromisoformat(raw_day) if raw_day else date.today()
    except ValueError:
        day = date.today()

    row = checkin_for_day(session, user.id, day)
    if row is None:
        row = CheckIn(user_id=user.id, day=day, mood=5, craving=5, sleep_quality=3)
        session.add(row)

    row.breathing_sessions = int(row.breathing_sessions or 0) + 1
    row.points = compute_points(
        mood=row.mood,
        craving=row.craving,
        sleep_hours=row.sleep_hours or 0.0,
        sleep_quality=row.sleep_quality,
        water_glasses=row.water_glasses or 0,
        activity_minutes=row.activity_minutes or 0,
        breathing_sessions=row.breathing_sessions,
    )
    session.commit()

    return {"ok": True, "breathing_sessions": row.breathing_sessions, "points": row.points}


@router.post("/push/subscribe")
async def push_subscribe(request: Request, user: CurrentUser, session: SessionDep):
    """Сохранить Web Push подписку.

    Отправка уведомлений требует VAPID-ключей и воркера — эндпоинт готовит
    хранилище подписок, а доставку подключает развёртывание.
    """
    if user is None:
        return JSONResponse({"ok": False, "error": "auth"}, status_code=401)

    payload = await request.json()
    endpoint = str(payload.get("endpoint") or "").strip()
    if not endpoint:
        return JSONResponse({"ok": False, "error": "endpoint"}, status_code=400)

    existing = session.execute(
        select(PushSubscription).where(PushSubscription.endpoint == endpoint)
    ).scalar_one_or_none()
    if existing is None:
        existing = PushSubscription(user_id=user.id, endpoint=endpoint)
        session.add(existing)
    existing.user_id = user.id
    existing.payload_json = json.dumps(payload, ensure_ascii=False)
    session.commit()
    return {"ok": True}
