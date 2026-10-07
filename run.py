"""Запуск приложения: python run.py

Переменные окружения:
    HOST            адрес (по умолчанию 127.0.0.1)
    PORT            порт (по умолчанию 8000)
    RELOAD          "1" — автоперезапуск при изменении кода
    VAPEFREE_DATABASE_URL   строка подключения SQLAlchemy
    VAPEFREE_SECRET_KEY     ключ подписи сессий
"""

from __future__ import annotations

import os

import uvicorn


def main() -> None:
    host = os.environ.get("HOST", "127.0.0.1")
    port = int(os.environ.get("PORT", "8000"))
    reload_enabled = os.environ.get("RELOAD", "0") == "1"

    print(f"VapeFree Anatomy -> http://{host}:{port}")
    uvicorn.run(
        "app.main:app",
        host=host,
        port=port,
        reload=reload_enabled,
        log_level=os.environ.get("LOG_LEVEL", "info"),
    )


if __name__ == "__main__":
    main()
