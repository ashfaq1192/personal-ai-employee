---
name: mcp-server
description: Pattern and boilerplate for building Python MCP (Model Context Protocol) servers that expose tools to Claude. Use when creating a new MCP server, adding tools to an existing one, wiring up approval checks, audit logging, rate limiting, or DEV_MODE/DRY_RUN safety guards. Covers the full server skeleton, Tool schema definition, call_tool dispatch, and the defense-in-depth approval pattern from the working AI Employee codebase.
---

# MCP Server Pattern

## Minimal Server Skeleton

```python
from __future__ import annotations
import json, logging
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import TextContent, Tool
from src.core.config import Config
from src.core.logger import AuditLogger
from src.core.rate_limiter import RateLimiter

log = logging.getLogger(__name__)

server = Server("my-mcp")          # name shown to Claude
config = Config()
audit  = AuditLogger(config.vault_path)
rate_limiter = RateLimiter({"my_action": config.rate_limit_social})

@server.list_tools()
async def list_tools() -> list[Tool]:
    return [
        Tool(
            name="do_thing",
            description="One sentence describing what this tool does.",
            inputSchema={
                "type": "object",
                "properties": {
                    "param": {"type": "string", "description": "..."},
                    "is_scheduled": {"type": "boolean", "default": True},
                },
                "required": ["param"],
            },
        )
    ]

@server.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    try:
        if name == "do_thing":
            # 1. approval gate  2. rate limit  3. dry_run  4. execute  5. audit
            if not _check_approval("my_action"):
                return [TextContent(type="text", text="Failed: No approval found")]
            if not rate_limiter.check("my_action"):
                return [TextContent(type="text", text="Failed: Rate limit exceeded")]
            if config.dry_run:
                return [TextContent(type="text", text=f"[DRY_RUN] Would do_thing: {arguments['param'][:80]}")]

            result = _do_the_work(arguments["param"])
            audit.log(action_type="my_action", actor="my-mcp",
                      target=arguments["param"], result="success")
            return [TextContent(type="text", text=json.dumps(result))]
        else:
            return [TextContent(type="text", text=f"Unknown tool: {name}")]
    except Exception as exc:
        audit.log(action_type=name, actor="my-mcp",
                  target="", result="failure", error=str(exc)[:200])
        return [TextContent(type="text", text=f"Failed: {exc}")]

async def main() -> None:
    async with stdio_server() as (read, write):
        await server.run(read, write, server.create_initialization_options())

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
```

## Approval Check Pattern (FR-015a)

The approval gate reads `{vault}/Approved/APPROVAL_*.md` files. Non-scheduled actions must have a matching approval file before execution.

```python
def _check_approval(action: str, target: str = "") -> bool:
    approved_dir = config.vault_path / "Approved"
    for f in approved_dir.glob("APPROVAL_*.md"):
        text = f.read_text(encoding="utf-8")
        if action in text and (not target or target in text):
            return True
    return False
```

- Scheduled/autonomous actions: pass `is_scheduled=True` and skip the gate
- Replies/reactive actions: must have a matching APPROVAL file
- Defense-in-depth: both the orchestrator AND the MCP server check (don't remove either)

## Safety Guard Order (always this order)

```
1. approval check  →  if not approved: return error
2. rate limit      →  if over limit: return error
3. dry_run         →  if dry_run: log + return mock result
4. execute         →  real API call
5. audit.log       →  record success/failure
```

## Rate Limiter

```python
# Sliding-window, in-memory, per-action-type
rate_limiter = RateLimiter({"email": 10, "social": 5, "payment": 3})
if not rate_limiter.check("social"):
    return error_response
# check() records the event if allowed — call it once per attempt
```

## DEV_MODE vs DRY_RUN

| Mode | Reads | Writes | Use for |
|------|-------|--------|---------|
| `DEV_MODE=true` | Mock only | Blocked | Unit tests, CI |
| `DRY_RUN=true` | Real | Logged only | Safe manual testing |
| Both false | Real | Real | Production |

`DEV_MODE=true` implies `DRY_RUN=true` — set in `Config.__init__`.

## Audit Logging

```python
audit.log(
    action_type="email_send",       # snake_case verb
    actor="email-mcp",              # server name
    target="user@example.com",      # recipient/resource
    parameters={"subject": s[:100]},# truncate long values
    approval_status="approved",     # or "not_required"
    result="success",               # or "failure"
    error="...",                    # only on failure
)
# Writes to {vault}/Logs/YYYY-MM-DD.json (append-only)
```

## pyproject.toml Entry Point

```toml
[project.scripts]
my-mcp = "src.mcp_servers.my_mcp:main"
```

Run: `uv run my-mcp` or via Claude Desktop config.

## Claude Desktop Config

```json
{
  "mcpServers": {
    "my-mcp": {
      "command": "uv",
      "args": ["run", "my-mcp"],
      "cwd": "/path/to/project"
    }
  }
}
```

See `references/full-server-examples.md` for complete annotated server files from this codebase.
