"""Git merge conflict resolver for vault sync.

Detects conflict markers in vault files, preserves both versions
as separate files, and creates ALERT files in Needs_Action.
"""

from __future__ import annotations

import argparse
import logging
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path

log = logging.getLogger(__name__)

_CONFLICT_RE = re.compile(
    r"<<<<<<<.*?\n(.*?)=======\n(.*?)>>>>>>>.*?\n",
    re.DOTALL,
)


def resolve_conflicts(vault_path: Path) -> list[str]:
    """Find and resolve Git merge conflicts in vault files.

    For each conflicted file:
    1. Save local version as <file>_LOCAL.<ext>
    2. Save remote version as <file>_REMOTE.<ext>
    3. Keep the local version as the main file
    4. Create ALERT_conflict_<file>.md in Needs_Action

    Returns list of resolved file paths.
    """
    resolved = []

    # Find conflicted files via git
    try:
        result = subprocess.run(
            ["git", "diff", "--name-only", "--diff-filter=U"],
            capture_output=True,
            text=True,
            cwd=str(vault_path),
        )
        conflicted = [f.strip() for f in result.stdout.strip().split("\n") if f.strip()]
    except Exception:
        log.exception("Failed to detect conflicted files")
        return resolved

    if not conflicted:
        log.info("No conflicted files found")
        return resolved

    needs_action = vault_path / "Needs_Action"
    needs_action.mkdir(parents=True, exist_ok=True)

    for rel_path in conflicted:
        file_path = vault_path / rel_path
        if not file_path.exists():
            continue

        content = file_path.read_text(encoding="utf-8", errors="replace")

        # Extract local and remote versions
        local_parts = []
        remote_parts = []
        last_end = 0

        for match in _CONFLICT_RE.finditer(content):
            local_parts.append(content[last_end:match.start()])
            local_parts.append(match.group(1))
            remote_parts.append(content[last_end:match.start()])
            remote_parts.append(match.group(2))
            last_end = match.end()

        local_parts.append(content[last_end:])
        remote_parts.append(content[last_end:])

        local_content = "".join(local_parts)
        remote_content = "".join(remote_parts)

        # Save versions
        stem = file_path.stem
        suffix = file_path.suffix

        local_file = file_path.parent / f"{stem}_LOCAL{suffix}"
        remote_file = file_path.parent / f"{stem}_REMOTE{suffix}"

        local_file.write_text(local_content, encoding="utf-8")
        remote_file.write_text(remote_content, encoding="utf-8")

        # Keep local as main
        file_path.write_text(local_content, encoding="utf-8")

        # Create alert
        now = datetime.now(timezone.utc)
        alert_name = f"ALERT_conflict_{stem}.md"
        alert_path = needs_action / alert_name
        alert_path.write_text(
            f"---\n"
            f"type: conflict_alert\n"
            f"created: {now.isoformat()}\n"
            f"priority: high\n"
            f"---\n\n"
            f"# Merge Conflict: {rel_path}\n\n"
            f"A Git merge conflict was detected during vault sync.\n\n"
            f"## Files\n"
            f"- **Main (local version kept):** `{rel_path}`\n"
            f"- **Local version:** `{local_file.relative_to(vault_path)}`\n"
            f"- **Remote version:** `{remote_file.relative_to(vault_path)}`\n\n"
            f"## Action Required\n"
            f"1. Compare the LOCAL and REMOTE versions\n"
            f"2. Edit the main file with the correct content\n"
            f"3. Delete the _LOCAL and _REMOTE copies\n"
            f"4. Move this alert to /Done/\n",
            encoding="utf-8",
        )

        resolved.append(rel_path)
        log.info("Resolved conflict: %s", rel_path)

    return resolved


def main() -> None:
    parser = argparse.ArgumentParser(description="Resolve Git merge conflicts in vault")
    parser.add_argument("--vault-path", type=str, required=True)
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO)
    vault_path = Path(args.vault_path).expanduser()
    resolved = resolve_conflicts(vault_path)
    if resolved:
        print(f"Resolved {len(resolved)} conflict(s): {', '.join(resolved)}")
    else:
        print("No conflicts to resolve")


if __name__ == "__main__":
    main()
