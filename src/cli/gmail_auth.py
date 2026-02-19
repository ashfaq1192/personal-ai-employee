"""CLI: Gmail OAuth2 authentication flow."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(description="Gmail OAuth2 setup")
    parser.add_argument(
        "--credentials",
        type=str,
        required=True,
        help="Path to OAuth client credentials JSON (from Google Cloud Console)",
    )
    parser.add_argument(
        "--output",
        type=str,
        default="~/.config/ai-employee/gmail_credentials.json",
        help="Path to save the authorized credentials",
    )
    args = parser.parse_args()

    creds_file = Path(args.credentials).expanduser().resolve()
    output_file = Path(args.output).expanduser().resolve()

    if not creds_file.exists():
        print(f"Error: Credentials file not found: {creds_file}")
        sys.exit(1)

    try:
        from google_auth_oauthlib.flow import InstalledAppFlow
    except ImportError:
        print("Error: google-auth-oauthlib not installed. Run: uv sync")
        sys.exit(1)

    SCOPES = [
        "https://www.googleapis.com/auth/gmail.readonly",
        "https://www.googleapis.com/auth/gmail.send",
        "https://www.googleapis.com/auth/gmail.modify",
    ]

    flow = InstalledAppFlow.from_client_secrets_file(str(creds_file), SCOPES)
    creds = flow.run_local_server(port=0)

    output_file.parent.mkdir(parents=True, exist_ok=True)
    output_file.write_text(creds.to_json(), encoding="utf-8")
    print(f"Credentials saved to: {output_file}")
    print("Gmail OAuth2 setup complete.")


if __name__ == "__main__":
    main()
