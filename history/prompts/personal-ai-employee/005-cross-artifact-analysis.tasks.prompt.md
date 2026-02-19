---
id: 005
title: Cross-Artifact Consistency Analysis
stage: tasks
date: 2026-02-08
surface: agent
model: claude-opus-4-6
feature: personal-ai-employee
branch: master
user: ashfaq
command: /sp.analyze
labels: ["analysis", "consistency", "quality-gate", "cross-artifact"]
links:
  spec: specs/personal-ai-employee/spec.md
  ticket: null
  adr: null
  pr: null
files:
  - N/A (read-only analysis, no files modified)
tests:
  - N/A (analysis stage)
---

## Prompt

/sp.analyze — Perform a non-destructive cross-artifact consistency and quality analysis across spec.md, plan.md, and tasks.md after task generation.

## Response snapshot

1. Loaded all 6 artifacts: spec.md, plan.md, tasks.md, constitution.md, data-model.md, contracts/mcp-tools.md.
2. Built semantic models: 21 functional requirements, 17 user stories, 71 tasks, 6 constitution principles.
3. Ran 6 detection passes: Duplication, Ambiguity, Underspecification, Constitution Alignment, Coverage Gaps, Inconsistency.
4. Identified 28 findings: 1 CRITICAL, 7 HIGH, 12 MEDIUM, 8 LOW.
5. CRITICAL: DEV_MODE vs DRY_RUN semantic distinction undefined (U1).
6. Key HIGH issues: HITL not enforced at MCP layer (C2), Node.js/Python inconsistency (I1/I2), Claude CLI invocation contract missing (U2), project-based operations uncovered (C1).
7. Coverage: 18/21 requirements (85.7%) have full task coverage; 3 partial.
8. Constitution alignment: 2 warnings (HITL bypass risk at MCP layer, Agent Skills boundary unclear), no violations.
9. All 71 tasks mapped to user stories — no orphan tasks.

## Outcome

- ✅ Impact: Comprehensive analysis identifying 28 findings across 6 categories. 1 CRITICAL issue blocks clean implementation start.
- 🧪 Tests: N/A — read-only analysis.
- 📁 Files: No files modified (read-only analysis per /sp.analyze contract).
- 🔁 Next prompts: Resolve CRITICAL (U1: DEV_MODE vs DRY_RUN) and HIGH issues before running `/sp.implement`. User can approve remediation edits.
- 🧠 Reflection: Analysis was thorough. The most significant finding is the HITL bypass risk (C2) — MCP servers can be invoked without approval validation if called outside the orchestrator flow. This is a constitution-level concern. The DEV_MODE/DRY_RUN ambiguity (U1) will cause implementation confusion if not resolved upfront.

## Evaluation notes (flywheel)

- Failure modes observed: None — analysis ran smoothly with all artifacts available.
- Graders run and results (PASS/FAIL): Constitution alignment: 2 WARNINGS, 0 FAILURES.
- Prompt variant (if applicable): N/A
- Next experiment (smallest change to try): Resolve U1 (DEV_MODE/DRY_RUN) and C2 (HITL at MCP layer), then proceed to /sp.implement.
