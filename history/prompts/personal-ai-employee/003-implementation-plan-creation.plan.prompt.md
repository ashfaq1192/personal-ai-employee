---
id: 003
title: Implementation Plan and Architecture Design
stage: plan
date: 2026-02-08
surface: agent
model: claude-opus-4-6
feature: personal-ai-employee
branch: master
user: ashfaq
command: /sp.plan
labels: ["plan", "architecture", "research", "platinum-tier"]
links:
  spec: specs/personal-ai-employee/spec.md
  ticket: null
  adr: null
  pr: null
files:
  - specs/personal-ai-employee/plan.md
  - specs/personal-ai-employee/research.md
  - specs/personal-ai-employee/data-model.md
  - specs/personal-ai-employee/quickstart.md
  - specs/personal-ai-employee/contracts/mcp-tools.md
tests:
  - N/A (planning stage)
---

## Prompt

/sp.plan — Execute the implementation planning workflow to generate design artifacts for the Personal AI Employee feature.

## Response snapshot

1. Loaded spec and constitution. Verified all constitution gates PASS.
2. Dispatched 4 parallel research agents for: MCP server patterns, Ralph Wiggum implementation, GCP VM sizing, social media APIs.
3. Read Ralph Wiggum plugin source code directly (hooks.json, stop-hook.sh, README.md) — confirmed plugin is installed and functional.
4. Consolidated research into `research.md` covering 8 topics: MCP servers, Ralph Wiggum, GCP sizing (e2-standard-2, ~$61/mo, ~5 months on $300), social media APIs (4 platforms), Gmail, WhatsApp, Odoo, PM2.
5. Generated `data-model.md` with 7 entities: Action Item, Plan, Approval Request, Audit Log Entry, CEO Briefing, Company Handbook, Dashboard. Full YAML schemas and state transitions.
6. Generated `contracts/mcp-tools.md` with 4 MCP servers (email, social, odoo, browser) and 11 tool definitions with JSON Schema input specs.
7. Generated `quickstart.md` with step-by-step setup guide and tier progression table.
8. Generated `plan.md` with: technical context, constitution checks (2x PASS), full project structure, architecture diagram, 5 key design decisions, tier-ordered implementation plan (25 steps).

## Outcome

- ✅ Impact: Complete architectural plan with 5 artifacts generated. All constitution gates passed.
- 🧪 Tests: No tests yet — planning stage.
- 📁 Files: 5 files created (plan.md, research.md, data-model.md, contracts/mcp-tools.md, quickstart.md)
- 🔁 Next prompts: Run `/sp.tasks` to generate dependency-ordered implementation tasks.
- 🧠 Reflection: Research agents hit permission issues (WebFetch/Read auto-denied in subagents). Worked around by reading Ralph Wiggum files directly from main context and using domain knowledge for GCP/social media research. Key risk: social media API approvals take weeks — start developer account applications immediately.

## Evaluation notes (flywheel)

- Failure modes observed: Subagent WebFetch/Read permissions auto-denied, causing research agents to rely on domain knowledge instead of live web data.
- Graders run and results (PASS/FAIL): Constitution Check PASS (both pre-design and post-design).
- Prompt variant (if applicable): N/A
- Next experiment (smallest change to try): Proceed to /sp.tasks for task generation.
