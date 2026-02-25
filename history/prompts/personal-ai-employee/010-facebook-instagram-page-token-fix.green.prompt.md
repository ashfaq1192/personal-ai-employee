---
id: 010
title: Facebook Instagram Page Token Fix and Live Post Verification
stage: green
date: 2026-02-26
surface: agent
model: claude-sonnet-4-6
feature: personal-ai-employee
branch: main
user: Muhammad Ashfaq
command: "Resume from CLAUDE_SESSION.md — test posting to Facebook and Instagram via fixed client code"
labels: ["facebook", "instagram", "meta-api", "page-token", "bug-fix", "live-test"]
links:
  spec: specs/personal-ai-employee/spec.md
  ticket: null
  adr: null
  pr: null
files:
  - src/mcp_servers/facebook_client.py
  - src/mcp_servers/instagram_client.py
  - src/mcp_servers/social_mcp.py
  - scripts/test_gold_tier.py
tests:
  - "scripts/test_gold_tier.py — 22/22 passed"
  - "Live Facebook post via FacebookClient — post_id 804653036075835_122118470451146459"
  - "Live Instagram post via InstagramClient — media_id 18025171913620286"
---

## Prompt

Please read @CLAUDE_SESSION.md and resume where we left off.

(Session context: had just discovered that META_ACCESS_TOKEN is a User token but /feed and Instagram publishing endpoints require a Page Access Token. FacebookClient was partially fixed. InstagramClient still used the raw User token.)

## Response snapshot

Resumed from CLAUDE_SESSION.md. FacebookClient fix was already fully applied (added `_get_page_token()` + `_page_tokens` cache, updated `post_to_page()` to use page token). Applied the same pattern to InstagramClient:

- Added `page_id: str` parameter to `InstagramClient.__init__()`
- Added `_get_page_token()` method (cached via `self._page_token`)
- Updated all three API calls in `post()` (container create, container status poll, media_publish) to use the page token instead of the user token
- Updated `social_mcp.py` to pass `config.facebook_page_id` when constructing `InstagramClient`
- Fixed `scripts/test_gold_tier.py` dry-run test to pass required `page_id` arg

Live API validation confirmed both clients work end-to-end with real credentials.

## Outcome

- ✅ Impact: Both Facebook and Instagram clients now correctly exchange User token → Page Access Token before any write API call. Root cause of 403 errors eliminated.
- 🧪 Tests: 22/22 gold-tier tests passing; two live API posts confirmed (Facebook post ID 804653036075835_122118470451146459, Instagram media ID 18025171913620286)
- 📁 Files: src/mcp_servers/instagram_client.py, src/mcp_servers/social_mcp.py, scripts/test_gold_tier.py (test fixture fix)
- 🔁 Next prompts: None outstanding — all social posting is now green
- 🧠 Reflection: The page-token exchange is a common Meta API pitfall. Both clients now share the same pattern; consider extracting a shared `MetaPageTokenMixin` if a third Meta client is added.

## Evaluation notes (flywheel)

- Failure modes observed: Instagram container creation timed out on first attempt (Unsplash URL slow); retry succeeded — normal behaviour under `with_retry`
- Graders run and results (PASS/FAIL): test_gold_tier.py — 22/22 PASS
- Prompt variant (if applicable): null
- Next experiment: Extend `_CONTAINER_MAX_WAIT` from 60s to 90s to reduce first-attempt timeouts on slow CDN images
