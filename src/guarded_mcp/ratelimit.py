"""Simple in-memory per-tool rate limiter (token bucket).

Good enough for a single-process demo server. A multi-process production
deployment would move the bucket state to Redis or similar, but the shape
of the guardrail -- check before running the tool, return a structured
error on exhaustion -- stays the same.
"""

from __future__ import annotations

import functools
import time


class TokenBucket:
    def __init__(self, capacity: int, refill_per_second: float):
        self.capacity = capacity
        self.tokens = float(capacity)
        self.refill_per_second = refill_per_second
        self.last_refill = time.monotonic()

    def take(self) -> bool:
        now = time.monotonic()
        elapsed = now - self.last_refill
        self.tokens = min(self.capacity, self.tokens + elapsed * self.refill_per_second)
        self.last_refill = now
        if self.tokens >= 1:
            self.tokens -= 1
            return True
        return False


_buckets: dict[str, TokenBucket] = {}


def rate_limited(tool_name: str, capacity: int = 20, refill_per_second: float = 1.0):
    """Decorator: reject the call with a structured error (not an
    exception) once the tool's token bucket runs dry, instead of letting
    calls queue up and pile load onto Postgres."""

    def decorator(fn):
        @functools.wraps(fn)
        async def wrapper(*args, **kwargs):
            bucket = _buckets.setdefault(tool_name, TokenBucket(capacity, refill_per_second))
            if not bucket.take():
                return {
                    "error_code": "RATE_LIMITED",
                    "message": f"Rate limit exceeded for tool '{tool_name}'.",
                    "hint": "Wait a moment before retrying, or batch your questions into fewer calls.",
                }
            return await fn(*args, **kwargs)

        return wrapper

    return decorator
