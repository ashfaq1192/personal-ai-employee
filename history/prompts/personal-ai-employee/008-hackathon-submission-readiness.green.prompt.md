---
id: "008"
title: Hackathon Submission Readiness
stage: green
date: 2026-02-18
surface: agent
model: claude-sonnet-4-6
feature: personal-ai-employee
branch: master
user: ashfaq
command: implement plan
labels: ["doctor","main.py","mcp","hooks","ecosystem","readme","gmail"]
links:
  spec: specs/personal-ai-employee/spec.md
  ticket: null
  adr: null
  pr: null
files:
  - doctor (created)
  - main.py (replaced stub with argparse CLI)
  - .mcp.json (fixed odoo entry: npx → uv)
  - .claude/plugins/ralph-wiggum/stop_hook.py (fixed: stdin JSON protocol)
  - .claude/plugins/ralph-wiggum/plugin.json (removed ${STATE_FILE} arg)
  - ecosystem.config.js (added 3 watcher/dashboard processes)
  - docs/setup-gmail.md (created Gmail OAuth guide)
  - README.md (updated with prerequisites, quick start, CLI ref, tier checklist)
tests:
  - uv run pytest tests/ -q → 89 passed
---

## Prompt

Implement the following plan:

# Implementation Plan: Full Hackathon Submission Readiness

[Full 9-phase plan covering: doctor health-check, main.py fix, Odoo MCP fix, Ralph Wiggum hook fix, Dashboard refresh, ecosystem.config.js expansion, Gmail OAuth guide, README update, test suite run]

## Response snapshot

Implemented all 9 phases:

1. **doctor** — Created executable shell health-check script with 11 checks (Python ≥3.13, uv, Node≥20, claude CLI, .env, vault path, vault folders, vault templates, Python deps, tests, MCP imports). Colored PASS/WARN/FAIL output. Exit 0 if no FAIL.

2. **main.py** — Replaced `print("Hello from hackathon-0!")` stub with proper argparse CLI delegating to orchestrator (default), --init-vault, --dashboard, --status, --demo subcommands.

3. **.mcp.json** — Fixed odoo entry from `npx mcp-odoo-adv` to `uv run python src/mcp_servers/odoo_mcp.py` preserving all env vars.

4. **stop_hook.py** — Rewrote to use Claude Code's actual hook protocol (read JSON from stdin, parse transcript, extract last assistant output, print `{"decision":"block","reason":"..."}` to stdout or exit 0 to allow exit).

5. **plugin.json** — Removed `${STATE_FILE}` arg from stop hook command args.

6. **Dashboard.md** — Refreshed via `update_dashboard()` call.

7. **ecosystem.config.js** — Added ai-employee-filesystem-watcher, ai-employee-gmail-watcher, ai-employee-web-dashboard processes with same restart/log policies as orchestrator.

8. **docs/setup-gmail.md** — Created 7-step OAuth guide covering Google Cloud Console setup, credentials download, authorization flow, .env config, and troubleshooting table.

9. **README.md** — Added prerequisites table, CLI reference table, tier checklist, demo video placeholder. Updated quick start to include `./doctor` step.

Tests: 89 passed in 15.31s

## Outcome

- ✅ Impact: All 8 critical files fixed; submission is credibly Platinum-tier complete
- 🧪 Tests: 89 passed (no regressions)
- 📁 Files: 8 files modified/created across project root, .claude/, docs/, ecosystem.config.js
- 🔁 Next prompts: run `./doctor` to verify live, record demo video, create PR
- 🧠 Reflection: Claude Code hook protocol uses stdin JSON — not file args. The `${STATE_FILE}` pattern was a placeholder that didn't match real Claude Code hook behavior.

## Evaluation notes (flywheel)

- Failure modes observed: None — all phases completed cleanly
- Graders run and results (PASS/FAIL): uv run pytest tests/ -q → PASS (89 passed)
- Prompt variant (if applicable): N/A
- Next experiment: Run ./doctor end-to-end to catch any runtime check failures
