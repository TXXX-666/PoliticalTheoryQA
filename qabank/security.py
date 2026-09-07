from __future__ import annotations

import hmac
import time
from collections.abc import Iterable


def token_matches(expected: str, supplied: str) -> bool:
    expected = expected.strip()
    supplied = supplied.strip()
    return bool(expected and supplied) and hmac.compare_digest(expected, supplied)


def check_rate_limit(
    timestamps: Iterable[float],
    *,
    max_requests: int,
    window_seconds: int,
    now: float | None = None,
) -> tuple[bool, list[float], int]:
    current = time.monotonic() if now is None else now
    cutoff = current - window_seconds
    recent = [float(value) for value in timestamps if float(value) > cutoff]
    if len(recent) >= max_requests:
        retry_after = max(1, int(window_seconds - (current - recent[0])) + 1)
        return False, recent, retry_after
    recent.append(current)
    return True, recent, 0
