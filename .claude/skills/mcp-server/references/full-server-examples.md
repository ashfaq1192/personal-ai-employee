# Full MCP Server Examples (from working codebase)

## social_mcp.py — multi-tool server with shared approval+rate check

```python
# src/mcp_servers/social_mcp.py

server = Server("social-mcp")
config = Config()
audit  = AuditLogger(config.vault_path)
rate_limiter = RateLimiter({"social": config.rate_limit_social})  # 5/hour

def _check_approval(action: str) -> bool:
    approved_dir = config.vault_path / "Approved"
    for f in approved_dir.glob("APPROVAL_*.md"):
        if action in f.read_text(encoding="utf-8"):
            return True
    return False

def _rate_and_approval_check(is_scheduled: bool) -> str | None:
    """Shared pre-flight for all social tools. Returns error string or None."""
    if not is_scheduled and not _check_approval("social_post"):
        return "Failed: Non-scheduled posts require approval"
    if not rate_limiter.check("social"):
        return "Failed: Rate limit exceeded (5 posts/hour)"
    return None

@server.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    try:
        if name == "post_linkedin":
            err = _rate_and_approval_check(arguments.get("is_scheduled", True))
            if err:
                return [TextContent(type="text", text=err)]
            client = LinkedInClient(config.linkedin_access_token, dry_run=config.dry_run)
            result = client.post(arguments["text"], ...)
            audit.log(action_type="social_post", actor="social_mcp",
                      target="linkedin", parameters={"text": arguments["text"][:100]}, result="success")
            return [TextContent(type="text", text=f"LinkedIn: {json.dumps(result)}")]
        # ... other tools follow same pattern
    except Exception as exc:
        audit.log(action_type=name, actor="social_mcp", target="", result="failure", error=str(exc)[:200])
        return [TextContent(type="text", text=f"Failed: {exc}")]
```

## email_mcp.py — tool with recipient-specific approval check

```python
# Approval check includes BOTH action type AND recipient
def _check_approval(action: str, recipient: str) -> bool:
    for f in (config.vault_path / "Approved").glob("APPROVAL_*.md"):
        text = f.read_text(encoding="utf-8")
        if recipient in text and action in text:
            return True
    # Also check Company_Handbook.md for auto-approved contacts
    handbook = config.vault_path / "Company_Handbook.md"
    if handbook.exists():
        content = handbook.read_text(encoding="utf-8")
        if recipient.lower() in content.lower() and "email_reply" in content.lower():
            return True
    return False

# In call_tool — full safety guard chain
if not _check_approval("email_send", to):
    audit.log(..., result="failure", error="No approval found")
    return [TextContent(type="text", text=f"Failed: No approval found for {to}")]
if not rate_limiter.check("email"):
    return [TextContent(type="text", text="Failed: Rate limit exceeded")]
if config.dry_run:
    audit.log(..., parameters={"dry_run": True}, result="success")
    return [TextContent(type="text", text=f"[DRY_RUN] Email would be sent to {to}")]
result = gmail.send_email(to, subject, body)
audit.log(..., approval_status="approved", result="success")
```

## whatsapp_mcp.py — single-tool server, approval only for replies

```python
# Scheduled sends bypass approval; replies require it
if not is_scheduled and not _check_approval(to):
    return error
# Approval file naming convention: APPROVAL_wa_reply_*.md
def _check_approval(to: str) -> bool:
    for f in (config.vault_path / "Approved").glob("APPROVAL_wa_reply_*.md"):
        text = f.read_text(encoding="utf-8")
        if to in text and "whatsapp_reply" in text:
            return True
    return False
```

## Core Classes

### Config (src/core/config.py)
```python
config = Config()          # loads .env automatically
config.dry_run             # True if DEV_MODE or DRY_RUN
config.dev_mode            # True if DEV_MODE
config.vault_path          # Path to Obsidian vault
config.rate_limit_social   # int, default 5
config.rate_limit_emails   # int, default 10
```

### AuditLogger (src/core/logger.py)
```python
audit = AuditLogger(config.vault_path)
audit.log(
    action_type="...",   # snake_case verb
    actor="my-mcp",
    target="...",
    parameters={...},    # keep values short — truncate to 100 chars
    approval_status="approved" | "not_required",
    result="success" | "failure",
    error="...",         # only on failure
)
# Appends JSON to {vault}/Logs/YYYY-MM-DD.json
```

### RateLimiter (src/core/rate_limiter.py)
```python
limiter = RateLimiter({"social": 5, "email": 10, "payment": 3})
# window_seconds defaults to 3600 (1 hour)
if not limiter.check("social"):  # records event if allowed
    return rate_limit_error
remaining = limiter.remaining("social")  # how many left
```

### with_retry (src/core/retry.py)
```python
from src.core.retry import with_retry

@with_retry(max_attempts=3, base_delay=1.0, max_delay=60.0)
def my_api_call(...):
    ...
# Exponential backoff: delay = min(base_delay * 2^(attempt-1), max_delay)
# Default catches all Exception — pass exceptions=(httpx.HTTPError,) to narrow
```
