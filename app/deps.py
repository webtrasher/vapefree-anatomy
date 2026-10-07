"""Зависимости FastAPI: текущий пользователь, обязательная авторизация."""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends, Request
from sqlalchemy.orm import Session

from .db import get_session
from .models import User

SessionDep = Annotated[Session, Depends(get_session)]


def current_user(request: Request, session: SessionDep) -> User | None:
    """Пользователь из подписанной сессионной cookie или None."""
    user_id = request.session.get("user_id")
    if not user_id:
        return None
    user = session.get(User, int(user_id))
    if user is None:
        request.session.clear()
    return user


CurrentUser = Annotated[User | None, Depends(current_user)]


def login_redirect(next_url: str = "/") -> str:
    return f"/login?next={next_url}"
