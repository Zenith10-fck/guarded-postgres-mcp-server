"""Append-only audit log, plus a decorator that wraps every tool call.

Every tool call is recorded: what was called, with what (redacted)
arguments, how many rows came back, how long it took, and whether it
succeeded or was rejected. This is one of the guardrails in
BLUEPRINT.md's reliability table -- it's what lets a client verify "this
is safe" instead of taking it on faith (see get_audit_log in tools/audit.py).
"""

from __future__ import annotations

import functools
import inspect
import json
import os
import time
from pathlib import Path

import structlog

from guarded_mcp.redact import redact_text

_LOG_PATH = Path(os.environ.get("AUDIT_LOG_PATH", "audit.log.jsonl"))

structlog.configure(
    processors=[
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.JSONRenderer(),
    ],
    logger_factory=structlog.WriteLoggerFactory(file=_LOG_PATH.open("a")),
)

_logger = structlog.get_logger("audit")


def record(
    tool: str,
    args: dict,
    *,
    rows_returned: int | None,
    latency_ms: float,
    outcome: str,
) -> None:
    _logger.info(
        "tool_call",
        tool=tool,
        args=args,
        rows_returned=rows_returned,
        latency_ms=round(latency_ms, 2),
        outcome=outcome,
    )


def read_recent(limit: int = 20) -> list[dict]:
    if not _LOG_PATH.exists():
        return []
    lines = [line for line in _LOG_PATH.read_text().splitlines() if line.strip()]
    return [json.loads(line) for line in lines[-limit:]]


def _summarize_result(result) -> tuple[int | None, str]:
    if isinstance(result, dict):
        if "error_code" in result:
            return None, result["error_code"]
        if "row_count" in result:
            return result["row_count"], "ok"
        if "sample_rows" in result:
            return len(result["sample_rows"]), "ok"
        return None, "ok"
    if isinstance(result, list):
        return len(result), "ok"
    return None, "ok"


def audited(tool_name: str):
    """Decorator: time the call, then write exactly one audit entry --
    whether the call succeeded, was rejected by a guard, or raised."""

    def decorator(fn):
        sig = inspect.signature(fn)

        @functools.wraps(fn)
        async def wrapper(*args, **kwargs):
            bound = sig.bind_partial(*args, **kwargs)
            bound.apply_defaults()
            logged_args = {
                key: (redact_text(value) if isinstance(value, str) else value)
                for key, value in bound.arguments.items()
            }

            start = time.perf_counter()
            try:
                result = await fn(*args, **kwargs)
            except Exception as exc:
                record(
                    tool_name,
                    logged_args,
                    rows_returned=None,
                    latency_ms=(time.perf_counter() - start) * 1000,
                    outcome=f"EXCEPTION:{type(exc).__name__}",
                )
                raise

            rows_returned, outcome = _summarize_result(result)
            record(
                tool_name,
                logged_args,
                rows_returned=rows_returned,
                latency_ms=(time.perf_counter() - start) * 1000,
                outcome=outcome,
            )
            return result

        return wrapper

    return decorator
