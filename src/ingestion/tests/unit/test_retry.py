"""Unit tests for retry logic."""

from __future__ import annotations

import time

import pytest

from shared.retry import retry_with_backoff


class CustomRetryableError(Exception):
    """Custom exception for testing."""


class CustomNonRetryableError(Exception):
    """Custom non-retryable exception."""


def test_retry_succeeds_on_first_attempt():
    """Test that retry succeeds without retrying on first attempt."""

    @retry_with_backoff(max_retries=3, operation_name="test_op")
    def func():
        return "success"

    assert func() == "success"


def test_retry_succeeds_after_failures():
    """Test that retry succeeds after transient failures."""
    call_count = 0

    @retry_with_backoff(
        max_retries=3,
        base_delay=0.01,
        max_delay=0.05,
        retryable_exceptions=(CustomRetryableError,),
        operation_name="test_op",
    )
    def func():
        nonlocal call_count
        call_count += 1
        if call_count < 3:
            raise CustomRetryableError("transient")
        return "success"

    assert func() == "success"
    assert call_count == 3


def test_retry_gives_up_after_max_retries():
    """Test that retry raises exception after max retries."""
    call_count = 0

    @retry_with_backoff(
        max_retries=2,
        base_delay=0.01,
        max_delay=0.05,
        retryable_exceptions=(CustomRetryableError,),
        operation_name="test_op",
    )
    def func():
        nonlocal call_count
        call_count += 1
        raise CustomRetryableError("always fails")

    with pytest.raises(CustomRetryableError):
        func()

    assert call_count == 3  # Initial + 2 retries


def test_retry_does_not_retry_non_retryable_exceptions():
    """Test that non-retryable exceptions are raised immediately."""
    call_count = 0

    @retry_with_backoff(
        max_retries=3,
        retryable_exceptions=(CustomRetryableError,),
        operation_name="test_op",
    )
    def func():
        nonlocal call_count
        call_count += 1
        raise CustomNonRetryableError("permanent")

    with pytest.raises(CustomNonRetryableError):
        func()

    assert call_count == 1


def test_retry_exponential_backoff():
    """Test that exponential backoff is applied."""
    call_count = 0
    call_times = []

    @retry_with_backoff(
        max_retries=3,
        base_delay=0.01,
        max_delay=0.1,
        retryable_exceptions=(CustomRetryableError,),
        operation_name="test_op",
    )
    def func():
        nonlocal call_count
        call_count += 1
        call_times.append(time.time())
        if call_count < 4:
            raise CustomRetryableError("transient")
        return "success"

    assert func() == "success"

    if len(call_times) >= 3:
        delay1 = call_times[1] - call_times[0]
        delay2 = call_times[2] - call_times[1]
        assert delay2 >= delay1 * 1.2 or (delay1 > 0.005 and delay2 > 0.01)


def test_retry_respects_max_delay():
    """Test that maximum delay is enforced."""
    call_count = 0

    @retry_with_backoff(
        max_retries=5,
        base_delay=1.0,
        max_delay=0.05,
        retryable_exceptions=(CustomRetryableError,),
        operation_name="test_op",
    )
    def func():
        nonlocal call_count
        call_count += 1
        if call_count < 3:
            raise CustomRetryableError("transient")
        return "success"

    start = time.time()
    result = func()
    elapsed = time.time() - start

    assert result == "success"
    assert elapsed < 0.2


def test_retry_with_multiple_exception_types():
    """Test retry with multiple retryable exception types."""
    call_count = 0

    @retry_with_backoff(
        max_retries=3,
        base_delay=0.01,
        max_delay=0.05,
        retryable_exceptions=(CustomRetryableError, ValueError),
        operation_name="test_op",
    )
    def func():
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            raise CustomRetryableError("transient")
        if call_count == 2:
            raise ValueError("transient")
        return "success"

    assert func() == "success"
    assert call_count == 3
