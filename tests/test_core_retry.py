"""Tests for retry decorator."""

import time
from unittest.mock import Mock

import pytest

from src.core.retry import with_retry


class TestRetry:
    """Test with_retry decorator functionality."""

    def test_successful_function_no_retry(self) -> None:
        """Test that successful functions don't retry."""
        mock_func = Mock(return_value="success")
        decorated = with_retry(max_attempts=3)(mock_func)

        result = decorated()

        assert result == "success"
        mock_func.assert_called_once()

    def test_retry_on_failure(self) -> None:
        """Test that function retries on failure."""
        call_count = 0

        def failing_then_success():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise Exception("fail")
            return "success"

        decorated = with_retry(max_attempts=3, base_delay=0.1)(failing_then_success)

        result = decorated()

        assert result == "success"
        assert call_count == 3

    def test_max_attempts_reached(self) -> None:
        """Test that exception is raised after max attempts."""
        mock_func = Mock(side_effect=Exception("always fails"))
        decorated = with_retry(max_attempts=3, base_delay=0.1)(mock_func)

        with pytest.raises(Exception, match="always fails"):
            decorated()

        assert mock_func.call_count == 3

    def test_exponential_backoff(self) -> None:
        """Test that delays increase exponentially."""
        attempts = []

        def failing_func():
            attempts.append(time.time())
            raise Exception("fail")

        decorated = with_retry(
            max_attempts=3,
            base_delay=0.1,
            max_delay=1.0,
        )(failing_func)

        with pytest.raises(Exception):
            decorated()

        # Check delays between attempts
        assert len(attempts) == 3
        delay1 = attempts[1] - attempts[0]
        delay2 = attempts[2] - attempts[1]

        # Second delay should be roughly 2x first delay
        assert delay2 > delay1

    def test_max_delay_cap(self) -> None:
        """Test that delay doesn't exceed max_delay."""
        attempts = []

        def failing_func():
            attempts.append(time.time())
            raise Exception("fail")

        decorated = with_retry(
            max_attempts=5,
            base_delay=0.5,
            max_delay=0.3,  # Cap at 0.3s
        )(failing_func)

        with pytest.raises(Exception):
            decorated()

        # All delays should be <= max_delay + small buffer
        for i in range(1, len(attempts)):
            delay = attempts[i] - attempts[i - 1]
            assert delay <= 0.35  # Small buffer for execution time

    def test_specific_exception_types(self) -> None:
        """Test that only specified exceptions trigger retry."""
        call_count = 0

        def specific_exception():
            nonlocal call_count
            call_count += 1
            raise ValueError("value error")

        decorated = with_retry(
            max_attempts=3,
            exceptions=(ValueError,),
        )(specific_exception)

        with pytest.raises(ValueError):
            decorated()

        assert call_count == 3

    def test_unexpected_exception_no_retry(self) -> None:
        """Test that unexpected exceptions don't trigger retry."""
        call_count = 0

        def unexpected_exception():
            nonlocal call_count
            call_count += 1
            raise RuntimeError("runtime error")

        decorated = with_retry(
            max_attempts=3,
            exceptions=(ValueError,),  # Only retry on ValueError
        )(unexpected_exception)

        with pytest.raises(RuntimeError):
            decorated()

        # Should only be called once (no retry)
        assert call_count == 1

    def test_function_arguments_preserved(self) -> None:
        """Test that function arguments are preserved across retries."""
        received_args = []

        def func_with_args(a, b, c=10):
            received_args.append((a, b, c))
            if len(received_args) < 2:
                raise Exception("fail")
            return a + b + c

        decorated = with_retry(max_attempts=3, base_delay=0.1)(func_with_args)

        result = decorated(1, 2, c=5)

        assert result == 8
        assert all(args == (1, 2, 5) for args in received_args)
