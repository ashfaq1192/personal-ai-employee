"""Pytest fixtures for AI Employee tests."""

from __future__ import annotations

import os
import shutil
import tempfile
from pathlib import Path

import pytest

from src.core.config import Config
from src.vault.init_vault import init_vault


@pytest.fixture
def temp_vault() -> Path:
    """Create a temporary vault directory for testing."""
    temp_dir = Path(tempfile.mkdtemp(prefix="ai_employee_test_"))
    vault_path = temp_dir / "test_vault"
    init_vault(vault_path)
    yield vault_path
    shutil.rmtree(temp_dir, ignore_errors=True)


@pytest.fixture
def temp_config(temp_vault: Path) -> Config:
    """Create a Config instance pointing to the temp vault."""
    # Set up environment for dev mode
    os.environ["VAULT_PATH"] = str(temp_vault)
    os.environ["DEV_MODE"] = "true"
    os.environ["DRY_RUN"] = "true"
    os.environ["GMAIL_CLIENT_ID"] = "test_client_id"
    os.environ["GMAIL_CLIENT_SECRET"] = "test_client_secret"
    os.environ["LINKEDIN_ACCESS_TOKEN"] = "test_linkedin_token"
    os.environ["META_ACCESS_TOKEN"] = "test_meta_token"
    os.environ["TWITTER_API_KEY"] = "test_twitter_key"
    os.environ["TWITTER_API_SECRET"] = "test_twitter_secret"
    os.environ["TWITTER_ACCESS_TOKEN"] = "test_twitter_token"
    os.environ["TWITTER_ACCESS_SECRET"] = "test_twitter_secret"
    os.environ["ODOO_URL"] = "http://localhost:8069"
    os.environ["ODOO_DB"] = "test_db"
    os.environ["ODOO_USERNAME"] = "admin"
    os.environ["ODOO_PASSWORD"] = "admin"
    
    config = Config()
    yield config
    
    # Cleanup environment
    for key in [
        "VAULT_PATH", "DEV_MODE", "DRY_RUN",
        "GMAIL_CLIENT_ID", "GMAIL_CLIENT_SECRET",
        "LINKEDIN_ACCESS_TOKEN", "META_ACCESS_TOKEN",
        "TWITTER_API_KEY", "TWITTER_API_SECRET",
        "TWITTER_ACCESS_TOKEN", "TWITTER_ACCESS_SECRET",
        "ODOO_URL", "ODOO_DB", "ODOO_USERNAME", "ODOO_PASSWORD",
    ]:
        os.environ.pop(key, None)


@pytest.fixture
def sample_email_action_file(temp_vault: Path) -> Path:
    """Create a sample email action file in Needs_Action."""
    needs_action = temp_vault / "Needs_Action"
    needs_action.mkdir(parents=True, exist_ok=True)
    
    content = """---
type: email
id: EMAIL_test_001
from: test@example.com
subject: Test Email
received: 2026-02-18T10:00:00Z
priority: high
status: pending
plan_ref: null
---

## Content
**From**: test@example.com
**Subject**: Test Email

This is a test email for unit testing.

## Suggested Actions
- [ ] Read and classify email
- [ ] Determine response action
"""
    file_path = needs_action / "EMAIL_test_001.md"
    file_path.write_text(content, encoding="utf-8")
    return file_path


@pytest.fixture
def sample_approval_request(temp_vault: Path) -> Path:
    """Create a sample approval request file."""
    pending_dir = temp_vault / "Pending_Approval"
    pending_dir.mkdir(parents=True, exist_ok=True)
    
    content = """---
type: approval_request
action: email_send
id: APPROVAL_email_send_test_2026-02-18
amount: null
recipient: client@example.com
reason: Reply to client inquiry
plan_ref: null
created: 2026-02-18T10:00:00Z
expires: 2026-02-19T10:00:00Z
status: pending
---

## Action Details
**Action**: email_send
**Recipient**: client@example.com
**Reason**: Reply to client inquiry

## To Approve
Move this file to /Approved/ folder.

## To Reject
Move this file to /Rejected/ folder.
"""
    file_path = pending_dir / "APPROVAL_email_send_test_2026-02-18.md"
    file_path.write_text(content, encoding="utf-8")
    return file_path
