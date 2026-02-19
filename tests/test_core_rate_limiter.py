"""Tests for rate limiter."""

import time

from src.core.rate_limiter import RateLimiter


class TestRateLimiter:
    """Test RateLimiter functionality."""

    def test_under_limit(self) -> None:
        """Test actions under limit are allowed."""
        limiter = RateLimiter({"email": 10}, window_seconds=3600)
        
        for i in range(10):
            assert limiter.check("email") is True
        
        assert limiter.remaining("email") == 0

    def test_over_limit(self) -> None:
        """Test actions over limit are rejected."""
        limiter = RateLimiter({"email": 3}, window_seconds=3600)
        
        # Use up the limit
        assert limiter.check("email") is True
        assert limiter.check("email") is True
        assert limiter.check("email") is True
        
        # Next should be rejected
        assert limiter.check("email") is False

    def test_no_limit_configured(self) -> None:
        """Test actions without limit are always allowed."""
        limiter = RateLimiter({"email": 10})
        
        for _ in range(100):
            assert limiter.check("other_action") is True

    def test_window_expiration(self) -> None:
        """Test that old events expire from the window."""
        # Use a very short window for testing
        limiter = RateLimiter({"test": 2}, window_seconds=1)
        
        assert limiter.check("test") is True
        assert limiter.check("test") is True
        assert limiter.check("test") is False
        
        # Wait for window to expire
        time.sleep(1.1)
        
        # Should be allowed again
        assert limiter.check("test") is True

    def test_remaining_count(self) -> None:
        """Test remaining count accuracy."""
        limiter = RateLimiter({"email": 5}, window_seconds=3600)
        
        assert limiter.remaining("email") == 5
        
        limiter.check("email")
        assert limiter.remaining("email") == 4
        
        limiter.check("email")
        limiter.check("email")
        assert limiter.remaining("email") == 2

    def test_multiple_action_types(self) -> None:
        """Test independent limits for different action types."""
        limiter = RateLimiter({"email": 2, "payment": 1, "social": 3})
        
        # Email limit
        assert limiter.check("email") is True
        assert limiter.check("email") is True
        assert limiter.check("email") is False
        
        # Payment limit (independent)
        assert limiter.check("payment") is True
        assert limiter.check("payment") is False
        
        # Social limit (independent)
        assert limiter.check("social") is True
        assert limiter.check("social") is True
        assert limiter.check("social") is True
        assert limiter.check("social") is False
