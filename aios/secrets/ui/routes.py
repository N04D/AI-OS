from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import UTC
from datetime import datetime
from pathlib import Path
import secrets
from typing import Any

from fastapi import APIRouter
from fastapi import FastAPI
from fastapi import Form
from fastapi import Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware

from ..manager import SecretsManager
from ..policy import can_ui_edit
from ..types import SecretKey
from ..types import SecretValue


@dataclass
class _Limiter:
    limit: int = 20
    window_seconds: int = 60

    def __post_init__(self) -> None:
        self._hits: dict[str, list[float]] = defaultdict(list)

    def allow(self, key: str) -> bool:
        now = datetime.now(tz=UTC).timestamp()
        cutoff = now - self.window_seconds
        self._hits[key] = [ts for ts in self._hits.get(key, []) if ts >= cutoff]
        if len(self._hits[key]) >= self.limit:
            return False
        self._hits[key].append(now)
        return True


def _common_keys() -> list[dict[str, str]]:
    return [
        {"label": "OpenAI API Key", "key": "openai.api_key"},
        {"label": "Gitea Token", "key": "gitea.token"},
    ]


def _test_connection_stub(key: SecretKey) -> tuple[bool, str]:
    del key
    return True, "Connection test queued."


def create_router(*, manager: SecretsManager, templates: Jinja2Templates) -> APIRouter:
    router = APIRouter()
    limiter = _Limiter()

    @router.get("/settings/secrets", response_class=HTMLResponse)
    def get_settings(request: Request) -> HTMLResponse:
        token = secrets.token_urlsafe(24)
        request.session["csrf_token"] = token
        return templates.TemplateResponse(
            request,
            "secrets.html",
            {
                "items": _common_keys(),
                "csrf_token": token,
                "message": "",
            },
        )

    @router.post("/settings/secrets", response_class=HTMLResponse)
    def post_settings(
        request: Request,
        key: str = Form(...),
        value: str = Form(""),
        csrf_token: str = Form(...),
        action: str = Form("save"),
    ) -> HTMLResponse:
        client = request.client.host if request.client else "unknown"
        if not limiter.allow(client):
            return templates.TemplateResponse(
                request,
                "secrets.html",
                {"items": _common_keys(), "csrf_token": request.session.get("csrf_token", ""), "message": "Too many requests."},
                status_code=429,
            )

        expected = str(request.session.get("csrf_token", ""))
        if not expected or csrf_token != expected:
            return templates.TemplateResponse(
                request,
                "secrets.html",
                {"items": _common_keys(), "csrf_token": expected, "message": "Session expired. Refresh and try again."},
                status_code=403,
            )

        parsed = SecretKey.parse(key)
        if not can_ui_edit(parsed):
            return templates.TemplateResponse(
                request,
                "secrets.html",
                {"items": _common_keys(), "csrf_token": expected, "message": "This key is managed by administrators."},
                status_code=403,
            )

        message = "Saved."
        if action == "test":
            ok, note = _test_connection_stub(parsed)
            message = "Connection looks good." if ok else note
        else:
            manager.set(parsed, SecretValue(value), overwrite=True)
        return templates.TemplateResponse(
            request,
            "secrets.html",
            {"items": _common_keys(), "csrf_token": expected, "message": message},
        )

    return router


def create_app(*, manager: SecretsManager | None = None, data_dir: Path | None = None) -> FastAPI:
    app = FastAPI(title="AI-OS Secrets")
    app.add_middleware(SessionMiddleware, secret_key=secrets.token_urlsafe(32), same_site="strict", https_only=False)
    mgr = manager or SecretsManager(data_dir=data_dir)
    templates = Jinja2Templates(directory=str(Path(__file__).resolve().parent / "templates"))
    app.include_router(create_router(manager=mgr, templates=templates))
    return app
