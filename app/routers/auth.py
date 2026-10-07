"""Регистрация, вход и выход."""

from __future__ import annotations

from fastapi import APIRouter, Form, Request, status
from fastapi.responses import RedirectResponse
from sqlalchemy import select

from ..deps import CurrentUser, SessionDep
from ..models import Profile, User
from ..security import (
    PasswordPolicyError,
    check_password_policy,
    hash_password,
    normalize_email,
    validate_email,
    verify_password,
)
from ..templating import templates

router = APIRouter(tags=["auth"])


def _safe_next(value: str | None) -> str:
    """Разрешить только внутренние переходы (защита от open redirect)."""
    if value and value.startswith("/") and not value.startswith("//"):
        return value
    return "/"


@router.get("/register")
def register_form(request: Request, user: CurrentUser):
    if user is not None:
        return RedirectResponse("/", status_code=status.HTTP_303_SEE_OTHER)
    return templates.TemplateResponse(
        request, "register.html", {"user": None, "next": _safe_next(request.query_params.get("next"))}
    )


@router.post("/register")
def register_submit(
    request: Request,
    session: SessionDep,
    email: str = Form(""),
    password: str = Form(""),
    password2: str = Form(""),
    display_name: str = Form(""),
    next_url: str = Form("/onboarding", alias="next"),
):
    email = normalize_email(email)
    errors: list[str] = []

    if not validate_email(email):
        errors.append("Укажите корректный адрес электронной почты")
    if password != password2:
        errors.append("Пароли не совпадают")
    try:
        check_password_policy(password)
    except PasswordPolicyError as exc:
        errors.append(str(exc))

    existing = session.execute(select(User).where(User.email == email)).scalar_one_or_none()
    if existing is not None:
        errors.append("Пользователь с такой почтой уже зарегистрирован")

    if errors:
        return templates.TemplateResponse(
            request,
            "register.html",
            {
                "user": None,
                "errors": errors,
                "email": email,
                "display_name": display_name,
                "next": _safe_next(next_url),
            },
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    user = User(
        email=email,
        password_hash=hash_password(password),
        display_name=(display_name or "").strip()[:120],
    )
    session.add(user)
    session.flush()
    session.add(Profile(user_id=user.id))
    session.commit()

    request.session.clear()
    request.session["user_id"] = user.id
    return RedirectResponse(_safe_next(next_url), status_code=status.HTTP_303_SEE_OTHER)


@router.get("/login")
def login_form(request: Request, user: CurrentUser):
    if user is not None:
        return RedirectResponse("/", status_code=status.HTTP_303_SEE_OTHER)
    return templates.TemplateResponse(
        request, "login.html", {"user": None, "next": _safe_next(request.query_params.get("next"))}
    )


@router.post("/login")
def login_submit(
    request: Request,
    session: SessionDep,
    email: str = Form(""),
    password: str = Form(""),
    next_url: str = Form("/", alias="next"),
):
    email = normalize_email(email)
    user = session.execute(select(User).where(User.email == email)).scalar_one_or_none()

    if user is None or not verify_password(password, user.password_hash):
        return templates.TemplateResponse(
            request,
            "login.html",
            {
                "user": None,
                "errors": ["Неверная почта или пароль"],
                "email": email,
                "next": _safe_next(next_url),
            },
            status_code=status.HTTP_401_UNAUTHORIZED,
        )

    request.session.clear()
    request.session["user_id"] = user.id
    target = _safe_next(next_url)
    if target == "/" and (user.profile is None or not user.profile.onboarding_completed):
        target = "/onboarding"
    return RedirectResponse(target, status_code=status.HTTP_303_SEE_OTHER)


@router.post("/logout")
def logout(request: Request):
    request.session.clear()
    return RedirectResponse("/", status_code=status.HTTP_303_SEE_OTHER)
