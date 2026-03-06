# Meta API Code Patterns (Working Reference)

All patterns below are from the live, tested codebase.

## Facebook: Post to Page

```python
# src/mcp_servers/facebook_client.py:37-81
# Requires: page_token (from _get_page_token), page_id

# Text-only post
resp = httpx.post(
    f"https://graph.facebook.com/v20.0/{page_id}/feed",
    data={"message": message, "access_token": page_token},
)

# Photo post with public URL
resp = httpx.post(
    f"https://graph.facebook.com/v20.0/{page_id}/photos",
    data={"url": image_url, "message": message, "access_token": page_token},
)

# Photo post with binary bytes (no public URL needed)
resp = httpx.post(
    f"https://graph.facebook.com/v20.0/{page_id}/photos",
    data={"message": message, "access_token": page_token},
    files={"source": ("image.jpg", image_bytes)},
)
```

## Instagram: 2-Step Publish

```python
# src/mcp_servers/instagram_client.py:42-97
# Requires: page_token, ig_user_id, image_url (must be publicly accessible)

GRAPH_API_BASE = "https://graph.facebook.com/v20.0"

# Step 1: Create media container
resp = httpx.post(
    f"{GRAPH_API_BASE}/{ig_user_id}/media",
    data={"image_url": image_url, "caption": caption, "access_token": page_token},
)
container_id = resp.json()["id"]

# Poll until FINISHED (do not use fixed sleep — unreliable)
while waited < 60:
    status_resp = httpx.get(
        f"{GRAPH_API_BASE}/{container_id}",
        params={"fields": "status_code", "access_token": page_token},
    )
    status_code = status_resp.json().get("status_code", "")
    if status_code == "FINISHED":
        break
    if status_code == "ERROR":
        raise RuntimeError("Instagram media container processing failed")
    time.sleep(3)
    waited += 3

# Step 2: Publish
resp = httpx.post(
    f"{GRAPH_API_BASE}/{ig_user_id}/media_publish",
    data={"creation_id": container_id, "access_token": page_token},
)
```

## Metrics: Facebook Page

```python
# src/mcp_servers/social_metrics.py:32-82
# Returns: followers, posts, engagements (if read_insights granted)

# Followers
resp = httpx.get(f"{GRAPH_BASE}/{page_id}",
    params={"fields": "fan_count,followers_count", "access_token": page_token})

# Recent posts
resp = httpx.get(f"{GRAPH_BASE}/{page_id}/posts",
    params={"limit": 100, "since": unix_ts, "access_token": page_token})

# Engagements (requires read_insights scope — gracefully skipped if unavailable)
resp = httpx.get(f"{GRAPH_BASE}/{page_id}/insights",
    params={"metric": "page_post_engagements", "period": "day",
            "since": unix_ts, "until": now_ts, "access_token": page_token})
```

## Metrics: Instagram Business Account

```python
# src/mcp_servers/social_metrics.py:85-139
# Returns: followers, total_media, posts, impressions, reach

resp = httpx.get(f"{GRAPH_BASE}/{ig_user_id}",
    params={"fields": "followers_count,media_count", "access_token": token})

# Recent media
resp = httpx.get(f"{GRAPH_BASE}/{ig_user_id}/media",
    params={"fields": "id,timestamp", "since": unix_ts, "access_token": token})

# Insights (requires instagram_manage_insights — gracefully skipped if unavailable)
resp = httpx.get(f"{GRAPH_BASE}/{ig_user_id}/insights",
    params={"metric": "impressions,reach", "period": "day",
            "since": unix_ts, "until": now_ts, "access_token": token})
```

## Key Notes
- Graph API version in this codebase: **v20.0**
- All clients use `httpx.Client` (sync), with `resp.raise_for_status()` before reading JSON
- Retry decorator: `@with_retry(max_attempts=2, base_delay=3.0)` from `src.core.retry`
- `dry_run=True` is the default — set `dry_run=False` for real posts
