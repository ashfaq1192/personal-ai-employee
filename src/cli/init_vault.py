"""CLI: Initialize the AI Employee Obsidian vault."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from src.vault.init_vault import init_vault


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Initialize the AI Employee Obsidian vault."
    )
    parser.add_argument(
        "--path",
        type=str,
        default=os.environ.get("VAULT_PATH", "~/AI_Employee_Vault"),
        help="Path to create the vault (default: VAULT_PATH env or ~/AI_Employee_Vault)",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite existing template files",
    )
    args = parser.parse_args()

    vault_path = Path(args.path).expanduser().resolve()
    print(f"Initializing vault at: {vault_path}")

    result = init_vault(vault_path, force=args.force)

    if result["folders_created"]:
        print(f"\nFolders created ({len(result['folders_created'])}):")
        for f in result["folders_created"]:
            print(f"  + {f}/")
    else:
        print("\nAll folders already exist.")

    if result["files_created"]:
        print(f"\nFiles created ({len(result['files_created'])}):")
        for f in result["files_created"]:
            print(f"  + {f}")
    else:
        print("\nAll template files already exist (use --force to overwrite).")

    print(f"\nVault ready at: {vault_path}")
    print("Open in Obsidian: Open folder as vault → select the path above.")


if __name__ == "__main__":
    main()
