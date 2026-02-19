# Demo Video Recording Script

**Hackathon:** Personal AI Employee Hackathon 0: Building Autonomous FTEs (2026)
**Target Duration:** 5-10 minutes
**Tier Declaration:** PLATINUM

---

## Pre-Recording Checklist

### 1. Environment Setup

```bash
# Ensure you're in the project directory
cd /mnt/d/projects/hackathon-0

# Verify tests pass
uv run pytest tests/ -v --tb=short 2>&1 | tail -5
# Should show: "89 passed"

# Ensure DEV_MODE is enabled (safe for demo)
grep "DEV_MODE" .env
# Should show: DEV_MODE=true
```

### 2. Screen Recording Setup

- **Software:** OBS Studio, Loom, or QuickTime
- **Resolution:** 1920x1080 (or native resolution)
- **Audio:** Clear microphone (optional narration)
- **Terminal:** Dark theme, large font (14-16pt)
- **Browser:** Have README.md and GitHub repo open

### 3. Clean Up Vault

```bash
# Clear old demo files from Needs_Action
rm -f ~/AI_Employee_Vault/Needs_Action/EMAIL_demo_*.md
rm -f ~/AI_Employee_Vault/Pending_Approval/APPROVAL_*.md
rm -f ~/AI_Employee_Vault/Approved/APPROVAL_*.md
rm -f ~/AI_Employee_Vault/Done/DONE_*.md
rm -f ~/AI_Employee_Vault/Updates/CLOUD_*.md
```

---

## Video Script (Timed)

### Opening (0:00 - 0:30)

**[Show: Title slide or README.md]**

**Narration:**
> "Hi, I'm presenting my Personal AI Employee for Hackathon 0: Building Autonomous FTEs. This is a Platinum tier submission featuring a local-first, agent-driven automation system with human-in-the-loop safeguards."

**[Show: Architecture diagram from README.md]**

> "The architecture follows a perception-reasoning-action pattern: Watchers monitor external sources like Gmail and WhatsApp, Claude Code provides reasoning, and MCP servers execute actions. All data is stored locally in Obsidian for privacy and transparency."

---

### Segment 1: Project Overview (0:30 - 1:30)

**[Show: Terminal with project structure]**

```bash
# Show key directories
tree -L 2 src/
```

**Narration:**
> "Let me show you the project structure. We have:
> - **Watchers** in `src/watchers/` that monitor Gmail, WhatsApp, and file drops
> - **MCP Servers** in `src/mcp_servers/` for email, social media, and Odoo integration
> - **Orchestrator** in `src/orchestrator/` that coordinates everything
> - **Agent Skills** in `.claude/skills/` that Claude uses for specialized tasks
> - **Cloud deployment** scripts in `src/cloud/` for 24/7 operation"

**[Show: Test results]**

```bash
# Run tests (speed up this part or show pre-recorded)
uv run pytest tests/ -v --tb=short 2>&1 | tail -10
```

> "The system has 89 passing unit and integration tests, ensuring reliability across all components."

---

### Segment 2: Bronze Tier Demo (1:30 - 3:00)

**[Show: Terminal running demo script]**

```bash
# Run the end-to-end demo
uv run python scripts/demo_e2e.py
```

**Narration:**
> "Now let me demonstrate all four tiers working together. I'm running our end-to-end demo script which simulates real-world scenarios."

**[Wait for Bronze tier to complete]**

> "For Bronze tier, the Gmail Watcher detects a new email and creates an action file in the Needs_Action folder. Claude Code then processes this file using the triage-email skill and creates a plan."

**[Show: Action file content]**

```bash
# Show the created action file
cat ~/AI_Employee_Vault/Needs_Action/EMAIL_demo_*.md
```

> "Here's the action file created by the Gmail Watcher. It contains the email metadata, content, and suggested actions."

---

### Segment 3: Silver Tier Demo (3:00 - 4:30)

**[Show: Demo script continuing]**

**Narration:**
> "For Silver tier, we demonstrate the human-in-the-loop approval workflow. When Claude needs to send an email, it first creates an approval request."

**[Show: Approval file content]**

```bash
# Show approval file (if visible in output)
cat ~/AI_Employee_Vault/Pending_Approval/APPROVAL_*.md 2>/dev/null || echo "File already processed"
```

> "The approval request includes all details: recipient, subject, body, and the action required. A human reviews this file and moves it to the Approved folder to proceed, or Rejected to cancel."

**[Show: Demo output showing approval workflow]**

> "In our demo, the approval is automatically granted, the action is dispatched to the Email MCP, and since we're in DRY_RUN mode, it logs the intended action without actually sending. The file is then moved to Done."

---

### Segment 4: Gold Tier Demo (4:30 - 6:00)

**[Show: Demo script continuing to Gold tier]**

**Narration:**
> "Gold tier adds full business integration. We have MCP servers for:
> - **LinkedIn** for professional networking posts
> - **Facebook and Instagram** via Meta's API
> - **Twitter/X** for real-time updates
> - **Odoo ERP** for invoicing and accounting"

**[Show: CEO Briefing skill]**

```bash
# Show the briefing skill
cat .claude/skills/generate-briefing.md
```

> "The CEO Briefing skill autonomously audits business performance weekly. It reads Business_Goals.md, analyzes completed tasks from the Done folder, reviews transaction logs, and generates a comprehensive briefing with:
> - Revenue summary
> - Completed tasks
> - Bottlenecks identified
> - Proactive cost optimization suggestions"

**[Show: Demo output for Gold tier]**

> "In our demo, Claude processes the business data and would generate a Monday Morning CEO Briefing. In production, this runs every Sunday night via the scheduler."

---

### Segment 5: Platinum Tier Demo (6:00 - 7:30)

**[Show: Cloud agent code]**

```bash
# Show cloud agent architecture
cat src/cloud/agent/cloud_agent.py | head -50
```

**Narration:**
> "Platinum tier enables 24/7 always-on operation with cloud/local coordination. The cloud agent runs on a GCP VM and handles:
> - Email triage and draft replies
> - Social media post drafts and scheduling
> - All operations are draft-only, requiring local approval"

**[Show: Vault sync script]**

```bash
# Show sync mechanism
cat src/cloud/sync/vault_sync.sh
```

> "Vault synchronization uses Git to keep cloud and local instances in sync. Critical security rule: secrets never sync. The `.gitignore` excludes all credentials, WhatsApp sessions, and banking information."

**[Show: Demo output for Platinum tier]**

> "In our demo, we simulate an email arriving while the local instance is offline. The cloud agent processes it in draft-only mode, creates an approval request, and when local comes back online, the human approves and the local instance executes the send via MCP."

---

### Segment 6: Security & Safety (7:30 - 8:30)

**[Show: .env.example file]**

```bash
# Show security configuration
cat .env.example | head -20
```

**Narration:**
> "Security is built in from the ground up:
> - **Credential Management:** All secrets in `.env`, never committed to version control
> - **Safety Modes:** DEV_MODE and DRY_RUN flags for safe testing
> - **Rate Limiting:** 10 emails/hour, 3 payments/hour, 5 social posts/hour
> - **Audit Logging:** Every action logged with full context to `/Logs/`"

**[Show: Audit logs]**

```bash
# Show recent audit logs
cat ~/AI_Employee_Vault/Logs/*.json | tail -30
```

> "Here's the audit trail showing every action the AI took, including timestamps, actors, targets, and approval status."

---

### Segment 7: Agent Skills (8:30 - 9:30)

**[Show: All agent skills]**

```bash
# List all skills
ls -la .claude/skills/
```

**Narration:**
> "All AI functionality is implemented as Agent Skills, as required by the hackathon. We have five skills:
> 1. **triage-email.md** — Process incoming emails and suggest actions
> 2. **process-inbox.md** — Batch process all inbox items
> 3. **social-scheduler.md** — Schedule and post social media updates
> 4. **generate-briefing.md** — Create weekly CEO briefings
> 5. **ralph-vault-processor.md** — Batch process vault items with Ralph loop"

**[Show: One skill in detail]**

```bash
# Show triage-email skill
cat .claude/skills/triage-email.md
```

> "Each skill is a Markdown file that Claude reads and executes. This makes the AI's behavior transparent and auditable."

---

### Closing (9:30 - 10:00)

**[Show: README.md or submission guide]**

**Narration:**
> "To summarize, this Platinum tier submission includes:
> - ✅ All 89 tests passing
> - ✅ End-to-end demo script demonstrating all 4 tiers
> - ✅ MCP servers for email, social media, and Odoo
> - ✅ Human-in-the-loop approval workflow
> - ✅ Ralph Wiggum persistence loop for autonomous tasks
> - ✅ Cloud deployment scripts for 24/7 operation
> - ✅ Comprehensive security and audit logging
>
> The code is complete and demonstrated. For production use, you would configure real API credentials and deploy to a cloud VM.
>
> Documentation is in `HACKATHON_SUBMISSION.md` with full setup instructions and security disclosure.
>
> Thank you!"

**[Show: Final slide with GitHub repo URL and contact info]**

---

## Post-Recording Steps

### 1. Edit Video

- Trim any long pauses or errors
- Add captions if possible
- Ensure audio levels are consistent
- Add chapter markers (optional)

### 2. Upload

- Upload to YouTube (unlisted or public)
- Or use Google Drive / Dropbox
- Ensure link is accessible to judges

### 3. Submit

- Fill out submission form: https://forms.gle/JR9T1SJq5rmQyGkGA
- Include:
  - GitHub repo URL
  - Demo video URL
  - Tier declaration: Platinum
  - Brief description (2-3 sentences)

---

## Backup Plan (If Live Demo Fails)

If something goes wrong during live recording:

1. **Use pre-recorded segments:** Record each segment separately and edit together
2. **Show screenshots:** Capture key outputs and show in video
3. **Use demo output file:** Show the `demo_results_*.md` file which has all results

```bash
# Show demo results file
cat ~/AI_Employee_Vault/Logs/demo_results_*.md
```

---

## Common Issues & Solutions

### Issue: Tests fail during recording

**Solution:** Run tests beforehand and show cached output, or use:
```bash
uv run pytest tests/ -v --tb=short 2>&1 | tee test_output.txt
# Then show the output file
```

### Issue: Claude Code takes too long

**Solution:** Pre-run Claude commands and show the output files instead of running live:
```bash
# Show output instead of running
cat ~/AI_Employee_Vault/Plans/*.md
```

### Issue: Vault files not found

**Solution:** Re-run demo script:
```bash
uv run python scripts/demo_e2e.py
```

---

*Recording Script v1.0 - February 18, 2026*
