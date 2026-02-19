---
id: 006
title: Cross-Artifact Remediation Edits
stage: tasks
date: 2026-02-08
surface: agent
model: claude-opus-4-6
feature: personal-ai-employee
branch: master
user: ashfaq
command: /sp.analyze (remediation follow-up)
labels: ["remediation", "consistency", "quality-gate", "edits"]
links:
  spec: specs/personal-ai-employee/spec.md
  ticket: null
  adr: null
  pr: null
files:
  - specs/personal-ai-employee/spec.md
  - specs/personal-ai-employee/plan.md
  - specs/personal-ai-employee/tasks.md
  - .specify/memory/constitution.md
tests:
  - N/A (remediation edits, no code changes)
---

## Prompt

Okay please resolve those. (Referring to CRITICAL and HIGH issues from /sp.analyze report)

## Response snapshot

Resolved 1 CRITICAL and 7 HIGH issues across 4 artifacts:

**spec.md (5 edits):**
1. U1 (CRITICAL): Defined DEV_MODE vs DRY_RUN semantics — DEV_MODE prevents external reads+writes; DRY_RUN prevents external writes only; DEV_MODE implies DRY_RUN.
2. A1 (HIGH): WhatsApp keyword list now references Company_Handbook.md as single source of truth.
3. A2 (HIGH): FR-017 clarified — Agent Skills = Claude prompts (markdown); orchestration = Python infrastructure code.
4. C1 (HIGH): FR-020 updated — project-based operations deferred to post-Platinum.
5. C2 (HIGH): Added FR-015a — MCP write tools MUST validate approval before execution (defense-in-depth).

**plan.md (3 edits):**
6. I2/D1 (HIGH): Fixed Node.js label from "MCP servers" to "PM2 + npx community tools".
7. A5 (LOW): Fixed architecture diagram PM2 annotation.
8. I1 (HIGH): Clarified `.claude/skills/` as canonical, `src/skills/` as source with symlinks.

**constitution.md (1 edit):**
9. I4 (MEDIUM): Updated Technology Stack table to "Python primary; npx for community tools".

**tasks.md (6 edits):**
10. U2 (HIGH): T026 now specifies full Claude CLI invocation contract (subprocess, timeout, exit codes, retry).
11. U3 (HIGH): Added T034a for PM2 production setup (log rotation, startup, monitoring).
12. C2 (HIGH): Added approval validation to T035, T040, T042, T047 (all MCP write tools).
13. U5 (MEDIUM): Added T058a for vault Git remote initialization.
14. F1 (MEDIUM): Added T064a for browser MCP server registration.
15. Updated notes: total tasks now 74 (T001-T071 + T034a, T058a, T064a).

Also fixed I3 (MEDIUM) in spec.md: MCP Server entity description updated to Python-primary.

## Outcome

- ✅ Impact: All CRITICAL (1) and HIGH (7) issues resolved. 3 MEDIUM issues also fixed as part of related edits. Task count: 71 → 74.
- 🧪 Tests: N/A — documentation edits only.
- 📁 Files: 4 files modified (spec.md, plan.md, tasks.md, constitution.md)
- 🔁 Next prompts: Run `/sp.implement` to begin Phase 1 execution. Remaining MEDIUM/LOW issues can be addressed incrementally.
- 🧠 Reflection: The most impactful fix was C2/FR-015a — adding defense-in-depth HITL validation at the MCP layer. This closes the constitution III bypass risk. The DEV_MODE/DRY_RUN distinction (U1) will prevent confusion during every phase of implementation.

## Evaluation notes (flywheel)

- Failure modes observed: None — all edits applied cleanly.
- Graders run and results (PASS/FAIL): All 8 HIGH/CRITICAL issues resolved. Constitution re-check: PASS.
- Prompt variant (if applicable): N/A
- Next experiment (smallest change to try): Proceed to /sp.implement for Phase 1.
