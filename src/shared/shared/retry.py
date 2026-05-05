"""Retry logic with exponential backoff for transient failures."""

from __future__ import annotations

import logging
import random
import time
from functools import wraps
from typing import Any, Callable, TypeVar

logger = logging.getLogger(__name__)

T = TypeVar("T")


def retry_with_backoff(
    max_retries: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 30.0,
    max_elapsed_time: float = 60.0,
    retryable_exceptions: tuple[type[Exception], ...] | None = None,
    should_retry: Callable[[Exception], bool] | None = None,
    operation_name: str = "operation",
) -> Callable[[Callable[..., T]], Callable[..., T]]:
    """Decorator for retrying functions with exponential backoff and jitter.

    Args:
        max_retries: Maximum number of retries (default 3)
        base_delay: Base delay in seconds (default 1.0)
        max_delay: Maximum delay in seconds (default 30.0)
        max_elapsed_time: Maximum total elapsed time in seconds (default 60.0)
        retryable_exceptions: Tuple of exception types to retry on
        should_retry: Optional predicate for per-exception retry decisions
        operation_name: Name of operation for logging

    Returns:
        Decorated function that retries on transient failures
    """
    if retryable_exceptions is None:
        retryable_exceptions = (Exception,)

    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> T:
            last_exception: Exception | None = None
            start_time = time.time()

            for attempt in range(max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except retryable_exceptions as e:
                    last_exception = e
                    elapsed_time = time.time() - start_time

                    if should_retry is not None and not should_retry(e):
                        logger.info(
                            "Not retrying %s for %s: %s",
                            type(e).__name__,
                            operation_name,
                            str(e),
                        )
                        raise

                    # Check if we've exceeded max retries
                    if attempt >= max_retries:
                        logger.error(
                            "Max retries exceeded for %s: %s",
                            operation_name,
                            str(e),
                            extra={
                                "exception_type": type(e).__name__,
                                "exception_args": getattr(e, "args", ()),
                            },
                        )
                        raise

                    # Check if we've exceeded max elapsed time
                    if elapsed_time >= max_elapsed_time:
                        logger.error(
                            "Max elapsed time (%.1fs) exceeded for %s: %s",
                            max_elapsed_time,
                            operation_name,
                            str(e),
                        )
                        raise

                    # Calculate exponential backoff with jitter (cap total at max_delay)
                    exponential_delay = min(base_delay * (2**attempt), max_delay)
                    jitter = random.uniform(0, min(base_delay, max_delay - exponential_delay))
                    delay = min(exponential_delay + jitter, max_delay)

                    # Ensure we don't exceed remaining time budget
                    remaining_time = max_elapsed_time - elapsed_time
                    delay = min(delay, remaining_time)

                    logger.info(
                        "Retry attempt %d/%d for %s after %.1fs (elapsed: %.1fs): %s",
                        attempt + 1,
                        max_retries,
                        operation_name,
                        delay,
                        elapsed_time,
                        str(e),
                    )
                    time.sleep(delay)

            # This should never be reached, but satisfy type checker
            if last_exception:
                raise last_exception
            return func(*args, **kwargs)

        return wrapper

    return decorator
