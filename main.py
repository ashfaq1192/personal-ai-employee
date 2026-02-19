"""Personal AI Employee — CLI entry point.

Delegates to the appropriate subsystem based on the subcommand.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path


def _run(cmd: list[str]) -> int:
    """Run a command and return its exit code."""
    result = subprocess.run(cmd, cwd=Path(__file__).parent)
    return result.returncode


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="main.py",
        description="Personal AI Employee — autonomous task agent",
    )
    parser.add_argument(
        "--init-vault",
        action="store_true",
        help="Initialize the Obsidian vault with required folders and templates",
    )
    parser.add_argument(
        "--dashboard",
        action="store_true",
        help="Start the web dashboard server",
    )
    parser.add_argument(
        "--status",
        action="store_true",
        help="Show current vault and agent status",
    )
    parser.add_argument(
        "--demo",
        action="store_true",
        help="Run end-to-end demo scenario",
    )

    args = parser.parse_args()

    if args.init_vault:
        sys.exit(_run(["uv", "run", "python", "src/cli/init_vault.py"]))
    elif args.dashboard:
        sys.exit(_run(["uv", "run", "python", "src/cli/web_dashboard.py"]))
    elif args.status:
        sys.exit(_run(["uv", "run", "python", "src/cli/status.py"]))
    elif args.demo:
        sys.exit(_run(["uv", "run", "python", "scripts/demo_e2e.py"]))
    else:
        # Default: start the orchestrator
        sys.exit(_run(["uv", "run", "python", "src/orchestrator/orchestrator.py"]))


if __name__ == "__main__":
    main()
