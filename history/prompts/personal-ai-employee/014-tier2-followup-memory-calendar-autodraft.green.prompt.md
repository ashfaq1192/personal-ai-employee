---
id: "014"
title: "Tier 2 — Auto-Draft, Contact Memory, Follow-Up Engine, Content Calendar"
stage: green
date: "2026-03-06"
surface: agent
model: claude-sonnet-4-6
feature: personal-ai-employee
branch: main
user: ashfaq
command: "yes please continue to tier 2"
labels: ["tier2", "auto-draft", "contact-memory", "followup-engine", "content-calendar"]
links:
  spec: "specs/personal-ai-employee/spec.md"
  ticket: "null"
  adr: "null"
  pr: "null"
files:
  - "src/watchers/gmail_watcher.py (_create_auto_draft, contact memory wiring)"
  - "src/orchestrator/contact_memory.py (NEW)"
  - "src/orchestrator/meeting_scheduler.py (preferred_name via ContactMemory)"
  - "src/orchestrator/followup_engine.py (NEW)"
  - "src/orchestrator/content_calendar.py (NEW)"
  - "src/orchestrator/orchestrator.py (_run_followup_engine, _generate_content_calendar, cron wiring)"
  - "src/cli/web_dashboard.py (api_contacts_memory, GET /api/contacts)"
tests:
  - "All imports OK"
  - "ContactMemory smoke test: 2 interactions, greeting=Hi Alice, history=[email_received, email_sent]"
  - "ContentCalendar post generation: Monday/linkedin 231 chars, Tuesday/facebook 213 chars"
---

## Prompt

> yes please continue to tier 2

## Implemented

### 1. Inbound Email Auto-Draft
- `gmail_watcher._create_auto_draft()` called after every inbound email (non-dev_mode)
- Creates Gmail Draft: "Hi {first_name}, Thank you for your email. I'll get back to you shortly."
- Applies `AI/drafted` label
- Appends `> Auto-draft created` note to EMAIL_*.md

### 2. Agent Memory & Personalization (`contact_memory.py`)
- Persisted at `vault/contacts_memory.json`
- Records every email interaction with full name, summary, timestamp
- `preferred_greeting(email)` → "Hi Alice,"
- `all_contacts()` sorted by last_interaction
- Dashboard GET /api/contacts endpoint

### 3. Proactive Follow-Up Engine (`followup_engine.py`)
- Daily at 09:00 (orchestrator cron)
- Scans Done/ + Approved/ for tasks > 3 days old
- Filters to outbound tasks (email_send, whatsapp_reply, meeting_request)
- 7-day cooldown prevents repeat follow-ups per recipient
- Writes FOLLOWUP_*.md to Needs_Action/ with personalised draft + action checklist

### 4. Content Calendar (`content_calendar.py`)
- Sunday at 08:00 (orchestrator cron)
- 7 posts/week: LinkedIn Mon/Thu, Twitter Wed/Fri, Facebook Tue/Sun, Instagram Sat
- Optimal UTC times: LinkedIn 08:00, Twitter 12:00, Facebook 15:00, Instagram 18:00
- Topic rotation: insight → tip → leadership → story → question → BTS → recap
- Writes Plans/Content_Calendar_YYYY-MM-DD.md with full post table
- Schedules each post via scheduler.schedule_at()
