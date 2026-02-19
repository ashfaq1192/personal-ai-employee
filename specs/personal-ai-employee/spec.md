# Feature Specification: Personal AI Employee (Digital FTE) — Platinum Tier

**Feature Branch**: `personal-ai-employee`
**Created**: 2026-02-08
**Status**: Draft
**Tier**: Platinum (All tiers inclusive: Bronze → Silver → Gold → Platinum)
**Input**: Build a local-first, agent-driven, human-in-the-loop Personal AI Employee using Claude Code + Obsidian that proactively manages personal and business affairs 24/7.

---

## Clarifications

### Session 2026-02-08

- Q: Where does the Obsidian vault live relative to the project repo? → A: Vault is a separate directory outside the project repo (e.g., `~/AI_Employee_Vault/`). Code (watchers, orchestrator, MCP servers) lives in the project repo; runtime data (action items, logs, approvals) lives in the vault.
- Q: Which cloud provider for Platinum 24/7 deployment? → A: GCP (Google Cloud) using the $300 free trial credit. Deployment targets a GCP Compute Engine VM.
- Q: What Gmail filtering criteria should the watcher use? → A: Known contacts (defined in `Company_Handbook.md`) + Gmail important flag. Emails from known contacts are always captured; Gmail's importance filter catches the rest. Unknown senders go to a lower-priority queue for Claude triage.
- Q: What is the default approval request expiry duration? → A: 24 hours default. Aligns with daily dashboard check schedule. Individual actions can override (e.g., urgent payments could use 4-hour expiry). Configurable in `Company_Handbook.md`.
- Q: What Python runtime and dependency management tool? → A: UV with Python 3.13. UV manages virtual environments and lockfiles. Project initialized as a UV Python project per hackathon prerequisites.

---

## User Scenarios & Testing

### User Story 1 — Obsidian Vault Foundation (Priority: P1)

As a user, I want a structured Obsidian vault with a real-time dashboard and company handbook so that my AI Employee has a centralized knowledge base and operating rules.

**Why this priority**: The vault is the foundational layer — every other feature reads from and writes to it. Without it, nothing works.

**Independent Test**: Create the vault, open in Obsidian, verify all folders exist and `Dashboard.md` renders correctly with placeholder data.

**Acceptance Scenarios**:

1. **Given** a fresh project setup, **When** the vault initialization script runs with a configurable vault path (default: `~/AI_Employee_Vault/`), **Then** the vault directory is created separately from the project repo and all canonical folders are created (`/Inbox`, `/Needs_Action`, `/Plans`, `/Pending_Approval`, `/Approved`, `/Rejected`, `/In_Progress`, `/Done`, `/Accounting`, `/Invoices`, `/Briefings`, `/Logs`, `/Active_Project`).
2. **Given** the vault is initialized, **When** I open `Dashboard.md` in Obsidian, **Then** I see sections for: bank balance (placeholder), pending messages count, active projects list, and recent activity log.
3. **Given** the vault is initialized, **When** I open `Company_Handbook.md`, **Then** I see configurable rules for: communication tone, payment approval thresholds, auto-approve contacts list, rate limits, and ethical boundaries.
4. **Given** the vault is initialized, **When** I open `Business_Goals.md`, **Then** I see sections for: revenue targets, key metrics with alert thresholds, active projects, and subscription audit rules.

---

### User Story 2 — Gmail Watcher (Priority: P1)

As a user, I want a background process that monitors my Gmail for urgent/important emails and creates actionable markdown files in the vault so that my AI Employee can process them.

**Why this priority**: Email is the primary business communication channel; capturing inbound requests is essential for the perception layer.

**Independent Test**: Send a test email marked as important, verify the watcher creates an `.md` file in `/Needs_Action/` within 2 minutes with correct metadata.

**Acceptance Scenarios**:

1. **Given** the Gmail Watcher is running with valid OAuth2 credentials, **When** an unread email arrives from a known contact (listed in `Company_Handbook.md`) OR is flagged as important by Gmail, **Then** a markdown file `EMAIL_<id>.md` is created in `/Needs_Action/` with YAML frontmatter (type, from, subject, received, priority: high|low, status). Emails from unknown senders that are Gmail-important are created with `priority: low` for Claude triage.
2. **Given** an email has been processed, **When** the watcher checks again, **Then** it does NOT create a duplicate file for the same email ID.
3. **Given** the Gmail API returns a rate limit error, **When** the watcher retries, **Then** it uses exponential backoff (1s, 2s, 4s, max 60s) and logs the retry attempt.
4. **Given** the Gmail API credentials expire, **When** the watcher detects a 401 error, **Then** it logs a warning, pauses operations, and creates an alert file in `/Needs_Action/` requesting credential refresh.
5. **Given** `DEV_MODE=true`, **When** the watcher runs, **Then** it logs all actions but does NOT mark emails as read or modify the Gmail state.

---

### User Story 3 — WhatsApp Watcher (Priority: P1)

As a user, I want a background process that monitors WhatsApp Web for messages containing business keywords and creates actionable files so that my AI Employee can respond to urgent client requests.

**Why this priority**: WhatsApp is a critical real-time communication channel for many businesses; missing urgent messages means lost revenue.

**Independent Test**: Send a WhatsApp message containing "invoice" to a monitored chat, verify the watcher creates an `.md` file in `/Needs_Action/` within 30 seconds.

**Acceptance Scenarios**:

1. **Given** the WhatsApp Watcher is running with a persistent Playwright session, **When** an unread message contains a keyword from the `WhatsApp Keywords` list in `Company_Handbook.md` (e.g., "urgent", "invoice", "payment", "help", "asap"), **Then** a markdown file `WHATSAPP_<contact>_<timestamp>.md` is created in `/Needs_Action/`. The keyword list is maintained exclusively in `Company_Handbook.md` — the watcher reads it at startup and on file change.
2. **Given** the WhatsApp Web session expires, **When** the watcher detects a QR code screen, **Then** it logs a warning and creates an alert file requesting re-authentication.
3. **Given** the watcher is running, **When** no keyword-matching messages exist, **Then** no files are created and no errors are logged.
4. **Given** `DEV_MODE=true`, **When** a keyword message is detected, **Then** the file is created but no read receipts or interactions are performed on WhatsApp.

---

### User Story 4 — File System Watcher (Priority: P1)

As a user, I want a process that monitors a designated drop folder and automatically moves new files into the vault for processing so that I can trigger AI actions by simply dropping files.

**Why this priority**: Provides the simplest interaction pattern — drag-and-drop triggers automation without any UI.

**Independent Test**: Drop a PDF into the watch folder, verify it appears in `/Needs_Action/` with a companion `.md` metadata file within 5 seconds.

**Acceptance Scenarios**:

1. **Given** the File System Watcher is running on a configured drop folder, **When** a new file is created in the folder, **Then** the file is copied to `/Needs_Action/FILE_<filename>` and a metadata `.md` file is created alongside it with frontmatter (type: file_drop, original_name, size).
2. **Given** a directory is dropped into the watch folder, **When** the watcher detects it, **Then** the directory is ignored (only files are processed).
3. **Given** a file with the same name already exists in `/Needs_Action/`, **When** a new file with the same name is dropped, **Then** the new file is renamed with a timestamp suffix to avoid conflicts.

---

### User Story 5 — Claude Code Reasoning Loop (Priority: P1)

As a user, I want Claude Code to read the `/Needs_Action/` folder, analyze items, create action plans, and write results back to the vault so that incoming items are automatically triaged and planned.

**Why this priority**: This is the "brain" — without reasoning, watchers just pile up unprocessed files.

**Independent Test**: Place a test email `.md` in `/Needs_Action/`, trigger Claude, verify a `Plan.md` is created in `/Plans/` with actionable steps.

**Acceptance Scenarios**:

1. **Given** one or more `.md` files exist in `/Needs_Action/`, **When** Claude Code is triggered (by orchestrator or manually), **Then** it reads each file, determines the action type, and creates a corresponding `PLAN_<subject>.md` in `/Plans/` with checkboxes for next steps.
2. **Given** an action requires human approval (payment, new contact email, bulk send), **When** Claude creates the plan, **Then** it also creates an approval request file in `/Pending_Approval/` and the plan references it.
3. **Given** Claude processes an item, **When** the plan is created, **Then** the original file in `/Needs_Action/` is updated with `status: in_progress` and a reference to the plan file.
4. **Given** Claude encounters an item it cannot classify, **When** processing, **Then** it creates a `REVIEW_<subject>.md` in `/Needs_Action/` flagged for human review rather than making assumptions.

---

### User Story 6 — Human-in-the-Loop Approval Workflow (Priority: P1)

As a user, I want a file-based approval system where my AI Employee requests permission before executing sensitive actions so that I maintain control over payments, emails to new contacts, and other high-risk operations.

**Why this priority**: Safety is non-negotiable. Without HITL, the system is a liability.

**Independent Test**: Trigger an action requiring approval, verify the approval file appears in `/Pending_Approval/`, move it to `/Approved/`, verify the action executes.

**Acceptance Scenarios**:

1. **Given** Claude determines an action requires approval, **When** it creates the approval request, **Then** the file in `/Pending_Approval/` contains: action type, parameters, amount (if financial), recipient, reason, created timestamp, expiry timestamp (default: created + 24 hours, overridable per action type via `Company_Handbook.md`), and status: pending.
2. **Given** an approval file is moved to `/Approved/`, **When** the orchestrator detects it, **Then** the corresponding MCP action is executed within 60 seconds.
3. **Given** an approval file is moved to `/Rejected/`, **When** the orchestrator detects it, **Then** the action is cancelled, the original task is updated with `status: rejected`, and the file moves to `/Done/`.
4. **Given** an approval file has expired (past `expires` timestamp, default 24 hours from creation), **When** the orchestrator checks, **Then** it moves the file to `/Rejected/` with a note "Auto-rejected: expired" and alerts the user.
5. **Given** a payment approval exists, **When** the user approves, **Then** the audit log records: timestamp, action_type, actor, target, parameters, approval_status, approved_by, and result.

---

### User Story 7 — Email MCP Server (Priority: P2)

As a user, I want an MCP server that can send emails, draft replies, and search my inbox so that Claude Code can execute email actions after approval.

**Why this priority**: Email is the primary outbound action channel. Required for Silver tier and above.

**Independent Test**: Use Claude to send a test email via the MCP server (with approval), verify it arrives at the destination.

**Acceptance Scenarios**:

1. **Given** the Email MCP server is running with valid Gmail API credentials, **When** Claude invokes `send_email(to, subject, body, attachment?)`, **Then** the email is sent and a success/failure result is returned.
2. **Given** `DRY_RUN=true`, **When** Claude invokes `send_email`, **Then** the email is logged but NOT actually sent.
3. **Given** rate limiting is configured at 10 emails/hour, **When** the 11th email is attempted within an hour, **Then** the action is queued and a rate-limit warning is logged.
4. **Given** an email send fails, **When** the error is transient (network), **Then** it retries with exponential backoff. **When** the error is permanent (invalid address), **Then** it returns failure immediately.

---

### User Story 8 — LinkedIn Auto-Posting (Priority: P2)

As a user, I want my AI Employee to automatically post business content to LinkedIn on a schedule so that I maintain consistent social media presence without manual effort.

**Why this priority**: Social media posting drives business leads. Required for Silver tier.

**Independent Test**: Schedule a test post, verify it appears on LinkedIn at the scheduled time (or in dry-run, verify the draft is created in the vault).

**Acceptance Scenarios**:

1. **Given** a scheduled post exists in `/Plans/SOCIAL_<date>.md`, **When** the scheduled time arrives, **Then** the post is published to LinkedIn via MCP/API and logged.
2. **Given** a post is of type "reply" or "DM", **When** it is created, **Then** it ALWAYS requires HITL approval (never auto-posted).
3. **Given** `DEV_MODE=true`, **When** a post is scheduled, **Then** it creates a draft file in `/Briefings/` but does NOT publish.
4. **Given** the LinkedIn API returns an error, **When** posting fails, **Then** the post is moved to `/Needs_Action/` with status: failed and the error details logged.

---

### User Story 9 — Orchestrator & Scheduling (Priority: P2)

As a user, I want a master orchestrator process that coordinates all watchers, handles scheduling (cron-like), and manages the file-based workflow so that the system runs autonomously.

**Why this priority**: The orchestrator is the glue that connects perception, reasoning, and action. Without it, each component runs in isolation.

**Independent Test**: Start the orchestrator, verify it launches all watchers, triggers Claude on `/Needs_Action/` changes, and processes approved actions.

**Acceptance Scenarios**:

1. **Given** the orchestrator starts, **When** it initializes, **Then** it launches all configured watchers as child processes and monitors their health.
2. **Given** a new file appears in `/Needs_Action/`, **When** the orchestrator detects it (within 30 seconds), **Then** it triggers Claude Code to process the file.
3. **Given** a file appears in `/Approved/`, **When** the orchestrator detects it, **Then** it triggers the appropriate MCP action within 60 seconds.
4. **Given** a scheduled task is configured (e.g., daily briefing at 8 AM), **When** the time arrives, **Then** the orchestrator triggers the task and logs the execution.
5. **Given** a watcher process crashes, **When** the orchestrator's health check detects it, **Then** it restarts the watcher within 60 seconds and logs the restart event.

---

### User Story 10 — Odoo ERP Integration (Priority: P3)

As a user, I want my AI Employee to integrate with Odoo Community Edition for accounting so that invoices, payments, and financial records are managed in a proper ERP system.

**Why this priority**: Professional accounting is a Gold tier requirement that transforms the AI Employee from a task manager into a business operations platform.

**Independent Test**: Create a test invoice via the Odoo MCP server, verify it appears in Odoo's accounting module.

**Acceptance Scenarios**:

1. **Given** the Odoo MCP server is connected to a running Odoo 19+ instance, **When** Claude invokes `create_invoice(client, amount, items)`, **Then** a draft invoice is created in Odoo via JSON-RPC API.
2. **Given** an invoice is created in Odoo, **When** it needs to be posted/sent, **Then** it ALWAYS requires HITL approval (draft-only by default).
3. **Given** the Odoo instance is self-hosted, **When** the MCP server connects, **Then** it uses HTTPS and validates the SSL certificate.
4. **Given** the Odoo API is unreachable, **When** an accounting action is attempted, **Then** the action is queued locally in `/Accounting/pending/` and retried when connectivity is restored.

---

### User Story 11 — Social Media Integration (Facebook, Instagram, Twitter/X) (Priority: P3)

As a user, I want my AI Employee to post to Facebook, Instagram, and Twitter/X, and generate engagement summaries so that I have comprehensive social media management.

**Why this priority**: Full social media coverage is a Gold tier requirement for cross-domain business management.

**Independent Test**: Schedule posts to each platform in dry-run mode, verify draft files are created with correct platform-specific formatting.

**Acceptance Scenarios**:

1. **Given** a social media post plan exists, **When** it targets Facebook, **Then** the post is published via Graph API and engagement metrics are logged.
2. **Given** a social media post plan exists, **When** it targets Instagram, **Then** the post is published via Instagram Graph API (business account required) with image/carousel support.
3. **Given** a social media post plan exists, **When** it targets Twitter/X, **Then** the post is published via X API v2 with character limit validation (280 chars).
4. **Given** posts were published during the week, **When** the weekly summary is triggered, **Then** a summary `.md` file is generated in `/Briefings/` with engagement metrics (likes, comments, shares, impressions) per platform.
5. **Given** any reply or DM is generated, **When** before sending, **Then** HITL approval is ALWAYS required.

---

### User Story 12 — Weekly CEO Briefing (Priority: P3)

As a user, I want my AI Employee to generate a weekly "Monday Morning CEO Briefing" that audits my business tasks, finances, and social media to give me a comprehensive status report.

**Why this priority**: The CEO Briefing is the flagship feature that demonstrates proactive AI value — it transforms the system from reactive to strategic.

**Independent Test**: Populate the vault with sample data for a week, trigger the briefing, verify the output matches the CEO Briefing template with calculated metrics.

**Acceptance Scenarios**:

1. **Given** a scheduled trigger fires every Sunday night, **When** the briefing generates, **Then** it produces `/Briefings/YYYY-MM-DD_Monday_Briefing.md` with sections: Executive Summary, Revenue (this week, MTD, trend), Completed Tasks, Bottlenecks, Proactive Suggestions, and Upcoming Deadlines.
2. **Given** bank transaction data exists in `/Accounting/`, **When** the briefing analyzes it, **Then** it identifies subscription patterns, flags unused subscriptions (no login in 30 days), and flags cost increases >20%.
3. **Given** tasks exist in `/Done/` for the week, **When** the briefing analyzes them, **Then** it calculates average completion time and flags tasks that exceeded their expected duration.
4. **Given** `Business_Goals.md` has defined targets, **When** the briefing compares actuals, **Then** it reports percentage progress toward each target and flags any metric below alert thresholds.

---

### User Story 13 — Ralph Wiggum Persistence Loop (Priority: P3)

As a user, I want Claude Code to persist on multi-step tasks until completion using the Ralph Wiggum Stop hook pattern so that complex tasks don't get abandoned mid-way.

**Why this priority**: Autonomous multi-step completion is what makes this a true "employee" rather than a one-shot assistant. Gold tier requirement.

**Independent Test**: Start a Ralph loop with a 3-step task, verify Claude iterates through all steps and only exits when the task file moves to `/Done/`.

**Acceptance Scenarios**:

1. **Given** a Ralph loop is started with a prompt and `--max-iterations 10`, **When** Claude tries to exit before the task is complete, **Then** the Stop hook blocks the exit, re-injects the prompt, and Claude continues.
2. **Given** a task uses promise-based completion, **When** Claude outputs `<promise>TASK_COMPLETE</promise>`, **Then** the Stop hook allows exit.
3. **Given** a task uses file-movement completion, **When** the task file is moved to `/Done/`, **Then** the Stop hook detects it and allows exit.
4. **Given** `--max-iterations` is reached, **When** the task is still incomplete, **Then** the loop exits with a warning and creates a `REVIEW_<task>.md` in `/Needs_Action/` for human follow-up.

---

### User Story 14 — Cloud 24/7 Deployment (Priority: P4)

As a user, I want my AI Employee to run on a cloud VM 24/7 with work-zone specialization so that email triage, social media drafts, and scheduling happen even when my local machine is off.

**Why this priority**: Always-on operation is the Platinum differentiator — the AI Employee never sleeps.

**Independent Test**: Shut down the local machine, send an email, verify the cloud agent drafts a reply and creates an approval file. When local returns, approve and verify the email is sent.

**Cloud Provider**: GCP Compute Engine VM (funded via $300 free trial credit).

**Acceptance Scenarios**:

1. **Given** a GCP Compute Engine VM is running, **When** an email arrives while local is offline, **Then** the cloud agent drafts a reply and writes an approval file to the synced vault.
2. **Given** the cloud agent creates a draft, **When** the local machine comes online and the vault syncs, **Then** the user sees the approval file in `/Pending_Approval/`.
3. **Given** the user approves on local, **When** the vault syncs to cloud, **Then** the cloud agent detects the approval and the local agent executes the send via MCP.
4. **Given** cloud and local are both online, **When** an item appears in `/Needs_Action/`, **Then** the claim-by-move rule ensures only ONE agent (first to move to `/In_Progress/<agent>/`) processes it.
5. **Given** secrets exist on local (.env, WhatsApp session, banking creds), **When** the vault syncs, **Then** secrets are NEVER included in the sync (enforced by `.gitignore` / sync exclusion rules).

**Cloud Owns**: Email triage, draft replies, social post drafts/scheduling (draft-only; requires local approval).
**Local Owns**: Approvals, WhatsApp session, payments/banking, final "send/post" actions.

---

### User Story 15 — Cloud Odoo Deployment (Priority: P4)

As a user, I want Odoo Community Edition deployed on a cloud VM with HTTPS, backups, and health monitoring so that my accounting system is always available.

**Why this priority**: Platinum tier requires persistent ERP access for both cloud and local agents.

**Independent Test**: Access Odoo via HTTPS, create a test invoice, verify backup runs, verify health monitor alerts on simulated downtime.

**Acceptance Scenarios**:

1. **Given** Odoo 19+ is deployed on a GCP Compute Engine VM, **When** accessed via browser, **Then** it serves over HTTPS with a valid certificate.
2. **Given** the cloud agent connects via MCP, **When** it creates a draft invoice, **Then** the invoice appears in Odoo as draft status (never auto-posted).
3. **Given** a backup schedule is configured, **When** the backup time arrives, **Then** the database and filestore are backed up and the backup is verified.
4. **Given** the Odoo process crashes, **When** the health monitor detects it, **Then** it restarts the service within 2 minutes and sends an alert.

---

### User Story 16 — Vault Sync (Cloud ↔ Local) (Priority: P4)

As a user, I want the Obsidian vault to sync between my local machine and cloud VM via Git so that both agents share the same state.

**Why this priority**: Vault sync is the communication channel between cloud and local agents. Required for Platinum.

**Independent Test**: Make a change on local, verify it appears on cloud within 5 minutes. Make a change on cloud, verify it appears on local after sync.

**Acceptance Scenarios**:

1. **Given** Git-based sync is configured, **When** either agent writes a file, **Then** it commits and pushes within 2 minutes.
2. **Given** both agents modify different files, **When** sync occurs, **Then** both changes are merged without conflict.
3. **Given** both agents modify the same file, **When** a conflict occurs, **Then** the system preserves both versions and creates a conflict resolution file in `/Needs_Action/`.
4. **Given** `.env`, WhatsApp session files, or banking credentials exist, **When** sync runs, **Then** these files are excluded by `.gitignore` and NEVER appear in the remote repository.
5. **Given** `Dashboard.md` is a single-writer file (local owns), **When** cloud has updates, **Then** cloud writes to `/Updates/` and local merges them into `Dashboard.md`.

---

### User Story 17 — Comprehensive Audit Logging (Priority: P2)

As a user, I want every action taken by my AI Employee to be logged in structured JSON format so that I can review, debug, and audit all system behavior.

**Why this priority**: Audit logging is a safety requirement across all tiers — you can't trust what you can't inspect.

**Independent Test**: Trigger several actions (email send, file create, approval), verify each produces a log entry in `/Logs/YYYY-MM-DD.json` with the required schema.

**Acceptance Scenarios**:

1. **Given** any action is executed (email, payment, social post, file move), **When** it completes, **Then** a JSON log entry is appended to `/Logs/YYYY-MM-DD.json` with: timestamp, action_type, actor, target, parameters, approval_status, approved_by, result.
2. **Given** logs exist for 90+ days, **When** the retention cleanup runs, **Then** logs older than 90 days are archived or deleted.
3. **Given** a user opens `Dashboard.md`, **When** it renders, **Then** it shows the 10 most recent activity log entries.

---

### Edge Cases

- What happens when the vault disk is full? → Watchers pause, alert the user, and resume when space is freed.
- What happens when two watchers detect the same external event? → Deduplication via unique ID in filename (e.g., `EMAIL_<gmail_id>.md`).
- What happens when the orchestrator crashes while an action is in-progress? → State files in `/In_Progress/` remain; orchestrator resumes processing on restart.
- What happens when Claude misinterprets a message? → HITL catches it at the approval stage; review queue handles ambiguous items.
- What happens when the cloud and local machines are both offline? → Watchers queue locally on each machine; sync resolves when connectivity restores.
- What happens when a `.md` file in `/Needs_Action/` is malformed? → Claude flags it for human review instead of processing.

---

## Requirements

### Functional Requirements

- **FR-001**: System MUST initialize an Obsidian vault at a configurable path (default: `~/AI_Employee_Vault/`) separate from the project repo, with all canonical folders and template files (`Dashboard.md`, `Company_Handbook.md`, `Business_Goals.md`). The vault path MUST be configurable via `VAULT_PATH` environment variable.
- **FR-002**: System MUST run three watchers (Gmail, WhatsApp, File System) as persistent background processes. Gmail Watcher MUST capture emails from known contacts (defined in `Company_Handbook.md`) and Gmail-important emails; unknown senders are triaged at lower priority.
- **FR-003**: All watchers MUST follow the `BaseWatcher` abstract class pattern with `check_for_updates()` and `create_action_file()` methods.
- **FR-004**: System MUST support two independent safety flags:
  - `DRY_RUN` (default: `true`): External **writes** are logged but not executed (emails not sent, posts not published, invoices not created). External **reads** (Gmail fetch, API queries) still operate normally. This is the production safety net.
  - `DEV_MODE` (default: `true`): Superset of `DRY_RUN` — additionally prevents external **reads** (watchers use mock data, no Gmail API calls, no WhatsApp session). Used during development/testing only.
  - When `DEV_MODE=true`, `DRY_RUN` is implicitly `true` regardless of its setting.
- **FR-005**: System MUST implement file-based HITL approval workflow (`/Pending_Approval/` → `/Approved/` or `/Rejected/`).
- **FR-006**: System MUST implement at least one MCP server for email operations (send, draft, search).
- **FR-007**: System MUST auto-post to LinkedIn on a configurable schedule.
- **FR-008**: System MUST integrate with Facebook, Instagram, and Twitter/X APIs for posting and engagement summaries.
- **FR-009**: System MUST integrate with Odoo Community 19+ via JSON-RPC API for accounting (invoices, payments).
- **FR-010**: System MUST generate a weekly CEO Briefing with revenue, tasks, bottlenecks, and proactive suggestions.
- **FR-011**: System MUST implement the Ralph Wiggum Stop hook pattern for multi-step task persistence.
- **FR-012**: System MUST deploy to a GCP Compute Engine VM (funded via $300 free trial) for 24/7 operation with work-zone specialization.
- **FR-013**: System MUST sync the vault between cloud and local via Git, excluding secrets.
- **FR-014**: System MUST log every action in structured JSON format with 90-day retention.
- **FR-015**: System MUST enforce rate limits: max 10 emails/hour, max 3 payments/hour.
- **FR-015a**: Each MCP server tool that performs a write action (send_email, post_linkedin, create_invoice, etc.) MUST validate that an approved approval file exists for the action OR the action falls within auto-approve thresholds defined in `Company_Handbook.md`, BEFORE executing. This is a defense-in-depth guard — even if invoked outside the orchestrator flow, sensitive actions cannot bypass HITL.
- **FR-016**: System MUST implement claim-by-move rule for multi-agent task ownership.
- **FR-017**: All Claude Code reasoning prompts MUST be implemented as Agent Skills (markdown files in `.claude/skills/`). Orchestration logic (Python scripts that invoke Claude, manage processes, or update the dashboard) is NOT required to be an Agent Skill — these are infrastructure code, not AI prompts.
- **FR-018**: System MUST implement exponential backoff retry for transient errors.
- **FR-019**: System MUST use a process manager (PM2/supervisord) for daemon lifecycle management.
- **FR-020**: System MUST support scheduled (cron-like via APScheduler) and continuous (watcher loops) operation types. Project-based operations (long-running multi-step work in `/Active_Project/`) are deferred to post-Platinum iteration — the vault folder is created but no workflow is implemented in the initial release.
- **FR-021**: Project MUST use UV as the Python dependency manager with Python 3.13 runtime. All Python dependencies MUST be locked via `uv.lock`.

### Key Entities

- **Action Item**: A markdown file in `/Needs_Action/` with YAML frontmatter describing an inbound event (email, message, file drop) that needs processing.
- **Plan**: A markdown file in `/Plans/` with checkboxes describing Claude's proposed steps to handle an action item.
- **Approval Request**: A markdown file in `/Pending_Approval/` requesting human permission for a sensitive action (payment, email to new contact).
- **Audit Log Entry**: A JSON object recording every system action with timestamp, actor, target, parameters, and result.
- **CEO Briefing**: A weekly markdown report in `/Briefings/` summarizing revenue, task completion, bottlenecks, and proactive suggestions.
- **Watcher**: A persistent Python process that monitors an external source and writes action items to the vault.
- **MCP Server**: A Python service (using the `mcp` Python SDK) exposing external capabilities (email, social media, accounting) to Claude Code via the Model Context Protocol. Community MCP tools (e.g., browser, mcp-odoo-adv) may use Node.js via `npx`.
- **Agent Skill**: A self-contained, reusable unit of AI functionality registered with Claude Code.

---

## Success Criteria

### Measurable Outcomes

- **SC-001**: Gmail Watcher detects and creates action files for 95%+ of important/urgent emails within 2 minutes of arrival.
- **SC-002**: WhatsApp Watcher detects keyword messages within 30 seconds with 0 false negatives on configured keywords.
- **SC-003**: File System Watcher processes dropped files within 5 seconds with 0 data loss.
- **SC-004**: HITL approval workflow prevents 100% of sensitive actions from executing without explicit human approval.
- **SC-005**: All system actions produce audit log entries — 0 unlogged actions.
- **SC-006**: CEO Briefing generates accurately within 5 minutes of scheduled trigger, covering all data sources.
- **SC-007**: Cloud agent continues operating when local machine is offline — Platinum demo scenario passes end-to-end.
- **SC-008**: System recovers from watcher crashes within 60 seconds via process manager auto-restart.
- **SC-009**: Rate limits are enforced with 0 violations (no more than 10 emails/hour, 3 payments/hour).
- **SC-010**: Vault sync between cloud and local completes within 5 minutes with 0 secret leaks.
- **SC-011**: Ralph Wiggum loop completes multi-step tasks without human re-prompting in 90%+ of cases.
- **SC-012**: System operates in `DEV_MODE` / `--dry-run` with 0 real external side effects.
