"""Configuration management — loads .env and exposes typed settings."""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv


class Config:
    """Singleton-style configuration loaded from environment variables.

    DEV_MODE=true  → no external reads or writes (mock data, no API calls).
    DRY_RUN=true   → external reads OK, writes logged-only.
    DEV_MODE=true implies DRY_RUN=true regardless of DRY_RUN setting.
    """

    def __init__(self, env_path: str | Path | None = None) -> None:
        if env_path:
            load_dotenv(env_path)
        else:
            load_dotenv()

        self.vault_path: Path = Path(
            os.environ.get("VAULT_PATH", "~/AI_Employee_Vault")
        ).expanduser()

        self.dev_mode: bool = os.environ.get("DEV_MODE", "true").lower() == "true"
        self.dry_run: bool = (
            self.dev_mode
            or os.environ.get("DRY_RUN", "true").lower() == "true"
        )

        # Gmail
        self.gmail_client_id: str = os.environ.get("GMAIL_CLIENT_ID", "")
        self.gmail_client_secret: str = os.environ.get("GMAIL_CLIENT_SECRET", "")
        self.gmail_credentials_path: Path = Path(
            os.environ.get(
                "GMAIL_CREDENTIALS_PATH",
                "~/.config/ai-employee/gmail_credentials.json",
            )
        ).expanduser()

        # WhatsApp (Playwright session — legacy Path A)
        self.whatsapp_session_path: Path = Path(
            os.environ.get(
                "WHATSAPP_SESSION_PATH",
                "~/.config/ai-employee/whatsapp-session",
            )
        ).expanduser()

        # WhatsApp Business API (Path B — Meta Cloud API)
        self.whatsapp_phone_number_id: str = os.environ.get("WHATSAPP_PHONE_NUMBER_ID", "")
        self.whatsapp_business_account_id: str = os.environ.get("WHATSAPP_BUSINESS_ACCOUNT_ID", "")
        self.whatsapp_webhook_verify_token: str = os.environ.get(
            "WHATSAPP_WEBHOOK_VERIFY_TOKEN", "ai_employee_verify"
        )
        self.whatsapp_access_token: str = os.environ.get(
            "WHATSAPP_ACCESS_TOKEN", ""
        ) or self.meta_access_token
        self.rate_limit_whatsapp: int = int(
            os.environ.get("RATE_LIMIT_WHATSAPP_PER_HOUR", "20")
        )

        # Social media
        self.linkedin_access_token: str = os.environ.get("LINKEDIN_ACCESS_TOKEN", "")
        self.meta_access_token: str = os.environ.get("META_ACCESS_TOKEN", "")
        self.facebook_page_id: str = os.environ.get("FACEBOOK_PAGE_ID", "")
        self.ig_user_id: str = os.environ.get("INSTAGRAM_USER_ID", "")
        self.twitter_bearer_token: str = os.environ.get("TWITTER_BEARER_TOKEN", "")
        self.twitter_api_key: str = os.environ.get("TWITTER_API_KEY", "")
        self.twitter_api_secret: str = os.environ.get("TWITTER_API_SECRET", "")
        self.twitter_access_token: str = os.environ.get("TWITTER_ACCESS_TOKEN", "")
        self.twitter_access_secret: str = os.environ.get("TWITTER_ACCESS_SECRET", "")

        # Odoo
        self.odoo_url: str = os.environ.get("ODOO_URL", "")
        self.odoo_db: str = os.environ.get("ODOO_DB", "")
        self.odoo_username: str = os.environ.get("ODOO_USERNAME", "")
        self.odoo_password: str = os.environ.get("ODOO_PASSWORD", "")

        # Rate limits
        self.rate_limit_emails: int = int(
            os.environ.get("RATE_LIMIT_EMAILS_PER_HOUR", "10")
        )
        self.rate_limit_payments: int = int(
            os.environ.get("RATE_LIMIT_PAYMENTS_PER_HOUR", "3")
        )
        self.rate_limit_social: int = int(
            os.environ.get("RATE_LIMIT_SOCIAL_PER_HOUR", "5")
        )

        # Claude
        self.claude_timeout: int = int(
            os.environ.get("CLAUDE_TIMEOUT", "300000")
        )

        # Ralph Wiggum
        self.ralph_batch_threshold: int = int(
            os.environ.get("RALPH_BATCH_THRESHOLD", "3")
        )

    def validate(self) -> list[str]:
        """Return list of validation errors (empty = valid)."""
        errors: list[str] = []
        if not self.vault_path.exists():
            errors.append(f"VAULT_PATH does not exist: {self.vault_path}")
        return errors
