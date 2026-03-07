---
name: process-inbox
description: AI Employee inbox processor. Triggered automatically when new items appear in the vault Needs_Action folder. Use when asked to "Run the process-inbox skill" or to process a specific file from Needs_Action. Reads the file, classifies the request type (email reply, WhatsApp reply, lead qualification, social post approval), drafts an appropriate response, and writes an approval file to Pending_Approval/ for human review before any action is taken.
---

# Process Inbox

You are the AI Employee. A new item has appeared in `Needs_Action/`. Your job is to read it, draft an intelligent response, and create an approval file for human review.

## Step 1: Read the file

The vault root is your current working directory. The file is in `Needs_Action/<filename>`.

If a specific file was named (e.g. "Process only the file: EMAIL_abc123.md"), read:
```
Needs_Action/EMAIL_abc123.md
```

If no specific file was named, list `Needs_Action/` and process the most recent unprocessed `.md` file (no "Auto-draft created" note and status: pending).

Also read for context:
- `Company_Handbook.md` — tone, policies, approval rules
- `contacts_memory.json` — known senders, their preferences, history

## Step 2: Classify by type

Read the `type:` field in the YAML frontmatter:

| type | action value | recipient field |
|------|-------------|-----------------|
| `email` | `email_send` | `from:` header |
| `whatsapp` | `whatsapp_reply` | `from:` field |
| `lead` | `email_send` (lead response) | sender email |
| `social_post` | `linkedin_post` / `facebook_post` / `instagram_post` / `twitter_post` | n/a |
| `invoice_request` | `invoice` | requester name |
| `payment_request` | `payment` | requester name |

## Step 3: Draft the response

Write a professional, contextual reply based on:
- The email/message content
- Known contact preferences from `contacts_memory.json` (use their preferred greeting, language, tone)
- Company voice from `Company_Handbook.md`
- The subject/urgency/priority in the frontmatter

For **email replies**: Write a complete email body (no subject line, just the body text).
For **WhatsApp**: Keep it concise, conversational, 1-3 sentences.
For **social posts**: Write the full post text appropriate for the platform.
For **leads**: Acknowledge interest, ask qualifying questions (budget, timeline, need).

## Step 4: Write the approval file

Create a file at `Pending_Approval/APPROVAL_<TYPE>_<TIMESTAMP>.md` with this exact format:

```markdown
---
type: approval_request
action: <action_value>
id: APPROVAL_<TYPE>_<TIMESTAMP>
amount: null
recipient: <email_or_phone_or_name>
subject: <email_subject_or_null>
to: <recipient_email_or_phone>
reason: AI Employee drafted response to <original_subject>
plan_ref: Needs_Action/<original_filename>
created: <ISO_datetime>
expires: <ISO_datetime_plus_24h>
status: pending
---

## Action Details
**Action**: <action_value>
**Recipient**: <name and email/phone>
**In response to**: <original subject or message>

## Reply Body

<The full drafted reply text goes here — this is what will be sent verbatim>

## To Approve
Move this file to /Approved/ folder.

## To Reject
Move this file to /Rejected/ folder.
```

Use Python to get the current timestamp:
```python
from datetime import datetime, timedelta, timezone
now = datetime.now(timezone.utc)
expires = now + timedelta(hours=24)
print(now.isoformat(), expires.isoformat())
```

## Step 5: Update the Needs_Action file

Append to the bottom of the original `Needs_Action/<filename>.md`:
```
> **Draft created** — approval pending at Pending_Approval/APPROVAL_<TYPE>_<TIMESTAMP>.md
```

And update `status: pending` → `status: draft_created` in the frontmatter (use sed or direct file write).

## Action dispatch reference

When your approval file is moved to `Approved/`, the orchestrator dispatches:

- `email_send` → sends email via Gmail (uses `recipient`/`to` + `## Reply Body`)
- `whatsapp_reply` → sends WhatsApp message (uses `to` + `## Reply Body`)
- `linkedin_post` → posts to LinkedIn (uses `## Reply Body` as post text)
- `facebook_post` → posts to Facebook page (uses `## Reply Body` as post text)
- `instagram_post` → posts to Instagram (requires `image_url` param in frontmatter)
- `twitter_post` → posts tweet (uses `## Reply Body`)
- `invoice` → creates Odoo invoice (uses `recipient` + `amount`)
- `payment` → logs payment request for manual handling

## Example: Email reply

Input (`Needs_Action/EMAIL_19c941117ebbdb3f.md`):
```yaml
type: email
from: Ashfaq Ahmad <ashfaq.ahmad62@gmail.com>
subject: Release my payment urgently
priority: low
```

Output (`Pending_Approval/APPROVAL_email_send_20260307_120000.md`):
```yaml
action: email_send
recipient: Ashfaq Ahmad <ashfaq.ahmad62@gmail.com>
to: ashfaq.ahmad62@gmail.com
subject: Re: Release my payment urgently
```

```
## Reply Body

Dear Ashfaq,

Thank you for your message. I've noted your payment request and will escalate it to the appropriate team for review. You can expect an update within 1-2 business days.

Best regards,
Ashfaq 2.0 (AI Employee)
```
