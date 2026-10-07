"""Dev-утилита для визуальной проверки интерфейса без ручного входа.

ВНИМАНИЕ. Скрипт намеренно подменяет зависимость `current_user` и выдаёт доступ
под демо-пользователем БЕЗ ПАРОЛЯ. Это инструмент контроля качества для снятия
скриншотов, а не часть приложения:

  * он не импортируется ни одним модулем `app/`;
  * подмена действует только внутри процесса, запущенного этим скриптом;
  * запуск требует явного подтверждения через переменную окружения
    ``VAPEFREE_ALLOW_DEV_LOGIN=1``.

Запуск:
    VAPEFREE_ALLOW_DEV_LOGIN=1 python tools/dev_shot.py [--port 8078]
    python tools/dev_shot.py --anonymous      # публичные страницы, без подмены
"""

from __future__ import annotations

import argparse
import os
import random
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app import deps  # noqa: E402
from app.db import Session, SessionLocal, get_session, init_db  # noqa: E402
from app.main import app  # noqa: E402
from app.models import CheckIn, LapseEvent, Profile, User  # noqa: E402
from app.security import hash_password  # noqa: E402
from fastapi import Depends, Request  # noqa: E402

DEMO_EMAIL = "demo-screenshots@vapefree.local"


def seed() -> int:
    """Создать (или переиспользовать) демо-пользователя с историей."""
    init_db()
    session = SessionLocal()
    try:
        user = session.query(User).filter(User.email == DEMO_EMAIL).one_or_none()
        if user is None:
            user = User(email=DEMO_EMAIL, password_hash=hash_password("demo-pass-1"), display_name="Алексей")
            session.add(user)
            session.flush()
            session.add(
                Profile(
                    user_id=user.id,
                    quit_at=datetime.utcnow() - timedelta(days=52, hours=7),
                    vape_years=3.5,
                    pods_per_day=1.5,
                    pod_volume_ml=2.0,
                    nicotine_strength=30.0,
                    nicotine_type="salt",
                    age=34,
                    sex="male",
                    height_cm=178.0,
                    weight_kg=84.0,
                    activity="moderate",
                    chronic_json='["hypertension"]',
                    onboarding_completed=True,
                )
            )
            session.add(
                LapseEvent(
                    user_id=user.id,
                    occurred_at=datetime.utcnow() - timedelta(days=11, hours=4),
                    severity="episode",
                    note="Стресс на работе",
                )
            )
            session.flush()

            rng = random.Random(7)
            for offset in range(20, -1, -1):
                day = date.today() - timedelta(days=offset)
                if rng.random() < 0.12:
                    continue
                progress = (20 - offset) / 20
                session.add(
                    CheckIn(
                        user_id=user.id,
                        day=day,
                        mood=max(1, min(10, int(round(4.5 + progress * 4 + rng.uniform(-1, 1))))),
                        craving=max(1, min(10, int(round(8.5 - progress * 5 + rng.uniform(-1, 1))))),
                        sleep_hours=round(max(3.5, min(9.5, 5.6 + progress * 2.4 + rng.uniform(-0.7, 0.7))), 1),
                        sleep_quality=max(1, min(5, int(round(2 + progress * 2.5)))),
                        water_glasses=rng.randint(4, 9),
                        activity_minutes=rng.choice([0, 15, 20, 30, 45, 60]),
                        breathing_sessions=rng.choice([0, 0, 1, 1, 2, 3]),
                        note="",
                        points=rng.randint(8, 26),
                    )
                )
            session.commit()
        return user.id
    finally:
        session.close()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=8078)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument(
        "--anonymous",
        action="store_true",
        help="не подменять пользователя — для скриншотов публичных страниц",
    )
    args = parser.parse_args()

    if args.anonymous:
        print("Режим анонимного просмотра (публичные страницы)", flush=True)
        import uvicorn

        print(f"QA-сервер: http://{args.host}:{args.port}", flush=True)
        uvicorn.run(app, host=args.host, port=args.port, log_level="warning")
        return 0

    # Защита от случайного запуска: подмена аутентификации требует явного согласия.
    if os.environ.get("VAPEFREE_ALLOW_DEV_LOGIN") != "1":
        print(
            "Отказ в запуске.\n\n"
            "Этот скрипт выдаёт доступ под демо-пользователем без пароля и предназначен\n"
            "только для локального снятия скриншотов. Чтобы подтвердить намерение, задайте\n"
            "переменную окружения:\n\n"
            "    VAPEFREE_ALLOW_DEV_LOGIN=1 python tools/dev_shot.py\n\n"
            "Для просмотра публичных страниц без подмены используйте --anonymous.\n",
            file=sys.stderr,
        )
        return 2

    user_id = seed()
    print(f"Демо-пользователь id={user_id}", flush=True)

    def override_current_user(request: Request, session: Session = Depends(get_session)):  # noqa: ARG001
        """Подмена зависимости: всегда возвращаем демо-пользователя.

        Важно: `Request`, `Session` и `Depends` импортированы на уровне модуля.
        Из-за `from __future__ import annotations` аннотации становятся строками,
        и FastAPI разбирает их через get_type_hints в глобальном пространстве
        модуля — локальные импорты там не видны, и `request` был бы принят за
        query-параметр.
        """
        return session.get(User, user_id)

    app.dependency_overrides[deps.current_user] = override_current_user

    import uvicorn

    print(f"QA-сервер: http://{args.host}:{args.port}", flush=True)
    uvicorn.run(app, host=args.host, port=args.port, log_level="warning")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
