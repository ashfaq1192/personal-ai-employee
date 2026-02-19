# Gmail OAuth Setup Guide

This guide walks you through authorizing the Personal AI Employee to access your Gmail account using OAuth 2.0.

## Prerequisites

- A Google account with Gmail
- Access to [Google Cloud Console](https://console.cloud.google.com)
- Python 3.13+ and `uv` installed

---

## Step 1 — Create a Google Cloud Project

1. Go to [Google Cloud Console](https://console.cloud.google.com)
2. Click **Select a project** → **New Project**
3. Name it `ai-employee` (or any name)
4. Click **Create**

---

## Step 2 — Enable Gmail API

1. In the Cloud Console, navigate to **APIs & Services → Library**
2. Search for **Gmail API**
3. Click it, then click **Enable**

---

## Step 3 — Configure OAuth Consent Screen

1. Go to **APIs & Services → OAuth consent screen**
2. Choose **External** (for personal accounts)
3. Fill in:
   - App name: `AI Employee`
   - User support email: your Gmail address
   - Developer contact: your Gmail address
4. Click **Save and Continue** through the remaining screens
5. On the **Test users** screen, add your Gmail address
6. Click **Save and Continue** then **Back to Dashboard**

---

## Step 4 — Create OAuth 2.0 Credentials

1. Go to **APIs & Services → Credentials**
2. Click **Create Credentials → OAuth client ID**
3. Application type: **Desktop app**
4. Name: `AI Employee Local`
5. Click **Create**
6. In the dialog, click **Download JSON**
7. Save the file to:
   ```
   ~/.config/ai-employee/gmail_credentials.json
   ```
   Create the directory if it doesn't exist:
   ```bash
   mkdir -p ~/.config/ai-employee
   mv ~/Downloads/client_secret_*.json ~/.config/ai-employee/gmail_credentials.json
   ```

---

## Step 5 — Authorize with Your Gmail Account

Run the authorization flow:

```bash
uv run python src/cli/gmail_auth.py
```

This will:
1. Open a browser window asking you to sign in to Google
2. Request permission to read and send Gmail
3. Save the OAuth token to `~/.config/ai-employee/gmail_token.json`

> **Note:** On first run, Google may show a warning "This app isn't verified." Click **Advanced → Go to AI Employee (unsafe)** to proceed (this is expected for personal/test apps).

---

## Step 6 — Update `.env`

Edit your `.env` file and set:

```bash
GMAIL_CREDENTIALS=~/.config/ai-employee/gmail_credentials.json
DEV_MODE=false
DRY_RUN=false
```

> **Warning:** Setting `DRY_RUN=false` allows the agent to send real emails. Start with `DRY_RUN=true` to validate behavior first.

---

## Step 7 — Verify

Run the health check:

```bash
./doctor
```

The Gmail watcher should show `[PASS]` or `[WARN]` (warn is OK if vault isn't initialized yet).

Start the Gmail watcher:

```bash
uv run python src/watchers/gmail_watcher.py
```

You should see:
```
[INFO] Gmail watcher started — polling every 60s
```

---

## Troubleshooting

| Error | Fix |
|-------|-----|
| `credentials file not found` | Check path in `.env` matches downloaded JSON location |
| `invalid_client` | Re-download credentials — the client secret may have changed |
| `Token expired` | Delete `~/.config/ai-employee/gmail_token.json` and re-run `gmail_auth.py` |
| `Access blocked` | Re-add your email as a test user in OAuth consent screen |

---

## Security Notes

- The credentials JSON and token are **never committed to version control** (`.gitignore` excludes `~/.config/`)
- The AI Employee only requests `gmail.readonly` and `gmail.send` scopes — not full account access
- All outbound emails go through the `Pending_Approval` folder first when `DRY_RUN=false`
