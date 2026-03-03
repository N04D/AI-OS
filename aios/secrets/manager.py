from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .audit import AuditLogger
from .budget_sink import BudgetChargeSink
from .budget_sink import BudgetSink
from .budget_gate import BudgetGate
from .backends.encrypted_store_backend import EncryptedStoreBackend
from .backends.keyring_backend import KeyringBackend
from .hardening import disable_core_dumps_best_effort
from .policy import allow_fallback_lookup
from .policy import is_capability_allowed
from .context import ContextFactory
from .context import SecretAccessContext
from .rate_limits import FixedWindowRateLimiter
from .types import AccessDenied
from .types import BackendUnavailable
from .types import NotInitialized
from .types import SecretKey
from .types import SecretValue
from .types import SecretsError


@dataclass
class MigrateReport:
    moved: int
    failed: int
    details: list[str]


class SecretsManager:
    """Single API entrypoint for all secret access in AI-OS."""

    def __init__(
        self,
        *,
        keyring_backend: KeyringBackend | None = None,
        fallback_backend: EncryptedStoreBackend | None = None,
        fallback_passphrase: str | None = None,
        data_dir: Path | None = None,
        rate_limiter: FixedWindowRateLimiter | None = None,
        disable_core_dumps: bool = False,
        budget_mode: str = "off",
        observe_budget_charges: bool = False,
        budget_sink: BudgetSink | None = None,
        budget_gate: BudgetGate | None = None,
    ) -> None:
        base = data_dir or (Path.home() / ".local" / "share" / "aios" / "secrets")
        self._core_dumps_disabled = disable_core_dumps_best_effort() if disable_core_dumps else False
        self._audit = AuditLogger(path=base / "audit.jsonl")
        if budget_mode not in {"off", "observe", "enforce"}:
            raise ValueError("budget_mode must be one of: off, observe, enforce")
        self._budget_mode = "observe" if observe_budget_charges and budget_mode == "off" else budget_mode
        self._observe_budget_charges = self._budget_mode in {"observe", "enforce"}
        self._budget_sink = budget_sink or BudgetChargeSink(path=base / "budget_events.jsonl")
        self._budget_gate = budget_gate or BudgetGate(mode=self._budget_mode, sink=self._budget_sink)
        self._fallback = fallback_backend or EncryptedStoreBackend(store_path=base / "store.v1")
        self._keyring = keyring_backend
        self._rate_limiter = rate_limiter or FixedWindowRateLimiter()
        self._last_error: str | None = None
        self._fallback_passphrase = fallback_passphrase
        if self._keyring is None:
            try:
                self._keyring = KeyringBackend(service_name="aios")
            except BackendUnavailable as exc:
                self._keyring = None
                self._last_error = str(exc)

    def set_fallback_passphrase(self, passphrase: str | None) -> None:
        self._fallback_passphrase = passphrase

    def _require_fallback_passphrase(self) -> str:
        if not self._fallback_passphrase:
            raise NotInitialized(
                "Fallback passphrase missing. Run 'aiosctl secrets init-fallback' or provide passphrase in command flow."
            )
        return self._fallback_passphrase

    def _keyring_available(self) -> bool:
        return self._keyring is not None and self._keyring.is_available()

    def _get_from_fallback(self, key: SecretKey) -> SecretValue | None:
        passphrase = self._require_fallback_passphrase()
        return self._fallback.get(key, passphrase=passphrase)

    def _list_from_fallback(self, prefix: str | None = None) -> list[SecretKey]:
        passphrase = self._require_fallback_passphrase()
        return self._fallback.list(prefix=prefix, passphrase=passphrase)

    def set(self, key: SecretKey, value: SecretValue, *, overwrite: bool = False) -> None:
        used_backend = "unknown"
        try:
            if self._keyring_available():
                assert self._keyring is not None
                self._keyring.set(key, value, overwrite=overwrite)
                used_backend = self._keyring.backend_name
                self._last_error = None
            elif self._fallback.is_initialized():
                passphrase = self._require_fallback_passphrase()
                self._fallback.set(key, value, overwrite=overwrite, passphrase=passphrase)
                used_backend = self._fallback.backend_name
                self._last_error = "KEYRING_UNAVAILABLE_FALLBACK_USED"
            else:
                raise BackendUnavailable(
                    "No secrets backend available. Configure OS keyring or run 'aiosctl secrets init-fallback'."
                )
            self._audit.log(action="set", key=key.as_str(), backend=used_backend, result="ok")
        except Exception as exc:
            self._last_error = str(exc)
            self._audit.log(
                action="backend_error",
                key=key.as_str(),
                backend=used_backend,
                result="error",
                error_code=exc.__class__.__name__,
            )
            raise

    def get(self, key: SecretKey, *, context: SecretAccessContext) -> SecretValue | None:
        ContextFactory.validate(context)
        if not is_capability_allowed(key, context):
            self._audit.log(
                action="get",
                key=key.as_str(),
                backend="policy",
                result="denied",
                error_code="AccessDenied",
            )
            raise AccessDenied(
                f"Capability context '{context.context_id}' is not authorized for key '{key.as_str()}'."
            )
        decision = self._rate_limiter.check_and_increment(
            classification=context.trust_level,
            bucket=context.context_id,
        )
        if not decision.allowed:
            self._audit.log(
                action="get",
                key=key.as_str(),
                backend="rate_limiter",
                result="denied",
                error_code="RATE_LIMIT_EXCEEDED",
            )
            if decision.anomaly:
                self._audit.log(
                    action="backend_error",
                    key=key.as_str(),
                    backend="rate_limiter",
                    result="error",
                    error_code="ANOMALY_SPIKE_DETECTED",
                )
            raise AccessDenied(
                f"Rate limit exceeded for context '{context.context_id}'. Retry in next window."
            )
        if self._observe_budget_charges:
            budget_decision = self._budget_gate.evaluate_and_charge(key=key, context=context, operation="get")
            if not budget_decision.allowed:
                self._audit.log(
                    action="get",
                    key=key.as_str(),
                    backend="budget_gate",
                    result="denied",
                    error_code=str(budget_decision.reason_code or "BUDGET_EXCEEDED"),
                )
                raise AccessDenied("Budget policy denied secret retrieval")

        used_backend = "unknown"
        try:
            if self._keyring_available():
                assert self._keyring is not None
                found = self._keyring.get(key)
                used_backend = self._keyring.backend_name
                if found is not None:
                    self._audit.log(action="get", key=key.as_str(), backend=used_backend, result="ok")
                    return found
                if self._fallback.is_initialized() and allow_fallback_lookup(key, context):
                    out = self._get_from_fallback(key)
                    self._audit.log(
                        action="get",
                        key=key.as_str(),
                        backend=self._fallback.backend_name,
                        result="ok" if out is not None else "missing",
                    )
                    return out
                self._audit.log(action="get", key=key.as_str(), backend=used_backend, result="missing")
                return None
            if self._fallback.is_initialized():
                out = self._get_from_fallback(key)
                self._audit.log(
                    action="get",
                    key=key.as_str(),
                    backend=self._fallback.backend_name,
                    result="ok" if out is not None else "missing",
                )
                return out
            raise BackendUnavailable(
                "No secrets backend available. Configure OS keyring or run 'aiosctl secrets init-fallback'."
            )
        except Exception as exc:
            self._last_error = str(exc)
            self._audit.log(
                action="backend_error",
                key=key.as_str(),
                backend=used_backend,
                result="error",
                error_code=exc.__class__.__name__,
            )
            raise

    def delete(self, key: SecretKey) -> None:
        used_backend = "unknown"
        try:
            if self._keyring_available():
                assert self._keyring is not None
                self._keyring.delete(key)
                used_backend = self._keyring.backend_name
            elif self._fallback.is_initialized():
                passphrase = self._require_fallback_passphrase()
                self._fallback.delete(key, passphrase=passphrase)
                used_backend = self._fallback.backend_name
            else:
                raise BackendUnavailable(
                    "No secrets backend available. Configure OS keyring or run 'aiosctl secrets init-fallback'."
                )
            self._audit.log(action="delete", key=key.as_str(), backend=used_backend, result="ok")
        except Exception as exc:
            self._last_error = str(exc)
            self._audit.log(
                action="backend_error",
                key=key.as_str(),
                backend=used_backend,
                result="error",
                error_code=exc.__class__.__name__,
            )
            raise

    def list(self, prefix: str | None = None) -> list[SecretKey]:
        if self._keyring_available():
            assert self._keyring is not None
            out = self._keyring.list(prefix=prefix)
            self._audit.log(action="list", key=prefix, backend=self._keyring.backend_name, result="ok")
            return out
        if self._fallback.is_initialized():
            out = self._list_from_fallback(prefix=prefix)
            self._audit.log(action="list", key=prefix, backend=self._fallback.backend_name, result="ok")
            return out
        raise BackendUnavailable("No backend available. Configure keyring or initialize fallback store.")

    def status(self) -> dict[str, Any]:
        keyring_available = self._keyring_available()
        fallback_initialized = self._fallback.is_initialized()
        backend = "keyring" if keyring_available else ("encrypted_store" if fallback_initialized else "none")
        return {
            "backend": backend,
            "initialized": bool(keyring_available or fallback_initialized),
            "keyring_available": keyring_available,
            "fallback_initialized": fallback_initialized,
            "core_dumps_disabled": self._core_dumps_disabled,
            "budget_mode": self._budget_mode,
            "observe_budget_charges": self._observe_budget_charges,
            "last_error": self._last_error,
        }

    def init_fallback(self, passphrase: str) -> None:
        self._fallback.init(passphrase=passphrase)
        self._fallback_passphrase = passphrase
        self._audit.log(action="init", key=None, backend=self._fallback.backend_name, result="ok")

    def rotate_fallback_passphrase(self, old: str, new: str) -> None:
        self._fallback.rotate_passphrase(old, new)
        self._fallback_passphrase = new
        self._audit.log(action="rotate", key=None, backend=self._fallback.backend_name, result="ok")

    def migrate_to_keyring(self) -> dict[str, Any]:
        if not self._keyring_available():
            raise BackendUnavailable("Keyring backend unavailable. Start desktop keychain session and retry.")
        if not self._fallback.is_initialized():
            return {"moved": 0, "failed": 0, "details": []}

        assert self._keyring is not None
        passphrase = self._require_fallback_passphrase()
        keys = self._fallback.list(passphrase=passphrase)
        moved = 0
        failed = 0
        details: list[str] = []
        for key in keys:
            try:
                value = self._fallback.get(key, passphrase=passphrase)
                if value is None:
                    continue
                self._keyring.set(key, value, overwrite=True)
                self._fallback.delete(key, passphrase=passphrase)
                moved += 1
            except Exception as exc:
                failed += 1
                details.append(f"{key.as_str()}:{exc.__class__.__name__}")
        self._audit.log(
            action="migrate",
            key=None,
            backend=f"{self._fallback.backend_name}->{self._keyring.backend_name}",
            result="ok" if failed == 0 else "partial",
            error_code="MIGRATION_PARTIAL" if failed else None,
        )
        return {"moved": moved, "failed": failed, "details": details}
