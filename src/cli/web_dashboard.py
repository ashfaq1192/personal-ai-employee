"""AI Employee — Live Operations Dashboard.

Start:  uv run python src/cli/web_dashboard.py
URL:    http://localhost:8080
"""

from __future__ import annotations

import json
import mimetypes
import os
import re
import subprocess
import urllib.parse
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, HTTPServer, ThreadingHTTPServer
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
    """Return current WhatsApp webhook status (Path B — no Playwright)."""
    needs_action = vault / "Needs_Action"
    wa_files = (
        [f.name for f in sorted(needs_action.iterdir(), key=lambda x: -x.stat().st_mtime)
         if f.is_file() and f.name.startswith("WHATSAPP_")]
        if needs_action.exists() else []
    )
    phone_id = config.whatsapp_phone_number_id
    audit.log("whatsapp_scan", "web_dashboard", "Needs_Action", parameters={"pending": len(wa_files)})
    return {
        "status": "ok",
        "mode": "business_api",
        "phone_number_id": phone_id,
        "webhook_port": 8081,
        "pending_messages": len(wa_files),
        "files": wa_files[:20],
        "note": "Inbound messages arrive via POST /whatsapp/webhook (port 8081)",
    }


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


def _parse_multipart(handler: BaseHTTPRequestHandler) -> dict[str, tuple[str | None, bytes]]:
    """Minimal multipart/form-data parser. Returns {name: (filename_or_None, bytes)}."""
    ct = handler.headers.get("Content-Type", "")
    boundary = ""
    for part in ct.split(";"):
        p = part.strip()
        if p.startswith("boundary="):
            boundary = p[9:].strip('"')
    if not boundary:
        return {}
    length = int(handler.headers.get("Content-Length", 0))
    raw = handler.rfile.read(length)
    delim = f"--{boundary}".encode()
    result: dict[str, tuple[str | None, bytes]] = {}
    for chunk in raw.split(delim):
        if b"\r\n\r\n" not in chunk:
            continue
        header_raw, body = chunk.split(b"\r\n\r\n", 1)
        if body.endswith(b"\r\n"):
            body = body[:-2]
        headers: dict[str, str] = {}
        for line in header_raw.strip().split(b"\r\n"):
            if b":" in line:
                k, _, v = line.partition(b":")
                headers[k.strip().lower().decode("latin-1")] = v.strip().decode("latin-1")
        cd = headers.get("content-disposition", "")
        name: str | None = None
        filename: str | None = None
        for seg in cd.split(";"):
            seg = seg.strip()
            if seg.startswith("name="):
                name = seg[5:].strip('"')
            elif seg.startswith("filename="):
                filename = seg[9:].strip('"')
        if name:
            result[name] = (filename, body)
    return result


def api_media_upload(handler: BaseHTTPRequestHandler) -> dict:
    """Accept a multipart file upload, save to vault/media/, return a /media/<name> URL."""
    content_type = handler.headers.get("Content-Type", "")
    if "multipart/form-data" not in content_type:
        return {"status": "error", "message": "Expected multipart/form-data"}
    media_dir = vault / "media"
    media_dir.mkdir(parents=True, exist_ok=True)
    try:
        parts = _parse_multipart(handler)
        if "file" not in parts:
            return {"status": "error", "message": "No 'file' field in request"}
        filename, data = parts["file"]
        if not filename:
            return {"status": "error", "message": "No filename provided"}
        orig_name = Path(filename).name
        suffix = Path(orig_name).suffix.lower()
        allowed = {".jpg", ".jpeg", ".png", ".gif", ".webp", ".mp4", ".mov"}
        if suffix not in allowed:
            return {"status": "error", "message": f"File type '{suffix}' not allowed. Use: jpg, png, gif, webp, mp4, mov"}
        now = datetime.now(timezone.utc)
        dest_name = f"upload_{now.strftime('%Y%m%d_%H%M%S')}{suffix}"
        dest = media_dir / dest_name
        dest.write_bytes(data)
        audit.log("media_upload", "web_dashboard", dest_name,
                  parameters={"original": orig_name, "size": dest.stat().st_size})
        return {"status": "ok", "url": f"/media/{dest_name}", "filename": dest_name, "original": orig_name}
    except Exception as e:
        return {"status": "error", "message": str(e)}


def api_linkedin_post(body: dict) -> dict:
    text = body.get("text", "").strip()
    image_url = body.get("image_url", "").strip()
    if not text:
        return {"status": "error", "message": "Post text is empty"}
    if config.dev_mode:
        audit.log("linkedin_post", "web_dashboard", "linkedin", parameters={"dev_mode": True})
        return {"status": "ok", "dry_run": True, "post_id": "dev-mock-id", "preview": text[:100]}
    try:
        token = os.environ.get("LINKEDIN_ACCESS_TOKEN", "")
        if not token:
            return {"status": "error", "message": "LINKEDIN_ACCESS_TOKEN missing in .env"}
        from src.mcp_servers.linkedin_client import LinkedInClient
        client = LinkedInClient(token, dry_run=config.dry_run)
        # Local uploaded file → read binary and upload via LinkedIn Assets API
        if image_url.startswith("/media/"):
            media_path = vault / "media" / image_url[7:]
            if not media_path.exists():
                return {"status": "error", "message": f"Uploaded file not found: {image_url}"}
            result = client.post(text, image_bytes=media_path.read_bytes(), image_filename=media_path.name)
        elif image_url:
            # Public URL — download then upload
            import httpx as _httpx
            img_resp = _httpx.get(image_url, timeout=30, follow_redirects=True)
            img_resp.raise_for_status()
            result = client.post(text, image_bytes=img_resp.content, image_filename=image_url.split("/")[-1].split("?")[0] or "image.jpg")
        else:
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


def api_facebook_post(body: dict) -> dict:
    text = body.get("text", "").strip()
    image_url = body.get("image_url", "").strip()
    if not text:
        return {"status": "error", "message": "Post text is empty"}
    if config.dev_mode:
        audit.log("facebook_post", "web_dashboard", "facebook", parameters={"dev_mode": True})
        return {"status": "ok", "dry_run": True, "post_id": "dev-mock-id", "preview": text[:100]}
    try:
        page_id = os.environ.get("FACEBOOK_PAGE_ID", "")
        token = os.environ.get("META_ACCESS_TOKEN", "")
        if not token or not page_id:
            return {"status": "error", "message": "META_ACCESS_TOKEN or FACEBOOK_PAGE_ID missing in .env"}
        from src.mcp_servers.facebook_client import FacebookClient
        client = FacebookClient(token, dry_run=config.dry_run)
        # Local uploaded file → send as binary (no public URL needed)
        if image_url.startswith("/media/"):
            media_path = vault / "media" / image_url[7:]
            if not media_path.exists():
                return {"status": "error", "message": f"Uploaded file not found: {image_url}"}
            result = client.post_to_page(
                page_id, text,
                image_bytes=media_path.read_bytes(),
                image_filename=media_path.name,
            )
        else:
            result = client.post_to_page(page_id, text, image_url=image_url or None)
        now = datetime.now(timezone.utc)
        fname = f"SOCIAL_{now.strftime('%Y-%m-%d_%H%M%S')}_facebook.md"
        content = (
            f"---\ntype: social_post\nplatform: facebook\n"
            f"status: {'dry_run' if config.dry_run else 'posted'}\n"
            f"post_id: {result.get('id', '')}\n"
            f"created: {now.isoformat()}\n---\n\n{text}\n"
        )
        (vault / "Plans" / fname).write_text(content, encoding="utf-8")
        audit.log("facebook_post", "web_dashboard", "facebook",
                  parameters={"dry_run": config.dry_run, "post_id": result.get("id", "")})
        return {"status": "ok", "dry_run": config.dry_run, "post_id": result.get("id", ""), "preview": text[:100]}
    except Exception as e:
        return {"status": "error", "message": str(e)}


def _compress_image(media_path: Path, max_kb: int = 200) -> bytes:
    """Return JPEG bytes, resizing/compressing to stay under max_kb."""
    from PIL import Image as _Image
    import io as _io
    img = _Image.open(media_path).convert("RGB")
    # Resize if wider/taller than 1080px (Instagram max)
    img.thumbnail((1080, 1080), _Image.LANCZOS)
    buf = _io.BytesIO()
    quality = 85
    while quality >= 40:
        buf.seek(0); buf.truncate()
        img.save(buf, format="JPEG", quality=quality, optimize=True)
        if buf.tell() <= max_kb * 1024:
            break
        quality -= 10
    return buf.getvalue()


def _upload_to_public_host(media_path: Path) -> str:
    """Compress then upload to a free public host; return the public URL."""
    import httpx as _httpx

    try:
        data = _compress_image(media_path)
    except Exception:
        data = media_path.read_bytes()

    filename = media_path.stem + "_compressed.jpg"

    # Primary: litterbox.catbox.moe (72h retention, no account needed)
    try:
        resp = _httpx.post(
            "https://litterbox.catbox.moe/resources/internals/api.php",
            data={"reqtype": "fileupload", "time": "72h"},
            files={"fileToUpload": (filename, data, "image/jpeg")},
            timeout=45,
        )
        resp.raise_for_status()
        url = resp.text.strip()
        if url.startswith("https://"):
            return url
    except Exception:
        pass

    # Fallback: tmpfiles.org
    resp = _httpx.post(
        "https://tmpfiles.org/api/v1/upload",
        files={"file": (filename, data, "image/jpeg")},
        timeout=45,
    )
    resp.raise_for_status()
    # tmpfiles returns {"status":"success","data":{"url":"https://tmpfiles.org/..."}}
    result = resp.json()
    url = result.get("data", {}).get("url", "")
    # Convert /dl/ URL so Meta can fetch the raw file
    return url.replace("tmpfiles.org/", "tmpfiles.org/dl/")


def api_instagram_post(body: dict) -> dict:
    text = body.get("text", "").strip()
    image_url = body.get("image_url", "").strip()
    if not text:
        return {"status": "error", "message": "Caption is empty"}
    if config.dev_mode:
        audit.log("instagram_post", "web_dashboard", "instagram", parameters={"dev_mode": True})
        return {"status": "ok", "dry_run": True, "media_id": "dev-mock-id", "preview": text[:100]}
    # Local upload — auto-publish to a free public host so Meta can fetch it
    if image_url.startswith("/media/") or image_url.startswith("http://localhost"):
        media_path = vault / "media" / image_url.split("/media/")[-1]
        if not media_path.exists():
            return {"status": "error", "message": f"Uploaded file not found: {image_url}"}
        try:
            image_url = _upload_to_public_host(media_path)
        except Exception as e:
            return {"status": "error", "message": f"Failed to upload image to public host: {e}"}
    if not image_url and not config.dry_run:
        return {"status": "error", "message": "Image URL is required for Instagram posts (API limitation)"}
    try:
        ig_user_id = os.environ.get("INSTAGRAM_USER_ID", "")
        fb_page_id = os.environ.get("FACEBOOK_PAGE_ID", "")
        token = os.environ.get("META_ACCESS_TOKEN", "")
        if not token or not ig_user_id or not fb_page_id:
            return {"status": "error", "message": "META_ACCESS_TOKEN, FACEBOOK_PAGE_ID, or INSTAGRAM_USER_ID missing in .env"}
        from src.mcp_servers.instagram_client import InstagramClient
        client = InstagramClient(token, fb_page_id, dry_run=config.dry_run)
        result = client.post(ig_user_id, image_url or "https://example.com/placeholder.jpg", text)
        now = datetime.now(timezone.utc)
        fname = f"SOCIAL_{now.strftime('%Y-%m-%d_%H%M%S')}_instagram.md"
        content = (
            f"---\ntype: social_post\nplatform: instagram\n"
            f"status: {'dry_run' if config.dry_run else 'posted'}\n"
            f"media_id: {result.get('media_id', result.get('id', ''))}\n"
            f"created: {now.isoformat()}\n---\n\n{text}\n"
        )
        (vault / "Plans" / fname).write_text(content, encoding="utf-8")
        audit.log("instagram_post", "web_dashboard", "instagram",
                  parameters={"dry_run": config.dry_run, "media_id": result.get("media_id", result.get("id", ""))})
        return {"status": "ok", "dry_run": config.dry_run, "media_id": result.get("media_id", result.get("id", "")), "preview": text[:100]}
    except Exception as e:
        return {"status": "error", "message": str(e)}


def api_twitter_post(body: dict) -> dict:
    text = body.get("text", "").strip()
    media_path = body.get("media_path")
    if not text:
        return {"status": "error", "message": "text required"}
    if config.dev_mode:
        audit.log("twitter_post", "web_dashboard", "twitter", parameters={"dev_mode": True})
        return {"status": "ok", "dry_run": True, "tweet_id": "dev-mock-id", "preview": text[:100]}
    try:
        api_key     = os.environ.get("TWITTER_API_KEY", "")
        api_secret  = os.environ.get("TWITTER_API_SECRET", "")
        access_token  = os.environ.get("TWITTER_ACCESS_TOKEN", "")
        access_secret = os.environ.get("TWITTER_ACCESS_TOKEN_SECRET", "")
        if not (api_key and api_secret and access_token and access_secret):
            return {"status": "error", "message": "Twitter credentials missing in .env (TWITTER_API_KEY, TWITTER_API_SECRET, TWITTER_ACCESS_TOKEN, TWITTER_ACCESS_TOKEN_SECRET)"}
        from src.mcp_servers.twitter_client import TwitterClient
        client = TwitterClient(api_key, api_secret, access_token, access_secret, dry_run=config.dry_run)
        result = client.post(text=text, media_path=media_path)
        now = datetime.now(timezone.utc)
        fname = f"SOCIAL_{now.strftime('%Y-%m-%d_%H%M%S')}_twitter.md"
        content = (
            f"---\ntype: social_post\nplatform: twitter\n"
            f"status: {'dry_run' if config.dry_run else 'posted'}\n"
            f"tweet_id: {result.get('id', '')}\n"
            f"created: {now.isoformat()}\n---\n\n{text}\n"
        )
        (vault / "Plans" / fname).write_text(content, encoding="utf-8")
        audit.log("twitter_post", "web_dashboard", "twitter",
                  parameters={"dry_run": config.dry_run, "tweet_id": result.get("id", "")},
                  result="success")
        return {"status": "ok", "dry_run": config.dry_run, "tweet_id": result.get("id", ""), "preview": text[:100]}
    except Exception as e:
        return {"status": "error", "message": str(e)}


def api_odoo_summary(_body: dict = {}) -> dict:
    """Fetch live financial summary from Odoo."""
    try:
        from src.mcp_servers.odoo_client import OdooClient
        client = OdooClient(
            os.environ.get("ODOO_URL", "http://localhost:8069"),
            os.environ.get("ODOO_DB", "odoo"),
            os.environ.get("ODOO_USERNAME", "admin"),
            os.environ.get("ODOO_PASSWORD", "admin"),
        )
        invoices = client.search_read(
            "account.move",
            [["move_type", "=", "out_invoice"]],
            ["name", "state", "amount_total", "invoice_date", "partner_id"],
            limit=10,
        )
        partners = client.search_read("res.partner", [["customer_rank", ">", 0]], ["name"], limit=500)
        total_invoiced = sum(inv.get("amount_total", 0) for inv in invoices if inv.get("state") == "posted")
        draft_count = sum(1 for inv in invoices if inv.get("state") == "draft")
        posted_count = sum(1 for inv in invoices if inv.get("state") == "posted")
        recent = [
            {
                "name": inv.get("name", ""),
                "state": inv.get("state", ""),
                "amount": inv.get("amount_total", 0),
                "date": inv.get("invoice_date", ""),
                "partner": inv.get("partner_id", [None, ""])[1] if inv.get("partner_id") else "",
            }
            for inv in invoices[:5]
        ]
        audit.log("odoo_summary", "web_dashboard", "odoo", parameters={"invoices": len(invoices)})
        return {
            "status": "ok",
            "connected": True,
            "url": os.environ.get("ODOO_URL", "http://localhost:8069"),
            "db": os.environ.get("ODOO_DB", "odoo"),
            "customers": len(partners),
            "invoices": {
                "total": len(invoices),
                "draft": draft_count,
                "posted": posted_count,
                "total_invoiced": total_invoiced,
                "recent": recent,
            },
        }
    except Exception as e:
        return {"status": "error", "connected": False, "message": str(e)[:200]}


def api_briefings() -> list:
    """List available CEO briefings, newest first."""
    folder = vault / "Briefings"
    if not folder.exists():
        return []
    items = []
    for f in sorted(folder.glob("*_Monday_Briefing.md"), reverse=True)[:10]:
        text = f.read_text(encoding="utf-8", errors="ignore")
        # Parse frontmatter
        fm: dict = {}
        m = re.match(r"^---\s*\n(.*?)\n---", text, re.DOTALL)
        if m:
            for line in m.group(1).splitlines():
                if ":" in line:
                    k, _, v = line.partition(":")
                    fm[k.strip()] = v.strip()
        # Extract executive summary line
        summary_m = re.search(r"## Executive Summary\s*\n(.+?)(?:\n|$)", text)
        summary = summary_m.group(1).strip() if summary_m else ""
        # Revenue line
        rev_m = re.search(r"\*\*This Week\*\*[:\s]*\$?([\d,\.]+)", text)
        week_revenue = rev_m.group(1) if rev_m else "—"
        items.append({
            "filename": f.name,
            "generated": fm.get("generated", ""),
            "period": fm.get("period", ""),
            "summary": summary,
            "week_revenue": week_revenue,
            "content": text[:3000],
        })
    return items


def api_generate_briefing(_body: dict = {}) -> dict:
    """Trigger CEO briefing generation immediately."""
    import subprocess as _sp
    try:
        date_arg = _body.get("date", "")
        cmd = ["uv", "run", "python", "scripts/generate_ceo_briefing.py"]
        if date_arg:
            cmd += ["--date", date_arg]
        r = _sp.run(cmd, capture_output=True, text=True, timeout=30,
                    cwd=str(Path(__file__).parent.parent.parent))
        if r.returncode == 0:
            audit.log("ceo_briefing", "web_dashboard", "Briefings", result="success")
            return {"status": "ok", "message": r.stdout.strip()}
        return {"status": "error", "message": r.stderr.strip()[:300]}
    except Exception as e:
        return {"status": "error", "message": str(e)[:200]}


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
    # Skip real dispatch in DEV_MODE / DRY_RUN
    if config.dev_mode or config.dry_run:
        result["dev_mode"] = True
        result["note"] = "DEV_MODE — action logged, no real send"
        return result
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
    "/api/gmail/pull":          api_gmail_pull,
    "/api/email/reply":         api_email_reply,
    "/api/email/done":          api_email_done,
    "/api/whatsapp/scan":       api_whatsapp_scan,
    "/api/whatsapp/reply":      api_whatsapp_reply,
    "/api/linkedin/post":       api_linkedin_post,
    "/api/facebook/post":       api_facebook_post,
    "/api/instagram/post":      api_instagram_post,
    "/api/twitter/post":        api_twitter_post,
    "/api/odoo/summary":        api_odoo_summary,
    "/api/briefing/generate":   api_generate_briefing,
    "/api/approve":             api_approve,
    "/api/reject":              api_reject,
    "/api/action/approve":      api_approve,
}


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *a: Any) -> None:
        pass

    def do_GET(self) -> None:
        path = urllib.parse.urlparse(self.path).path.rstrip("/") or "/"
        qs = dict(urllib.parse.parse_qsl(urllib.parse.urlparse(self.path).query))
        routes = {
            "/api/status":            lambda: api_status(),
            "/api/emails":            lambda: api_emails(),
            "/api/email-content":     lambda: api_email_content(qs.get("file", "")),
            "/api/whatsapp":          lambda: api_whatsapp(),
            "/api/whatsapp-content":  lambda: api_whatsapp_content(qs.get("file", "")),
            "/api/plans":             lambda: api_plans(),
            "/api/pending":           lambda: api_pending(),
            "/api/logs":              lambda: audit.get_recent(40),
            "/api/briefings":         lambda: api_briefings(),
            "/api/whatsapp/status":   lambda: api_whatsapp_scan(),
        }
        if path == "/":
            _html_file = Path(__file__).parent / "dashboard.html"
            b = _html_file.read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(b)))
            self.end_headers()
            self.wfile.write(b)
        elif path.startswith("/media/"):
            fname = path[7:]
            if not fname or "/" in fname or "\\" in fname or fname.startswith("."):
                self.send_error(403)
                return
            fpath = vault / "media" / fname
            if not fpath.exists() or not fpath.is_file():
                self.send_error(404)
                return
            mime = mimetypes.guess_type(str(fpath))[0] or "application/octet-stream"
            data = fpath.read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", mime)
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)
        elif path in routes:
            try:
                _json(self, routes[path]())
            except Exception as e:
                _json(self, {"error": str(e)}, 500)
        else:
            self.send_error(404)

    def do_POST(self) -> None:
        path = urllib.parse.urlparse(self.path).path.rstrip("/")
        # Multipart file upload — handle before JSON body read
        if path == "/api/media/upload":
            try:
                _json(self, api_media_upload(self))
            except Exception as e:
                _json(self, {"error": str(e)}, 500)
            return
        b = _body(self)
        fn = POST.get(path)
        if fn:
            try:
                _json(self, fn(b))
            except Exception as e:
                _json(self, {"error": str(e)}, 500)
        else:
            self.send_error(404)


def main() -> None:
    port = 8080
    server = ThreadingHTTPServer(("0.0.0.0", port), Handler)
    mode = "DEV_MODE" if config.dev_mode else ("DRY_RUN" if config.dry_run else "LIVE")
    print(f"AI Employee Dashboard  →  http://localhost:{port}  [{mode}]")
    print(f"Vault: {vault}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        server.server_close()


if __name__ == "__main__":
    main()
