"""Quick test: reconnect to WhatsApp Web using saved session."""
import os, sys, time
os.environ['DEV_MODE'] = 'false'
os.environ['DRY_RUN'] = 'true'
sys.path.insert(0, '.')

from src.core.config import Config
from src.watchers.whatsapp_watcher import WhatsAppWatcher

cfg = Config()
print(f"Session path : {cfg.whatsapp_session_path}")
print(f"Session exists: {cfg.whatsapp_session_path.exists()}")
print()

w = WhatsAppWatcher(cfg)
print("Connecting to WhatsApp Web (no QR needed)...")
page = w._ensure_browser()

if page:
    print("Connected successfully!")
    print("Checking for keyword messages...")
    items = w.check_for_updates()
    print(f"Found {len(items)} keyword-matching messages")
    for item in items[:5]:
        text = item.get("text", "")[:80]
        print(f"  - {text}")
    if w._browser:
        w._browser.close()
else:
    print("Could not connect — session may have expired")
