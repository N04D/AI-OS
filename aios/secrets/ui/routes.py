from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import UTC
from datetime import datetime
from pathlib import Path
import secrets

from fastapi import APIRouter
from fastapi import FastAPI
from fastapi import Form
from fastapi import Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware

from ..context import ContextFactory
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
        {"label": "OpenAI API Key", "key": "openai.api_key", "placeholder": "sk-...", "multiline": "false"},
        {"label": "Gitea Token", "key": "gitea.token", "placeholder": "Paste token", "multiline": "false"},
        {
            "label": "Gitea SSH Private Key",
            "key": "gitea.ssh_private_key",
            "placeholder": "-----BEGIN OPENSSH PRIVATE KEY-----",
            "multiline": "true",
        },
        {"label": "Email SMTP Password", "key": "smtp.pass", "placeholder": "Paste SMTP password", "multiline": "false"},
        {
            "label": "GitHub Personal Token",
            "key": "github.personal.token",
            "placeholder": "ghp_... or github_pat_...",
            "multiline": "false",
        },
        {
            "label": "GitHub Work Token",
            "key": "github.work.token",
            "placeholder": "ghp_... or github_pat_...",
            "multiline": "false",
        },
    ]


def _resolve_test_secret(*, manager: SecretsManager, key: SecretKey, submitted_value: str) -> str:
    candidate = submitted_value.strip()
    if candidate:
        return candidate
    stored = manager.get(key, context=ContextFactory.ui_test_connection())
    if stored is None:
        return ""
    return stored.as_str().strip()


def _test_connection(key: SecretKey, *, secret_value: str) -> tuple[bool, str]:
    if not secret_value:
        return False, "No key available to test. Paste a key or save one first."
    raw = key.as_str()
    if raw == "openai.api_key":
        if not secret_value.startswith("sk-"):
            return False, "OpenAI key format looks invalid (expected prefix 'sk-')."
        return True, "OpenAI key format looks valid."
    if raw == "gitea.token":
        if len(secret_value) < 8:
            return False, "Gitea token format looks too short."
        return True, "Gitea token format looks valid."
    if raw == "gitea.ssh_private_key":
        if "BEGIN OPENSSH PRIVATE KEY" in secret_value or "BEGIN RSA PRIVATE KEY" in secret_value:
            return True, "SSH private key format looks valid."
        return False, "SSH key format looks invalid (missing private-key header)."
    if raw == "smtp.pass":
        if len(secret_value) < 6:
            return False, "SMTP password looks too short."
        return True, "SMTP password format looks valid."
    if raw in {"github.personal.token", "github.work.token"}:
        if secret_value.startswith("ghp_") or secret_value.startswith("github_pat_"):
            return True, "GitHub token format looks valid."
        return False, "GitHub token format looks invalid (expected ghp_ or github_pat_)."
    return False, "Connection test is not available for this key."


def _render(
    *,
    request: Request,
    templates: Jinja2Templates,
    manager: SecretsManager,
    csrf_token: str,
    message: str,
    message_kind: str = "info",
    status_code: int = 200,
) -> HTMLResponse:
    status = manager.status()
    return templates.TemplateResponse(
        request,
        "secrets.html",
        {
            "items": _common_keys(),
            "csrf_token": csrf_token,
            "message": message,
            "backend": status.get("backend", "none"),
            "keyring_available": bool(status.get("keyring_available", False)),
            "message_kind": message_kind,
        },
        status_code=status_code,
    )


def create_router(*, manager: SecretsManager, templates: Jinja2Templates) -> APIRouter:
    router = APIRouter()
    limiter = _Limiter()

    @router.get("/settings/secrets", response_class=HTMLResponse)
    def get_settings(request: Request) -> HTMLResponse:
        token = secrets.token_urlsafe(24)
        request.session["csrf_token"] = token
        return _render(request=request, templates=templates, manager=manager, csrf_token=token, message="")

    @router.post("/settings/secrets", response_class=HTMLResponse)
    def post_settings(
        request: Request,
        key: str = Form(...),
        secret_value: str = Form("", alias="secret_value"),
        value: str = Form(""),
        csrf_token: str = Form(...),
        action: str = Form("save"),
    ) -> HTMLResponse:
        submitted_value = secret_value or value
        client = request.client.host if request.client else "unknown"
        if not limiter.allow(client):
            return _render(
                request=request,
                templates=templates,
                manager=manager,
                csrf_token=str(request.session.get("csrf_token", "")),
                message="Too many requests.",
                message_kind="error",
                status_code=429,
            )

        expected = str(request.session.get("csrf_token", ""))
        if not expected or csrf_token != expected:
            return _render(
                request=request,
                templates=templates,
                manager=manager,
                csrf_token=expected,
                message="Session expired. Refresh and try again.",
                message_kind="error",
                status_code=403,
            )

        parsed = SecretKey.parse(key)
        if not can_ui_edit(parsed):
            return _render(
                request=request,
                templates=templates,
                manager=manager,
                csrf_token=expected,
                message="This key is managed by administrators.",
                message_kind="error",
                status_code=403,
            )

        message = "Saved to OS keyring."
        message_kind = "success"
        status_code = 200
        if action == "test":
            test_value = _resolve_test_secret(manager=manager, key=parsed, submitted_value=submitted_value)
            ok, note = _test_connection(parsed, secret_value=test_value)
            message = note
            message_kind = "success" if ok else "error"
            status_code = 200 if ok else 400
        else:
            status = manager.status()
            if not bool(status.get("keyring_available", False)):
                return _render(
                    request=request,
                    templates=templates,
                    manager=manager,
                    csrf_token=expected,
                    message="OS keyring unavailable. Unlock or configure keyring; UI save is keyring-only.",
                    message_kind="error",
                    status_code=503,
                )
            clean_value = submitted_value.strip()
            if not clean_value:
                return _render(
                    request=request,
                    templates=templates,
                    manager=manager,
                    csrf_token=expected,
                    message="Value is required.",
                    message_kind="error",
                    status_code=400,
                )
            manager.set(parsed, SecretValue(clean_value), overwrite=True)
        return _render(
            request=request,
            templates=templates,
            manager=manager,
            csrf_token=expected,
            message=message,
            message_kind=message_kind,
            status_code=status_code,
        )

    return router


def create_app(*, manager: SecretsManager | None = None, data_dir: Path | None = None) -> FastAPI:
    app = FastAPI(title="AI-OS Secrets")
    app.add_middleware(SessionMiddleware, secret_key=secrets.token_urlsafe(32), same_site="strict", https_only=False)
    mgr = manager or SecretsManager(data_dir=data_dir)
    templates = Jinja2Templates(directory=str(Path(__file__).resolve().parent / "templates"))
    app.include_router(create_router(manager=mgr, templates=templates))
    return app
