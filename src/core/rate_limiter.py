"""Per-action sliding-window rate limiter."""

from __future__ import annotations

import logging
import time
from collections import defaultdict

log = logging.getLogger(__name__)


class RateLimiter:
    """In-memory sliding-window rate limiter.

    Enforces per-action limits:
      - emails: 10/hour
      - payments: 3/hour
      - social: 5/hour

    Usage:
        limiter = RateLimiter({"email": 10, "payment": 3, "social": 5})
        if limiter.check("email"):
            ... # proceed
        else:
            ... # rate limited
    """

    def __init__(self, limits: dict[str, int], window_seconds: int = 3600) -> None:
        self._limits = limits
        self._window = window_seconds
        self._events: dict[str, list[float]] = defaultdict(list)

    def check(self, action_type: str) -> bool:
        """Check if action is allowed. Records the event if allowed.

        Returns True if under limit, False if rate-limited.
        """
        limit = self._limits.get(action_type)
        if limit is None:
            return True  # no limit configured for this action type

        now = time.monotonic()
        cutoff = now - self._window

        # Prune old events
        self._events[action_type] = [
            t for t in self._events[action_type] if t > cutoff
        ]

        if len(self._events[action_type]) >= limit:
            log.warning(
                "Rate limit exceeded for %s: %d/%d in window",
                action_type,
                len(self._events[action_type]),
                limit,
            )
            return False

        self._events[action_type].append(now)
        return True

    def remaining(self, action_type: str) -> int:
        """Return how many actions remain in the current window."""
        limit = self._limits.get(action_type)
        if limit is None:
            return 999

        now = time.monotonic()
        cutoff = now - self._window
        current = sum(1 for t in self._events.get(action_type, []) if t > cutoff)
        return max(0, limit - current)
