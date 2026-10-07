"""Конфигурация приложения и константы предметной области."""

from __future__ import annotations

import os
import secrets
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
APP_DIR = BASE_DIR / "app"

DATA_DIR = Path(os.environ.get("VAPEFREE_DATA_DIR", BASE_DIR / "data"))
DATA_DIR.mkdir(parents=True, exist_ok=True)

DATABASE_URL = os.environ.get(
    "VAPEFREE_DATABASE_URL",
    f"sqlite:///{(DATA_DIR / 'vapefree.db').as_posix()}",
)

def _load_secret_key() -> str:
    """Ключ подписи сессий: из окружения, иначе — сохранённый в data/, иначе новый.

    Сохранение на диск важно, чтобы сессии не разлогинивались при перезапуске.
    """
    env_key = os.environ.get("VAPEFREE_SECRET_KEY")
    if env_key:
        return env_key

    key_file = DATA_DIR / "secret_key.txt"
    try:
        if key_file.exists():
            stored = key_file.read_text(encoding="utf-8").strip()
            if stored:
                return stored
        generated = secrets.token_urlsafe(48)
        key_file.write_text(generated, encoding="utf-8")
        try:
            key_file.chmod(0o600)
        except OSError:
            pass
        return generated
    except OSError:
        # Каталог только для чтения — работаем с временным ключом.
        return secrets.token_urlsafe(48)


SECRET_KEY = _load_secret_key()
SESSION_COOKIE = "vf_session"
SESSION_MAX_AGE = 60 * 60 * 24 * 30  # 30 дней

APP_NAME = "VapeFree Anatomy"
APP_TAGLINE = "Анатомия восстановления после отказа от вейпа"

MEDICAL_DISCLAIMER = (
    "Приложение носит информационно-мотивационный характер. Оно не ставит диагнозы "
    "и не заменяет консультацию врача. Таймлайны восстановления основаны на данных ВОЗ, "
    "CDC и исследованиях пульмонологии и кардиологии, адаптированных под специфику "
    "вейпинга, и являются усреднёнными ориентирами, а не персональным прогнозом."
)

# --- Справочники онбординга -------------------------------------------------
ACTIVITY_LEVELS: tuple[tuple[str, str], ...] = (
    ("low", "Низкая — почти нет физической активности"),
    ("moderate", "Средняя — 1–3 тренировки или прогулки в неделю"),
    ("high", "Высокая — 4+ тренировок в неделю"),
)

SEX_OPTIONS: tuple[tuple[str, str], ...] = (
    ("male", "Мужской"),
    ("female", "Женский"),
    ("other", "Другой / не указывать"),
)

NICOTINE_TYPES: tuple[tuple[str, str], ...] = (
    ("salt", "Солевой никотин"),
    ("freebase", "Щелочной (freebase)"),
    ("mixed", "Смешанный / не знаю"),
)

CHRONIC_CONDITIONS: tuple[tuple[str, str], ...] = (
    ("asthma", "Бронхиальная астма"),
    ("copd", "ХОБЛ или хронический бронхит"),
    ("hypertension", "Повышенное давление"),
    ("heart", "Заболевания сердца и сосудов"),
    ("diabetes", "Диабет"),
    ("allergy", "Аллергия, аллергический ринит"),
    ("anxiety", "Тревожность или депрессия"),
    ("thyroid", "Заболевания щитовидной железы"),
    ("other", "Другое хроническое заболевание"),
)

LAPSE_SEVERITIES: tuple[tuple[str, str], ...] = (
    ("puff", "Одна затяжка"),
    ("episode", "Короткий эпизод (пара затяжек за день)"),
    ("day", "Вернулся к вейпу на день или больше"),
)

BREATHING_PATTERN = {
    "name": "Дыхание 4-7-8",
    "inhale": 4,
    "hold": 7,
    "exhale": 8,
    "cycles": 4,
    "description": (
        "Метод 4-7-8 активирует парасимпатическую систему и снимает острый приступ тяги "
        "за 1–2 минуты. Сядьте ровно, кончик языка — за верхними зубами. Вдох носом на 4 счёта, "
        "задержка на 7, выдох через рот на 8."
    ),
}

HABIT_REPLACEMENTS: tuple[dict[str, str], ...] = (
    {
        "title": "Жевательная резинка без никотина",
        "detail": "Занимает рот и снижает оральную тягу. Держите упаковку там, где раньше лежал вейп.",
        "tag": "рот",
    },
    {
        "title": "Эспандер для кисти",
        "detail": "Загружает руку, которая тянулась к устройству. Работает в офисе и в дороге.",
        "tag": "руки",
    },
    {
        "title": "Чётки или маленький массажный шарик",
        "detail": "Даёт пальцам постоянную мелкую моторику — именно её не хватает без ритуала.",
        "tag": "руки",
    },
    {
        "title": "Соломинка или трубочка для питья",
        "detail": "Имитирует затяжку без никотина. Хорошо работает в первые 2 недели.",
        "tag": "рот",
    },
    {
        "title": "Дыхание 4-7-8",
        "detail": "Самый быстрый способ переждать острый приступ тяги: 4 цикла — около 2 минут.",
        "tag": "нервная система",
    },
    {
        "title": "Стакан холодной воды",
        "detail": "Снимает раздражение слизистой, помогает выводить продукты метаболизма никотина.",
        "tag": "тело",
    },
    {
        "title": "Короткая прогулка 5–10 минут",
        "detail": "Переключает контекст и снижает кортизол. Особенно помогает в привычных триггерах.",
        "tag": "тело",
    },
    {
        "title": "Смена сценария перерыва",
        "detail": "Вейп был привязан к месту и времени. Поменяйте место перерыва — тяга ослабнет.",
        "tag": "поведение",
    },
)
