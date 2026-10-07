"""Точка входа FastAPI-приложения VapeFree Anatomy."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.gzip import GZipMiddleware
from starlette.middleware.sessions import SessionMiddleware

from .config import APP_DIR, APP_NAME, APP_TAGLINE, SESSION_COOKIE, SESSION_MAX_AGE, SECRET_KEY
from .db import init_db
from .routers import api, auth, pages
from .templating import templates

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("vapefree")


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    logger.info("%s запущен", APP_NAME)
    yield


app = FastAPI(
    title=APP_NAME,
    description=APP_TAGLINE,
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(GZipMiddleware, minimum_size=800)
app.add_middleware(
    SessionMiddleware,
    secret_key=SECRET_KEY,
    session_cookie=SESSION_COOKIE,
    max_age=SESSION_MAX_AGE,
    same_site="lax",
    https_only=False,
)

app.mount("/static", StaticFiles(directory=str(APP_DIR / "static")), name="static")

app.include_router(auth.router)
app.include_router(pages.router)
app.include_router(api.router)


@app.get("/healthz", include_in_schema=False)
def healthz():
    return {"status": "ok", "app": APP_NAME}


@app.get("/manifest.webmanifest", include_in_schema=False)
def manifest():
    from .config import APP_NAME as name

    return JSONResponse(
        {
            "name": name,
            "short_name": "VapeFree",
            "description": APP_TAGLINE,
            "start_url": "/",
            "scope": "/",
            "display": "standalone",
            "orientation": "portrait",
            "background_color": "#F7FBFC",
            "theme_color": "#7FB894",
            "lang": "ru",
            "icons": [
                {"src": "/static/icons/icon-192.png", "sizes": "192x192", "type": "image/png", "purpose": "any"},
                {"src": "/static/icons/icon-512.png", "sizes": "512x512", "type": "image/png", "purpose": "any"},
                {"src": "/static/icons/icon-maskable-512.png", "sizes": "512x512", "type": "image/png", "purpose": "maskable"},
            ],
            "shortcuts": [
                {"name": "Чек-ин", "url": "/checkin"},
                {"name": "Дыхание 4-7-8", "url": "/breathing"},
            ],
        }
    )


@app.get("/sw.js", include_in_schema=False)
def service_worker():
    """Service worker отдаётся с корня, чтобы область видимости была '/'."""
    from .config import APP_DIR as _APP_DIR

    content = (_APP_DIR / "static" / "sw.js").read_text(encoding="utf-8")
    return HTMLResponse(
        content,
        media_type="application/javascript",
        headers={"Cache-Control": "no-cache", "Service-Worker-Allowed": "/"},
    )


@app.exception_handler(404)
async def not_found(request: Request, exc):  # noqa: ARG001
    if request.url.path.startswith("/api/"):
        return JSONResponse({"error": "not_found"}, status_code=404)
    return templates.TemplateResponse(
        request, "error.html", {"user": None, "code": 404, "message": "Страница не найдена"}, status_code=404
    )


@app.exception_handler(500)
async def server_error(request: Request, exc):  # noqa: ARG001
    logger.exception("Внутренняя ошибка")
    if request.url.path.startswith("/api/"):
        return JSONResponse({"error": "internal"}, status_code=500)
    return templates.TemplateResponse(
        request,
        "error.html",
        {"user": None, "code": 500, "message": "Внутренняя ошибка сервера"},
        status_code=500,
    )


@app.get("/favicon.ico", include_in_schema=False)
def favicon():
    return RedirectResponse("/static/icons/icon-192.png")
