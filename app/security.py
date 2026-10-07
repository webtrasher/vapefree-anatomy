"""Хеширование паролей и работа с сессией.

Используется только стандартная библиотека: PBKDF2-HMAC-SHA256. Это снимает
зависимость от bcrypt/argon2, которые требуют нативной сборки.
"""

from __future__ import annotations

import hashlib
import hmac
import re
import secrets

ALGORITHM = "pbkdf2_sha256"
ITERATIONS = 240_000
SALT_BYTES = 16

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[A-Za-z]{2,}$")


def hash_password(password: str, *, iterations: int = ITERATIONS) -> str:
    """Вернуть строку вида pbkdf2_sha256$iterations$salt$hash."""
    salt = secrets.token_bytes(SALT_BYTES)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations)
    return f"{ALGORITHM}${iterations}${salt.hex()}${digest.hex()}"


def verify_password(password: str, stored: str) -> bool:
    """Проверить пароль, устойчиво к повреждённому формату хеша."""
    try:
        algorithm, iterations_s, salt_hex, digest_hex = stored.split("$")
        if algorithm != ALGORITHM:
            return False
        iterations = int(iterations_s)
        salt = bytes.fromhex(salt_hex)
        expected = bytes.fromhex(digest_hex)
    except (ValueError, AttributeError):
        return False
    actual = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations)
    return hmac.compare_digest(actual, expected)


def validate_email(email: str) -> bool:
    return bool(EMAIL_RE.match((email or "").strip()))


def normalize_email(email: str) -> str:
    return (email or "").strip().lower()


class PasswordPolicyError(ValueError):
    pass


def check_password_policy(password: str) -> None:
    """Минимальные требования: 8+ символов, буква и цифра."""
    if len(password or "") < 8:
        raise PasswordPolicyError("Пароль должен быть не короче 8 символов")
    if not re.search(r"[A-Za-zА-Яа-я]", password):
        raise PasswordPolicyError("Пароль должен содержать хотя бы одну букву")
    if not re.search(r"\d", password):
        raise PasswordPolicyError("Пароль должен содержать хотя бы одну цифру")
