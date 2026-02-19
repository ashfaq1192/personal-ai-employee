# MCP Server Tool Contracts

**Date**: 2026-02-08

## Email MCP Server (`email-mcp`)

### Tool: `send_email`

```json
{
  "name": "send_email",
  "description": "Send an email via Gmail API. Requires prior HITL approval for new contacts.",
  "inputSchema": {
    "type": "object",
    "properties": {
      "to": { "type": "string", "description": "Recipient email address" },
      "subject": { "type": "string", "description": "Email subject line" },
      "body": { "type": "string", "description": "Email body (plain text or HTML)" },
      "attachment": { "type": "string", "description": "Path to attachment file (optional)" },
      "reply_to_id": { "type": "string", "description": "Gmail message ID to reply to (optional)" }
    },
    "required": ["to", "subject", "body"]
  }
}
```

**Response**: `{ "content": [{ "type": "text", "text": "Email sent to <to>. Message ID: <id>" }], "isError": false }`

**Error**: `{ "content": [{ "type": "text", "text": "Failed: <reason>" }], "isError": true }`

### Tool: `draft_email`

```json
{
  "name": "draft_email",
  "description": "Create a draft email in Gmail (does not send).",
  "inputSchema": {
    "type": "object",
    "properties": {
      "to": { "type": "string" },
      "subject": { "type": "string" },
      "body": { "type": "string" },
      "attachment": { "type": "string" }
    },
    "required": ["to", "subject", "body"]
  }
}
```

### Tool: `search_email`

```json
{
  "name": "search_email",
  "description": "Search Gmail inbox with a query string.",
  "inputSchema": {
    "type": "object",
    "properties": {
      "query": { "type": "string", "description": "Gmail search query (e.g., 'from:client@email.com subject:invoice')" },
      "max_results": { "type": "integer", "default": 10, "maximum": 50 }
    },
    "required": ["query"]
  }
}
```

---

## Social Media MCP Server (`social-mcp`)

### Tool: `post_linkedin`

```json
{
  "name": "post_linkedin",
  "description": "Post content to LinkedIn (personal or organization page).",
  "inputSchema": {
    "type": "object",
    "properties": {
      "text": { "type": "string", "description": "Post content text" },
      "image_path": { "type": "string", "description": "Path to image file (optional)" },
      "org_id": { "type": "string", "description": "LinkedIn organization ID (optional, uses personal if omitted)" }
    },
    "required": ["text"]
  }
}
```

### Tool: `post_facebook`

```json
{
  "name": "post_facebook",
  "description": "Post content to a Facebook Page.",
  "inputSchema": {
    "type": "object",
    "properties": {
      "page_id": { "type": "string", "description": "Facebook Page ID" },
      "message": { "type": "string", "description": "Post content text" },
      "image_url": { "type": "string", "description": "URL to image (optional)" },
      "link": { "type": "string", "description": "Link to share (optional)" }
    },
    "required": ["page_id", "message"]
  }
}
```

### Tool: `post_instagram`

```json
{
  "name": "post_instagram",
  "description": "Post content to Instagram (Business/Creator account required).",
  "inputSchema": {
    "type": "object",
    "properties": {
      "ig_user_id": { "type": "string", "description": "Instagram Business user ID" },
      "image_url": { "type": "string", "description": "Publicly accessible image URL (required)" },
      "caption": { "type": "string", "description": "Post caption" }
    },
    "required": ["ig_user_id", "image_url", "caption"]
  }
}
```

### Tool: `post_twitter`

```json
{
  "name": "post_twitter",
  "description": "Post a tweet to Twitter/X (280 char limit).",
  "inputSchema": {
    "type": "object",
    "properties": {
      "text": { "type": "string", "description": "Tweet text (max 280 characters)", "maxLength": 280 },
      "media_path": { "type": "string", "description": "Path to media file (optional)" }
    },
    "required": ["text"]
  }
}
```

### Tool: `get_social_metrics`

```json
{
  "name": "get_social_metrics",
  "description": "Get engagement metrics for recent posts on a platform.",
  "inputSchema": {
    "type": "object",
    "properties": {
      "platform": { "type": "string", "enum": ["linkedin", "facebook", "instagram", "twitter"] },
      "days": { "type": "integer", "default": 7, "description": "Number of days to look back" }
    },
    "required": ["platform"]
  }
}
```

---

## Odoo MCP Server (`odoo-mcp`)

Based on `mcp-odoo-adv` + custom extensions.

### Tool: `create_invoice`

```json
{
  "name": "create_invoice",
  "description": "Create a DRAFT invoice in Odoo (never auto-posts). Requires HITL approval to post.",
  "inputSchema": {
    "type": "object",
    "properties": {
      "partner_name": { "type": "string", "description": "Client/partner name" },
      "partner_email": { "type": "string", "description": "Client email" },
      "invoice_lines": {
        "type": "array",
        "items": {
          "type": "object",
          "properties": {
            "description": { "type": "string" },
            "quantity": { "type": "number" },
            "unit_price": { "type": "number" }
          },
          "required": ["description", "quantity", "unit_price"]
        }
      },
      "currency": { "type": "string", "default": "USD" }
    },
    "required": ["partner_name", "invoice_lines"]
  }
}
```

### Tool: `search_invoices`

```json
{
  "name": "search_invoices",
  "description": "Search invoices in Odoo by partner, status, or date range.",
  "inputSchema": {
    "type": "object",
    "properties": {
      "partner_name": { "type": "string" },
      "status": { "type": "string", "enum": ["draft", "posted", "cancel"] },
      "date_from": { "type": "string", "format": "date" },
      "date_to": { "type": "string", "format": "date" }
    }
  }
}
```

### Tool: `get_financial_summary`

```json
{
  "name": "get_financial_summary",
  "description": "Get financial summary (revenue, expenses, outstanding) for a period.",
  "inputSchema": {
    "type": "object",
    "properties": {
      "period": { "type": "string", "enum": ["week", "month", "quarter", "year"] }
    },
    "required": ["period"]
  }
}
```

---

## Browser MCP Server (`browser-mcp`)

### Tool: `navigate_and_interact`

```json
{
  "name": "navigate_and_interact",
  "description": "Navigate to a URL and perform actions (click, fill, screenshot). For payment portals.",
  "inputSchema": {
    "type": "object",
    "properties": {
      "url": { "type": "string", "description": "URL to navigate to" },
      "actions": {
        "type": "array",
        "items": {
          "type": "object",
          "properties": {
            "type": { "type": "string", "enum": ["click", "fill", "screenshot", "wait"] },
            "selector": { "type": "string" },
            "value": { "type": "string" }
          },
          "required": ["type"]
        }
      },
      "headless": { "type": "boolean", "default": true }
    },
    "required": ["url"]
  }
}
```

---

## MCP Server Configuration

```json
// .mcp.json (project-level) or ~/.config/claude-code/mcp.json
{
  "mcpServers": {
    "email": {
      "command": "uv",
      "args": ["run", "python", "src/mcp_servers/email_mcp.py"],
      "env": {
        "GMAIL_CREDENTIALS": "${HOME}/.config/ai-employee/gmail_credentials.json",
        "VAULT_PATH": "${VAULT_PATH}",
        "DRY_RUN": "${DRY_RUN:-true}",
        "RATE_LIMIT_EMAILS_PER_HOUR": "10"
      }
    },
    "social": {
      "command": "uv",
      "args": ["run", "python", "src/mcp_servers/social_mcp.py"],
      "env": {
        "VAULT_PATH": "${VAULT_PATH}",
        "DRY_RUN": "${DRY_RUN:-true}",
        "LINKEDIN_ACCESS_TOKEN": "${LINKEDIN_ACCESS_TOKEN}",
        "META_ACCESS_TOKEN": "${META_ACCESS_TOKEN}",
        "TWITTER_BEARER_TOKEN": "${TWITTER_BEARER_TOKEN}"
      }
    },
    "odoo": {
      "command": "npx",
      "args": ["mcp-odoo-adv"],
      "env": {
        "ODOO_URL": "${ODOO_URL}",
        "ODOO_DB": "${ODOO_DB}",
        "ODOO_USERNAME": "${ODOO_USERNAME}",
        "ODOO_PASSWORD": "${ODOO_PASSWORD}"
      }
    },
    "browser": {
      "command": "npx",
      "args": ["@anthropic/browser-mcp"],
      "env": {
        "HEADLESS": "true"
      }
    }
  }
}
```
