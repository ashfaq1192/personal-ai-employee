"""CLI: Trigger Claude Code reasoning on vault items."""

from __future__ import annotations

import argparse
import json
import logging
import subprocess
import sys
from pathlib import Path

from src.core.config import Config
from src.core.logger import AuditLogger
from src.core.retry import with_retry

log = logging.getLogger(__name__)


@with_retry(max_attempts=3, base_delay=5.0, max_delay=30.0, exceptions=(subprocess.TimeoutExpired,))
def _invoke_claude(vault_path: Path, skill: str, timeout_ms: int, file_arg: str | None = None) -> dict:
    """Invoke Claude Code CLI as subprocess. Returns result dict."""
    prompt = f"Run the {skill} skill."
    if file_arg:
        prompt += f" Process only the file: {file_arg}"

    cmd = [
        "claude",
        "--print",
        prompt,
    ]

    timeout_s = timeout_ms / 1000
    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        timeout=timeout_s,
        cwd=str(vault_path),
    )

    return {
        "exit_code": result.returncode,
        "stdout": result.stdout[:2000],
        "stderr": result.stderr[:500],
        "success": result.returncode == 0,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Trigger Claude reasoning on vault items")
    parser.add_argument(
        "--file",
        type=str,
        default=None,
        help="Process a single file (relative to vault Needs_Action/)",
    )
    parser.add_argument(
        "--skill",
        type=str,
        default="process-inbox",
        help="Agent skill to invoke (default: process-inbox)",
    )
    args = parser.parse_args()

    config = Config()
    audit = AuditLogger(config.vault_path)

    audit.log(
        action_type="system",
        actor="trigger_reasoning",
        target=args.file or "Needs_Action/*",
        parameters={"skill": args.skill},
    )

    try:
        result = _invoke_claude(
            config.vault_path,
            args.skill,
            config.claude_timeout,
            args.file,
        )

        if result["success"]:
            print("Claude reasoning completed successfully.")
            audit.log(
                action_type="system",
                actor="trigger_reasoning",
                target=args.file or "Needs_Action/*",
                parameters={"skill": args.skill},
                result="success",
            )
        else:
            print(f"Claude reasoning failed (exit code {result['exit_code']}).")
            print(f"stderr: {result['stderr']}")
            audit.log(
                action_type="system",
                actor="trigger_reasoning",
                target=args.file or "Needs_Action/*",
                parameters={"skill": args.skill},
                result="failure",
                error=result["stderr"][:200],
            )
            sys.exit(1)

    except subprocess.TimeoutExpired:
        print(f"Claude reasoning timed out after {config.claude_timeout}ms")
        audit.log(
            action_type="system",
            actor="trigger_reasoning",
            target=args.file or "Needs_Action/*",
            result="failure",
            error="timeout",
        )
        sys.exit(1)
    except Exception as exc:
        print(f"Error: {exc}")
        audit.log(
            action_type="system",
            actor="trigger_reasoning",
            target=args.file or "Needs_Action/*",
            result="failure",
            error=str(exc)[:200],
        )
        sys.exit(1)


if __name__ == "__main__":
    main()
