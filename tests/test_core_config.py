"""Tests for core configuration module."""

import os
from pathlib import Path

import pytest

from src.core.config import Config


class TestConfig:
    """Test Config class initialization and validation."""

    def test_default_dev_mode(self, temp_config: Config) -> None:
        """Test that dev mode defaults to true in test environment."""
        assert temp_config.dev_mode is True
        assert temp_config.dry_run is True

    def test_vault_path_expansion(self, temp_config: Config) -> None:
        """Test that vault path is properly expanded."""
        assert temp_config.vault_path.is_absolute()

    def test_rate_limits(self, temp_config: Config) -> None:
        """Test default rate limit values."""
        assert temp_config.rate_limit_emails == 10
        assert temp_config.rate_limit_payments == 3
        assert temp_config.rate_limit_social == 5

    def test_claude_timeout(self, temp_config: Config) -> None:
        """Test Claude timeout default value."""
        assert temp_config.claude_timeout == 300000  # 5 minutes in ms

    def test_ralph_batch_threshold(self, temp_config: Config) -> None:
        """Test Ralph batch threshold default value."""
        assert temp_config.ralph_batch_threshold == 3

    def test_validate_missing_vault(self, temp_vault: Path) -> None:
        """Test validation fails for non-existent vault."""
        os.environ["VAULT_PATH"] = str(temp_vault / "nonexistent")
        config = Config()
        errors = config.validate()
        assert len(errors) == 1
        assert "does not exist" in errors[0]

    def test_validate_existing_vault(self, temp_config: Config) -> None:
        """Test validation passes for existing vault."""
        errors = temp_config.validate()
        assert len(errors) == 0

    def test_whatsapp_session_path(self, temp_config: Config) -> None:
        """Test WhatsApp session path is set."""
        assert temp_config.whatsapp_session_path is not None
        assert temp_config.whatsapp_session_path.is_absolute()

    def test_social_media_tokens(self, temp_config: Config) -> None:
        """Test social media tokens are loaded from environment."""
        assert temp_config.linkedin_access_token == "test_linkedin_token"
        assert temp_config.meta_access_token == "test_meta_token"
        assert temp_config.twitter_api_key == "test_twitter_key"

    def test_odoo_config(self, temp_config: Config) -> None:
        """Test Odoo configuration is loaded."""
        assert temp_config.odoo_url == "http://localhost:8069"
        assert temp_config.odoo_db == "test_db"
        assert temp_config.odoo_username == "admin"
