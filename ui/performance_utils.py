"""Lightweight helpers for tracking UI operation timings."""

from __future__ import annotations

from contextlib import contextmanager
from time import perf_counter
from typing import Iterator

PROFILE_HISTORY_LIMIT = 50
PROFILE_PRINT_THRESHOLD_MS = 250.0


def _get_profile_history(window) -> list[dict]:
    history = getattr(window, "_ui_profile_history", None)
    if history is None:
        history = []
        setattr(window, "_ui_profile_history", history)
    return history


def _get_pending_spans(window) -> dict[int, dict]:
    pending = getattr(window, "_ui_profile_pending", None)
    if pending is None:
        pending = {}
        setattr(window, "_ui_profile_pending", pending)
    return pending


def _normalize_details(details: dict) -> dict:
    return {
        key: value
        for key, value in details.items()
        if value is not None
    }


def _format_profile_details(details: dict) -> str:
    if not details:
        return ""
    parts = [f"{key}={details[key]!r}" for key in sorted(details)]
    return " " + " ".join(parts)


def begin_profile_span(window, operation: str, **details) -> int:
    """Start tracking a potentially long-running UI operation."""
    pending = _get_pending_spans(window)
    next_token = getattr(window, "_ui_profile_next_token", 0) + 1
    setattr(window, "_ui_profile_next_token", next_token)
    pending[next_token] = {
        "operation": operation,
        "details": _normalize_details(details),
        "started_at": perf_counter(),
    }
    return next_token


def finish_profile_span(window, token: int | None, *, outcome: str = "ok") -> dict | None:
    """Finish tracking an operation and store the elapsed timing."""
    if token is None:
        return None

    pending = _get_pending_spans(window)
    span = pending.pop(token, None)
    if span is None:
        return None

    entry = {
        "operation": span["operation"],
        "elapsed_ms": (perf_counter() - span["started_at"]) * 1000.0,
        "outcome": outcome,
        "details": span["details"],
    }

    history = _get_profile_history(window)
    history.append(entry)
    overflow = len(history) - PROFILE_HISTORY_LIMIT
    if overflow > 0:
        del history[:overflow]

    if entry["elapsed_ms"] >= PROFILE_PRINT_THRESHOLD_MS:
        print(
            f"[PROFILE] {entry['operation']} {entry['elapsed_ms']:.1f}ms "
            f"outcome={entry['outcome']}{_format_profile_details(entry['details'])}"
        )

    return entry


@contextmanager
def profile_window_operation(window, operation: str, **details) -> Iterator[int]:
    """Measure a synchronous UI operation and store the elapsed time."""
    token = begin_profile_span(window, operation, **details)
    try:
        yield token
    except Exception:
        finish_profile_span(window, token, outcome="error")
        raise
    else:
        finish_profile_span(window, token)
