# Tasks: Personal AI Employee (Digital FTE)

**Input**: Design documents from `/specs/personal-ai-employee/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/mcp-tools.md, quickstart.md

**Tests**: Not explicitly requested — test tasks omitted. Use `DEV_MODE=true` and `--dry-run` for system testing per spec.

**Organization**: Tasks grouped by user story (consolidated by tier). Each phase is independently testable.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2)
- Include exact file paths in descriptions

---

## Phase 1: Setup (Project Initialization)

**Purpose**: Initialize UV project, directory structure, and configuration files

- [x] T001 Initialize UV Python 3.13 project with `uv init --python 3.13` and configure `pyproject.toml` with project metadata, dependencies (google-api-python-client, google-auth, google-auth-oauthlib, playwright, watchdog, httpx, tweepy, apscheduler, mcp, python-dotenv), and dev dependencies (pytest, pytest-asyncio)
- [x] T002 Create source directory structure per plan.md: `src/watchers/`, `src/orchestrator/`, `src/mcp_servers/`, `src/skills/`, `src/vault/`, `src/vault/templates/`, `src/cli/`, `src/core/`, `src/cloud/deploy/`, `src/cloud/sync/`, `src/cloud/agent/`, `tests/unit/`, `tests/integration/`
- [x] T003 [P] Create `.env.example` with all required environment variables (VAULT_PATH, DEV_MODE, DRY_RUN, Gmail, WhatsApp, social media, Odoo credentials) per quickstart.md
- [x] T004 [P] Create `.gitignore` with entries for `.env`, `__pycache__/`, `.venv/`, `*.pyc`, WhatsApp session files, credential files, `node_modules/`
- [x] T005 [P] Create `.mcp.json` with MCP server configuration for email, social, odoo, and browser servers per contracts/mcp-tools.md
- [x] T006 [P] Create `ecosystem.config.js` PM2 configuration for orchestrator process with Python interpreter, env vars, and log paths
- [x] T007 Run `uv sync` to install all dependencies and verify lock file generation at `uv.lock`

**Checkpoint**: Project skeleton ready. `uv run python -c "import watchdog; import httpx; print('OK')"` succeeds.

---

## Phase 2: Foundational (Core Utilities)

**Purpose**: Shared infrastructure that ALL user stories depend on. MUST complete before any story work.

**⚠️ CRITICAL**: No user story work can begin until this phase is complete.

- [x] T008 Implement configuration manager in `src/core/config.py` — load `.env` via python-dotenv, expose typed settings: `VAULT_PATH` (Path), `DEV_MODE` (bool, default True), `DRY_RUN` (bool, default True), `GMAIL_CREDENTIALS_PATH`, rate limit values. Validate `VAULT_PATH` exists on startup.
- [x] T009 [P] Implement audit logger in `src/core/logger.py` — `AuditLogger` class that appends JSON log entries to `{VAULT_PATH}/Logs/YYYY-MM-DD.json`. Schema per data-model.md: timestamp, action_type, actor, target, parameters, approval_status, approved_by, result, error, source_file. Include 90-day retention cleanup method.
- [x] T010 [P] Implement exponential backoff retry decorator in `src/core/retry.py` — `@with_retry(max_attempts=3, base_delay=1, max_delay=60)` that catches configurable exception types, logs retries via audit logger, and re-raises after max attempts.
- [x] T011 [P] Implement rate limiter in `src/core/rate_limiter.py` — `RateLimiter` class with `check(action_type) -> bool` that enforces per-action limits (emails: 10/hr, payments: 3/hr, social: 5/hr). Uses in-memory sliding window. Returns False and logs when limit exceeded.
- [x] T012 Create `src/core/__init__.py` exporting Config, AuditLogger, with_retry, RateLimiter

**Checkpoint**: `uv run python -c "from src.core import Config, AuditLogger; print('Core ready')"` succeeds. All core utilities importable.

---

## Phase 3: US1 — Vault Foundation (Priority: P1) 🎯 MVP

**Goal**: Structured Obsidian vault with Dashboard.md, Company_Handbook.md, Business_Goals.md, and all canonical folders.

**Independent Test**: Run vault init script, open vault in Obsidian, verify all folders exist and templates render correctly.

### Implementation

- [x] T013 [US1] Create vault template `src/vault/templates/Dashboard.md` with YAML frontmatter (last_updated, owner: local) and sections: Status (watcher indicators), Pending Items (folder counts table), Recent Activity (last 10 log entries table), Financials MTD — per data-model.md Dashboard entity
- [x] T014 [P] [US1] Create vault template `src/vault/templates/Company_Handbook.md` with YAML frontmatter (last_updated, version) and sections: Communication Rules, Known Contacts table, Approval Thresholds table (email/payment/social/file ops), Rate Limits, Approval Expiry (24h default, overrides), WhatsApp Keywords list — per data-model.md Company Handbook entity
- [x] T015 [P] [US1] Create vault template `src/vault/templates/Business_Goals.md` with YAML frontmatter (last_updated, review_frequency) and sections: Revenue Target, Key Metrics table (metric/target/alert threshold), Active Projects list, Subscription Audit Rules — per hackathon doc template
- [x] T016 [US1] Implement vault initialization script `src/vault/init_vault.py` — accept `--path` argument (default from VAULT_PATH env), create vault directory and all canonical folders (`Inbox`, `Needs_Action`, `Plans`, `Pending_Approval`, `Approved`, `Rejected`, `In_Progress`, `Done`, `Accounting`, `Accounting/pending`, `Invoices`, `Briefings`, `Logs`, `Active_Project`, `Updates`), copy template files to vault root. Skip existing folders/files. Log initialization via AuditLogger.
- [x] T017 [US1] Create CLI entry point `src/cli/init_vault.py` — argparse wrapper for vault init with `--path` and `--force` (overwrite templates) flags. Print summary of created folders and files.

**Checkpoint**: Run `uv run python src/cli/init_vault.py --path /tmp/test_vault`. Verify 15 folders and 3 template files exist. Open in Obsidian — Dashboard, Handbook, Goals render correctly.

---

## Phase 4: US2+US3+US4 — Watchers (Priority: P1)

**Goal**: Three persistent background watchers (Gmail, WhatsApp, File System) following BaseWatcher pattern, writing action files to `/Needs_Action/`.

**Independent Test**: Drop a file into watch folder → verify `.md` in Needs_Action. Send important email → verify EMAIL_*.md appears within 2 minutes. Send WhatsApp keyword message → verify WHATSAPP_*.md appears.

### Implementation

- [x] T018 [US2] Implement `BaseWatcher` abstract class in `src/watchers/base_watcher.py` — ABC with `__init__(self, vault_path, check_interval)`, abstract methods `check_for_updates() -> list` and `create_action_file(item) -> Path`, concrete `run()` loop with try/except logging, DEV_MODE awareness. Uses AuditLogger for all events.
- [x] T019 [US4] Implement File System Watcher in `src/watchers/filesystem_watcher.py` — extends BaseWatcher, uses `watchdog.observers.Observer` and `FileSystemEventHandler`. On `on_created`: copy file to `Needs_Action/FILE_<filename>`, create companion `.md` metadata file with YAML frontmatter (type: file_drop, original_name, size, id, received, priority: high, status: pending). Handle same-name conflicts with timestamp suffix. Ignore directories.
- [x] T020 [US2] Implement Gmail Watcher in `src/watchers/gmail_watcher.py` — extends BaseWatcher with `check_interval=120`. Uses google-api-python-client with OAuth2. `check_for_updates()`: query `is:unread is:important` PLUS unread from known contacts (loaded from Company_Handbook.md's Known Contacts table). Dedup via `processed_ids` set. `create_action_file()`: write `EMAIL_<gmail_id>.md` with YAML frontmatter (type: email, id, from, subject, received, priority: high|low, status: pending). DEV_MODE: log but don't mark as read.
- [x] T021 [P] [US2] Implement Gmail OAuth2 CLI helper in `src/cli/gmail_auth.py` — run Google OAuth2 installed app flow, save credentials to `GMAIL_CREDENTIALS_PATH`, handle token refresh. Uses google-auth-oauthlib.
- [x] T022 [US3] Implement WhatsApp Watcher in `src/watchers/whatsapp_watcher.py` — extends BaseWatcher with `check_interval=30`. Uses playwright persistent browser context at `WHATSAPP_SESSION_PATH`. `check_for_updates()`: navigate to WhatsApp Web, wait for chat list, find unread messages, check against keyword list from Company_Handbook.md. `create_action_file()`: write `WHATSAPP_<contact>_<timestamp>.md`. Detect QR code screen → create ALERT_auth_expired.md. DEV_MODE: no read receipts or interactions.
- [x] T023 Create `src/watchers/__init__.py` exporting BaseWatcher, GmailWatcher, WhatsAppWatcher, FileSystemWatcher

**Checkpoint**: Start filesystem watcher → drop file → verify `FILE_*.md` in Needs_Action. Start Gmail watcher (DEV_MODE) → send important email → verify `EMAIL_*.md` appears. WhatsApp watcher may require QR scan for initial session.

---

## Phase 5: US5 — Claude Code Reasoning Loop (Priority: P1)

**Goal**: Claude Code reads `/Needs_Action/`, creates Plans and Approval Requests in the vault.

**Independent Test**: Place a test `EMAIL_*.md` in Needs_Action, trigger Claude skill, verify `PLAN_*.md` created in Plans with actionable steps.

### Implementation

- [x] T024 [US5] Create Agent Skill `src/skills/process_inbox.md` (and symlink to `.claude/skills/process-inbox.md`) — prompt template that instructs Claude to: read all `.md` files in `/Needs_Action/`, classify each by type (email/whatsapp/file_drop/alert), determine required actions, create `PLAN_<subject_slug>.md` in `/Plans/` with YAML frontmatter (id, created, source, status, requires_approval, approval_ref) and step checklist. For actions requiring approval: create approval request in `/Pending_Approval/` per data-model.md schema. Update source file status to `in_progress`. For unclassifiable items: create `REVIEW_<subject>.md` flagged for human review.
- [x] T025 [P] [US5] Create Agent Skill `src/skills/triage_email.md` (and symlink to `.claude/skills/triage-email.md`) — specialized prompt for email classification: extract sender, intent (invoice request, inquiry, support, spam), urgency, and recommended action. Reference Company_Handbook.md for known contact lookup and auto-approve rules.
- [x] T026 [US5] Create wrapper script `src/cli/trigger_reasoning.py` — invokes Claude Code via subprocess: `claude --cwd $VAULT_PATH --skill process-inbox --allowedTools Read,Write,Edit,Glob,Grep --timeout 300000`. Accepts `--file` flag to process a single item. Must handle: exit code 0 (success), non-zero (failure), timeout (5 min default, configurable via `CLAUDE_TIMEOUT`), and Claude API rate limits (retry with backoff, max 3 attempts). Logs invocation start, completion, and errors via AuditLogger. Returns structured result (success/failure + files created).

**Checkpoint**: Place test `EMAIL_test123.md` in Needs_Action with sample email content → run `uv run python src/cli/trigger_reasoning.py` → verify PLAN_*.md created in Plans with correct frontmatter and steps.

---

## Phase 6: US6 — Human-in-the-Loop Approval Workflow (Priority: P1)

**Goal**: File-based approval system where moving files between folders triggers or blocks actions.

**Independent Test**: Create approval request in Pending_Approval, move to Approved, verify orchestrator (Phase 7) will detect and act.

### Implementation

- [x] T027 [US6] Implement approval manager in `src/orchestrator/approval_manager.py` — `ApprovalManager` class: `create_approval(action, params, amount, recipient, reason, plan_ref) -> Path` that writes approval request `.md` to `/Pending_Approval/` with YAML frontmatter per data-model.md (type, action, id, amount, recipient, reason, plan_ref, created, expires=created+24h default, status: pending). `check_expired()` scans Pending_Approval for expired files (past `expires`), moves to `/Rejected/` with "Auto-rejected: expired" note, logs via AuditLogger. `process_approved(filepath)` reads approved file, returns action parameters. `process_rejected(filepath)` updates original task status, moves to `/Done/`.
- [x] T028 [US6] Implement folder watcher for approval folders in `src/orchestrator/approval_watcher.py` — uses watchdog to monitor `/Approved/` and `/Rejected/` for new files. On file detected in Approved: parse YAML frontmatter, invoke corresponding MCP action (email_send, payment, social_post), log result, move all related files (approval + plan + action item) to `/Done/`. On file in Rejected: update statuses, move to Done.

**Checkpoint**: Manually create `APPROVAL_test_2026-02-08.md` in Pending_Approval → move to Approved → verify ApprovalManager correctly parses it. Verify expired check moves old files to Rejected.

---

## Phase 7: US9+US17 — Orchestrator & Audit Logging (Priority: P2)

**Goal**: Master orchestrator that coordinates watchers, scheduling, and the file-based workflow. Comprehensive audit trail.

**Independent Test**: Start orchestrator → verify it launches watchers, detects Needs_Action changes, processes approvals, runs scheduled tasks, and logs everything.

### Implementation

- [x] T029 [US9] Implement scheduler in `src/orchestrator/scheduler.py` — uses APScheduler `BackgroundScheduler`. Methods: `add_scheduled_task(name, func, cron_expr)`, `add_interval_task(name, func, seconds)`, `start()`, `stop()`. Pre-configured tasks: expired approval check (every 5 min), log retention cleanup (daily at 2 AM), dashboard update (every 10 min).
- [x] T030 [US9] Implement health monitor in `src/orchestrator/health_monitor.py` — `HealthMonitor` class that tracks subprocess PIDs, checks if alive (via `os.kill(pid, 0)`), restarts dead processes, and creates ALERT files in Needs_Action when restart happens. Configurable check_interval (default 30s). Logs all events via AuditLogger.
- [x] T031 [US9] Implement master orchestrator in `src/orchestrator/orchestrator.py` — `Orchestrator` class: `start()` initializes Config, AuditLogger, launches watchers as subprocesses (GmailWatcher, WhatsAppWatcher, FileSystemWatcher), starts HealthMonitor, starts Scheduler, starts ApprovalWatcher. Watches `/Needs_Action/` via watchdog — on new file, triggers Claude reasoning (via `trigger_reasoning.py`). Graceful shutdown on SIGTERM/SIGINT. Main loop with `signal.pause()`.
- [x] T032 [US17] Implement dashboard updater in `src/orchestrator/dashboard_updater.py` — reads latest 10 entries from `/Logs/YYYY-MM-DD.json`, counts files in Needs_Action/Pending_Approval/In_Progress, writes updated `Dashboard.md` with current timestamps and counts. Called by scheduler every 10 minutes.
- [x] T033 [US17] Implement log viewer CLI in `src/cli/view_logs.py` — argparse CLI that reads and formats audit log JSON files. Flags: `--date today|YYYY-MM-DD`, `--action-type <type>`, `--last <n>`. Pretty-prints log entries as table.
- [x] T034 [US9] Create `src/orchestrator/__init__.py` exporting Orchestrator, Scheduler, HealthMonitor, ApprovalManager

- [x] T034a [US9] Create PM2 production setup guide and update `ecosystem.config.js` — configure: log rotation (`pm2 install pm2-logrotate`, max 10MB per file, retain 30 days), startup script (`pm2 startup` + `pm2 save` for boot persistence), monitoring (`pm2 monit`), env-specific configs (development vs production). Document in quickstart.md Production Mode section.

**Checkpoint**: Run `uv run python src/orchestrator/orchestrator.py` with DEV_MODE=true → verify watchers launch (check PIDs), scheduler starts, dashboard updates, logs are written. Drop a file → verify reasoning triggers. Run `pm2 start ecosystem.config.js` → verify PM2 manages orchestrator with log rotation.

---

## Phase 8: US7 — Email MCP Server (Priority: P2)

**Goal**: MCP server exposing send_email, draft_email, search_email tools to Claude Code via Gmail API.

**Independent Test**: Claude invokes `send_email` via MCP → email sent (or logged in dry-run). Rate limiting enforced.

### Implementation

- [x] T035 [US7] Implement Email MCP server in `src/mcp_servers/email_mcp.py` — uses `mcp` Python SDK. Declares tools: `send_email`, `draft_email`, `search_email` per contracts/mcp-tools.md schemas. `send_email`: (1) validates approval — checks `/Approved/` for matching approval file OR verifies recipient is in Company_Handbook.md auto-approve contacts (defense-in-depth per FR-015a), (2) validates rate limit via RateLimiter, (3) checks DRY_RUN (log only if true), (4) sends via Gmail API (google-api-python-client), returns success/error content. `draft_email` and `search_email` do not require approval (read-only or draft-only). Implements exponential backoff for transient errors. Logs every action via AuditLogger.
- [x] T036 [US7] Implement Gmail service wrapper in `src/mcp_servers/gmail_service.py` — encapsulates Gmail API calls (send, draft, search) with credential loading, token refresh, error handling. Shared between email_mcp and gmail_watcher.
- [x] T037 [US7] Update `.mcp.json` to register email MCP server with correct command (`uv run python src/mcp_servers/email_mcp.py`) and env vars

**Checkpoint**: Start email MCP server → Claude invokes `search_email` → returns results. Invoke `send_email` with DRY_RUN=true → logged but not sent. Verify rate limiting blocks after 10 calls.

---

## Phase 9: US8 — LinkedIn Auto-Posting (Priority: P2)

**Goal**: Scheduled LinkedIn posts via social MCP server. Drafts in vault, HITL for replies/DMs.

**Independent Test**: Schedule a post in dry-run → verify draft file created. In production mode → post appears on LinkedIn.

### Implementation

- [x] T038 [US8] Implement LinkedIn posting module in `src/mcp_servers/linkedin_client.py` — OAuth 2.0 token management (access + refresh), Posts API v2 (`POST /rest/posts`), image upload (two-step: register + upload), error handling. Supports DRY_RUN mode. Rate limiting via RateLimiter.
- [x] T039 [US8] Create Agent Skill `src/skills/social_scheduler.md` (and symlink to `.claude/skills/social-scheduler.md`) — prompt template that instructs Claude to: read Business_Goals.md for context, generate relevant business content, create scheduled post plans in `/Plans/SOCIAL_<date>.md` with frontmatter (platform, scheduled_time, status, content). HITL required for replies/DMs.
- [x] T040 [US8] Add LinkedIn posting to social MCP server in `src/mcp_servers/social_mcp.py` — initial implementation with `post_linkedin` tool per contracts/mcp-tools.md. `post_linkedin`: validates approval (scheduled posts auto-approved per Company_Handbook.md thresholds; replies/DMs always require explicit approval per FR-015a). Register in `.mcp.json`. Add scheduled posting task to orchestrator scheduler.

**Checkpoint**: Create `Plans/SOCIAL_2026-02-09.md` with LinkedIn post → orchestrator detects scheduled time → MCP posts (or logs in dry-run). Verify audit log entry.

---

## Phase 10: US10 — Odoo ERP Integration (Priority: P3)

**Goal**: Create/search invoices and get financial summaries via Odoo JSON-RPC through MCP server.

**Independent Test**: Invoke `create_invoice` via MCP → draft invoice appears in Odoo. HITL required to post.

### Implementation

- [x] T041 [US10] Implement Odoo JSON-RPC client in `src/mcp_servers/odoo_client.py` — connect to Odoo 19+ at ODOO_URL via JSON-RPC (`/jsonrpc`). Methods: `authenticate()`, `search_read(model, domain, fields)`, `create(model, values)`, `write(model, ids, values)`. HTTPS with SSL validation. Queue actions locally to `/Accounting/pending/` when Odoo unreachable.
- [x] T042 [US10] Implement Odoo MCP server in `src/mcp_servers/odoo_mcp.py` — uses `mcp` Python SDK. Tools: `create_invoice`, `search_invoices`, `get_financial_summary` per contracts/mcp-tools.md. `create_invoice`: validates approval file exists in `/Approved/` before creation (defense-in-depth per FR-015a). All invoice creations are draft-only (never auto-post). `search_invoices` and `get_financial_summary` do not require approval (read-only). Logs via AuditLogger.
- [x] T043 [US10] Update `.mcp.json` to register Odoo MCP server with ODOO_URL, ODOO_DB, ODOO_USERNAME, ODOO_PASSWORD env vars

**Checkpoint**: With running Odoo instance → invoke `create_invoice` → draft invoice appears in Odoo Accounting. Invoke `search_invoices` → returns results. Offline Odoo → action queued in `/Accounting/pending/`.

---

## Phase 11: US11 — Social Media (Facebook, Instagram, Twitter/X) (Priority: P3)

**Goal**: Post to Facebook, Instagram, and Twitter/X via social MCP server. Weekly engagement summaries.

**Independent Test**: Schedule posts in dry-run → draft files created per platform. Engagement summary generates.

### Implementation

- [x] T044 [US11] Implement Facebook posting module in `src/mcp_servers/facebook_client.py` — Graph API v20+ integration. Page token management via System User. `post_to_page(page_id, message, image_url, link)`. Error handling with retry. DRY_RUN support.
- [x] T045 [P] [US11] Implement Instagram posting module in `src/mcp_servers/instagram_client.py` — Content Publishing API via Graph API. Two-step publish (create container → publish). Business account validation. Image URL must be publicly accessible. 25 posts/day hard limit enforcement. DRY_RUN support.
- [x] T046 [P] [US11] Implement Twitter/X posting module in `src/mcp_servers/twitter_client.py` — X API v2 via `tweepy`. OAuth 1.0a for non-expiring tokens. Character limit validation (280). Media upload via v1.1 endpoint. DRY_RUN support.
- [x] T047 [US11] Extend social MCP server `src/mcp_servers/social_mcp.py` — add tools `post_facebook`, `post_instagram`, `post_twitter`, `get_social_metrics` per contracts/mcp-tools.md. Each write tool: (1) validates approval — scheduled posts auto-approved per Company_Handbook.md; replies/DMs always require explicit approval file (FR-015a defense-in-depth), (2) enforces rate limits, (3) checks DRY_RUN, (4) logs via AuditLogger. `get_social_metrics` is read-only and requires no approval.
- [x] T048 [US11] Implement engagement metrics collector in `src/mcp_servers/social_metrics.py` — fetch engagement data (likes, comments, shares, impressions) from each platform API for the last N days. Generate summary `.md` in `/Briefings/`.

**Checkpoint**: With DEV_MODE=true → invoke each `post_*` tool → draft files created. `get_social_metrics` returns formatted summary. With valid API keys → actual posts appear on platforms.

---

## Phase 12: US12 — Weekly CEO Briefing (Priority: P3)

**Goal**: Auto-generated Monday Morning CEO Briefing analyzing tasks, finances, social media, and goals.

**Independent Test**: Populate vault with sample week data → trigger briefing → verify output matches template with calculated metrics.

### Implementation

- [x] T049 [US12] Create Agent Skill `src/skills/generate_briefing.md` (and symlink to `.claude/skills/generate-briefing.md`) — prompt template instructing Claude to: read `Business_Goals.md` (targets), scan `/Done/` files from the past week (completed tasks, calculate completion times), read `/Accounting/` and Odoo financial data (revenue, expenses, subscriptions), read social media engagement summaries from `/Briefings/`, compare actuals vs targets, identify bottlenecks (tasks exceeding expected duration), detect subscription anomalies (no login 30 days, cost increase >20%), generate `/Briefings/YYYY-MM-DD_Monday_Briefing.md` per data-model.md CEO Briefing schema.
- [x] T050 [US12] Add weekly briefing scheduled task to orchestrator scheduler in `src/orchestrator/scheduler.py` — cron expression: Sunday 23:00 (generates Monday briefing). Invokes Claude with generate-briefing skill. Logs execution.
- [x] T051 [US12] Create sample data generator `tests/fixtures/generate_sample_week.py` — creates sample action items, plans, done files, accounting entries, and business goals in a temp vault for testing the briefing flow.

**Checkpoint**: Run sample data generator → trigger briefing skill → verify `/Briefings/YYYY-MM-DD_Monday_Briefing.md` contains: Executive Summary, Revenue (week/MTD/trend), Completed Tasks, Bottlenecks table, Proactive Suggestions, Upcoming Deadlines.

---

## Phase 13: US13 — Ralph Wiggum Persistence Loop (Priority: P3)

**Goal**: Claude persists on multi-step tasks until completion using the installed Ralph Loop plugin.

**Independent Test**: Start a Ralph loop with a 3-step task → Claude iterates through all steps → exits when done.

### Implementation

- [x] T052 [US13] Create orchestrator integration for Ralph Wiggum in `src/orchestrator/ralph_integration.py` — `start_ralph_loop(prompt, completion_promise, max_iterations)` that: writes state file, invokes Claude with `/ralph-loop` command, monitors for completion. `trigger_vault_processing()` convenience method that starts a Ralph loop with prompt: "Process all items in /Needs_Action, create plans, request approvals. Move completed to /Done. Output <promise>TASK_COMPLETE</promise> when empty." Max iterations: 10.
- [x] T053 [US13] Add Ralph loop trigger to orchestrator — when `/Needs_Action/` has >3 pending items, use Ralph loop instead of single-shot Claude invocation for batch processing. Configurable threshold in Config.
- [x] T054 [US13] Create Agent Skill `src/skills/ralph_vault_processor.md` — prompt optimized for Ralph loop iteration: check Needs_Action items, process one at a time, create plan, handle approvals, move completed items, report progress, output `<promise>TASK_COMPLETE</promise>` only when Needs_Action is truly empty.

**Checkpoint**: Place 5 test action items in Needs_Action → start Ralph loop → Claude processes all 5 iteratively → all moved to Done → Claude exits with TASK_COMPLETE promise.

---

## Phase 14: US14+US15+US16 — Cloud Deployment & Vault Sync (Priority: P4)

**Goal**: GCP VM running 24/7 with Odoo, cloud agent (draft-only), and Git-based vault sync.

**Independent Test**: Platinum demo — email arrives while local offline → cloud drafts reply → local approves after sync → email sends.

### Implementation

- [x] T055 [US14] Create GCP VM provisioning script `src/cloud/deploy/setup-vm.sh` — gcloud CLI commands to: create e2-standard-2 VM (2 vCPU, 8GB RAM) in us-central1 with Ubuntu 24.04 LTS, 50GB SSD boot disk, firewall rules (TCP 443, 22), static IP reservation. Install Python 3.13, UV, Node.js 24, PM2, Git, nginx, Playwright dependencies.
- [x] T056 [P] [US15] Create Odoo installation script `src/cloud/deploy/install-odoo.sh` — install PostgreSQL, Odoo 19 Community Edition from source, configure Odoo with production settings. Create systemd service for Odoo with auto-restart.
- [x] T057 [P] [US15] Create nginx reverse proxy config `src/cloud/deploy/nginx.conf` — HTTPS termination for Odoo (Let's Encrypt via certbot), proxy_pass to Odoo on localhost:8069, security headers, rate limiting.
- [x] T058 [US15] Create Odoo backup script `src/cloud/deploy/backup-odoo.sh` — daily cron job to backup PostgreSQL database and Odoo filestore to GCS bucket or local archive. Verify backup integrity. Retain 7 daily + 4 weekly backups.
- [x] T058a [US16] Initialize vault as Git repository for sync — `git init` the vault directory, create a private GitHub/GCP Cloud Source repo, configure `.gitignore` to exclude `.env`, `*.session`, `*credentials*`, `*.key`, and any secret files. Add remote, create initial commit, push. Deploy SSH keys on cloud VM for passwordless push/pull. Document in cloud deployment README.
- [x] T059 [US16] Implement vault sync script `src/cloud/sync/vault_sync.sh` — cron job (every 2 min): `git add -A && git commit -m "auto-sync $(date)" && git pull --rebase && git push`. Handle merge conflicts by preserving both versions and creating conflict resolution file in `/Needs_Action/`. Exclude secrets via `.gitignore`.
- [x] T060 [US16] Implement conflict resolver `src/cloud/sync/conflict_resolver.py` — detect Git merge conflicts in vault files, preserve both versions (local and remote) as separate files, create `ALERT_conflict_<filename>.md` in Needs_Action for human resolution.
- [x] T061 [US16] Enforce single-writer rule for Dashboard.md — cloud agent writes updates to `/Updates/` folder, local agent's dashboard_updater.py merges Updates into Dashboard.md. Add cloud-update detection to dashboard_updater.
- [x] T062 [US14] Implement cloud agent orchestrator `src/cloud/agent/cloud_agent.py` — stripped-down orchestrator for cloud: runs Gmail Watcher only (no WhatsApp — local owns session), runs Social MCP (draft-only), processes Needs_Action items but creates only drafts/approval requests (never executes send actions). Implements claim-by-move rule: first agent to move file from Needs_Action to `/In_Progress/<agent>/` owns it.
- [x] T063 [US14] Implement claim-by-move rule in `src/orchestrator/claim_manager.py` — `claim(item_path, agent_name) -> bool` that atomically moves file from Needs_Action to `/In_Progress/<agent>/`. Returns False if file already moved (another agent claimed it). Used by both local and cloud orchestrators.
- [x] T064 [US14] Create cloud deployment README `src/cloud/deploy/README.md` — step-by-step guide: create GCP account, run setup-vm.sh, install Odoo, configure vault sync, start cloud agent. Include security checklist and monitoring setup.
- [x] T064a [US14] Configure browser MCP server — register `@anthropic/browser-mcp` (community npx tool) in `.mcp.json` per contracts/mcp-tools.md. Used for payment portal interactions (Platinum tier). No custom code needed — uses existing `navigate_and_interact` tool contract. All browser actions require HITL approval. Add `HEADLESS=true` env var.

**Checkpoint**: Platinum demo end-to-end: 1) Local machine offline. 2) Send email. 3) Cloud agent detects, drafts reply, creates approval file. 4) Vault syncs via Git. 5) Local comes online, user sees approval in Pending_Approval. 6) User moves to Approved. 7) Vault syncs. 8) Local agent sends email via MCP. 9) Files move to Done. 10) Audit log records all steps.

---

## Phase 15: Polish & Cross-Cutting Concerns

**Purpose**: Final hardening, documentation, and demo preparation

- [x] T065 [P] Create `src/cli/status.py` — system status CLI showing: watcher process statuses (running/stopped), orchestrator health, vault folder counts, recent errors, DEV_MODE/DRY_RUN status, GCP VM status (if configured)
- [x] T066 [P] Create comprehensive `.env.example` documentation with inline comments explaining each variable, which tier requires it, and how to obtain credentials (OAuth setup links, developer portal URLs)
- [x] T067 Implement log retention cleanup in `src/core/logger.py` — `cleanup_old_logs(retention_days=90)` method that archives or deletes log files older than retention period. Integrate with scheduler (daily at 2 AM).
- [x] T068 Security audit — verify: no credentials in code, `.env` in `.gitignore`, DRY_RUN defaults to true, rate limits enforced, approval workflow prevents unauthorized actions, vault sync excludes secrets, HTTPS for Odoo
- [x] T069 Create demo video script `docs/demo-script.md` — 5-10 minute walkthrough covering: vault setup, watcher demo (email + file drop), Claude reasoning, HITL approval flow, CEO briefing, cloud agent (Platinum)
- [x] T070 Run quickstart.md validation — follow quickstart.md end-to-end on a fresh environment, fix any incorrect steps or missing dependencies
- [x] T071 Create project README.md — architecture overview, tier descriptions, setup instructions (link to quickstart.md), security disclosure, demo video link, hackathon tier declaration (Platinum)

**Checkpoint**: All tiers functional. README complete. Demo video script ready. Security audit passed.

---

## Dependencies & Execution Order

### Phase Dependencies

- **Phase 1 (Setup)**: No dependencies — start immediately
- **Phase 2 (Foundational)**: Depends on Phase 1 — BLOCKS all user stories
- **Phase 3 (US1 Vault)**: Depends on Phase 2 — **MVP milestone**
- **Phase 4 (Watchers)**: Depends on Phase 2 + Phase 3 (needs vault)
- **Phase 5 (Reasoning)**: Depends on Phase 3 (needs vault with Needs_Action items)
- **Phase 6 (HITL)**: Depends on Phase 3 (needs vault folders)
- **Phase 7 (Orchestrator)**: Depends on Phase 4 + Phase 5 + Phase 6 (coordinates them)
- **Phase 8 (Email MCP)**: Depends on Phase 2 (uses core utilities), integrates with Phase 7
- **Phase 9 (LinkedIn)**: Depends on Phase 7 (needs scheduler) + Phase 8 (MCP pattern)
- **Phase 10 (Odoo)**: Depends on Phase 2 (uses core utilities), independent of other MCP servers
- **Phase 11 (Social Media)**: Depends on Phase 9 (extends social_mcp.py)
- **Phase 12 (CEO Briefing)**: Depends on Phase 7 (scheduler) + Phase 3 (vault data)
- **Phase 13 (Ralph Wiggum)**: Depends on Phase 7 (orchestrator integration)
- **Phase 14 (Cloud)**: Depends on ALL previous phases (deploys the full system)
- **Phase 15 (Polish)**: Depends on all desired phases being complete

### User Story Independence

| Story | Can Start After | Dependencies on Other Stories |
|-------|----------------|-------------------------------|
| US1 (Vault) | Phase 2 | None — fully independent |
| US2-4 (Watchers) | Phase 3 | Needs vault (US1) |
| US5 (Reasoning) | Phase 3 | Needs vault (US1) |
| US6 (HITL) | Phase 3 | Needs vault (US1) |
| US7 (Email MCP) | Phase 2 | Independent of other MCP servers |
| US8 (LinkedIn) | Phase 7 | Needs orchestrator for scheduling |
| US9 (Orchestrator) | Phase 4+5+6 | Coordinates watchers + reasoning + HITL |
| US10 (Odoo) | Phase 2 | Independent of other features |
| US11 (Social) | Phase 9 | Extends LinkedIn work |
| US12 (Briefing) | Phase 7 | Needs orchestrator + vault data |
| US13 (Ralph) | Phase 7 | Needs orchestrator |
| US14-16 (Cloud) | All phases | Full system deployment |

### Parallel Opportunities

Within Phase 2: T009, T010, T011 can all run in parallel (different files).
Within Phase 4: T019 (filesystem), T020 (gmail), T022 (whatsapp) have a dependency on T018 (base_watcher) but are otherwise parallel.
Within Phase 11: T044 (facebook), T045 (instagram), T046 (twitter) can all run in parallel.
Phase 8 and Phase 10 are fully independent and can run in parallel.
Phase 12 and Phase 13 are independent and can run in parallel.

---

## Parallel Example: Phase 4 (Watchers)

```bash
# First: create base class
Task T018: "Implement BaseWatcher in src/watchers/base_watcher.py"

# Then: all three watchers in parallel (different files, same base class)
Task T019: "Implement FileSystemWatcher in src/watchers/filesystem_watcher.py"
Task T020: "Implement GmailWatcher in src/watchers/gmail_watcher.py"
Task T022: "Implement WhatsAppWatcher in src/watchers/whatsapp_watcher.py"
```

---

## Implementation Strategy

### MVP First (Bronze Tier — Phases 1-3)

1. Complete Phase 1: Setup (~1 hour)
2. Complete Phase 2: Foundational (~2 hours)
3. Complete Phase 3: US1 Vault Foundation (~2 hours)
4. **STOP and VALIDATE**: Open vault in Obsidian, verify templates
5. Demo: "Vault initialized with dashboard and handbook"

### Bronze Complete (Phases 1-4)

6. Complete Phase 4: Watchers (~4 hours)
7. **VALIDATE**: Drop file → verify action item in vault
8. Demo: "File drop and Gmail monitoring working"

### Silver Tier (Phases 5-9)

9. Complete Phases 5-6: Reasoning + HITL (~3 hours)
10. Complete Phase 7: Orchestrator (~4 hours)
11. Complete Phases 8-9: Email MCP + LinkedIn (~4 hours)
12. **VALIDATE**: End-to-end: email arrives → Claude plans → approval → email sent
13. Demo: "Autonomous email handling with approval workflow"

### Gold Tier (Phases 10-13)

14. Complete Phases 10-11: Odoo + Social Media (~6 hours)
15. Complete Phase 12: CEO Briefing (~3 hours)
16. Complete Phase 13: Ralph Wiggum (~2 hours)
17. **VALIDATE**: Weekly briefing generates, Ralph loop processes batch items
18. Demo: "Full cross-domain integration with CEO briefing"

### Platinum Tier (Phase 14)

19. Complete Phase 14: Cloud Deployment (~8 hours)
20. Complete Phase 15: Polish (~4 hours)
21. **VALIDATE**: Platinum demo end-to-end
22. Demo: "24/7 cloud operation with vault sync"

### Total Estimated: ~43 hours (aligns with Platinum 60+ hours including setup, API approvals, testing)

---

## Notes

- [P] tasks = different files, no dependencies on incomplete tasks
- [Story] label maps task to specific user story for traceability
- All MCP server tools support DRY_RUN mode — test safely before production
- Social media API developer accounts should be applied for immediately (LinkedIn/Facebook approval takes weeks)
- Start with DEV_MODE=true for ALL development work
- Commit after each phase checkpoint
- The Ralph Wiggum plugin is already installed — no setup needed for Phase 13
- Tasks T034a, T058a, T064a were added during /sp.analyze remediation (total: 74 tasks)
