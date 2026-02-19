"""Web-Based Testing Dashboard for AI Employee demo.

Zero new dependencies — uses Python's built-in http.server.
Start with:  uv run python src/cli/web_dashboard.py
Opens at:    http://localhost:8080
"""

from __future__ import annotations

import json
import subprocess
import urllib.parse
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from typing import Any

from src.core.config import Config
from src.core.logger import AuditLogger

config = Config()
vault = config.vault_path
audit = AuditLogger(vault)

VAULT_FOLDERS = [
    "Needs_Action", "Pending_Approval", "Approved", "Rejected",
    "In_Progress", "Done", "Logs", "Briefings", "Accounting",
]


def _count_files(directory: Path) -> int:
    if not directory.exists():
        return 0
    return sum(1 for f in directory.iterdir() if f.is_file())


def _json_response(handler: BaseHTTPRequestHandler, data: Any, status: int = 200) -> None:
    body = json.dumps(data, indent=2, ensure_ascii=False, default=str).encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json")
    handler.send_header("Content-Length", str(len(body)))
    handler.end_headers()
    handler.wfile.write(body)


def _read_body(handler: BaseHTTPRequestHandler) -> dict:
    length = int(handler.headers.get("Content-Length", 0))
    if length == 0:
        return {}
    raw = handler.rfile.read(length)
    return json.loads(raw)


# ---------------------------------------------------------------------------
# API handlers
# ---------------------------------------------------------------------------

def api_status() -> dict:
    mode = "DEV_MODE" if config.dev_mode else ("DRY_RUN" if config.dry_run else "PRODUCTION")
    folders = {}
    for name in VAULT_FOLDERS:
        folders[name] = _count_files(vault / name)

    # PM2 process check
    processes = {}
    for proc_name in ["orchestrator", "cloud-agent"]:
        try:
            result = subprocess.run(
                ["pm2", "jlist"], capture_output=True, text=True, timeout=5
            )
            if result.returncode == 0:
                plist = json.loads(result.stdout)
                status = "not found"
                for p in plist:
                    if p.get("name") == proc_name:
                        status = p.get("pm2_env", {}).get("status", "unknown")
                processes[proc_name] = status
            else:
                processes[proc_name] = "pm2 unavailable"
        except (FileNotFoundError, json.JSONDecodeError, subprocess.TimeoutExpired):
            processes[proc_name] = "pm2 unavailable"

    return {
        "mode": mode,
        "vault_path": str(vault),
        "vault_exists": vault.exists(),
        "folders": folders,
        "processes": processes,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


def api_logs() -> list[dict]:
    return audit.get_recent(50)


def api_vault_folder(folder: str) -> dict:
    folder_path = vault / folder
    if not folder_path.exists():
        return {"folder": folder, "exists": False, "files": []}
    files = []
    for f in sorted(folder_path.iterdir()):
        if f.is_file():
            files.append({
                "name": f.name,
                "size": f.stat().st_size,
                "modified": datetime.fromtimestamp(f.stat().st_mtime, tz=timezone.utc).isoformat(),
            })
    return {"folder": folder, "exists": True, "files": files}


def api_file_content(rel_path: str) -> dict:
    # Security: only serve files under the vault
    target = (vault / rel_path).resolve()
    if not str(target).startswith(str(vault.resolve())):
        return {"error": "Access denied", "content": ""}
    if not target.exists():
        return {"error": "File not found", "content": ""}
    try:
        content = target.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        content = "(binary file)"
    return {"path": str(target), "content": content}


def api_create_email(body: dict) -> dict:
    subject = body.get("subject", "New email task")
    sender = body.get("sender", "demo@example.com")
    now = datetime.now(timezone.utc)
    slug = subject.lower().replace(" ", "_")[:30]
    filename = f"EMAIL_{now.strftime('%Y%m%d_%H%M%S')}_{slug}.md"
    content = (
        f"---\n"
        f"type: email_action\n"
        f"from: {sender}\n"
        f"subject: \"{subject}\"\n"
        f"received: {now.isoformat()}\n"
        f"priority: normal\n"
        f"---\n\n"
        f"# Email: {subject}\n\n"
        f"From: {sender}\n\n"
        f"{body.get('body', 'Sample email body for demo.')}\n"
    )
    dest = vault / "Needs_Action" / filename
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(content, encoding="utf-8")
    audit.log("create_email_action", "web_dashboard", str(dest), parameters={"subject": subject})
    return {"created": str(dest), "filename": filename}


def api_create_approval(body: dict) -> dict:
    title = body.get("title", "Payment approval request")
    amount = body.get("amount", "$500.00")
    now = datetime.now(timezone.utc)
    slug = title.lower().replace(" ", "_")[:30]
    filename = f"APPROVAL_{now.strftime('%Y%m%d_%H%M%S')}_{slug}.md"
    content = (
        f"---\n"
        f"type: approval_request\n"
        f"requested_by: orchestrator\n"
        f"requested_at: {now.isoformat()}\n"
        f"action: {body.get('action', 'payment')}\n"
        f"amount: \"{amount}\"\n"
        f"---\n\n"
        f"# Approval Request: {title}\n\n"
        f"**Amount:** {amount}\n\n"
        f"**Details:** {body.get('details', 'Requires human approval before proceeding.')}\n"
    )
    dest = vault / "Pending_Approval" / filename
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(content, encoding="utf-8")
    audit.log("create_approval", "web_dashboard", str(dest), parameters={"title": title}, approval_status="pending")
    return {"created": str(dest), "filename": filename}


def api_approve(body: dict) -> dict:
    filename = body.get("filename", "")
    if not filename:
        return {"error": "No filename provided"}
    source = vault / "Pending_Approval" / filename
    if not source.exists():
        return {"error": f"File not found: {filename}"}
    dest = vault / "Approved" / filename
    dest.parent.mkdir(parents=True, exist_ok=True)
    source.rename(dest)
    audit.log("approve_request", "web_dashboard", str(dest), approval_status="approved", approved_by="human_via_dashboard")
    return {"moved": str(dest), "status": "approved"}


def api_generate_sample(body: dict) -> dict:
    from tests.fixtures.generate_sample_week import generate_sample_week
    generate_sample_week(vault)
    audit.log("generate_sample_data", "web_dashboard", str(vault))
    return {"status": "ok", "message": "Sample week data generated"}


def api_update_dashboard(body: dict) -> dict:
    from src.orchestrator.dashboard_updater import update_dashboard
    # Ensure Dashboard.md exists
    dash = vault / "Dashboard.md"
    if not dash.exists():
        dash.write_text("# Dashboard\n", encoding="utf-8")
    update_dashboard(vault)
    audit.log("update_dashboard", "web_dashboard", str(dash))
    return {"status": "ok", "message": "Dashboard.md updated"}


def api_post_social(body: dict) -> dict:
    platform = body.get("platform", "linkedin")
    text = body.get("text", "Hello from AI Employee!")
    # Always dry-run from the dashboard
    audit.log(
        "social_post_dry_run", "web_dashboard", platform,
        parameters={"text": text[:100], "dry_run": True},
    )
    return {
        "status": "dry_run",
        "platform": platform,
        "text": text,
        "message": f"[DRY RUN] Would post to {platform}: {text[:80]}...",
    }


def api_metrics(body: dict) -> dict:
    from src.mcp_servers.social_metrics import generate_metrics_summary
    path = generate_metrics_summary(vault, days=body.get("days", 7))
    audit.log("generate_metrics", "web_dashboard", path)
    # Read and return the generated file content
    content = Path(path).read_text(encoding="utf-8")
    return {"status": "ok", "path": path, "content": content}


# ---------------------------------------------------------------------------
# HTTP handler
# ---------------------------------------------------------------------------

class DashboardHandler(BaseHTTPRequestHandler):
    def log_message(self, format: str, *args: Any) -> None:
        # Quieter logging
        pass

    def do_GET(self) -> None:
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path.rstrip("/") or "/"
        qs = dict(urllib.parse.parse_qsl(parsed.query))

        if path == "/":
            self._serve_html()
        elif path == "/api/status":
            _json_response(self, api_status())
        elif path == "/api/logs":
            _json_response(self, api_logs())
        elif path.startswith("/api/vault/"):
            folder = path.split("/api/vault/", 1)[1]
            _json_response(self, api_vault_folder(folder))
        elif path == "/api/file":
            _json_response(self, api_file_content(qs.get("path", "")))
        else:
            self.send_error(404)

    def do_POST(self) -> None:
        path = urllib.parse.urlparse(self.path).path.rstrip("/")
        body = _read_body(self)

        routes: dict[str, Any] = {
            "/api/action/create-email": api_create_email,
            "/api/action/create-approval": api_create_approval,
            "/api/action/approve": api_approve,
            "/api/action/generate-sample": api_generate_sample,
            "/api/action/update-dashboard": api_update_dashboard,
            "/api/mcp/post-social": api_post_social,
            "/api/mcp/metrics": api_metrics,
        }

        handler_fn = routes.get(path)
        if handler_fn:
            try:
                result = handler_fn(body)
                _json_response(self, result)
            except Exception as exc:
                _json_response(self, {"error": str(exc)}, 500)
        else:
            self.send_error(404)

    def _serve_html(self) -> None:
        body = DASHBOARD_HTML.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


# ---------------------------------------------------------------------------
# Embedded HTML/CSS/JS
# ---------------------------------------------------------------------------

DASHBOARD_HTML = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>AI Employee — Testing Dashboard</title>
<style>
:root {
  --bg: #0d1117; --bg2: #161b22; --bg3: #21262d;
  --border: #30363d; --text: #c9d1d9; --text2: #8b949e;
  --accent: #58a6ff; --green: #3fb950; --yellow: #d29922;
  --red: #f85149; --purple: #bc8cff;
}
* { box-sizing: border-box; margin: 0; padding: 0; }
body {
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Helvetica, Arial, sans-serif;
  background: var(--bg); color: var(--text); display: flex; height: 100vh;
}
/* Sidebar */
.sidebar {
  width: 220px; background: var(--bg2); border-right: 1px solid var(--border);
  display: flex; flex-direction: column; flex-shrink: 0;
}
.sidebar h1 {
  font-size: 14px; padding: 16px; border-bottom: 1px solid var(--border);
  color: var(--accent); letter-spacing: 0.5px;
}
.sidebar nav a {
  display: block; padding: 10px 16px; color: var(--text2); text-decoration: none;
  font-size: 13px; border-left: 3px solid transparent; transition: all 0.15s;
}
.sidebar nav a:hover, .sidebar nav a.active {
  background: var(--bg3); color: var(--text); border-left-color: var(--accent);
}
.sidebar .mode-badge {
  margin: auto 16px 16px; padding: 6px 10px; border-radius: 6px;
  font-size: 11px; text-align: center; font-weight: 600;
}
.mode-dev { background: rgba(210,153,34,0.15); color: var(--yellow); border: 1px solid var(--yellow); }
.mode-dry { background: rgba(88,166,255,0.15); color: var(--accent); border: 1px solid var(--accent); }
.mode-prod { background: rgba(248,81,73,0.15); color: var(--red); border: 1px solid var(--red); }

/* Main */
.main { flex: 1; overflow-y: auto; padding: 24px; }
.section { display: none; }
.section.active { display: block; }
.section h2 { font-size: 20px; margin-bottom: 16px; color: var(--text); }
.card {
  background: var(--bg2); border: 1px solid var(--border); border-radius: 8px;
  padding: 16px; margin-bottom: 16px;
}
.card h3 { font-size: 14px; color: var(--accent); margin-bottom: 10px; }
.grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(200px, 1fr)); gap: 12px; }
.stat {
  background: var(--bg3); border-radius: 6px; padding: 12px; text-align: center;
}
.stat .value { font-size: 24px; font-weight: 700; color: var(--accent); }
.stat .label { font-size: 11px; color: var(--text2); margin-top: 4px; }

/* Tables */
table { width: 100%; border-collapse: collapse; font-size: 13px; }
th { text-align: left; padding: 8px 10px; border-bottom: 2px solid var(--border); color: var(--text2); font-weight: 600; }
td { padding: 8px 10px; border-bottom: 1px solid var(--border); }
tr:hover td { background: var(--bg3); }

/* Forms */
.form-group { margin-bottom: 12px; }
.form-group label { display: block; font-size: 12px; color: var(--text2); margin-bottom: 4px; }
.form-group input, .form-group textarea, .form-group select {
  width: 100%; padding: 8px 10px; background: var(--bg); border: 1px solid var(--border);
  border-radius: 6px; color: var(--text); font-size: 13px; font-family: inherit;
}
.form-group textarea { min-height: 80px; resize: vertical; }
.btn {
  padding: 8px 16px; border: none; border-radius: 6px; font-size: 13px;
  cursor: pointer; font-weight: 600; transition: opacity 0.15s;
}
.btn:hover { opacity: 0.85; }
.btn-primary { background: var(--accent); color: #fff; }
.btn-green { background: var(--green); color: #fff; }
.btn-yellow { background: var(--yellow); color: #000; }
.btn-purple { background: var(--purple); color: #fff; }
.btn-red { background: var(--red); color: #fff; }
.btn + .btn { margin-left: 8px; }

/* Toast */
.toast {
  position: fixed; bottom: 20px; right: 20px; background: var(--bg2);
  border: 1px solid var(--green); color: var(--green); padding: 12px 20px;
  border-radius: 8px; font-size: 13px; z-index: 999; opacity: 0;
  transition: opacity 0.3s; pointer-events: none;
}
.toast.show { opacity: 1; }
.toast.error { border-color: var(--red); color: var(--red); }

/* File viewer */
.file-viewer {
  background: var(--bg); border: 1px solid var(--border); border-radius: 6px;
  padding: 16px; font-family: 'SFMono-Regular', Consolas, monospace;
  font-size: 12px; white-space: pre-wrap; max-height: 400px; overflow-y: auto;
  line-height: 1.5; margin-top: 12px;
}

/* Status dot */
.dot { display: inline-block; width: 8px; height: 8px; border-radius: 50%; margin-right: 6px; }
.dot-green { background: var(--green); }
.dot-yellow { background: var(--yellow); }
.dot-red { background: var(--red); }

/* Approval flow */
.flow-steps { display: flex; gap: 12px; margin: 16px 0; flex-wrap: wrap; }
.flow-step {
  flex: 1; min-width: 150px; background: var(--bg3); border-radius: 8px; padding: 16px;
  text-align: center; border: 2px solid var(--border); transition: border-color 0.3s;
}
.flow-step.done { border-color: var(--green); }
.flow-step.active { border-color: var(--accent); }
.flow-step .step-num { font-size: 24px; font-weight: 700; color: var(--text2); }
.flow-step.done .step-num { color: var(--green); }
.flow-step.active .step-num { color: var(--accent); }
.flow-step .step-label { font-size: 12px; color: var(--text2); margin-top: 4px; }

/* Responsive */
@media (max-width: 768px) {
  body { flex-direction: column; }
  .sidebar { width: 100%; flex-direction: row; overflow-x: auto; }
  .sidebar h1 { display: none; }
  .sidebar nav { display: flex; }
  .sidebar nav a { white-space: nowrap; }
  .sidebar .mode-badge { display: none; }
}
</style>
</head>
<body>

<div class="sidebar">
  <h1>AI EMPLOYEE</h1>
  <nav>
    <a href="#" data-section="status" class="active">System Status</a>
    <a href="#" data-section="vault">Vault Browser</a>
    <a href="#" data-section="actions">Action Simulator</a>
    <a href="#" data-section="mcp">MCP Test Panel</a>
    <a href="#" data-section="logs">Audit Log Viewer</a>
    <a href="#" data-section="flow">Approval Flow Demo</a>
  </nav>
  <div class="mode-badge" id="modeBadge">Loading...</div>
</div>

<div class="main">
  <!-- STATUS -->
  <div class="section active" id="sec-status">
    <h2>System Status</h2>
    <div class="card">
      <h3>Configuration</h3>
      <div id="statusConfig"></div>
    </div>
    <div class="card">
      <h3>Vault Folders</h3>
      <div class="grid" id="statusFolders"></div>
    </div>
    <div class="card">
      <h3>Processes</h3>
      <div id="statusProcesses"></div>
    </div>
  </div>

  <!-- VAULT BROWSER -->
  <div class="section" id="sec-vault">
    <h2>Vault Browser</h2>
    <div class="card">
      <h3>Select Folder</h3>
      <div class="grid" id="vaultFolderGrid"></div>
    </div>
    <div class="card" id="vaultFileList" style="display:none">
      <h3 id="vaultFolderTitle">Files</h3>
      <table>
        <thead><tr><th>Name</th><th>Size</th><th>Modified</th><th></th></tr></thead>
        <tbody id="vaultFileBody"></tbody>
      </table>
    </div>
    <div id="vaultFileViewer" style="display:none">
      <div class="card">
        <h3 id="viewerFileName">File</h3>
        <div class="file-viewer" id="viewerContent"></div>
      </div>
    </div>
  </div>

  <!-- ACTION SIMULATOR -->
  <div class="section" id="sec-actions">
    <h2>Action Simulator</h2>
    <div style="display:grid; grid-template-columns: 1fr 1fr; gap: 16px;">
      <div class="card">
        <h3>Create Email Action Item</h3>
        <div class="form-group"><label>Subject</label><input id="emailSubject" value="Invoice from Acme Corp"></div>
        <div class="form-group"><label>Sender</label><input id="emailSender" value="billing@acmecorp.com"></div>
        <div class="form-group"><label>Body</label><textarea id="emailBody">Please review and process the attached invoice #1234 for $2,500.</textarea></div>
        <button class="btn btn-primary" onclick="createEmail()">Create in /Needs_Action/</button>
      </div>
      <div class="card">
        <h3>Create Approval Request</h3>
        <div class="form-group"><label>Title</label><input id="approvalTitle" value="Payment to vendor XYZ"></div>
        <div class="form-group"><label>Amount</label><input id="approvalAmount" value="$2,500.00"></div>
        <div class="form-group"><label>Details</label><textarea id="approvalDetails">Vendor invoice for consulting services. Requires CEO approval before processing.</textarea></div>
        <button class="btn btn-yellow" onclick="createApproval()">Create in /Pending_Approval/</button>
      </div>
    </div>
    <div style="display:grid; grid-template-columns: 1fr 1fr 1fr; gap: 16px; margin-top: 0;">
      <div class="card">
        <h3>Approve Pending Item</h3>
        <div class="form-group"><label>Select file to approve</label>
          <select id="approveSelect"><option value="">Loading...</option></select>
        </div>
        <button class="btn btn-green" onclick="approveItem()">Approve (move to /Approved/)</button>
      </div>
      <div class="card">
        <h3>Generate Sample Data</h3>
        <p style="font-size:13px;color:var(--text2);margin-bottom:12px;">Creates a week of sample emails, invoices, accounting entries, and social metrics.</p>
        <button class="btn btn-purple" onclick="generateSample()">Generate Sample Week</button>
      </div>
      <div class="card">
        <h3>Update Dashboard.md</h3>
        <p style="font-size:13px;color:var(--text2);margin-bottom:12px;">Refresh the vault's Dashboard.md with current folder counts and activity.</p>
        <button class="btn btn-primary" onclick="updateDashboard()">Force Dashboard Update</button>
      </div>
    </div>
  </div>

  <!-- MCP TEST PANEL -->
  <div class="section" id="sec-mcp">
    <h2>MCP Test Panel</h2>
    <div style="display:grid; grid-template-columns: 1fr 1fr; gap: 16px;">
      <div class="card">
        <h3>Social Post (Dry Run)</h3>
        <div class="form-group"><label>Platform</label>
          <select id="socialPlatform">
            <option value="linkedin">LinkedIn</option>
            <option value="twitter">Twitter/X</option>
            <option value="facebook">Facebook</option>
            <option value="instagram">Instagram</option>
          </select>
        </div>
        <div class="form-group"><label>Post Text</label>
          <textarea id="socialText">Excited to announce our new AI-powered workflow automation! #AI #Productivity</textarea>
        </div>
        <button class="btn btn-primary" onclick="postSocial()">Post (Dry Run)</button>
        <div id="socialResult" class="file-viewer" style="display:none;margin-top:12px;max-height:150px;"></div>
      </div>
      <div class="card">
        <h3>Generate Metrics Summary</h3>
        <div class="form-group"><label>Period (days)</label><input id="metricsDays" type="number" value="7"></div>
        <button class="btn btn-purple" onclick="generateMetrics()">Generate Metrics</button>
        <div id="metricsResult" class="file-viewer" style="display:none;margin-top:12px;max-height:300px;"></div>
      </div>
    </div>
  </div>

  <!-- AUDIT LOG VIEWER -->
  <div class="section" id="sec-logs">
    <h2>Audit Log Viewer <span style="font-size:12px;color:var(--text2);">(auto-refreshes every 5s)</span></h2>
    <div class="card">
      <table>
        <thead><tr><th>Timestamp</th><th>Action</th><th>Actor</th><th>Target</th><th>Result</th><th>Approval</th></tr></thead>
        <tbody id="logBody"></tbody>
      </table>
      <p id="logEmpty" style="color:var(--text2);padding:12px;display:none;">No log entries yet. Use the Action Simulator to create some!</p>
    </div>
  </div>

  <!-- APPROVAL FLOW DEMO -->
  <div class="section" id="sec-flow">
    <h2>Approval Flow Demo</h2>
    <p style="color:var(--text2);margin-bottom:16px;">Step-by-step walkthrough of the Human-in-the-Loop approval flow.</p>
    <div class="flow-steps" id="flowSteps">
      <div class="flow-step" id="fs1"><div class="step-num">1</div><div class="step-label">Create Action Item</div></div>
      <div class="flow-step" id="fs2"><div class="step-num">2</div><div class="step-label">Orchestrator Routes</div></div>
      <div class="flow-step" id="fs3"><div class="step-num">3</div><div class="step-label">Pending Approval</div></div>
      <div class="flow-step" id="fs4"><div class="step-num">4</div><div class="step-label">Human Approves</div></div>
      <div class="flow-step" id="fs5"><div class="step-num">5</div><div class="step-label">Action Executed</div></div>
    </div>
    <div class="card">
      <h3>Run Full Demo Flow</h3>
      <div id="flowLog" class="file-viewer" style="min-height:120px;">Click "Start Demo" to begin the approval flow walkthrough.</div>
      <div style="margin-top:12px;">
        <button class="btn btn-green" onclick="runFlowDemo()">Start Demo</button>
        <button class="btn btn-yellow" onclick="resetFlowDemo()">Reset</button>
      </div>
    </div>
  </div>
</div>

<div class="toast" id="toast"></div>

<script>
const $ = s => document.querySelector(s);
const $$ = s => document.querySelectorAll(s);

// Navigation
$$('.sidebar nav a').forEach(a => {
  a.addEventListener('click', e => {
    e.preventDefault();
    $$('.sidebar nav a').forEach(x => x.classList.remove('active'));
    a.classList.add('active');
    $$('.section').forEach(s => s.classList.remove('active'));
    $(`#sec-${a.dataset.section}`).classList.add('active');
    if (a.dataset.section === 'logs') refreshLogs();
    if (a.dataset.section === 'actions') loadPendingFiles();
    if (a.dataset.section === 'vault') initVaultBrowser();
  });
});

// Toast
function toast(msg, isError) {
  const t = $('#toast');
  t.textContent = msg;
  t.classList.toggle('error', !!isError);
  t.classList.add('show');
  setTimeout(() => t.classList.remove('show'), 3000);
}

// API helpers
async function api(url, opts) {
  const res = await fetch(url, opts);
  return res.json();
}
async function post(url, body) {
  return api(url, { method: 'POST', headers: {'Content-Type':'application/json'}, body: JSON.stringify(body) });
}

// ---- STATUS ----
async function refreshStatus() {
  const d = await api('/api/status');
  // Mode badge
  const badge = $('#modeBadge');
  badge.textContent = d.mode;
  badge.className = 'mode-badge ' + (d.mode === 'DEV_MODE' ? 'mode-dev' : d.mode === 'DRY_RUN' ? 'mode-dry' : 'mode-prod');

  // Config
  $('#statusConfig').innerHTML = `
    <table>
      <tr><td><span class="dot ${d.vault_exists ? 'dot-green' : 'dot-red'}"></span>Vault Path</td><td>${d.vault_path}</td></tr>
      <tr><td><span class="dot dot-green"></span>Mode</td><td>${d.mode}</td></tr>
      <tr><td><span class="dot dot-green"></span>Last Check</td><td>${new Date(d.timestamp).toLocaleString()}</td></tr>
    </table>`;

  // Folders
  let fhtml = '';
  for (const [name, count] of Object.entries(d.folders)) {
    const color = count > 0 ? (name === 'Needs_Action' || name === 'Pending_Approval' ? 'var(--yellow)' : 'var(--green)') : 'var(--text2)';
    fhtml += `<div class="stat"><div class="value" style="color:${color}">${count}</div><div class="label">${name}</div></div>`;
  }
  $('#statusFolders').innerHTML = fhtml;

  // Processes
  let phtml = '<table>';
  for (const [name, status] of Object.entries(d.processes)) {
    const dotClass = status === 'online' ? 'dot-green' : status === 'not found' ? 'dot-yellow' : 'dot-red';
    phtml += `<tr><td><span class="dot ${dotClass}"></span>${name}</td><td>${status}</td></tr>`;
  }
  phtml += '</table>';
  $('#statusProcesses').innerHTML = phtml;
}

// ---- VAULT BROWSER ----
const FOLDERS = ['Needs_Action','Pending_Approval','Approved','Rejected','In_Progress','Done','Logs','Briefings','Accounting'];
function initVaultBrowser() {
  let html = '';
  FOLDERS.forEach(f => {
    html += `<div class="stat" style="cursor:pointer" onclick="loadFolder('${f}')"><div class="value" style="font-size:16px">${f}</div></div>`;
  });
  $('#vaultFolderGrid').innerHTML = html;
  $('#vaultFileList').style.display = 'none';
  $('#vaultFileViewer').style.display = 'none';
}
async function loadFolder(name) {
  const d = await api(`/api/vault/${name}`);
  $('#vaultFolderTitle').textContent = `/${name}/ (${d.files.length} files)`;
  let rows = '';
  if (d.files.length === 0) {
    rows = '<tr><td colspan="4" style="color:var(--text2)">No files</td></tr>';
  }
  d.files.forEach(f => {
    const sz = f.size < 1024 ? f.size + ' B' : (f.size / 1024).toFixed(1) + ' KB';
    const mod = new Date(f.modified).toLocaleString();
    rows += `<tr><td>${f.name}</td><td>${sz}</td><td>${mod}</td><td><a href="#" onclick="viewFile('${name}/${f.name}');return false" style="color:var(--accent)">View</a></td></tr>`;
  });
  $('#vaultFileBody').innerHTML = rows;
  $('#vaultFileList').style.display = 'block';
  $('#vaultFileViewer').style.display = 'none';
}
async function viewFile(relPath) {
  const d = await api(`/api/file?path=${encodeURIComponent(relPath)}`);
  if (d.error) { toast(d.error, true); return; }
  $('#viewerFileName').textContent = relPath;
  $('#viewerContent').textContent = d.content;
  $('#vaultFileViewer').style.display = 'block';
}

// ---- ACTIONS ----
async function createEmail() {
  const r = await post('/api/action/create-email', {
    subject: $('#emailSubject').value,
    sender: $('#emailSender').value,
    body: $('#emailBody').value,
  });
  toast(r.error ? r.error : `Created: ${r.filename}`);
  refreshStatus();
}
async function createApproval() {
  const r = await post('/api/action/create-approval', {
    title: $('#approvalTitle').value,
    amount: $('#approvalAmount').value,
    details: $('#approvalDetails').value,
  });
  toast(r.error ? r.error : `Created: ${r.filename}`);
  refreshStatus(); loadPendingFiles();
}
async function loadPendingFiles() {
  const d = await api('/api/vault/Pending_Approval');
  const sel = $('#approveSelect');
  sel.innerHTML = '';
  if (!d.files || d.files.length === 0) {
    sel.innerHTML = '<option value="">No pending items</option>';
  } else {
    d.files.forEach(f => {
      sel.innerHTML += `<option value="${f.name}">${f.name}</option>`;
    });
  }
}
async function approveItem() {
  const filename = $('#approveSelect').value;
  if (!filename) { toast('No file selected', true); return; }
  const r = await post('/api/action/approve', { filename });
  toast(r.error ? r.error : `Approved: ${filename}`);
  refreshStatus(); loadPendingFiles();
}
async function generateSample() {
  toast('Generating sample data...');
  const r = await post('/api/action/generate-sample', {});
  toast(r.error ? r.error : r.message);
  refreshStatus();
}
async function updateDashboard() {
  const r = await post('/api/action/update-dashboard', {});
  toast(r.error ? r.error : r.message);
  refreshStatus();
}

// ---- MCP ----
async function postSocial() {
  const r = await post('/api/mcp/post-social', {
    platform: $('#socialPlatform').value,
    text: $('#socialText').value,
  });
  $('#socialResult').style.display = 'block';
  $('#socialResult').textContent = JSON.stringify(r, null, 2);
  toast(r.message || 'Done');
}
async function generateMetrics() {
  const r = await post('/api/mcp/metrics', { days: parseInt($('#metricsDays').value) || 7 });
  $('#metricsResult').style.display = 'block';
  $('#metricsResult').textContent = r.content || JSON.stringify(r, null, 2);
  toast('Metrics generated');
}

// ---- LOGS ----
async function refreshLogs() {
  const logs = await api('/api/logs');
  const body = $('#logBody');
  if (!logs || logs.length === 0) {
    body.innerHTML = '';
    $('#logEmpty').style.display = 'block';
    return;
  }
  $('#logEmpty').style.display = 'none';
  let html = '';
  logs.forEach(e => {
    const resultColor = e.result === 'success' ? 'var(--green)' : e.result === 'failure' ? 'var(--red)' : 'var(--text2)';
    const ts = (e.timestamp || '').replace('T', ' ').substring(0, 19);
    const target = (e.target || '').length > 50 ? e.target.substring(0, 50) + '...' : (e.target || '');
    html += `<tr>
      <td style="white-space:nowrap">${ts}</td>
      <td>${e.action_type || ''}</td>
      <td>${e.actor || ''}</td>
      <td title="${e.target || ''}">${target}</td>
      <td style="color:${resultColor}">${e.result || ''}</td>
      <td>${e.approval_status || '-'}</td>
    </tr>`;
  });
  body.innerHTML = html;
}

// ---- APPROVAL FLOW DEMO ----
let flowStep = 0;
let flowFile = '';

function updateFlowSteps() {
  for (let i = 1; i <= 5; i++) {
    const el = $(`#fs${i}`);
    el.classList.remove('done', 'active');
    if (i < flowStep) el.classList.add('done');
    if (i === flowStep) el.classList.add('active');
  }
}

async function runFlowDemo() {
  const log = $('#flowLog');
  flowStep = 1; updateFlowSteps();
  log.textContent = '[Step 1] Creating email action item in /Needs_Action/...\n';

  const emailResult = await post('/api/action/create-email', {
    subject: 'Demo: Vendor payment request',
    sender: 'vendor@demo.com',
    body: 'Please process payment of $1,500 for services rendered.',
  });
  log.textContent += `  Created: ${emailResult.filename}\n\n`;

  flowStep = 2; updateFlowSteps();
  log.textContent += '[Step 2] Orchestrator routes item to /Pending_Approval/...\n';
  const approvalResult = await post('/api/action/create-approval', {
    title: 'Demo: Vendor payment $1,500',
    amount: '$1,500.00',
    details: 'Payment to vendor@demo.com for services rendered. Requires approval.',
  });
  flowFile = approvalResult.filename;
  log.textContent += `  Created approval: ${flowFile}\n\n`;

  flowStep = 3; updateFlowSteps();
  log.textContent += '[Step 3] Item is now in /Pending_Approval/ — waiting for human...\n';
  log.textContent += '  (In production, this appears in Obsidian for the CEO to review)\n\n';

  await new Promise(r => setTimeout(r, 1500));

  flowStep = 4; updateFlowSteps();
  log.textContent += '[Step 4] Human approves — moving to /Approved/...\n';
  const approveResult = await post('/api/action/approve', { filename: flowFile });
  if (approveResult.error) {
    log.textContent += `  Error: ${approveResult.error}\n`;
    return;
  }
  log.textContent += `  Moved to: /Approved/${flowFile}\n\n`;

  await new Promise(r => setTimeout(r, 1000));

  flowStep = 5; updateFlowSteps();
  log.textContent += '[Step 5] Action executed! Item processed and logged.\n';
  log.textContent += '  Audit log entry created.\n';
  log.textContent += '\nDemo complete! Check the Audit Log Viewer for entries.\n';

  refreshStatus();
  toast('Approval flow demo complete!');
}

function resetFlowDemo() {
  flowStep = 0; updateFlowSteps();
  $('#flowLog').textContent = 'Click "Start Demo" to begin the approval flow walkthrough.';
}

// ---- AUTO REFRESH ----
refreshStatus();
setInterval(() => {
  refreshStatus();
  if ($('#sec-logs').classList.contains('active')) refreshLogs();
}, 5000);

initVaultBrowser();
</script>
</body>
</html>
"""


def main() -> None:
    port = 8080
    server = HTTPServer(("0.0.0.0", port), DashboardHandler)
    print(f"AI Employee Testing Dashboard")
    print(f"  URL:  http://localhost:{port}")
    print(f"  Mode: {'DEV_MODE' if config.dev_mode else ('DRY_RUN' if config.dry_run else 'PRODUCTION')}")
    print(f"  Vault: {vault}")
    print(f"\nPress Ctrl+C to stop.\n")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down.")
        server.server_close()


if __name__ == "__main__":
    main()
