---
name: meta-setup
description: Guide for setting up Meta (Facebook/Instagram) API credentials from scratch — App creation, token generation, asset ID discovery, and .env configuration. Use when the user needs to connect to Meta Graph API, generate a 60-day access token, find Page ID or Instagram User ID, debug token errors, or configure META_ACCESS_TOKEN/FACEBOOK_PAGE_ID/INSTAGRAM_USER_ID env vars. Also covers the Page Token exchange pattern required by the working codebase.
---

# Meta API Setup

## The 5 Required .env Keys

```
META_APP_ID=<numeric app ID>
META_APP_SECRET=<secret string>
META_ACCESS_TOKEN=<60-day long-lived token starting with EAAM...>
FACEBOOK_PAGE_ID=<numeric page ID>
INSTAGRAM_USER_ID=<numeric IG business account ID>
```

## Setup Flow (do in order)

### 1. Create Meta App
- [developers.facebook.com](https://developers.facebook.com) → Create App → **Business** type (critical — other types lack Instagram tools)
- App Settings → Basic → copy `META_APP_ID` and `META_APP_SECRET`
- Use Cases → add **"Manage messaging & content on Instagram"**

### 2. Link the Golden Triangle (must all be connected)
- Facebook Page must be a **Business Page**
- Instagram account must be **Business or Creator** account
- Facebook Page Settings → Linked Accounts → Instagram must be fully confirmed

### 3. Generate 60-Day Token
Open [Graph API Explorer](https://developers.facebook.com/tools/explorer/):
1. Method: GET, Endpoint: `me?fields=id,name`
2. Add **all** permissions in the sidebar:
   - `pages_manage_posts`
   - `pages_read_engagement`
   - `instagram_basic`
   - `instagram_content_publish`
   - `instagram_manage_comments`
3. Click **Generate Access Token** → approve popups → select your Page
4. Go to [Access Token Debugger](https://developers.facebook.com/tools/debug/accesstoken/), paste token → **Extend Access Token** → this is your `META_ACCESS_TOKEN`

### 4. Get Asset IDs
In Graph API Explorer (with your new token):
```
me/accounts?fields=name,id,instagram_business_account
```
- `FACEBOOK_PAGE_ID` = `id` field
- `INSTAGRAM_USER_ID` = `instagram_business_account.id` field

## Critical Code Pattern: Page Token Exchange

**The working code always exchanges the user token for a Page Access Token before API calls.** This is required for both Facebook posts and Instagram publishing.

```python
# Exchange user token → Page Access Token (see facebook_client.py:25-35)
def _get_page_token(user_token: str, page_id: str) -> str:
    resp = httpx.get(
        f"https://graph.facebook.com/v20.0/{page_id}",
        params={"fields": "access_token", "access_token": user_token},
    )
    resp.raise_for_status()
    return resp.json()["access_token"]
```

See `references/code-patterns.md` for Instagram 2-step publish and metrics patterns.

## Verify Connection

```bash
# Load .env vars into terminal (must run in same terminal session)
export $(grep -v '^#' .env | xargs)

# Quick sanity check
uv run python -c "
from src.mcp_servers.social_metrics import collect_platform_metrics
import os
result = collect_platform_metrics('facebook', 7,
    meta_access_token=os.environ.get('META_ACCESS_TOKEN'),
    facebook_page_id=os.environ.get('FACEBOOK_PAGE_ID'))
print(result)
"
```

If you see `{"error": "Token required"}` → the `export` command above was not run in the same terminal session.

## Common Errors

| Error | Cause | Fix |
|-------|-------|-----|
| `OAuthException 190` | Token expired | Re-generate via Graph API Explorer → Extend |
| `access_token missing` | Page token exchange failed | Check `FACEBOOK_PAGE_ID` matches the page the token was generated for |
| `(#10) Application does not have permission` | Missing permission scope | Re-generate token and add all 5 permissions above |
| `instagram_business_account` not in response | IG not linked to FB page | Fix the Golden Triangle (Step 2) |
| `INSTAGRAM_USER_ID` wrong | Used FB page ID instead | Use the nested `.instagram_business_account.id`, not the top-level `id` |

## Token Expiry
- Short-lived tokens: ~1 hour
- Long-lived (extended): **60 days** — must re-generate after expiry
- No automatic refresh exists; set a calendar reminder at day 55
