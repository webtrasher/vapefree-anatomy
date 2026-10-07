"""Общая настройка тестов: изолированная БД и ключ сессий."""

from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# Переменные окружения должны быть заданы до импорта app.config.
_TMP = Path(tempfile.mkdtemp(prefix="vapefree-tests-"))
os.environ.setdefault("VAPEFREE_DATA_DIR", str(_TMP))
os.environ.setdefault("VAPEFREE_DATABASE_URL", f"sqlite:///{(_TMP / 'test.db').as_posix()}")
os.environ.setdefault("VAPEFREE_SECRET_KEY", "test-secret-key-not-for-production")
