"""Bounded structured diagnostics for one repository-analysis request."""
from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar
from datetime import datetime, timezone
import json
import logging
import re
import traceback
import time
from typing import Iterator

def _redact(value: str) -> str:
    from app.services.source_evidence_extractor import redact_secrets
    safe = redact_secrets(value)
    return re.sub(r"(?i)(https?://)[^/@\s]+@", r"\1[REDACTED]@", safe)

analysis_run_id_var: ContextVar[str] = ContextVar("analysis_run_id", default="")
analysis_stage_var: ContextVar[str] = ContextVar("analysis_stage", default="request")


def _safe(value):
    if isinstance(value, str):
        return _redact(value[:1000])
    if isinstance(value, dict):
        return {str(key)[:80]: _safe(item) for key, item in list(value.items())[:40]
                if not (str(key).lower() in {"key", "token", "api_key", "api_token", "access_token", "authorization", "content", "source_content"}
                        or any(term in str(key).lower() for term in ("secret", "password", "private_key")))}
    if isinstance(value, (list, tuple, set)):
        return [_safe(item) for item in list(value)[:40]]
    if value is None or isinstance(value, (int, float, bool)):
        return value
    return _redact(str(value)[:1000])


def emit(logger: logging.Logger, event: str, *, level: int = logging.INFO, stage: str | None = None,
         exc_info: bool = False, **fields) -> None:
    safe_fields = _safe(fields)
    if exc_info:
        stack = traceback.format_exc()
        if stack and stack.strip() != "NoneType: None":
            safe_fields["traceback"] = _safe(stack[:6000])
    record = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "event": event,
        "analysis_run_id": analysis_run_id_var.get() or fields.pop("analysis_run_id", ""),
        "stage": stage or analysis_stage_var.get(),
        **safe_fields,
    }
    logger.log(level, json.dumps(record, ensure_ascii=False, separators=(",", ":")))


@contextmanager
def run_context(run_id: str) -> Iterator[None]:
    token = analysis_run_id_var.set(run_id)
    try:
        yield
    finally:
        analysis_run_id_var.reset(token)


@contextmanager
def stage(logger: logging.Logger, name: str, **fields) -> Iterator[None]:
    token = analysis_stage_var.set(name)
    started = time.perf_counter()
    emit(logger, "stage_started", stage=name, **fields)
    try:
        yield
    except Exception as exc:
        emit(logger, "stage_failed", level=logging.ERROR, stage=name, duration_ms=round((time.perf_counter() - started) * 1000), exception_type=type(exc).__name__, reason=str(exc), exc_info=True, **fields)
        raise
    else:
        emit(logger, "stage_completed", stage=name, duration_ms=round((time.perf_counter() - started) * 1000), **fields)
    finally:
        analysis_stage_var.reset(token)
