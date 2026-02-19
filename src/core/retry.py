"""Exponential backoff retry decorator."""

from __future__ import annotations

import functools
import logging
import time
from typing import Any, Callable

log = logging.getLogger(__name__)


def with_retry(
    max_attempts: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 60.0,
    exceptions: tuple[type[Exception], ...] = (Exception,),
) -> Callable:
    """Decorator: retry on specified exceptions with exponential backoff.

    Args:
        max_attempts: Maximum number of attempts (including the first).
        base_delay: Initial delay in seconds between retries.
        max_delay: Maximum delay cap in seconds.
        exceptions: Tuple of exception types to catch and retry on.
    """

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            last_exc: Exception | None = None
            func_name = getattr(func, "__name__", str(func))
            for attempt in range(1, max_attempts + 1):
                try:
                    return func(*args, **kwargs)
                except exceptions as exc:
                    last_exc = exc
                    if attempt == max_attempts:
                        log.error(
                            "Function %s failed after %d attempts: %s",
                            func_name,
                            max_attempts,
                            exc,
                        )
                        raise
                    delay = min(base_delay * (2 ** (attempt - 1)), max_delay)
                    log.warning(
                        "Function %s attempt %d/%d failed: %s. Retrying in %.1fs",
                        func_name,
                        attempt,
                        max_attempts,
                        exc,
                        delay,
                    )
                    time.sleep(delay)
            raise last_exc  # type: ignore[misc]  # unreachable but satisfies type checker

        return wrapper

    return decorator
