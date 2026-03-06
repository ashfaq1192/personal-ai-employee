---
name: gmail-pubsub-push
description: Setup guide for Gmail Push Notifications via Google Cloud Pub/Sub. Use when setting up real-time Gmail inbox monitoring (replacing polling), running setup_gmail_push.py, configuring GCP ADC credentials, registering a Gmail watch, or debugging PubSub permission errors. Covers the correct GCP project ID, ADC account switching, the 4-step setup script, required .env vars, and all common errors encountered in WSL2/dev environments.
---

# Gmail PubSub Push Setup

Replaces polling-based `GmailWatcher` with event-driven `GmailPushWatcher`. Google fires a PubSub message immediately when a new email arrives — zero latency, no rate limits.

## Prerequisites

- `google-cloud-pubsub` installed: `uv add google-cloud-pubsub`
- `gcloud` CLI authenticated with the **correct account** (see below)
- Gmail OAuth token valid (see `gmail-oauth` skill)

## Critical: ADC Must Match Gmail Account

`pubsub_v1.PublisherClient()` uses Application Default Credentials (ADC), not the Gmail OAuth token. These are separate auth systems.

### Check and switch ADC account

```bash
# See which account ADC is using
gcloud auth application-default print-access-token | python3 -c "
import sys, urllib.request, json
token = sys.stdin.read().strip()
d = json.loads(urllib.request.urlopen('https://oauth2.googleapis.com/tokeninfo?access_token=' + token).read())
print('ADC account:', d.get('email'))
"

# If wrong account — revoke and re-login
gcloud auth application-default revoke --quiet
gcloud auth application-default login
# Opens browser → sign in with the Gmail account owner (e.g. ashfaqahmed1192@gmail.com)
```

## Finding the Correct GCP Project ID

Two IDs exist and are easy to confuse:
- **OAuth Client project** (e.g. `project-030bbae1-06bc-44ee-bbe`) — where the OAuth app lives
- **Gmail-linked GCP project** (e.g. `ai-employee-487907`) — where PubSub must be created

**The Gmail watch registration will reveal the correct project ID in its error message** if you use the wrong one:
```
"Invalid topicName does not match projects/ai-employee-487907/topics/*"
```

Use that project ID.

## Run the Setup Script

```bash
uv run python scripts/setup_gmail_push.py --project ai-employee-487907
```

This runs 4 steps:
1. Creates PubSub topic `gmail-push`
2. Grants `gmail-api-push@system.gserviceaccount.com` publish permission
3. Creates pull subscription `gmail-pull-sub`
4. Registers Gmail watch (uses Gmail OAuth token, not ADC)

Steps 1-3 use ADC. Step 4 uses `gmail_credentials.json`.

## Add to .env

After successful setup, add:
```
GMAIL_PUBSUB_PROJECT=ai-employee-487907
GMAIL_PUBSUB_TOPIC=projects/ai-employee-487907/topics/gmail-push
GMAIL_PUBSUB_SUBSCRIPTION=projects/ai-employee-487907/subscriptions/gmail-pull-sub
```

## Gmail Watch Renewal

The Gmail watch expires after **7 days**. The `GmailPushWatcher` renews it automatically on startup. Re-run `setup_gmail_push.py` if it lapses.

## Common Errors

| Error | Cause | Fix |
|-------|-------|-----|
| `403 IAM_PERMISSION_DENIED pubsub.topics.create` | ADC is wrong account or account lacks Pub/Sub Admin role | Switch ADC account (`gcloud auth application-default login`) |
| `400 Invalid topicName does not match projects/X/topics/*` | Wrong GCP project ID | Use the project ID from the error message |
| `invalid_grant` on step 4 | Gmail OAuth token expired | Re-run OOB auth flow (see gmail-oauth skill), then re-run setup script |
| `google-cloud-pubsub not installed` | Missing package | `uv add google-cloud-pubsub` |
| `UserWarning: without a quota project` | ADC user creds lack quota project | Harmless warning — set with `gcloud auth application-default set-quota-project ai-employee-487907` to silence |
