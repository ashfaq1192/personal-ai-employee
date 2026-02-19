"""Ralph Wiggum persistence loop integration.

Uses Claude Code's stop-hook mechanism to iterate on multi-step tasks
until a completion promise is detected.
"""

from __future__ import annotations

import json
import logging
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

from src.core.config import Config
from src.core.logger import AuditLogger

log = logging.getLogger(__name__)

_DEFAULT_MAX_ITERATIONS = 10


class RalphIntegration:
    """Manages Ralph Wiggum persistence loops for batch task processing."""

    def __init__(self, config: Config | None = None) -> None:
        self.config = config or Config()
        self.vault_path = self.config.vault_path
        self.audit = AuditLogger(self.vault_path)

    def start_ralph_loop(
        self,
        prompt: str,
        completion_promise: str = "TASK_COMPLETE",
        max_iterations: int = _DEFAULT_MAX_ITERATIONS,
    ) -> dict:
        """Start a Ralph loop that invokes Claude iteratively until completion.

        Args:
            prompt: The task prompt for Claude.
            completion_promise: String Claude outputs when done.
            max_iterations: Safety limit on iterations.

        Returns:
            Dict with status, iterations, and any output.
        """
        state_file = self.vault_path / "Logs" / "ralph_state.json"
        state_file.parent.mkdir(parents=True, exist_ok=True)

        state = {
            "started": datetime.now(timezone.utc).isoformat(),
            "prompt": prompt[:200],
            "completion_promise": completion_promise,
            "max_iterations": max_iterations,
            "iteration": 0,
            "status": "running",
        }

        self.audit.log(
            action_type="ralph_loop",
            actor="ralph_integration",
            target="Needs_Action",
            parameters={"prompt": prompt[:100], "max_iterations": max_iterations},
        )

        for i in range(1, max_iterations + 1):
            state["iteration"] = i
            state_file.write_text(json.dumps(state, indent=2), encoding="utf-8")

            log.info("Ralph loop iteration %d/%d", i, max_iterations)

            try:
                result = subprocess.run(
                    [
                        "claude",
                        "--print",
                        prompt,
                    ],
                    capture_output=True,
                    text=True,
                    timeout=self.config.claude_timeout / 1000,
                    cwd=str(self.vault_path),
                )

                output = result.stdout or ""

                if completion_promise in output:
                    log.info("Ralph loop completed at iteration %d", i)
                    state["status"] = "completed"
                    state["finished"] = datetime.now(timezone.utc).isoformat()
                    state_file.write_text(json.dumps(state, indent=2), encoding="utf-8")
                    self.audit.log(
                        action_type="ralph_loop",
                        actor="ralph_integration",
                        target="Needs_Action",
                        parameters={"iteration": i},
                        result="completed",
                    )
                    return {"status": "completed", "iterations": i, "output": output[:500]}

                if result.returncode != 0:
                    log.warning(
                        "Ralph iteration %d failed (exit %d): %s",
                        i, result.returncode, result.stderr[:200],
                    )

            except subprocess.TimeoutExpired:
                log.warning("Ralph iteration %d timed out", i)
                self.audit.log(
                    action_type="ralph_loop",
                    actor="ralph_integration",
                    target="Needs_Action",
                    parameters={"iteration": i},
                    result="timeout",
                )

            except Exception:
                log.exception("Ralph iteration %d error", i)

        state["status"] = "max_iterations_reached"
        state["finished"] = datetime.now(timezone.utc).isoformat()
        state_file.write_text(json.dumps(state, indent=2), encoding="utf-8")

        self.audit.log(
            action_type="ralph_loop",
            actor="ralph_integration",
            target="Needs_Action",
            parameters={"iterations": max_iterations},
            result="max_iterations_reached",
        )

        return {"status": "max_iterations_reached", "iterations": max_iterations}

    def trigger_vault_processing(self) -> dict:
        """Convenience: start a Ralph loop to process all Needs_Action items."""
        prompt = (
            "Process all items in /Needs_Action, create plans, request approvals. "
            "Move completed to /Done. "
            "Output <promise>TASK_COMPLETE</promise> when Needs_Action is empty."
        )
        return self.start_ralph_loop(
            prompt=prompt,
            completion_promise="TASK_COMPLETE",
            max_iterations=self.config.ralph_batch_threshold * 3 + 1,
        )
