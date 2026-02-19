#!/usr/bin/env python3
"""Ralph Wiggum Stop Hook — keeps Claude iterating until task completion.

Claude Code hook protocol: JSON is passed on stdin.
The hook may print a JSON object to stdout to block exit:
  {"decision": "block", "reason": "<reason>"}
Exiting with code 0 (or printing nothing) allows Claude to exit.

Reference: https://docs.anthropic.com/en/docs/claude-code/hooks
"""

from __future__ import annotations

import json
import os
import sys
from datetime import datetime
from pathlib import Path


def check_task_complete(vault_path: Path, output: str) -> bool:
    """Check if task is complete by examining vault state and output."""
    done_dir = vault_path / "Done"
    needs_action_dir = vault_path / "Needs_Action"

    # Check if output contains completion promise
    if "TASK_COMPLETE" in output or "<promise>TASK_COMPLETE</promise>" in output:
        return True

    # Check if Needs_Action is empty (all items processed)
    if needs_action_dir.exists():
        pending_items = list(needs_action_dir.glob("*.md"))
        if len(pending_items) == 0:
            return True

    # Check if any files were moved to Done recently (last hour)
    if done_dir.exists():
        recent_done = [
            f for f in done_dir.glob("*.md")
            if f.stat().st_mtime > (datetime.now().timestamp() - 3600)
        ]
        if recent_done:
            return True

    return False


def extract_last_assistant_output(transcript: list[dict]) -> str:
    """Extract the last assistant message text from the transcript."""
    for message in reversed(transcript):
        if message.get("role") == "assistant":
            content = message.get("content", "")
            if isinstance(content, str):
                return content
            if isinstance(content, list):
                texts = [
                    block.get("text", "")
                    for block in content
                    if isinstance(block, dict) and block.get("type") == "text"
                ]
                return "\n".join(texts)
    return ""


def main() -> None:
    """Stop hook entry point — reads JSON from stdin per Claude Code hook protocol."""
    try:
        raw = sys.stdin.read()
        if not raw.strip():
            # No input — allow exit
            sys.exit(0)

        data = json.loads(raw)
    except Exception:
        # Parse error — allow exit to prevent infinite loops
        sys.exit(0)

    # Extract hook context
    hook_event = data.get("hook_event_name", "")
    transcript = data.get("transcript", [])

    # Resolve vault path from env or default
    vault_raw = os.environ.get("VAULT_PATH", "~/AI_Employee_Vault")
    vault_path = Path(vault_raw).expanduser()

    # Get last assistant output from transcript
    last_output = extract_last_assistant_output(transcript)

    # Check task completion
    if check_task_complete(vault_path, last_output):
        # Task complete — allow exit (print nothing / exit 0)
        sys.exit(0)

    # Task not complete — block exit and ask Claude to continue
    response = {
        "decision": "block",
        "reason": (
            "Task not yet complete. Needs_Action folder still has pending items "
            "or TASK_COMPLETE was not signalled. Please continue processing."
        ),
    }
    print(json.dumps(response))
    sys.exit(0)


if __name__ == "__main__":
    main()
