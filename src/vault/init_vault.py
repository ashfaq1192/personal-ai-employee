"""Vault initialization — creates directory structure and template files."""

from __future__ import annotations

import shutil
from pathlib import Path

CANONICAL_FOLDERS = [
    "Inbox",
    "Needs_Action",
    "Plans",
    "Pending_Approval",
    "Approved",
    "Rejected",
    "In_Progress",
    "Done",
    "Accounting",
    "Accounting/pending",
    "Invoices",
    "Briefings",
    "Logs",
    "Active_Project",
    "Updates",
]

TEMPLATE_FILES = [
    "Dashboard.md",
    "Company_Handbook.md",
    "Business_Goals.md",
]


def init_vault(vault_path: Path, *, force: bool = False) -> dict[str, list[str]]:
    """Initialize the Obsidian vault at the given path.

    Args:
        vault_path: Absolute path where the vault will be created.
        force: If True, overwrite existing template files.

    Returns:
        Dict with 'folders_created' and 'files_created' lists.
    """
    templates_dir = Path(__file__).parent / "templates"
    folders_created: list[str] = []
    files_created: list[str] = []

    # Create vault root
    vault_path.mkdir(parents=True, exist_ok=True)

    # Create canonical folders
    for folder in CANONICAL_FOLDERS:
        folder_path = vault_path / folder
        if not folder_path.exists():
            folder_path.mkdir(parents=True, exist_ok=True)
            folders_created.append(folder)

    # Copy template files
    for template in TEMPLATE_FILES:
        src = templates_dir / template
        dst = vault_path / template
        if not dst.exists() or force:
            shutil.copy2(src, dst)
            files_created.append(template)

    return {"folders_created": folders_created, "files_created": files_created}
