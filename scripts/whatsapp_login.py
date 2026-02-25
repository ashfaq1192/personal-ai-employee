"""
WhatsApp QR login — run this directly in your terminal:

    cd /mnt/d/projects/hackathon-0
    uv run python3 scripts/whatsapp_login.py
"""
import sys, time
sys.path.insert(0, ".")

from playwright.sync_api import sync_playwright

print("Opening WhatsApp Web...")
print("A browser window will appear on your desktop.")
print("Scan the QR code with your phone, then press Enter here to save and close.\n")

with sync_playwright() as p:
    browser = p.chromium.launch_persistent_context(
        "/home/ashfaq/.config/ai-employee/whatsapp-session",
        headless=False,
        user_agent=(
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/131.0.0.0 Safari/537.36"
        ),
        args=[
            "--no-sandbox",
            "--disable-dev-shm-usage",
            "--disable-blink-features=AutomationControlled",
        ],
        ignore_default_args=["--enable-automation"],
        viewport={"width": 1280, "height": 800},
    )
    page = browser.pages[0] if browser.pages else browser.new_page()
    page.goto("https://web.whatsapp.com", timeout=30000)

    # Poll for login every 3 seconds (up to 3 minutes)
    for i in range(60):
        chat = page.query_selector('[data-testid="chat-list"]')
        if chat:
            print("\n✅ LOGGED IN! Session saved.")
            print("   Chats are visible. Closing browser...")
            break
        if i % 5 == 0:
            print(f"   Waiting for QR scan... ({i*3}s elapsed)")
        time.sleep(3)
    else:
        print("\n⚠️  Timed out (3 min). Session may still be saved — try running test_whatsapp.py")

    browser.close()
    print("Session persisted to ~/.config/ai-employee/whatsapp-session")
