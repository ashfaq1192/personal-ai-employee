# Research: Personal AI Employee (Digital FTE)

**Date**: 2026-02-08 | **Spec**: `specs/personal-ai-employee/spec.md`

## Research Topics

### 1. MCP Server Implementation

**Decision**: Build custom MCP servers using the official MCP Python SDK (`mcp`) and Node.js SDK (`@modelcontextprotocol/sdk`).

**Rationale**: The MCP protocol uses JSON-RPC 2.0 over stdio. Each server declares capabilities and exposes tools via `tools/list` and `tools/call` methods. Custom servers give full control over rate limiting, dry-run mode, and audit logging — all constitution requirements. The hackathon doc references `mcp-odoo-adv` for Odoo; we will evaluate and extend it.

**Alternatives Considered**:
- Use only community MCP servers → Rejected: Most don't support our HITL/audit requirements.
- No MCP (direct API calls from Claude) → Rejected: Violates constitution principle II (action layer must use MCP).

**Key Findings**:
- MCP tools are defined with `name`, `description`, `inputSchema` (JSON Schema)
- Tools return `content[]` with `type: text|image|resource` and `isError` flag
- Servers declare capabilities: `{"capabilities": {"tools": {"listChanged": true}}}`
- Configuration in Claude Code: `~/.config/claude-code/mcp.json` or project `.mcp.json`
- Security: Servers MUST validate inputs, implement rate limiting, sanitize outputs

### 2. Ralph Wiggum Stop Hook Pattern

**Decision**: Use the official `ralph-loop` Claude Code plugin (already installed at `~/.claude/plugins/marketplaces/claude-plugins-official/plugins/ralph-loop/`).

**Rationale**: The plugin is a mature implementation with:
- Stop hook (`hooks/stop-hook.sh`) that intercepts session exit
- State file (`.claude/ralph-loop.local.md`) tracking iteration count, max iterations, completion promise
- Promise-based completion via `<promise>TASK_COMPLETE</promise>` tag detection
- Max-iterations safety limit
- Slash commands: `/ralph-loop`, `/cancel-ralph`

**Implementation Details** (from reading the actual plugin):
```
hooks/hooks.json → Registers Stop hook
hooks/stop-hook.sh → Core logic:
  1. Reads state file (.claude/ralph-loop.local.md)
  2. Checks max_iterations limit
  3. Reads transcript, extracts last assistant output
  4. Checks for <promise> tag matching completion_promise
  5. If not complete: increments iteration, outputs JSON {decision: "block", reason: prompt}
  6. If complete/max reached: removes state file, exits 0 (allows exit)
```

**For our use case**: The orchestrator will invoke Ralph loops for complex multi-step tasks (e.g., processing multiple Needs_Action items). The file-movement completion strategy aligns with our vault workflow — task moves to `/Done/` = task complete.

### 3. GCP Compute Engine VM Sizing

**Decision**: Single `e2-standard-2` VM (2 vCPU, 8GB RAM) for all services including Odoo, with 50GB SSD boot disk.

**Rationale**: Running all services on one VM maximizes budget efficiency. The workload (Python watchers + orchestrator + Node.js MCP servers + Odoo) fits within 8GB RAM. Odoo Community requires ~2GB RAM; watchers and MCP servers use <1GB combined.

**Cost Breakdown** (us-central1, on-demand):
| VM Type | vCPU | RAM | $/hour | $/month | $300 lasts |
|---------|------|-----|--------|---------|------------|
| e2-micro | 0.25 | 1GB | $0.008 | ~$6 | ~50 months (too small) |
| e2-small | 0.5 | 2GB | $0.017 | ~$12 | ~25 months (too small for Odoo) |
| e2-medium | 1 | 4GB | $0.034 | ~$24 | ~12 months (tight for Odoo) |
| **e2-standard-2** | **2** | **8GB** | **$0.067** | **~$49** | **~6 months** |
| e2-standard-4 | 4 | 16GB | $0.134 | ~$98 | ~3 months |

**Recommendation**: `e2-standard-2` at ~$49/month gives ~6 months of runtime on $300 credit. Adequate for Python watchers + Odoo + MCP servers.

**Additional Costs**: 50GB SSD persistent disk (~$8.50/mo), static IP (~$2.88/mo if reserved), network egress (~$1-2/mo). Total ~$61/month → ~4.9 months.

**OS**: Ubuntu 24.04 LTS (standard GCP image).

**Firewall Rules**: Allow TCP 443 (HTTPS/Odoo), TCP 22 (SSH), deny all others.

### 4. Social Media API Requirements

**Decision**: Implement all four platforms (LinkedIn, Facebook, Instagram, Twitter/X) using direct REST API calls with `httpx` (async). Use `tweepy` for Twitter/X specifically.

| Platform | API | Auth | Post Limit | Account Required | Cost |
|----------|-----|------|-----------|-----------------|------|
| LinkedIn | Marketing API (Posts API) | OAuth 2.0 (3-legged) | ~100/day member, ~150/day org | Org posting needs Company Page | Free |
| Facebook | Graph API v20+ | OAuth 2.0 (System User for long-lived tokens) | ~25/day practical (Page) | Yes (Page + Business Manager) | Free |
| Instagram | Graph API (Content Publishing) | OAuth 2.0 (via Facebook) | **25/day hard limit** | Yes (Business/Creator + Facebook Page) | Free |
| Twitter/X | X API v2 | OAuth 2.0 PKCE or 1.0a | 1,500/mo free, 3,000/mo basic | No (but developer account needed) | Free (limited) or $200+/mo |

**Key Gotchas**:
- Instagram is most restrictive: Business account + Facebook Page + 25 posts/day + images must be publicly accessible URLs
- Twitter/X Free tier only allows 1,500 tweets/month; Basic is $200/month
- Facebook/Instagram share infrastructure — one Meta Developer App covers both
- LinkedIn org posting requires app review (2-4 weeks approval)
- All platforms require developer account setup before implementation

**Approval Timeline**: Start developer account applications immediately — LinkedIn and Facebook/Instagram reviews can take weeks.

### 5. Gmail API Integration

**Decision**: Use `google-api-python-client` with OAuth2 service account for the watcher, personal OAuth2 for send operations via MCP.

**Rationale**: The Gmail API Python quickstart is well-documented. OAuth2 with token refresh handles long-running watcher processes. Service accounts work for monitoring; user-context tokens are needed for sending (to maintain "from" identity).

**Key Libraries**: `google-auth`, `google-auth-oauthlib`, `google-api-python-client`

### 6. WhatsApp Web Automation

**Decision**: Use Playwright with persistent browser context for WhatsApp Web monitoring.

**Rationale**: No official WhatsApp Business API for personal accounts. Playwright's persistent context maintains the login session across restarts. Headless mode reduces resource usage.

**Risks**:
- WhatsApp may detect and block automation
- Session can expire requiring QR code re-scan
- WhatsApp ToS technically prohibits automation

**Mitigation**: DEV_MODE prevents actual interactions; keyword filtering reduces unnecessary processing; session monitoring alerts on expiry.

### 7. Odoo Integration

**Decision**: Use the community `mcp-odoo-adv` MCP server, customized for our HITL requirements.

**Rationale**: The hackathon doc explicitly recommends this package. Odoo 19+ exposes JSON-RPC APIs for external integration. Draft-only mode aligns with our HITL constitution principle.

**API**: Odoo External API via JSON-RPC at `/jsonrpc` endpoint. Operations: `search_read`, `create`, `write`, `unlink` on models like `account.move` (invoices).

### 8. Process Management

**Decision**: Use PM2 for all daemon processes (watchers, orchestrator, MCP servers).

**Rationale**: PM2 handles auto-restart, boot persistence (`pm2 startup`), log management, and process monitoring. Originally for Node.js but works perfectly with Python (`--interpreter python3`). Single tool for both Python and Node.js processes.

**Alternative Considered**: supervisord → Rejected: PM2 is simpler to set up, has better ecosystem, and the hackathon doc explicitly recommends it.
