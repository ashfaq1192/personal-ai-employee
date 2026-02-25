"""AI Employee — Live Operations Dashboard.

Start:  uv run python src/cli/web_dashboard.py
URL:    http://localhost:8080
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import urllib.parse
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

load_dotenv()

from src.core.config import Config
from src.core.logger import AuditLogger

config = Config()
vault = config.vault_path
audit = AuditLogger(vault)


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _parse_fm(text: str) -> dict:
    m = re.match(r"^---\s*\n(.*?)\n---", text, re.DOTALL)
    if not m:
        return {}
    d: dict = {}
    for line in m.group(1).splitlines():
        if ":" in line:
            k, _, v = line.partition(":")
            d[k.strip()] = v.strip().strip('"').strip("'")
    return d


def _count(folder: str) -> int:
    p = vault / folder
    if not p.exists():
        return 0
    return sum(1 for f in p.iterdir() if f.is_file() and f.suffix == ".md")


def _json(h: BaseHTTPRequestHandler, data: Any, status: int = 200) -> None:
    body = json.dumps(data, default=str, ensure_ascii=False).encode()
    h.send_response(status)
    h.send_header("Content-Type", "application/json")
    h.send_header("Content-Length", str(len(body)))
    h.send_header("Access-Control-Allow-Origin", "*")
    h.end_headers()
    h.wfile.write(body)


def _body(h: BaseHTTPRequestHandler) -> dict:
    n = int(h.headers.get("Content-Length", 0))
    return json.loads(h.rfile.read(n)) if n else {}


# ─── API ──────────────────────────────────────────────────────────────────────

def api_status() -> dict:
    mode = "DEV_MODE" if config.dev_mode else ("DRY_RUN" if config.dry_run else "LIVE")
    procs: dict = {}
    try:
        r = subprocess.run(["pm2", "jlist"], capture_output=True, text=True, timeout=5)
        if r.returncode == 0:
            for p in json.loads(r.stdout):
                procs[p["name"]] = p.get("pm2_env", {}).get("status", "unknown")
    except Exception:
        pass
    return {
        "mode": mode,
        "vault": str(vault),
        "vault_exists": vault.exists(),
        "counts": {
            "email": _count("Needs_Action"),
            "whatsapp": sum(
                1 for f in (vault / "Needs_Action").iterdir()
                if f.is_file() and f.name.startswith("WHATSAPP_")
            ) if (vault / "Needs_Action").exists() else 0,
            "pending": _count("Pending_Approval"),
            "plans": _count("Plans"),
            "done": _count("Done"),
        },
        "processes": procs,
        "ts": datetime.now(timezone.utc).isoformat(),
    }


def api_emails() -> list:
    folder = vault / "Needs_Action"
    if not folder.exists():
        return []
    out = []
    for f in sorted(folder.iterdir(), key=lambda x: -x.stat().st_mtime):
        if not (f.is_file() and f.name.startswith("EMAIL_") and f.suffix == ".md"):
            continue
        text = f.read_text(encoding="utf-8", errors="replace")
        fm = _parse_fm(text)
        lines = [l for l in text.splitlines() if l.strip() and not l.startswith("-") and not l.startswith("#") and "---" not in l]
        snippet = next((l for l in lines if len(l.strip()) > 20), "")[:140]
        out.append({
            "filename": f.name,
            "from": fm.get("from", "Unknown"),
            "subject": fm.get("subject", "(no subject)"),
            "received": fm.get("received", ""),
            "priority": fm.get("priority", "normal"),
            "status": fm.get("status", "pending"),
            "plan_ref": fm.get("plan_ref", ""),
            "snippet": snippet,
            "mtime": f.stat().st_mtime,
        })
    return out


def api_whatsapp() -> list:
    folder = vault / "Needs_Action"
    if not folder.exists():
        return []
    out = []
    for f in sorted(folder.iterdir(), key=lambda x: -x.stat().st_mtime):
        if not (f.is_file() and f.name.startswith("WHATSAPP_") and f.suffix == ".md"):
            continue
        text = f.read_text(encoding="utf-8", errors="replace")
        fm = _parse_fm(text)
        lines = [l for l in text.splitlines() if l.strip() and not l.startswith("-") and not l.startswith("#") and "---" not in l]
        snippet = next((l for l in lines if len(l.strip()) > 5), "")[:200]
        out.append({
            "filename": f.name,
            "from": fm.get("from", "Unknown"),
            "chat": fm.get("chat", ""),
            "received": fm.get("received", ""),
            "priority": fm.get("priority", "normal"),
            "keywords": fm.get("keywords_matched", ""),
            "snippet": snippet,
        })
    return out


def api_plans() -> list:
    folder = vault / "Plans"
    if not folder.exists():
        return []
    out = []
    for f in sorted(folder.iterdir(), key=lambda x: -x.stat().st_mtime):
        if not (f.is_file() and f.suffix == ".md"):
            continue
        text = f.read_text(encoding="utf-8", errors="replace")
        fm = _parse_fm(text)
        total = text.count("- [")
        done = text.count("- [x]")
        is_social = f.name.startswith("SOCIAL_")
        out.append({
            "filename": f.name,
            "type": "social" if is_social else "plan",
            "status": fm.get("status", "pending"),
            "platform": fm.get("platform", ""),
            "post_id": fm.get("post_id", ""),
            "created": fm.get("created", ""),
            "steps_total": total,
            "steps_done": done,
            "mtime": f.stat().st_mtime,
        })
    return out


def api_pending() -> list:
    folder = vault / "Pending_Approval"
    if not folder.exists():
        return []
    out = []
    for f in sorted(folder.iterdir(), key=lambda x: x.stat().st_mtime):
        if not (f.is_file() and f.suffix == ".md"):
            continue
        text = f.read_text(encoding="utf-8", errors="replace")
        fm = _parse_fm(text)
        body_match = re.search(r"## Reply Body\s*\n\n([\s\S]+)", text)
        reply_preview = body_match.group(1).strip()[:120] if body_match else ""
        out.append({
            "filename": f.name,
            "action": fm.get("action", "unknown"),
            "to": fm.get("to", fm.get("recipient", "")),
            "subject": fm.get("subject", ""),
            "amount": fm.get("amount", ""),
            "requested_at": fm.get("requested_at", fm.get("created", "")),
            "reply_preview": reply_preview,
        })
    return out


def api_email_content(filename: str) -> dict:
    """Return full markdown content of an email file."""
    if not filename or "/" in filename or "\\" in filename:
        return {"error": "Invalid filename", "content": ""}
    target = vault / "Needs_Action" / filename
    if not target.exists():
        return {"error": "File not found", "content": ""}
    try:
        content = target.read_text(encoding="utf-8", errors="replace")
        return {"filename": filename, "content": content}
    except Exception as e:
        return {"error": str(e), "content": ""}


def api_whatsapp_scan(_body: dict = {}) -> dict:
    """Trigger one WhatsApp scan cycle."""
    try:
        from src.watchers.whatsapp_watcher import WhatsAppWatcher
        watcher = WhatsAppWatcher(config)
        items = watcher.check_for_updates()
        created = []
        for item in items:
            p = watcher.create_action_file(item)
            created.append(p.name)
        if watcher._browser:
            try:
                watcher._browser.close()
            except Exception:
                pass
        audit.log("whatsapp_scan", "web_dashboard", "Needs_Action", parameters={"new": len(items)})
        return {"status": "ok", "new_messages": len(created), "files": created}
    except Exception as e:
        return {"status": "error", "message": str(e)}


def api_whatsapp_content(filename: str) -> dict:
    """Return full content of a WHATSAPP_*.md file."""
    if not filename or "/" in filename or "\\" in filename:
        return {"error": "Invalid filename", "content": ""}
    target = vault / "Needs_Action" / filename
    if not target.exists():
        return {"error": "File not found", "content": ""}
    try:
        return {"filename": filename, "content": target.read_text(encoding="utf-8", errors="replace")}
    except Exception as e:
        return {"error": str(e), "content": ""}


def api_email_reply(body: dict) -> dict:
    """Create an APPROVAL_*.md for replying to an email — HITL gate."""
    filename = body.get("filename", "")
    subject  = body.get("subject", "")
    sender   = body.get("from", "")
    reply_body = body.get("reply_body", "").strip()
    if not filename:
        return {"status": "error", "message": "No filename"}
    if not reply_body:
        return {"status": "error", "message": "Reply text is required"}
    now = datetime.now(timezone.utc)
    slug = filename.replace("EMAIL_", "").replace(".md", "")
    approval_fn = f"APPROVAL_email_reply_{slug}.md"
    content = (
        f"---\n"
        f"type: approval_request\n"
        f"action: email_send\n"
        f"requested_by: web_dashboard\n"
        f"requested_at: {now.isoformat()}\n"
        f"to: {sender}\n"
        f"subject: Re: {subject}\n"
        f"source_email: {filename}\n"
        f"expires: {now.replace(hour=(now.hour+24)%24).isoformat()}\n"
        f"---\n\n"
        f"## Reply Body\n\n"
        f"{reply_body}\n"
    )
    dest = vault / "Pending_Approval" / approval_fn
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(content, encoding="utf-8")
    audit.log("create_reply_approval", "web_dashboard", approval_fn,
              parameters={"source": filename, "to": sender}, approval_status="pending")
    return {"status": "ok", "approval_file": approval_fn}


def api_whatsapp_reply(body: dict) -> dict:
    """Create an APPROVAL_*.md for a WhatsApp reply — HITL gate."""
    filename = body.get("filename", "")
    sender   = body.get("from", "")
    reply_body = body.get("reply_body", "").strip()
    if not filename:
        return {"status": "error", "message": "No filename"}
    if not reply_body:
        return {"status": "error", "message": "Reply text is required"}
    now = datetime.now(timezone.utc)
    slug = filename.replace("WHATSAPP_", "").replace(".md", "")
    approval_fn = f"APPROVAL_wa_reply_{slug}.md"
    content = (
        f"---\n"
        f"type: approval_request\n"
        f"action: whatsapp_reply\n"
        f"requested_by: web_dashboard\n"
        f"requested_at: {now.isoformat()}\n"
        f"to: {sender}\n"
        f"subject: WhatsApp reply to {sender}\n"
        f"source_whatsapp: {filename}\n"
        f"expires: {now.replace(hour=(now.hour+24)%24).isoformat()}\n"
        f"---\n\n"
        f"## Reply Body\n\n"
        f"{reply_body}\n"
    )
    dest = vault / "Pending_Approval" / approval_fn
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(content, encoding="utf-8")
    audit.log("create_wa_reply_approval", "web_dashboard", approval_fn,
              parameters={"source": filename, "to": sender}, approval_status="pending")
    return {"status": "ok", "approval_file": approval_fn}


def api_email_done(body: dict) -> dict:
    """Move an email from /Needs_Action/ to /Done/."""
    filename = body.get("filename", "")
    if not filename or "/" in filename:
        return {"status": "error", "message": "Invalid filename"}
    src = vault / "Needs_Action" / filename
    if not src.exists():
        return {"status": "error", "message": "File not found"}
    dst = vault / "Done" / filename
    dst.parent.mkdir(parents=True, exist_ok=True)
    src.rename(dst)
    audit.log("mark_done", "web_dashboard", filename, result="success")
    return {"status": "ok", "moved_to": str(dst)}


def api_gmail_pull(_body: dict = {}) -> dict:
    try:
        from google.oauth2.credentials import Credentials
        from google.auth.transport.requests import Request
        from googleapiclient.discovery import build

        creds_path = config.gmail_credentials_path
        creds = Credentials.from_authorized_user_file(str(creds_path))
        if creds.expired and creds.refresh_token:
            creds.refresh(Request())
            creds_path.write_text(creds.to_json(), encoding="utf-8")

        from src.watchers.gmail_watcher import GmailWatcher
        watcher = GmailWatcher(config)
        watcher._service = build("gmail", "v1", credentials=creds)
        items = watcher.check_for_updates()
        created = []
        for item in items:
            p = watcher.create_action_file(item)
            created.append(p.name)
        audit.log("gmail_pull", "web_dashboard", "Needs_Action", parameters={"new": len(created)})
        return {"status": "ok", "new_emails": len(created), "files": created}
    except Exception as e:
        return {"status": "error", "message": str(e)}


def api_linkedin_post(body: dict) -> dict:
    text = body.get("text", "").strip()
    if not text:
        return {"status": "error", "message": "Post text is empty"}
    try:
        token = os.environ.get("LINKEDIN_ACCESS_TOKEN", "")
        if not token:
            return {"status": "error", "message": "LINKEDIN_ACCESS_TOKEN missing in .env"}
        from src.mcp_servers.linkedin_client import LinkedInClient
        client = LinkedInClient(token, dry_run=config.dry_run)
        result = client.post(text)
        now = datetime.now(timezone.utc)
        fname = f"SOCIAL_{now.strftime('%Y-%m-%d_%H%M%S')}_linkedin.md"
        content = (
            f"---\ntype: social_post\nplatform: linkedin\n"
            f"status: {'dry_run' if config.dry_run else 'posted'}\n"
            f"post_id: {result.get('id', '')}\n"
            f"created: {now.isoformat()}\n---\n\n{text}\n"
        )
        (vault / "Plans" / fname).write_text(content, encoding="utf-8")
        audit.log("linkedin_post", "web_dashboard", "linkedin",
                  parameters={"dry_run": config.dry_run, "post_id": result.get("id", "")})
        return {"status": "ok", "dry_run": config.dry_run, "post_id": result.get("id", ""), "preview": text[:100]}
    except Exception as e:
        return {"status": "error", "message": str(e)}


def api_approve(body: dict) -> dict:
    fn = body.get("filename", "")
    src = vault / "Pending_Approval" / fn
    if not src.exists():
        return {"status": "error", "message": "File not found"}
    # Read before moving so we can execute the action
    text = src.read_text(encoding="utf-8", errors="replace")
    fm = _parse_fm(text)
    action = fm.get("action", "unknown")
    dst = vault / "Approved" / fn
    dst.parent.mkdir(parents=True, exist_ok=True)
    src.rename(dst)
    audit.log("approve_request", "web_dashboard", fn, approval_status="approved", approved_by="human")
    result: dict = {"status": "approved", "action": action}
    # Execute the approved action
    if action == "email_send":
        try:
            from src.mcp_servers.gmail_service import GmailService
            svc = GmailService(config.gmail_credentials_path)
            to = fm.get("to", "")
            subject = fm.get("subject", "")
            body_match = re.search(r"## Reply Body\s*\n\n([\s\S]+)", text)
            reply_text = body_match.group(1).strip() if body_match else "(no reply body)"
            send_result = svc.send_email(to=to, subject=subject, body=reply_text)
            result["sent"] = True
            result["to"] = to
            result["message_id"] = send_result.get("message_id", "")
            audit.log("email_send", "web_dashboard", to,
                      parameters={"subject": subject, "msg_id": send_result.get("message_id", "")},
                      result="success")
        except Exception as e:
            result["sent"] = False
            result["send_error"] = str(e)[:200]
            audit.log("email_send", "web_dashboard", fn, result="failure", error=str(e)[:200])
    elif action == "whatsapp_reply":
        to = fm.get("to", "")
        body_match = re.search(r"## Reply Body\s*\n\n([\s\S]+)", text)
        reply_text = body_match.group(1).strip() if body_match else ""
        result["to"] = to
        import time as _time
        try:
            # Stop the WhatsApp watcher so it releases the Chromium session lock
            subprocess.run(["pm2", "stop", "ai-employee-whatsapp-watcher"],
                           capture_output=True, timeout=10)
            _time.sleep(4)  # wait for process + browser to fully close

            project_root = Path(__file__).resolve().parent.parent.parent
            send_script = project_root / "scripts" / "whatsapp_send.py"
            env = {
                **os.environ,
                "DISPLAY": ":0",
                "WHATSAPP_SESSION_PATH": str(config.whatsapp_session_path),
            }
            proc = subprocess.run(
                ["uv", "run", "python", str(send_script), to, reply_text],
                cwd=str(project_root),
                env=env,
                capture_output=True, text=True, timeout=90,
            )
            output = proc.stdout.strip()
            if "SENT_OK" in output:
                result["sent"] = True
                audit.log("whatsapp_send", "web_dashboard", to,
                          parameters={"contact": to, "preview": reply_text[:80]},
                          result="success")
            else:
                err = (output or proc.stderr or "unknown error")[-200:]
                result["sent"] = False
                result["send_error"] = err
                audit.log("whatsapp_send", "web_dashboard", to,
                          parameters={"error": err[:100]}, result="failure")
        except Exception as e:
            result["sent"] = False
            result["send_error"] = str(e)[:200]
        finally:
            # Always restart the WhatsApp watcher
            subprocess.run(["pm2", "start", "ai-employee-whatsapp-watcher"],
                           capture_output=True, timeout=10)
    return result


def api_reject(body: dict) -> dict:
    fn = body.get("filename", "")
    src = vault / "Pending_Approval" / fn
    if not src.exists():
        return {"status": "error", "message": "File not found"}
    dst = vault / "Rejected" / fn
    dst.parent.mkdir(parents=True, exist_ok=True)
    src.rename(dst)
    audit.log("reject_request", "web_dashboard", fn, approval_status="rejected", approved_by="human")
    return {"status": "rejected"}


# ─── HTTP Handler ─────────────────────────────────────────────────────────────

POST = {
    "/api/gmail/pull":       api_gmail_pull,
    "/api/email/reply":      api_email_reply,
    "/api/email/done":       api_email_done,
    "/api/whatsapp/scan":    api_whatsapp_scan,
    "/api/whatsapp/reply":   api_whatsapp_reply,
    "/api/linkedin/post":    api_linkedin_post,
    "/api/approve":          api_approve,
    "/api/reject":           api_reject,
    "/api/action/approve":   api_approve,
}


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *a: Any) -> None:
        pass

    def do_GET(self) -> None:
        path = urllib.parse.urlparse(self.path).path.rstrip("/") or "/"
        qs = dict(urllib.parse.parse_qsl(urllib.parse.urlparse(self.path).query))
        routes = {
            "/api/status":        lambda: api_status(),
            "/api/emails":        lambda: api_emails(),
            "/api/email-content":     lambda: api_email_content(qs.get("file", "")),
            "/api/whatsapp":          lambda: api_whatsapp(),
            "/api/whatsapp-content":  lambda: api_whatsapp_content(qs.get("file", "")),
            "/api/plans":         lambda: api_plans(),
            "/api/pending":       lambda: api_pending(),
            "/api/logs":          lambda: audit.get_recent(40),
        }
        if path == "/":
            b = DASHBOARD_HTML.encode()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(b)))
            self.end_headers()
            self.wfile.write(b)
        elif path in routes:
            try:
                _json(self, routes[path]())
            except Exception as e:
                _json(self, {"error": str(e)}, 500)
        else:
            self.send_error(404)

    def do_POST(self) -> None:
        path = urllib.parse.urlparse(self.path).path.rstrip("/")
        b = _body(self)
        fn = POST.get(path)
        if fn:
            try:
                _json(self, fn(b))
            except Exception as e:
                _json(self, {"error": str(e)}, 500)
        else:
            self.send_error(404)


# ─── Dashboard HTML ───────────────────────────────────────────────────────────

DASHBOARD_HTML = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>AI Employee — Operations Center</title>
<style>
:root{
  --bg:#060d1f;--bg2:#0d1b2e;--bg3:#111f35;--bg4:#162847;
  --border:#1e3a5f;--text:#e2eaf6;--muted:#607898;
  --email:#3b82f6;--email-dim:#1d3d7a;
  --wa:#22c55e;--wa-dim:#0f3d20;
  --li:#0ea5e9;--li-dim:#073d5c;
  --warn:#f59e0b;--warn-dim:#4a2e06;
  --red:#ef4444;--red-dim:#4a1010;
  --green:#22c55e;--purple:#8b5cf6;
  --radius:10px;
}
*{box-sizing:border-box;margin:0;padding:0}
body{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;
  background:var(--bg);color:var(--text);min-height:100vh;display:flex;flex-direction:column}

/* ── Header ── */
.header{
  background:linear-gradient(135deg,#0a1628 0%,#0d1f3c 100%);
  border-bottom:1px solid var(--border);
  padding:0 24px;height:60px;display:flex;align-items:center;gap:16px;
  position:sticky;top:0;z-index:100;
}
.logo{font-size:18px;font-weight:700;color:#fff;display:flex;align-items:center;gap:8px}
.logo-icon{font-size:22px}
.header-spacer{flex:1}
.header-pills{display:flex;gap:8px;align-items:center}
.pill{padding:4px 10px;border-radius:20px;font-size:11px;font-weight:600;letter-spacing:.4px}
.pill-mode-dry{background:rgba(14,165,233,.15);color:#38bdf8;border:1px solid #0ea5e9}
.pill-mode-dev{background:rgba(245,158,11,.15);color:#fbbf24;border:1px solid #f59e0b}
.pill-mode-live{background:rgba(34,197,94,.15);color:#4ade80;border:1px solid #22c55e}
.pill-proc{background:rgba(34,197,94,.1);color:#4ade80;font-size:10px;padding:3px 8px;border-radius:12px;border:1px solid rgba(34,197,94,.3)}
.pill-proc.offline{background:rgba(239,68,68,.1);color:#f87171;border-color:rgba(239,68,68,.3)}
.clock{font-size:12px;color:var(--muted);font-family:monospace}

/* ── Stats bar ── */
.stats-bar{
  display:flex;gap:1px;background:var(--border);
  border-bottom:1px solid var(--border);
}
.stat-item{
  flex:1;background:var(--bg2);padding:14px 20px;
  display:flex;align-items:center;gap:12px;cursor:pointer;
  transition:background .15s;
}
.stat-item:hover,.stat-item.active{background:var(--bg3)}
.stat-item.active{border-bottom:2px solid var(--email)}
.stat-item.active.wa-tab{border-bottom-color:var(--wa)}
.stat-item.active.li-tab{border-bottom-color:var(--li)}
.stat-item.active.ap-tab{border-bottom-color:var(--warn)}
.stat-item.active.log-tab{border-bottom-color:var(--purple)}
.stat-icon{font-size:24px}
.stat-info .label{font-size:11px;color:var(--muted);text-transform:uppercase;letter-spacing:.6px}
.stat-info .value{font-size:22px;font-weight:700;line-height:1.1}
.stat-item.active .stat-info .value{color:var(--email)}
.stat-item.active.wa-tab .stat-info .value{color:var(--wa)}
.stat-item.active.li-tab .stat-info .value{color:var(--li)}
.stat-item.active.ap-tab .stat-info .value{color:var(--warn)}
.stat-item.active.log-tab .stat-info .value{color:var(--purple)}
.stat-badge{
  margin-left:auto;background:var(--red);color:#fff;
  font-size:10px;font-weight:700;padding:2px 7px;border-radius:10px;
  display:none;
}
.stat-badge.show{display:inline-block}

/* ── Main layout ── */
.main{flex:1;padding:20px 24px;display:none}
.main.active{display:block}

/* ── Cards ── */
.card{background:var(--bg2);border:1px solid var(--border);border-radius:var(--radius);overflow:hidden}
.card-header{
  padding:12px 16px;border-bottom:1px solid var(--border);
  display:flex;align-items:center;justify-content:space-between;gap:8px;
}
.card-title{font-size:13px;font-weight:600;color:var(--text);display:flex;align-items:center;gap:6px}
.card-body{padding:0}

/* ── Grid ── */
.grid-2{display:grid;grid-template-columns:1fr 1fr;gap:16px}
.grid-3{display:grid;grid-template-columns:1fr 1fr 1fr;gap:16px}
.mb{margin-bottom:16px}

/* ── Buttons ── */
.btn{padding:6px 14px;border:none;border-radius:6px;font-size:12px;font-weight:600;cursor:pointer;transition:opacity .15s;display:inline-flex;align-items:center;gap:5px}
.btn:hover{opacity:.85}
.btn:disabled{opacity:.4;cursor:not-allowed}
.btn-blue{background:var(--email);color:#fff}
.btn-green{background:var(--green);color:#000}
.btn-red{background:var(--red);color:#fff}
.btn-amber{background:var(--warn);color:#000}
.btn-ghost{background:transparent;color:var(--muted);border:1px solid var(--border)}
.btn-ghost:hover{color:var(--text);border-color:var(--text)}
.btn-sm{padding:4px 10px;font-size:11px}
.btn-li{background:#0a66c2;color:#fff}
.btn-wa{background:#075e54;color:#fff}

/* ── Email split panel ── */
.email-split{display:flex;gap:0;height:520px;border-radius:var(--radius);overflow:hidden;border:1px solid var(--border)}
.email-list-panel{width:340px;flex-shrink:0;border-right:1px solid var(--border);overflow-y:auto;background:var(--bg2)}
.email-detail-panel{flex:1;overflow-y:auto;background:var(--bg2);display:flex;flex-direction:column}
.email-detail-empty{flex:1;display:flex;flex-direction:column;align-items:center;justify-content:center;color:var(--muted);gap:8px}
.email-detail-empty .icon{font-size:40px;opacity:.3}
.email-detail-header{padding:16px;border-bottom:1px solid var(--border)}
.email-detail-subject{font-size:16px;font-weight:700;color:var(--text);line-height:1.3}
.email-detail-from{font-size:12px;color:var(--muted);margin-top:6px}
.email-detail-meta{display:flex;gap:6px;margin-top:8px;flex-wrap:wrap;align-items:center}
.email-detail-body{padding:16px;font-size:13px;line-height:1.7;color:#c9d8ee;flex:1;white-space:pre-wrap;font-family:inherit}
.email-detail-actions{padding:12px 16px;border-top:1px solid var(--border);display:flex;gap:8px}

/* ── Email list items ── */
.email-item{
  padding:10px 14px;border-bottom:1px solid var(--border);
  cursor:pointer;transition:background .12s;display:flex;gap:10px;align-items:flex-start;
}
.email-item:last-child{border-bottom:none}
.email-item:hover{background:var(--bg3)}
.email-item.selected{background:var(--email-dim);border-left:3px solid var(--email)}
.email-dot{width:7px;height:7px;border-radius:50%;background:var(--email);flex-shrink:0;margin-top:5px}
.email-dot.low{background:var(--muted)}
.email-content{flex:1;min-width:0}
.email-from{font-size:11px;font-weight:600;color:var(--text);white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.email-subject{font-size:12px;color:var(--text);margin-top:2px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.email-meta{display:flex;gap:5px;align-items:center;margin-top:4px;flex-wrap:wrap}
.badge{padding:2px 7px;border-radius:10px;font-size:10px;font-weight:600}
.badge-high{background:rgba(239,68,68,.15);color:#f87171;border:1px solid rgba(239,68,68,.3)}
.badge-low{background:rgba(96,120,152,.1);color:var(--muted);border:1px solid var(--border)}
.badge-pending{background:rgba(59,130,246,.1);color:#60a5fa;border:1px solid rgba(59,130,246,.3)}
.badge-done{background:rgba(34,197,94,.1);color:#4ade80;border:1px solid rgba(34,197,94,.3)}
.badge-plan{background:rgba(139,92,246,.1);color:#a78bfa;border:1px solid rgba(139,92,246,.3)}
.email-time{font-size:10px;color:var(--muted);flex-shrink:0;white-space:nowrap}

/* ── Plan list ── */
.plan-item{
  padding:11px 16px;border-bottom:1px solid var(--border);
  display:flex;align-items:center;gap:10px;
}
.plan-item:last-child{border-bottom:none}
.plan-icon{font-size:16px;flex-shrink:0}
.plan-name{font-size:12px;font-weight:600;flex:1;min-width:0;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.plan-sub{font-size:10px;color:var(--muted);margin-top:1px}
.progress-bar{height:3px;background:var(--bg3);border-radius:2px;margin-top:4px}
.progress-fill{height:100%;background:var(--green);border-radius:2px;transition:width .3s}

/* ── WhatsApp ── */
.wa-session{
  display:flex;align-items:center;gap:8px;padding:10px 16px;
  background:var(--wa-dim);border-radius:var(--radius);
  border:1px solid rgba(34,197,94,.2);
}
.wa-session .dot{width:8px;height:8px;border-radius:50%;background:var(--wa);animation:pulse 2s infinite}
.wa-keywords{display:flex;flex-wrap:wrap;gap:6px;padding:12px 16px}
.keyword-chip{background:var(--bg3);border:1px solid var(--border);border-radius:6px;padding:3px 10px;font-size:11px;font-family:monospace;color:var(--wa)}
.wa-empty{padding:40px 20px;text-align:center;color:var(--muted);font-size:13px;line-height:1.8}
/* WhatsApp split panel (same pattern as email) */
.wa-split{display:flex;gap:0;height:460px;border-radius:var(--radius);overflow:hidden;border:1px solid var(--border)}
.wa-list-panel{width:320px;flex-shrink:0;border-right:1px solid var(--border);overflow-y:auto;background:var(--bg2)}
.wa-detail-panel{flex:1;overflow-y:auto;background:var(--bg2);display:flex;flex-direction:column}
.wa-detail-empty{flex:1;display:flex;flex-direction:column;align-items:center;justify-content:center;color:var(--muted);gap:8px}
.wa-item{padding:10px 14px;border-bottom:1px solid var(--border);cursor:pointer;transition:background .12s;display:flex;gap:10px;align-items:flex-start}
.wa-item:hover{background:var(--bg3)}
.wa-item.selected{background:var(--wa-dim);border-left:3px solid var(--wa)}

/* ── LinkedIn ── */
.li-composer{padding:16px}
.li-composer textarea{
  width:100%;background:var(--bg);border:1px solid var(--border);border-radius:8px;
  color:var(--text);padding:12px;font-size:13px;font-family:inherit;
  resize:vertical;min-height:120px;line-height:1.5;
}
.li-composer textarea:focus{outline:none;border-color:var(--li)}
.li-composer-footer{display:flex;justify-content:space-between;align-items:center;margin-top:8px}
.li-posts .post-item{padding:12px 16px;border-bottom:1px solid var(--border);display:flex;gap:12px;align-items:flex-start}
.post-item:last-child{border-bottom:none}
.post-content{flex:1;min-width:0}
.post-id{font-size:10px;font-family:monospace;color:var(--muted);margin-top:3px}
.post-status-posted{color:var(--green)}
.post-status-dry_run{color:var(--warn)}
.char-count{font-size:11px;color:var(--muted)}

/* ── Approvals ── */
.approval-item{padding:14px 16px;border-bottom:1px solid var(--border);display:flex;gap:12px;align-items:flex-start}
.approval-item:last-child{border-bottom:none}
.approval-info{flex:1}
.approval-title{font-size:13px;font-weight:600}
.approval-meta{font-size:11px;color:var(--muted);margin-top:3px}
.approval-actions{display:flex;gap:6px;flex-shrink:0}
.approval-empty{padding:40px 20px;text-align:center;color:var(--muted);font-size:13px}
.flow-steps{display:flex;gap:0;margin-bottom:20px;overflow:hidden;border-radius:var(--radius);border:1px solid var(--border)}
.flow-step{flex:1;padding:14px 8px;text-align:center;background:var(--bg2);border-right:1px solid var(--border);transition:background .3s}
.flow-step:last-child{border-right:none}
.flow-step.done{background:rgba(34,197,94,.1);border-color:rgba(34,197,94,.2)}
.flow-step.active{background:rgba(59,130,246,.1);border-color:rgba(59,130,246,.2)}
.flow-step .step-n{font-size:18px;font-weight:700;color:var(--muted)}
.flow-step.done .step-n{color:var(--green)}
.flow-step.active .step-n{color:var(--email)}
.flow-step .step-l{font-size:10px;color:var(--muted);margin-top:2px}

/* ── Logs ── */
.log-table{width:100%;border-collapse:collapse;font-size:12px}
.log-table th{text-align:left;padding:8px 12px;border-bottom:2px solid var(--border);color:var(--muted);font-size:11px;text-transform:uppercase;letter-spacing:.5px}
.log-table td{padding:8px 12px;border-bottom:1px solid var(--border);font-family:monospace;white-space:nowrap;overflow:hidden;max-width:200px;text-overflow:ellipsis}
.log-table tr:hover td{background:var(--bg3)}
.result-ok{color:var(--green)}
.result-err{color:var(--red)}

/* ── Toast ── */
.toast{position:fixed;bottom:24px;right:24px;background:var(--bg2);border:1px solid var(--green);
  color:var(--green);padding:12px 20px;border-radius:8px;font-size:13px;font-weight:600;
  z-index:999;opacity:0;transform:translateY(8px);transition:all .25s;pointer-events:none;max-width:320px}
.toast.show{opacity:1;transform:translateY(0)}
.toast.err{border-color:var(--red);color:#f87171}

/* ── Spinner ── */
.spinner{width:16px;height:16px;border:2px solid rgba(255,255,255,.2);
  border-top-color:#fff;border-radius:50%;animation:spin .6s linear infinite;display:none}
.loading .spinner{display:inline-block}
.loading .btn-text{display:none}

@keyframes spin{to{transform:rotate(360deg)}}
@keyframes pulse{0%,100%{opacity:1}50%{opacity:.5}}

/* ── Scrollable ── */
.scroll{overflow-y:auto;max-height:480px}
.scroll-sm{overflow-y:auto;max-height:360px}

/* ── Responsive ── */
@media(max-width:900px){.grid-2{grid-template-columns:1fr}.grid-3{grid-template-columns:1fr 1fr}}
</style>
</head>
<body>

<!-- ── HEADER ── -->
<header class="header">
  <div class="logo">
    <span class="logo-icon">🤖</span>
    Personal AI Employee
  </div>
  <div class="header-spacer"></div>
  <div class="header-pills">
    <span id="modePill" class="pill">...</span>
    <span id="orchPill" class="pill-proc" title="Orchestrator">⚙ Orch</span>
    <span id="gmailPill" class="pill-proc" title="Gmail Watcher">📧 Gmail</span>
    <span id="waPill" class="pill-proc" title="WhatsApp Watcher">💬 WA</span>
  </div>
  <div class="clock" id="clock">00:00:00</div>
</header>

<!-- ── STATS / TAB BAR ── -->
<div class="stats-bar">
  <div class="stat-item active" id="tab-email-btn" onclick="switchTab('email')">
    <div class="stat-icon">📧</div>
    <div class="stat-info">
      <div class="label">Gmail Inbox</div>
      <div class="value" id="cnt-email">—</div>
    </div>
  </div>
  <div class="stat-item wa-tab" id="tab-wa-btn" onclick="switchTab('wa')">
    <div class="stat-icon">💬</div>
    <div class="stat-info">
      <div class="label">WhatsApp</div>
      <div class="value" id="cnt-wa">—</div>
    </div>
    <span class="stat-badge" id="badge-wa">NEW</span>
  </div>
  <div class="stat-item li-tab" id="tab-li-btn" onclick="switchTab('li')">
    <div class="stat-icon">💼</div>
    <div class="stat-info">
      <div class="label">LinkedIn</div>
      <div class="value" id="cnt-li">—</div>
    </div>
  </div>
  <div class="stat-item ap-tab" id="tab-ap-btn" onclick="switchTab('ap')">
    <div class="stat-icon">⏳</div>
    <div class="stat-info">
      <div class="label">Approvals</div>
      <div class="value" id="cnt-ap">—</div>
    </div>
    <span class="stat-badge" id="badge-ap">!</span>
  </div>
  <div class="stat-item log-tab" id="tab-log-btn" onclick="switchTab('log')">
    <div class="stat-icon">📋</div>
    <div class="stat-info">
      <div class="label">Audit Log</div>
      <div class="value" id="cnt-done">—</div>
    </div>
  </div>
</div>

<!-- ═══════════════════ EMAIL TAB ═══════════════════ -->
<div class="main active" id="tab-email">

  <!-- Toolbar row -->
  <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:12px">
    <div style="display:flex;align-items:center;gap:10px">
      <span style="font-size:13px;font-weight:600">📥 Gmail Inbox — <span id="email-count-label">loading...</span></span>
      <span class="badge badge-pending" id="email-account">ashfaqahmed1192@gmail.com</span>
    </div>
    <div style="display:flex;gap:8px">
      <button class="btn btn-ghost btn-sm" id="planToggleBtn" onclick="togglePlans()">🧠 Show Plans</button>
      <button class="btn btn-blue btn-sm" id="pullBtn" onclick="pullGmail()">
        <span class="spinner"></span><span class="btn-text">↻ Pull Gmail</span>
      </button>
    </div>
  </div>

  <!-- Split panel: email list + detail -->
  <div class="email-split mb" id="emailSplit">
    <!-- LEFT: email list -->
    <div class="email-list-panel" id="email-list">
      <div style="padding:30px;text-align:center;color:var(--muted);font-size:13px">Loading...</div>
    </div>
    <!-- RIGHT: email detail -->
    <div class="email-detail-panel" id="email-detail">
      <div class="email-detail-empty">
        <div class="icon">📭</div>
        <div style="font-size:13px;font-weight:600">Select an email to read</div>
        <div style="font-size:11px">Click any email on the left to see its full content here</div>
      </div>
    </div>
  </div>

  <!-- Plans panel (toggled) -->
  <div id="plans-panel" style="display:none" class="card mb">
    <div class="card-header">
      <span class="card-title">🧠 AI Plans Generated by Claude</span>
      <span class="badge badge-plan" id="plan-count">0 plans</span>
    </div>
    <div class="card-body scroll-sm" id="plans-list">
      <div style="padding:20px;text-align:center;color:var(--muted)">Loading...</div>
    </div>
  </div>

  <!-- Flow diagram -->
  <div class="card">
    <div class="card-header"><span class="card-title">⚡ Email Flow</span></div>
    <div style="padding:14px;display:flex;gap:0;overflow:hidden;border-radius:8px">
      <div style="flex:1;text-align:center;padding:10px;background:var(--bg3);border-radius:6px 0 0 6px;border:1px solid var(--border)">
        <div style="font-size:18px">📬</div><div style="font-size:10px;font-weight:600;margin-top:4px">Gmail Watcher</div>
        <div style="font-size:10px;color:var(--muted)">polls every 2 min</div>
      </div>
      <div style="display:flex;align-items:center;padding:0 4px;color:var(--muted);font-size:12px">→</div>
      <div style="flex:1;text-align:center;padding:10px;background:var(--bg3);border:1px solid var(--border)">
        <div style="font-size:18px">📂</div><div style="font-size:10px;font-weight:600;margin-top:4px">/Needs_Action/</div>
        <div style="font-size:10px;color:var(--muted)">EMAIL_*.md</div>
      </div>
      <div style="display:flex;align-items:center;padding:0 4px;color:var(--muted);font-size:12px">→</div>
      <div style="flex:1;text-align:center;padding:10px;background:var(--bg3);border:1px solid var(--border)">
        <div style="font-size:18px">🤖</div><div style="font-size:10px;font-weight:600;margin-top:4px">Claude Reasons</div>
        <div style="font-size:10px;color:var(--muted)">triage-email skill</div>
      </div>
      <div style="display:flex;align-items:center;padding:0 4px;color:var(--muted);font-size:12px">→</div>
      <div style="flex:1;text-align:center;padding:10px;background:var(--bg3);border:1px solid var(--border)">
        <div style="font-size:18px">📝</div><div style="font-size:10px;font-weight:600;margin-top:4px">PLAN_*.md</div>
        <div style="font-size:10px;color:var(--muted)">checklist created</div>
      </div>
      <div style="display:flex;align-items:center;padding:0 4px;color:var(--muted);font-size:12px">→</div>
      <div style="flex:1;text-align:center;padding:10px;background:var(--bg3);border-radius:0 6px 6px 0;border:1px solid var(--border)">
        <div style="font-size:18px">✅</div><div style="font-size:10px;font-weight:600;margin-top:4px">Human Approves</div>
        <div style="font-size:10px;color:var(--muted)">HITL gate</div>
      </div>
    </div>
  </div>
</div>

<!-- ═══════════════════ WHATSAPP TAB ═══════════════════ -->
<div class="main" id="tab-wa">

  <!-- Session bar + action buttons in one row -->
  <div style="display:flex;align-items:center;gap:12px;margin-bottom:16px;flex-wrap:wrap">
    <div class="wa-session" style="margin-bottom:0;flex:1;min-width:240px">
      <div class="dot"></div>
      <span style="font-size:13px;font-weight:600;color:var(--wa)">WhatsApp Session Active</span>
      <span style="font-size:11px;color:var(--muted);margin-left:4px">— phone number linked</span>
    </div>
    <button class="btn btn-wa" id="waScanBtn" onclick="scanWhatsApp()" style="flex-shrink:0">
      <span class="spinner"></span>
      <span class="btn-text">💬 Check Messages Now</span>
    </button>
  </div>

  <!-- WhatsApp split panel -->
  <div class="wa-split mb">
    <!-- LEFT: message list -->
    <div class="wa-list-panel" id="wa-list">
      <div style="padding:30px;text-align:center;color:var(--muted);font-size:12px">
        No keyword messages yet.<br><br>
        Send a WhatsApp with:<br>
        <strong style="color:var(--wa)">invoice · urgent · payment</strong>
      </div>
    </div>
    <!-- RIGHT: message detail -->
    <div class="wa-detail-panel" id="wa-detail">
      <div class="wa-detail-empty">
        <div style="font-size:40px;opacity:.3">💬</div>
        <div style="font-size:13px;font-weight:600">Select a message to read</div>
        <div style="font-size:11px">Click any message on the left</div>
      </div>
    </div>
  </div>

  <div class="grid-2 mb">
    <div class="card" style="display:none"><!-- hidden spacer --></div>

    <div class="card">
      <div class="card-header">
        <span class="card-title">🔑 Active Trigger Keywords</span>
      </div>
      <div class="card-body">
        <div class="wa-keywords">
          <span class="keyword-chip">urgent</span>
          <span class="keyword-chip">asap</span>
          <span class="keyword-chip">invoice</span>
          <span class="keyword-chip">payment</span>
          <span class="keyword-chip">help</span>
          <span class="keyword-chip">pricing</span>
          <span class="keyword-chip">contract</span>
          <span class="keyword-chip">deadline</span>
        </div>
        <div style="padding:12px 16px;border-top:1px solid var(--border)">
          <div style="font-size:11px;color:var(--muted);line-height:1.8">
            Edit keywords in <code style="color:var(--wa)">Company_Handbook.md</code><br>
            No code change needed — Claude reads the rules before every decision.
          </div>
        </div>
      </div>
      <div class="card-header" style="margin-top:0;border-top:1px solid var(--border)">
        <span class="card-title">⚡ WhatsApp Flow</span>
      </div>
      <div style="padding:14px 16px;font-size:12px;color:var(--muted);line-height:2">
        📱 Message received on phone<br>
        → 🌐 WhatsApp Web (Playwright headless)<br>
        → 🔍 Keyword scan every 30s<br>
        → 📂 WHATSAPP_*.md → /Needs_Action/<br>
        → 🤖 Claude processes → PLAN_*.md<br>
        → ✅ Human approves reply
      </div>
    </div>
  </div>
</div>

<!-- ═══════════════════ LINKEDIN TAB ═══════════════════ -->
<div class="main" id="tab-li">
  <div class="grid-2 mb">
    <!-- Composer -->
    <div class="card">
      <div class="card-header">
        <span class="card-title">✍️ Compose & Post to LinkedIn</span>
        <span id="li-mode-badge" class="badge badge-pending">DRY_RUN</span>
      </div>
      <div class="li-composer">
        <textarea id="li-text" placeholder="Write your LinkedIn post here...
Share your AI Employee project progress, business updates, client wins...

(Tip: mention #AI #AgentEngineering #ClaudeCode for reach)"></textarea>
        <div class="li-composer-footer">
          <span class="char-count" id="li-char">0 / 3000</span>
          <button class="btn btn-li" id="li-post-btn" onclick="postLinkedIn()">
            <span class="spinner"></span>
            <span class="btn-text">🚀 Post to LinkedIn</span>
          </button>
        </div>
        <div id="li-result" style="display:none;margin-top:12px;padding:10px;background:var(--bg);border-radius:6px;font-size:12px;font-family:monospace;border:1px solid var(--border)"></div>
      </div>
    </div>

    <!-- Recent Posts -->
    <div class="card">
      <div class="card-header">
        <span class="card-title">📊 Recent Posts</span>
        <span class="badge badge-done" id="li-post-count">0 posts</span>
      </div>
      <div class="card-body li-posts scroll" id="li-posts-list">
        <div style="padding:30px;text-align:center;color:var(--muted)">Loading...</div>
      </div>
    </div>
  </div>

  <!-- LinkedIn MCP architecture -->
  <div class="card">
    <div class="card-header">
      <span class="card-title">🔧 LinkedIn MCP Architecture</span>
    </div>
    <div style="padding:16px;font-size:12px;line-height:1.8;color:var(--muted)">
      <strong style="color:var(--text)">social-scheduler skill</strong> reads Business_Goals.md
      → drafts post text → writes SOCIAL_*.md to /Plans/<br>
      → <strong style="color:var(--text)">social_mcp.py</strong> calls
      <code style="color:var(--li)">LinkedInClient.post()</code>
      → <code style="color:var(--li)">GET /v2/userinfo</code> (get person URN)
      → <code style="color:var(--li)">POST /v2/ugcPosts</code> (lifecycleState: PUBLISHED, visibility: PUBLIC)<br>
      → post ID returned in <code style="color:var(--li)">x-restli-id</code> response header
      → logged to /Logs/YYYY-MM-DD.json
    </div>
  </div>
</div>

<!-- ═══════════════════ APPROVALS TAB ═══════════════════ -->
<div class="main" id="tab-ap">
  <!-- HITL flow diagram -->
  <div class="flow-steps mb" id="flowSteps">
    <div class="flow-step" id="fs1"><div class="step-n">1</div><div class="step-l">Item Detected</div></div>
    <div class="flow-step" id="fs2"><div class="step-n">2</div><div class="step-l">Claude Reasons</div></div>
    <div class="flow-step" id="fs3"><div class="step-n">3</div><div class="step-l">APPROVAL_*.md Created</div></div>
    <div class="flow-step" id="fs4"><div class="step-n">4</div><div class="step-l">Human Reviews</div></div>
    <div class="flow-step" id="fs5"><div class="step-n">5</div><div class="step-l">Action Executed</div></div>
  </div>

  <div class="grid-2">
    <div class="card">
      <div class="card-header">
        <span class="card-title">⏳ Pending Approvals</span>
        <button class="btn btn-ghost btn-sm" onclick="runFlowDemo()">▶ Run Demo</button>
      </div>
      <div class="card-body" id="approval-list">
        <div class="approval-empty">No pending approvals.<br><span style="font-size:11px">All clear — the AI hasn't flagged anything for review.</span></div>
      </div>
    </div>

    <div class="card">
      <div class="card-header"><span class="card-title">📖 Approval Rules</span></div>
      <div style="padding:14px 16px;font-size:12px;line-height:2;color:var(--muted)">
        <strong style="color:var(--text)">Auto-approve:</strong> Scheduled social posts, read-only ops<br>
        <strong style="color:var(--warn)">Requires approval:</strong> Email sends to new contacts<br>
        <strong style="color:var(--red)">Always approve:</strong> Payments, bulk sends, new payees<br>
        <strong style="color:var(--text)">Expires:</strong> 24h — auto-rejected if not actioned<br><br>
        Edit thresholds in <code style="color:var(--warn)">Company_Handbook.md</code>
      </div>
    </div>
  </div>
</div>

<!-- ═══════════════════ AUDIT LOG TAB ═══════════════════ -->
<div class="main" id="tab-log">
  <div class="card">
    <div class="card-header">
      <span class="card-title">📋 Audit Log <span style="font-weight:400;color:var(--muted)">(last 40 entries)</span></span>
      <span style="font-size:11px;color:var(--muted)">auto-refreshes every 5s</span>
    </div>
    <div class="card-body scroll">
      <table class="log-table">
        <thead><tr><th>Time</th><th>Action</th><th>Actor</th><th>Target</th><th>Result</th><th>Approval</th></tr></thead>
        <tbody id="log-body"></tbody>
      </table>
      <div id="log-empty" style="padding:40px;text-align:center;color:var(--muted);display:none">No log entries yet.</div>
    </div>
  </div>
</div>

<div class="toast" id="toast"></div>

<script>
// ── Utilities ──────────────────────────────────────────────────────────────
const $ = s => document.querySelector(s);
const toast = (msg, err) => {
  const t = $('#toast');
  t.textContent = msg;
  t.className = 'toast show' + (err ? ' err' : '');
  clearTimeout(t._t);
  t._t = setTimeout(() => t.classList.remove('show'), 3500);
};
const post = (url, body={}) => fetch(url, {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(body)}).then(r=>r.json());
const get  = url => fetch(url).then(r=>r.json());
const timeAgo = iso => {
  if(!iso) return '';
  const d = new Date(iso), now = new Date();
  const s = Math.floor((now-d)/1000);
  if(s<60) return `${s}s ago`;
  if(s<3600) return `${Math.floor(s/60)}m ago`;
  if(s<86400) return `${Math.floor(s/3600)}h ago`;
  return d.toLocaleDateString();
};
const fmt = iso => iso ? iso.replace('T',' ').substring(0,19) : '';

// ── Tab switching ──────────────────────────────────────────────────────────
let activeTab = 'email';
function switchTab(tab) {
  activeTab = tab;
  document.querySelectorAll('.main').forEach(el => el.classList.remove('active'));
  document.querySelectorAll('.stat-item').forEach(el => el.classList.remove('active'));
  $(`#tab-${tab}`).classList.add('active');
  $(`#tab-${tab}-btn`).classList.add('active');
  if(tab === 'log') refreshLogs();
  if(tab === 'ap') refreshApprovals();
  if(tab === 'li') refreshLinkedIn();
}

// ── Clock ──────────────────────────────────────────────────────────────────
setInterval(() => {
  $('#clock').textContent = new Date().toLocaleTimeString();
}, 1000);

// ── Status ─────────────────────────────────────────────────────────────────
async function refreshStatus() {
  const d = await get('/api/status');
  // Mode pill
  const mp = $('#modePill');
  mp.textContent = d.mode;
  mp.className = 'pill ' + (d.mode==='DEV_MODE'?'pill-mode-dev':d.mode==='DRY_RUN'?'pill-mode-dry':'pill-mode-live');
  // Counts
  $('#cnt-email').textContent = d.counts.email;
  $('#cnt-wa').textContent = d.counts.whatsapp;
  $('#cnt-ap').textContent = d.counts.pending;
  $('#cnt-done').textContent = d.counts.done + ' done';
  // Pending badge
  if(d.counts.pending > 0) {
    $('#badge-ap').textContent = d.counts.pending;
    $('#badge-ap').classList.add('show');
  } else {
    $('#badge-ap').classList.remove('show');
  }
  if(d.counts.whatsapp > 0) $('#badge-wa').classList.add('show');
  else $('#badge-wa').classList.remove('show');
  // Process pills
  const status = d.processes || {};
  function setPill(id, names) {
    const el = $(id);
    const online = names.some(n => status[n] === 'online');
    el.className = 'pill-proc' + (online?'':' offline');
  }
  setPill('#orchPill', ['ai-employee-orchestrator']);
  setPill('#gmailPill', ['ai-employee-gmail-watcher']);
  setPill('#waPill', ['ai-employee-whatsapp-watcher']);
}

// ── Email ──────────────────────────────────────────────────────────────────
let selectedEmail = null;
let currentEmail = null;
let plansVisible = false;

function togglePlans() {
  plansVisible = !plansVisible;
  $('#plans-panel').style.display = plansVisible ? 'block' : 'none';
  $('#planToggleBtn').textContent = plansVisible ? '🧠 Hide Plans' : '🧠 Show Plans';
  if(plansVisible) refreshPlans();
}

async function refreshEmails() {
  const emails = await get('/api/emails');
  $('#email-count-label').textContent = emails.length + ' emails pending';
  const el = $('#email-list');
  if(!emails.length) {
    el.innerHTML = '<div style="padding:30px;text-align:center;color:var(--muted);font-size:12px">No emails in /Needs_Action/<br><button class="btn btn-blue btn-sm" style="margin-top:10px" onclick="pullGmail()">↻ Pull Gmail Now</button></div>';
    return;
  }
  el.innerHTML = emails.map(e => {
    const pri = e.priority === 'high';
    const sel = selectedEmail === e.filename;
    return `<div class="email-item ${sel?'selected':''}" onclick="selectEmail('${escHtml(e.filename)}', this)">
      <div class="email-dot ${pri?'':'low'}"></div>
      <div class="email-content">
        <div class="email-from">${escHtml(e.from)}</div>
        <div class="email-subject">${escHtml(e.subject)}</div>
        <div class="email-meta">
          <span class="badge ${pri?'badge-high':'badge-low'}">${e.priority}</span>
          <span class="badge badge-pending">${e.status}</span>
          ${e.plan_ref && e.plan_ref!='null' && e.plan_ref!='None'?'<span class="badge badge-plan">plan</span>':''}
        </div>
      </div>
      <div class="email-time">${timeAgo(e.received)}</div>
    </div>`;
  }).join('');
}

async function selectEmail(filename, el) {
  // Update selection state
  document.querySelectorAll('.email-item').forEach(e => e.classList.remove('selected'));
  el.classList.add('selected');
  selectedEmail = filename;

  const detail = $('#email-detail');
  detail.innerHTML = '<div class="email-detail-empty"><div class="icon">⏳</div><div style="font-size:12px">Loading...</div></div>';

  const d = await get('/api/email-content?file=' + encodeURIComponent(filename));
  if(d.error) {
    detail.innerHTML = `<div class="email-detail-empty"><div class="icon">⚠️</div><div>${escHtml(d.error)}</div></div>`;
    return;
  }

  // Parse frontmatter for header
  const fm = parseFm(d.content);
  const body = d.content.replace(/^---[\s\S]*?---\s*\n/, '').trim();
  currentEmail = {filename, from: fm.from || '', subject: fm.subject || ''};

  detail.innerHTML = `
    <div class="email-detail-header">
      <div class="email-detail-subject">${escHtml(fm.subject || '(no subject)')}</div>
      <div class="email-detail-from">From: ${escHtml(fm.from || 'Unknown')}</div>
      <div class="email-detail-meta">
        <span class="badge ${fm.priority==='high'?'badge-high':'badge-low'}">${fm.priority||'normal'}</span>
        <span class="badge badge-pending">${fm.status||'pending'}</span>
        ${fm.plan_ref && fm.plan_ref!='null'?`<span class="badge badge-plan">has plan</span>`:''}
        <span style="font-size:10px;color:var(--muted);margin-left:4px">${escHtml(fm.received||'')}</span>
      </div>
    </div>
    <div class="email-detail-body">${escHtml(body)}</div>
    <div class="email-detail-actions">
      <button class="btn btn-blue btn-sm" onclick="toggleReplyBox()">↩ Reply</button>
      <button class="btn btn-green btn-sm" onclick="markEmailDone()">✅ Mark Done</button>
    </div>
    <div id="reply-box" style="display:none;padding:12px 16px;border-top:1px solid var(--border);background:var(--bg3)">
      <div style="font-size:11px;color:var(--muted);margin-bottom:6px">↩ Replying to: <strong style="color:var(--text)">${escHtml(fm.from||'')}</strong> — <span style="color:var(--warn)">requires your approval before sending</span></div>
      <textarea id="reply-text" style="width:100%;background:var(--bg);border:1px solid var(--border);border-radius:6px;color:var(--text);padding:8px;font-size:12px;font-family:inherit;resize:vertical;min-height:90px" placeholder="Type your reply here..."></textarea>
      <div style="display:flex;gap:8px;margin-top:8px;justify-content:flex-end">
        <button class="btn btn-ghost btn-sm" onclick="toggleReplyBox()">Cancel</button>
        <button class="btn btn-amber btn-sm" onclick="submitEmailReply()">📤 Submit for Approval</button>
      </div>
    </div>`;
}

function parseFm(text) {
  const m = text.match(/^---\s*\n([\s\S]*?)\n---/);
  if(!m) return {};
  const d = {};
  m[1].split('\n').forEach(line => {
    const i = line.indexOf(':');
    if(i>0) d[line.slice(0,i).trim()] = line.slice(i+1).trim().replace(/^["']|["']$/g,'');
  });
  return d;
}

async function refreshPlans() {
  const plans = await get('/api/plans');
  const planItems = plans.filter(p => p.type === 'plan');
  $('#plan-count').textContent = planItems.length + ' plans';
  const pl = $('#plans-list');
  if(!planItems.length) {
    pl.innerHTML = '<div style="padding:20px;text-align:center;color:var(--muted);font-size:12px">No plans yet. Claude generates PLAN_*.md when it processes emails.</div>';
    return;
  }
  pl.innerHTML = planItems.map(p => {
    const pct = p.steps_total > 0 ? Math.round(p.steps_done/p.steps_total*100) : 0;
    return `<div class="plan-item">
      <div class="plan-icon">${p.status==='done'?'✅':'📋'}</div>
      <div style="flex:1;min-width:0">
        <div class="plan-name">${escHtml(p.filename.replace('.md',''))}</div>
        <div class="plan-sub">${p.steps_done}/${p.steps_total} steps · ${timeAgo(p.created||p.mtime)}</div>
        <div class="progress-bar"><div class="progress-fill" style="width:${pct}%"></div></div>
      </div>
      <span class="badge badge-plan">${p.status}</span>
    </div>`;
  }).join('');
}

async function pullGmail() {
  const btn = $('#pullBtn');
  btn.classList.add('loading'); btn.disabled = true;
  try {
    const r = await post('/api/gmail/pull');
    if(r.status === 'ok') {
      toast(`✅ Gmail pulled — ${r.new_emails} new email${r.new_emails!==1?'s':''}`);
      refreshEmails(); refreshStatus();
    } else {
      toast('❌ ' + (r.message||'Pull failed'), true);
    }
  } finally {
    btn.classList.remove('loading'); btn.disabled = false;
  }
}

// ── WhatsApp ────────────────────────────────────────────────────────────────
async function refreshWA() {
  const msgs = await get('/api/whatsapp');
  const el = $('#wa-list');
  const cntEl = $('#wa-msg-count');
  if(cntEl) cntEl.textContent = msgs.length + ' messages';
  if(!msgs.length) {
    el.innerHTML = `<div class="wa-empty">
      No keyword messages yet.<br><br>
      Send a WhatsApp message to yourself containing:<br>
      <strong style="color:var(--wa)">invoice · urgent · payment · help · asap</strong><br><br>
      Click <strong>"Check Messages Now"</strong> above or wait 30s for auto-scan.
    </div>`;
    return;
  }
  el.innerHTML = msgs.map(m => `
    <div class="wa-item" onclick="selectWhatsApp('${escHtml(m.filename)}', this)">
      <div style="font-size:20px;flex-shrink:0">💬</div>
      <div style="flex:1">
        <div style="font-size:12px;font-weight:600">${escHtml(m.from)}</div>
        <div style="font-size:13px;margin-top:3px;line-height:1.5">${escHtml(m.snippet)}</div>
        <div style="display:flex;gap:6px;margin-top:5px;flex-wrap:wrap">
          <span class="badge badge-high">${escHtml(m.priority)}</span>
          ${m.keywords?`<span class="badge" style="background:var(--wa-dim);color:var(--wa);border:1px solid rgba(34,197,94,.4)">${escHtml(m.keywords)}</span>`:''}
          <span style="font-size:10px;color:var(--muted)">${timeAgo(m.received)}</span>
        </div>
      </div>
    </div>
  `).join('');
}

async function scanWhatsApp() {
  const btn = $('#waScanBtn');
  btn.classList.add('loading'); btn.disabled = true;
  try {
    const r = await post('/api/whatsapp/scan');
    if(r.status === 'ok') {
      toast(`💬 Scanned — ${r.new_messages} new message${r.new_messages!==1?'s':''}`);
      refreshWA(); refreshStatus();
    } else {
      toast('⚠️ ' + (r.message||'Scan failed'), true);
    }
  } finally {
    btn.classList.remove('loading'); btn.disabled = false;
  }
}

let selectedWA = null;
let currentWAFrom = '';

async function selectWhatsApp(filename, el) {
  document.querySelectorAll('.wa-item').forEach(e => e.classList.remove('selected'));
  el.classList.add('selected');
  selectedWA = filename;
  const detail = $('#wa-detail');
  detail.innerHTML = '<div class="wa-detail-empty"><div style="font-size:30px;opacity:.3">⏳</div><div style="font-size:12px;margin-top:8px">Loading...</div></div>';
  const d = await get('/api/whatsapp-content?file=' + encodeURIComponent(filename));
  if(d.error) {
    detail.innerHTML = `<div class="wa-detail-empty"><div style="font-size:30px;opacity:.3">⚠️</div><div>${escHtml(d.error)}</div></div>`;
    return;
  }
  const fm = parseFm(d.content);
  const body = d.content.replace(/^---[\s\S]*?---\s*\n/, '').trim();
  currentWAFrom = fm.from || '';
  detail.innerHTML = `
    <div class="email-detail-header">
      <div class="email-detail-subject">💬 ${escHtml(fm.from||'Unknown')}</div>
      <div class="email-detail-from">${escHtml(fm.subject||'WhatsApp Message')}</div>
      <div class="email-detail-meta">
        <span class="badge badge-high">${escHtml(fm.priority||'high')}</span>
        <span class="badge badge-pending">${escHtml(fm.status||'pending')}</span>
        <span style="font-size:10px;color:var(--muted);margin-left:4px">${escHtml(fm.received||'')}</span>
      </div>
    </div>
    <div class="email-detail-body">${escHtml(body)}</div>
    <div class="email-detail-actions">
      <button class="btn btn-wa btn-sm" onclick="toggleWAReplyBox()">↩ Draft Reply</button>
      <button class="btn btn-green btn-sm" onclick="markWADone()">✅ Archive</button>
    </div>
    <div id="wa-reply-box" style="display:none;padding:12px 16px;border-top:1px solid var(--border);background:var(--bg3)">
      <div style="font-size:11px;color:var(--muted);margin-bottom:6px">↩ Reply to: <strong style="color:var(--text)">${escHtml(fm.from||'')}</strong> — <span style="color:var(--warn)">requires your approval before sending</span></div>
      <textarea id="wa-reply-text" style="width:100%;background:var(--bg);border:1px solid var(--border);border-radius:6px;color:var(--text);padding:8px;font-size:12px;font-family:inherit;resize:vertical;min-height:90px" placeholder="Type your WhatsApp reply..."></textarea>
      <div style="display:flex;gap:8px;margin-top:8px;justify-content:flex-end">
        <button class="btn btn-ghost btn-sm" onclick="toggleWAReplyBox()">Cancel</button>
        <button class="btn btn-amber btn-sm" onclick="submitWAReply()">📤 Request Approval</button>
      </div>
    </div>`;
}

async function markWADone() {
  if(!selectedWA) return;
  const r = await post('/api/email/done', {filename: selectedWA});
  if(r.status === 'ok') {
    toast('✅ WhatsApp message archived to /Done/');
    selectedWA = null;
    $('#wa-detail').innerHTML = '<div class="wa-detail-empty"><div style="font-size:40px;opacity:.3">💬</div><div style="font-size:13px;font-weight:600">Select a message to read</div><div style="font-size:11px">Click any message on the left</div></div>';
    refreshWA(); refreshStatus();
  } else {
    toast('❌ ' + (r.message||'Failed'), true);
  }
}

function toggleReplyBox() {
  const rb = document.getElementById('reply-box');
  if(rb) rb.style.display = rb.style.display === 'none' ? 'block' : 'none';
}

async function submitEmailReply() {
  if(!currentEmail) return;
  const textEl = document.getElementById('reply-text');
  const replyText = textEl ? textEl.value.trim() : '';
  if(!replyText) { toast('Please type a reply first', true); return; }
  const r = await post('/api/email/reply', {...currentEmail, reply_body: replyText});
  if(r.status === 'ok') {
    toast('📝 Reply submitted for approval! Switching to Approvals tab...');
    refreshStatus();
    setTimeout(() => switchTab('ap'), 1500);
  } else {
    toast('❌ ' + (r.message||'Failed'), true);
  }
}

function toggleWAReplyBox() {
  const rb = document.getElementById('wa-reply-box');
  if(rb) rb.style.display = rb.style.display === 'none' ? 'block' : 'none';
}

async function submitWAReply() {
  if(!selectedWA) return;
  const textEl = document.getElementById('wa-reply-text');
  const replyText = textEl ? textEl.value.trim() : '';
  if(!replyText) { toast('Please type a reply first', true); return; }
  const r = await post('/api/whatsapp/reply', {filename: selectedWA, from: currentWAFrom, reply_body: replyText});
  if(r.status === 'ok') {
    toast('📝 WhatsApp reply submitted for approval! Switching to Approvals...');
    refreshStatus();
    setTimeout(() => switchTab('ap'), 1500);
  } else {
    toast('❌ ' + (r.message||'Failed'), true);
  }
}

async function markEmailDone() {
  if(!currentEmail) return;
  const r = await post('/api/email/done', {filename: currentEmail.filename});
  if(r.status === 'ok') {
    toast('✅ Email moved to /Done/');
    currentEmail = null;
    selectedEmail = null;
    $('#email-detail').innerHTML = '<div class="email-detail-empty"><div class="icon">📭</div><div style="font-size:13px;font-weight:600">Select an email to read</div><div style="font-size:11px">Click any email on the left to see its full content here</div></div>';
    refreshEmails(); refreshStatus();
  } else {
    toast('❌ ' + (r.message||'Failed'), true);
  }
}

// ── LinkedIn ────────────────────────────────────────────────────────────────
async function refreshLinkedIn() {
  const plans = await get('/api/plans');
  const posts = plans.filter(p => p.type === 'social');
  $('#cnt-li').textContent = posts.length;
  $('#li-post-count').textContent = posts.length + ' posts';
  const el = $('#li-posts-list');
  if(!posts.length) {
    el.innerHTML = '<div style="padding:30px;text-align:center;color:var(--muted)">No posts yet.<br>Compose and post using the form.</div>';
    return;
  }
  el.innerHTML = posts.map(p => `
    <div class="post-item">
      <div style="font-size:20px">💼</div>
      <div class="post-content">
        <div style="font-size:12px;font-weight:600">${escHtml(p.filename.replace('.md',''))}</div>
        <div class="post-id">${p.post_id||'(no post ID — dry run)'}</div>
        <div style="display:flex;gap:6px;margin-top:4px">
          <span class="badge ${p.status==='posted'?'badge-done':'badge-pending'} post-status-${p.status}">${p.status}</span>
          <span style="font-size:10px;color:var(--muted)">${timeAgo(p.created||p.mtime)}</span>
        </div>
      </div>
    </div>
  `).join('');
}

// Live post
$('#li-text').addEventListener('input', function() {
  $('#li-char').textContent = this.value.length + ' / 3000';
});

async function postLinkedIn() {
  const text = $('#li-text').value.trim();
  if(!text) { toast('Please write something first', true); return; }
  const btn = $('#li-post-btn');
  btn.classList.add('loading'); btn.disabled = true;
  try {
    const r = await post('/api/linkedin/post', {text});
    const res = $('#li-result');
    res.style.display = 'block';
    if(r.status === 'ok') {
      res.style.borderColor = 'var(--green)';
      res.textContent = r.dry_run
        ? `[DRY_RUN] Would post: "${r.preview}..."`
        : `✅ Posted! ID: ${r.post_id}`;
      toast(r.dry_run ? '(Dry run) Would post to LinkedIn' : '🚀 Posted to LinkedIn! ' + r.post_id);
      $('#li-text').value = '';
      $('#li-char').textContent = '0 / 3000';
      refreshLinkedIn(); refreshStatus();
    } else {
      res.style.borderColor = 'var(--red)';
      res.textContent = '❌ Error: ' + r.message;
      toast('❌ ' + r.message, true);
    }
  } finally {
    btn.classList.remove('loading'); btn.disabled = false;
  }
}

// ── Approvals ───────────────────────────────────────────────────────────────
let flowStep = 0;
function updateFlow(n) {
  flowStep = n;
  for(let i=1;i<=5;i++){
    const el = $(`#fs${i}`);
    el.classList.remove('done','active');
    if(i < n) el.classList.add('done');
    if(i === n) el.classList.add('active');
  }
}

async function refreshApprovals() {
  const items = await get('/api/pending');
  const el = $('#approval-list');
  if(!items.length) {
    el.innerHTML = '<div class="approval-empty">✅ No pending approvals.<br><span style="font-size:11px;color:var(--muted)">All clear — the AI hasn\'t flagged anything for review.</span></div>';
    updateFlow(0);
    return;
  }
  updateFlow(4);
  el.innerHTML = items.map(item => `
    <div class="approval-item">
      <div style="font-size:22px">${item.action==='email_send'?'📧':item.action==='whatsapp_reply'?'💬':'⏳'}</div>
      <div class="approval-info">
        <div class="approval-title">${item.action==='email_send'?'Send Email Reply':'Send WhatsApp Reply'} → <span style="color:var(--text)">${escHtml(item.to||'')}</span></div>
        ${item.subject?`<div class="approval-meta">Subject: ${escHtml(item.subject)}</div>`:''}
        ${item.reply_preview?`<div style="margin-top:6px;padding:8px;background:var(--bg);border-radius:6px;border:1px solid var(--border);font-size:12px;color:var(--text);line-height:1.5">${escHtml(item.reply_preview)}${item.reply_preview.length>=120?'…':''}</div>`:''}
        ${item.amount?`<div class="approval-meta">Amount: <strong style="color:var(--warn)">${escHtml(item.amount)}</strong></div>`:''}
        <div class="approval-meta" style="margin-top:4px">${escHtml(item.filename)}</div>
        <div class="approval-meta" style="font-size:10px">${timeAgo(item.requested_at)}</div>
      </div>
      <div class="approval-actions">
        <button class="btn btn-green btn-sm" onclick="doApprove('${escHtml(item.filename)}')">✅ Approve & Send</button>
        <button class="btn btn-red btn-sm" onclick="doReject('${escHtml(item.filename)}')">❌ Reject</button>
      </div>
    </div>
  `).join('');
}

async function doApprove(fn) {
  updateFlow(5);
  const r = await post('/api/approve', {filename: fn});
  if(r.status === 'approved') {
    if(r.action === 'email_send') {
      if(r.sent) {
        toast(`✅ Email sent to ${r.to}! Message ID: ${(r.message_id||'').substring(0,10)}...`);
      } else if(r.send_error) {
        toast(`⚠️ Approved but send failed: ${r.send_error}`, true);
      } else {
        toast('✅ Email approved!');
      }
    } else if(r.action === 'whatsapp_reply') {
      if(r.sent) {
        toast(`✅ WhatsApp reply sent to ${r.to}!`);
      } else if(r.send_error) {
        toast(`⚠️ Approved but WhatsApp send failed: ${r.send_error}`, true);
      } else {
        toast(`✅ WhatsApp reply approved!`);
      }
    } else {
      toast('✅ Approved and executed!');
    }
  } else {
    toast('❌ ' + (r.message||'Approval failed'), true);
  }
  setTimeout(() => { refreshApprovals(); refreshStatus(); updateFlow(0); }, 1000);
}

async function doReject(fn) {
  const r = await post('/api/reject', {filename: fn});
  toast(r.status === 'rejected' ? '🚫 Rejected.' : '❌ ' + r.message, r.status !== 'rejected');
  setTimeout(() => { refreshApprovals(); refreshStatus(); }, 800);
}

async function runFlowDemo() {
  toast('Running approval flow demo...');
  updateFlow(1); await sleep(600);
  updateFlow(2); await sleep(600);
  // Create a demo approval
  const now = new Date();
  const slug = 'demo_' + now.getTime();
  // We'll just show the animation
  updateFlow(3); await sleep(800);
  updateFlow(4);
  toast('⏳ Demo: Waiting for human approval...');
  await sleep(1000);
  updateFlow(5);
  toast('✅ Demo complete! In production, this executes the MCP action.');
  setTimeout(() => updateFlow(0), 2000);
}

const sleep = ms => new Promise(r => setTimeout(r, ms));

// ── Audit Log ───────────────────────────────────────────────────────────────
async function refreshLogs() {
  const logs = await get('/api/logs');
  const body = $('#log-body');
  if(!logs || !logs.length) {
    body.innerHTML = '';
    $('#log-empty').style.display = 'block';
    return;
  }
  $('#log-empty').style.display = 'none';
  body.innerHTML = logs.map(e => {
    const okColor = e.result==='success'||e.result==='ok' ? 'result-ok' : (e.result==='failure'?'result-err':'');
    return `<tr>
      <td>${fmt(e.timestamp)}</td>
      <td style="color:var(--li)">${e.action_type||''}</td>
      <td style="color:var(--muted)">${e.actor||''}</td>
      <td title="${e.target||''}">${(e.target||'').substring(0,40)}</td>
      <td class="${okColor}">${e.result||''}</td>
      <td style="color:var(--warn)">${e.approval_status||'-'}</td>
    </tr>`;
  }).join('');
}

// ── Helpers ────────────────────────────────────────────────────────────────
function escHtml(s) {
  return String(s||'').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}

// ── LinkedIn dry run badge ─────────────────────────────────────────────────
async function updateLinkedInBadge() {
  const d = await get('/api/status');
  const badge = $('#li-mode-badge');
  if(d.mode === 'LIVE') {
    badge.textContent = '⚡ LIVE — posts are real';
    badge.className = 'badge badge-done';
  } else if(d.mode === 'DRY_RUN') {
    badge.textContent = '🧪 DRY_RUN';
    badge.className = 'badge badge-pending';
  } else {
    badge.textContent = '🔒 DEV_MODE';
    badge.className = 'badge badge-low';
  }
}

// ── Init & polling ─────────────────────────────────────────────────────────
async function fullRefresh() {
  await refreshStatus();
  if(activeTab === 'email') await refreshEmails();
  else if(activeTab === 'wa') await refreshWA();
  else if(activeTab === 'li') await refreshLinkedIn();
  else if(activeTab === 'ap') await refreshApprovals();
  else if(activeTab === 'log') await refreshLogs();
}

fullRefresh();
updateLinkedInBadge();
setInterval(fullRefresh, 5000);
</script>
</body>
</html>
"""


def main() -> None:
    port = 8080
    server = HTTPServer(("0.0.0.0", port), Handler)
    mode = "DEV_MODE" if config.dev_mode else ("DRY_RUN" if config.dry_run else "LIVE")
    print(f"AI Employee Dashboard  →  http://localhost:{port}  [{mode}]")
    print(f"Vault: {vault}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        server.server_close()


if __name__ == "__main__":
    main()
