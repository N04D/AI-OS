from __future__ import annotations


def disable_core_dumps_best_effort() -> bool:
    """Best-effort core dump disabling for Unix-like platforms."""
    try:
        import resource  # Unix-only module

        resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
        return True
    except Exception:
        return False
