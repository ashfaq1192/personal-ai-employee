# Facebook & Instagram API Setup Guide

Time required: ~30 minutes

## What you'll get
- `META_ACCESS_TOKEN` — posts to Facebook Page + Instagram
- `FACEBOOK_PAGE_ID` — your Facebook Page numeric ID
- `INSTAGRAM_USER_ID` — your Instagram Business account ID

---

## Step 1: Create a Meta Developer App

1. Go to **https://developers.facebook.com**
2. Click **My Apps** → **Create App**
3. Choose: **Other** → **Business** type
4. Give it a name (e.g. "AI Employee")
5. Click **Create App**

---

## Step 2: Add Facebook Login + Instagram Graph API products

In your app dashboard:
1. Click **Add Product** → find **Facebook Login** → click **Set Up**
2. Click **Add Product** → find **Instagram Graph API** → click **Set Up**

---

## Step 3: Generate a Page Access Token

1. In the left sidebar, go to **Tools** → **Graph API Explorer**
2. Under **Meta App**, select your app
3. Under **User or Page**, select your Facebook **Page** (not personal profile)
4. Click **Generate Access Token** → grant all requested permissions:
   - `pages_manage_posts`
   - `pages_read_engagement`
   - `instagram_basic`
   - `instagram_content_publish`
   - `instagram_manage_insights`
5. Copy the **Page Access Token** — this is your `META_ACCESS_TOKEN`

> ⚠️ Short-lived tokens expire in 1 hour. Generate a long-lived token:

```bash
# Exchange short-lived for long-lived (60 days)
curl "https://graph.facebook.com/oauth/access_token
  ?grant_type=fb_exchange_token
  &client_id=YOUR_APP_ID
  &client_secret=YOUR_APP_SECRET
  &fb_exchange_token=SHORT_LIVED_TOKEN"
```

Copy the `access_token` from the response.

---

## Step 4: Get your Facebook Page ID

1. Go to your **Facebook Page**
2. Click **About** → scroll to the bottom
3. Find **Page ID** (a long number like `123456789012345`)

Or via API:
```bash
curl "https://graph.facebook.com/me/accounts?access_token=YOUR_TOKEN"
```
Find your page in the list and copy the `id` field.

---

## Step 5: Get your Instagram Business User ID

Your Instagram account **must be** a Business or Creator account connected to a Facebook Page.

```bash
curl "https://graph.facebook.com/YOUR_PAGE_ID?fields=instagram_business_account&access_token=YOUR_TOKEN"
```

Copy the `id` from `instagram_business_account.id` — this is your `INSTAGRAM_USER_ID`.

---

## Step 6: Add to `.env`

```bash
# Edit your .env file
META_ACCESS_TOKEN=EAAxxxxxxxx...
FACEBOOK_PAGE_ID=123456789012345
INSTAGRAM_USER_ID=987654321098765
```

---

## Step 7: Test with dry-run

```bash
uv run python scripts/test_gold_tier.py
```

Then test with real APIs (no actual post will be published because DRY_RUN=true):
```bash
# Test Facebook
uv run python -c "
from src.mcp_servers.social_metrics import collect_platform_metrics
import os
result = collect_platform_metrics('facebook', 7,
    meta_access_token=os.environ.get('META_ACCESS_TOKEN'),
    facebook_page_id=os.environ.get('FACEBOOK_PAGE_ID'))
print(result)
"
```

To make a real test post (sets DRY_RUN=false for just this call):
```bash
uv run python -c "
from src.mcp_servers.facebook_client import FacebookClient
import os
# WARNING: This will post for real!
client = FacebookClient(os.environ.get('META_ACCESS_TOKEN'), dry_run=False)
result = client.post_to_page(os.environ.get('FACEBOOK_PAGE_ID'), 'Test post from AI Employee 🤖')
print(result)
"
```

---

## Troubleshooting

| Error | Fix |
|-------|-----|
| `(#200) Permissions error` | Re-generate token with correct permissions |
| `(#100) Invalid parameter` | Check Page ID is numeric (not page name) |
| `Token expired` | Generate a new long-lived token (Step 3) |
| `Instagram account not connected` | Go to Facebook Page Settings → Instagram → Connect |
| `Media container ERROR` | Image URL must be publicly accessible, not localhost |

---

## Instagram Requirements

- Account must be **Business** or **Creator** type
- Must be connected to a **Facebook Page**
- Images must be at a **public URL** (use a CDN or upload to a hosting service first)
- Max **25 posts per day** (enforced by our rate limiter)
