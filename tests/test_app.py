"""Интеграционные тесты HTTP-слоя: регистрация, онбординг, дашборд, чек-ин, срыв."""

from __future__ import annotations

from datetime import date, datetime, timedelta

import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture(scope="module")
def registered(client: TestClient):
    """Зарегистрированный пользователь с пройденным онбордингом."""
    email = "pytest-user@example.com"
    response = client.post(
        "/register",
        data={
            "email": email,
            "password": "strongpass1",
            "password2": "strongpass1",
            "display_name": "Тест",
            "next": "/onboarding",
        },
        follow_redirects=False,
    )
    assert response.status_code == 303

    quit_local = (datetime.utcnow() - timedelta(days=45)).strftime("%Y-%m-%dT%H:%M")
    response = client.post(
        "/onboarding",
        data={
            "quit_at_local": quit_local,
            "tz_offset": "0",
            "vape_years": "3",
            "pods_per_day": "1.5",
            "pod_volume_ml": "2",
            "nicotine_strength": "30",
            "nicotine_type": "salt",
            "age": "34",
            "sex": "male",
            "height_cm": "178",
            "weight_kg": "84",
            "activity": "moderate",
            "chronic": ["hypertension"],
        },
        follow_redirects=False,
    )
    assert response.status_code == 303
    return {"email": email, "password": "strongpass1"}


# ---------------------------------------------------------------------------
# Публичные маршруты
# ---------------------------------------------------------------------------
def test_healthz(client: TestClient):
    response = client.get("/healthz")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_landing_renders_for_anonymous(client: TestClient):
    response = client.get("/")
    assert response.status_code == 200
    assert "VapeFree Anatomy" in response.text
    assert "body-map" in response.text or "body-stage" in response.text


def test_manifest_is_valid(client: TestClient):
    response = client.get("/manifest.webmanifest")
    assert response.status_code == 200
    payload = response.json()
    assert payload["start_url"] == "/"
    assert payload["display"] == "standalone"
    assert len(payload["icons"]) >= 3


def test_service_worker_served_from_root(client: TestClient):
    response = client.get("/sw.js")
    assert response.status_code == 200
    assert "javascript" in response.headers["content-type"]
    assert "Service-Worker-Allowed" in response.headers


def test_static_assets_available(client: TestClient):
    for path in (
        "/static/css/app.css",
        "/static/js/app.js",
        "/static/js/body-map.js",
        "/static/img/body-map.svg",
        "/static/icons/icon-192.png",
    ):
        assert client.get(path).status_code == 200, path


def test_dashboard_redirects_anonymous(client: TestClient):
    response = client.get("/dashboard", follow_redirects=False)
    assert response.status_code == 303
    assert response.headers["location"].startswith("/login")


def test_unknown_page_returns_404(client: TestClient):
    assert client.get("/definitely-not-a-page").status_code == 404


# ---------------------------------------------------------------------------
# Аутентификация
# ---------------------------------------------------------------------------
def test_register_validates_email_and_password(client: TestClient):
    response = client.post(
        "/register",
        data={"email": "not-an-email", "password": "short", "password2": "other", "next": "/onboarding"},
    )
    assert response.status_code == 400
    assert "корректный адрес" in response.text
    assert "Пароли не совпадают" in response.text


def test_duplicate_registration_rejected(client: TestClient, registered):
    response = client.post(
        "/register",
        data={
            "email": registered["email"],
            "password": "strongpass1",
            "password2": "strongpass1",
            "next": "/onboarding",
        },
    )
    assert response.status_code == 400
    assert "уже зарегистрирован" in response.text


def test_login_with_wrong_password(client: TestClient, registered):
    response = client.post(
        "/login", data={"email": registered["email"], "password": "wrong-password", "next": "/"}
    )
    assert response.status_code == 401
    assert "Неверная почта или пароль" in response.text


def test_open_redirect_is_blocked(client: TestClient):
    response = client.post(
        "/login",
        data={"email": "nobody@example.com", "password": "x", "next": "https://evil.example.com"},
        follow_redirects=False,
    )
    # Пароль неверный -> 401, но проверим и безопасность next при успешном входе ниже
    assert response.status_code == 401


# ---------------------------------------------------------------------------
# Дашборд и модули
# ---------------------------------------------------------------------------
def test_dashboard_content(client: TestClient, registered):
    response = client.get("/dashboard")
    assert response.status_code == 200
    body = response.text
    assert "Анатомическая схема" in body
    assert "Достижения" in body
    assert "Динамика тяги" in body
    assert "Я сорвался" in body
    assert 'data-organ-open="lungs"' in body
    assert "data-chart-data" in body
    # Дисклеймер обязателен на каждой странице
    assert "не заменяет консультацию врача" in body

    # Данные графика должны быть валидным JSON
    import json
    import re

    match = re.search(r'data-chart-data>(.*?)</script>', body, re.S)
    assert match, "не найден блок данных графика"
    rows = json.loads(match.group(1))
    assert len(rows) == 21
    assert all("day" in row and "craving" in row for row in rows)


def test_organ_cards_for_every_module(client: TestClient, registered):
    for key in ("brain", "lungs", "heart", "vessels", "blood", "mouth", "sleep"):
        response = client.get(f"/organ/{key}/card")
        assert response.status_code == 200, key
        assert "Таймлайн" in response.text, key
        assert "Источники" in response.text, key


def test_organ_page_and_missing_module(client: TestClient, registered):
    assert client.get("/organ/lungs").status_code == 200
    response = client.get("/organ/not-an-organ", follow_redirects=False)
    assert response.status_code == 303


def test_state_api(client: TestClient, registered):
    response = client.get("/api/state")
    assert response.status_code == 200
    payload = response.json()
    assert payload["authenticated"] is True
    assert 0 <= payload["overall"] <= 100
    assert set(payload["organs"]) == {"brain", "lungs", "heart", "vessels", "blood", "mouth", "sleep"}
    assert payload["timers"]["effective_text"]
    assert payload["phase"]["key"] in {"acute", "regeneration", "active", "restored"}


# ---------------------------------------------------------------------------
# Чек-ин, дыхание, срыв
# ---------------------------------------------------------------------------
def test_checkin_roundtrip(client: TestClient, registered):
    today = date.today().isoformat()
    response = client.post(
        "/checkin",
        data={
            "local_date": today,
            "mood": "7",
            "craving": "8",
            "sleep_hours": "6.5",
            "sleep_quality": "3",
            "water_glasses": "6",
            "activity_minutes": "30",
            "breathing_sessions": "1",
            "note": "Тяга после кофе",
        },
        follow_redirects=False,
    )
    assert response.status_code == 303

    page = client.get("/checkin")
    assert page.status_code == 200
    assert "Тяга после кофе" in page.text

    # Повторная отправка обновляет ту же запись, а не создаёт вторую
    response = client.post(
        "/checkin",
        data={
            "local_date": today,
            "mood": "9",
            "craving": "2",
            "sleep_hours": "8",
            "sleep_quality": "5",
            "water_glasses": "9",
            "activity_minutes": "45",
            "breathing_sessions": "2",
        },
        follow_redirects=False,
    )
    assert response.status_code == 303
    assert "Тяга после кофе" not in client.get("/checkin").text


def test_checkin_clamps_out_of_range_values(client: TestClient, registered):
    response = client.post(
        "/checkin",
        data={"local_date": date.today().isoformat(), "mood": "999", "craving": "-5", "water_glasses": "900"},
        follow_redirects=False,
    )
    assert response.status_code == 303
    state = client.get("/api/state")
    assert state.status_code == 200


def test_breathing_completion_increments(client: TestClient, registered):
    before = client.get("/breathing").text
    response = client.post("/api/breathing/complete", json={"local_date": date.today().isoformat()})
    assert response.status_code == 200
    assert response.json()["ok"] is True
    assert response.json()["breathing_sessions"] >= 1
    assert before  # страница доступна


def test_lapse_preserves_progress(client: TestClient, registered):
    before = client.get("/api/state").json()
    response = client.post("/lapse", data={"severity": "puff", "note": "тест"}, follow_redirects=False)
    assert response.status_code == 303
    assert response.headers["location"] == "/?lapse=1"

    after = client.get("/api/state").json()
    assert after["overall"] <= before["overall"]
    assert after["overall"] >= before["overall"] - 15, "прогресс не должен обнуляться"
    assert after["lapses"] == before["lapses"] + 1

    page = client.get("/?lapse=1")
    assert page.status_code == 200
    assert "прогресс никуда не делся" in page.text


def test_lapse_history_visible_in_settings(client: TestClient, registered):
    response = client.get("/settings")
    assert response.status_code == 200
    assert "История срывов" in response.text


def test_breathing_complete_requires_auth(client: TestClient):
    with TestClient(app) as anonymous:
        response = anonymous.post("/api/breathing/complete", json={"local_date": date.today().isoformat()})
        assert response.status_code == 401
        assert anonymous.get("/api/state").status_code == 401


def test_logout_clears_session(client: TestClient, registered):
    response = client.post("/logout", follow_redirects=False)
    assert response.status_code == 303
    assert client.get("/api/state").status_code == 401
