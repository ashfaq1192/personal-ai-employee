#!/usr/bin/env python3
"""
Guided Playwright helper for Facebook Graph API Explorer permission setup.

1. Opens a browser, navigates to the Explorer
2. Waits for you to log in if needed
3. Takes screenshots to show progress
4. Captures the new token when generated
5. Discovers Page ID + Instagram Business Account ID
6. Writes everything to .env
"""
import os, json, time, re
from pathlib import Path
from playwright.sync_api import sync_playwright

ENV_FILE = Path(__file__).parent.parent / ".env"
SCREENSHOTS = Path("/tmp/fb_setup")
SCREENSHOTS.mkdir(exist_ok=True)

NEEDED_PERMS = ["pages_show_list", "pages_manage_posts", "pages_read_engagement"]
EXPLORER_URL = "https://developers.facebook.com/tools/explorer/"


def load_env():
    if ENV_FILE.exists():
        for line in ENV_FILE.read_text().splitlines():
            if "=" in line and not line.startswith("#"):
                k, _, v = line.partition("=")
                os.environ.setdefault(k.strip(), v.strip())


def update_env(key: str, value: str):
    text = ENV_FILE.read_text()
    if re.search(rf"^{key}=", text, re.MULTILINE):
        text = re.sub(rf"^{key}=.*$", f"{key}={value}", text, flags=re.MULTILINE)
    else:
        text += f"\n{key}={value}"
    ENV_FILE.write_text(text)
    print(f"  ✅ .env updated: {key}")


def graph_api(path, token):
    import urllib.request
    url = f"https://graph.facebook.com/v21.0/{path}&access_token={token}"
    try:
        res = urllib.request.urlopen(url, timeout=10)
        return json.loads(res.read())
    except Exception as e:
        try:
            return json.loads(e.fp.read())
        except Exception:
            return {"error": str(e)}


def main():
    load_env()
    old_token = os.getenv("META_ACCESS_TOKEN", "")

    print("=" * 60)
    print("FB Graph API Explorer Helper")
    print("=" * 60)

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=False,
            slow_mo=200,
            args=["--window-size=1280,900"],
        )
        ctx = browser.new_context(viewport={"width": 1280, "height": 900})
        page = ctx.new_page()

        # Step 1: Navigate to Explorer
        print("\n[1/5] Opening Graph API Explorer...")
        page.goto(EXPLORER_URL)
        time.sleep(3)

        # Step 2: Check if login needed
        if "login" in page.url.lower() or "log_in" in page.url.lower():
            print("[2/5] Login required.")
            print()
            print("━" * 60)
            print("ACTION REQUIRED: Log in to Facebook in the browser window.")
            print("Use your Facebook account (ashfaq.ahmad).")
            print("Waiting up to 3 minutes for you to complete login...")
            print("━" * 60)

            # Save screenshot
            page.screenshot(path=str(SCREENSHOTS / "01_login.png"))

            # Wait for redirect away from login page
            deadline = time.time() + 180
            while time.time() < deadline:
                if "login" not in page.url.lower() and "log_in" not in page.url.lower():
                    print("  Login detected! Navigating to Explorer...")
                    break
                time.sleep(2)
            else:
                print("  Timeout waiting for login. Exiting.")
                browser.close()
                return

            # Navigate back to Explorer after login
            page.goto(EXPLORER_URL)
            page.wait_for_load_state("networkidle")
            time.sleep(3)

        page.screenshot(path=str(SCREENSHOTS / "02_explorer.png"))
        print("\n[3/5] Explorer loaded. Screenshot: /tmp/fb_setup/02_explorer.png")

        # Step 3: Guide user through permissions
        print()
        print("━" * 60)
        print("ACTION REQUIRED in the browser:")
        print()
        print("1. Make sure 'AI Employee' app is selected (top dropdown)")
        print("   - Click the app dropdown (top right) if wrong app shown")
        print()
        print("2. Click 'Add a Permission' dropdown and search/add:")
        for perm in NEEDED_PERMS:
            print(f"   • {perm}")
        print()
        print("3. Click 'Generate Access Token' (blue button)")
        print("4. In the popup: click Continue → Allow")
        print()
        print("The script will auto-capture the new token.")
        print("Waiting up to 5 minutes...")
        print("━" * 60)

        # Step 4: Poll for new token
        new_token = None
        deadline = time.time() + 300

        while time.time() < deadline:
            try:
                # Try various selectors the Explorer might use
                for selector in [
                    'input[aria-label="Access Token"]',
                    'input[placeholder*="Access Token"]',
                    'textarea[aria-label*="token" i]',
                    '.uiTextInput[value*="EAA"]',
                ]:
                    try:
                        el = page.locator(selector).first
                        if el.is_visible(timeout=500):
                            val = el.input_value()
                            if val and len(val) > 50 and val != old_token:
                                new_token = val
                                break
                    except Exception:
                        pass

                if new_token:
                    print(f"\n  ✅ New token captured! ({len(new_token)} chars)")
                    break

                # Try getting text of any element containing a long token-like string
                try:
                    content = page.content()
                    # Find EAAxxxxx... patterns (FB tokens start with EAA)
                    matches = re.findall(r'EAA[A-Za-z0-9]{50,}', content)
                    for m in matches:
                        if m != old_token:
                            new_token = m
                            print(f"\n  ✅ Token found in page content! ({len(m)} chars)")
                            break
                    if new_token:
                        break
                except Exception:
                    pass

                # Take periodic screenshot every 30s
                elapsed = time.time() - (deadline - 300)
                if int(elapsed) % 30 < 2:
                    page.screenshot(path=str(SCREENSHOTS / f"waiting_{int(elapsed)}.png"))

            except Exception:
                pass
            time.sleep(2)

        page.screenshot(path=str(SCREENSHOTS / "03_after_token.png"))

        if not new_token:
            print("\n⚠️  Token not auto-captured.")
            print("Please copy it manually from the browser token field")
            print("and paste it at the prompt below.")
            # Keep browser open so user can copy
            time.sleep(30)
            browser.close()
            return

        # Step 5: Wire everything up
        print("\n[4/5] Updating .env with new token...")
        update_env("META_ACCESS_TOKEN", new_token)

        print("\n[5/5] Discovering Page ID and Instagram Business Account ID...")
        accounts = graph_api("me/accounts?fields=id,name,instagram_business_account", new_token)
        pages = accounts.get("data", [])

        if not pages:
            print()
            print("  ⚠️  No Facebook Pages found — me/accounts is empty.")
            print()
            print("  This means either:")
            print("  a) The token still lacks 'pages_show_list' permission")
            print("  b) You don't have a Facebook Page yet")
            print()
            # Verify permissions
            perms_data = graph_api("me/permissions?", new_token)
            granted = [p['permission'] for p in perms_data.get('data', []) if p['status'] == 'granted']
            print(f"  Permissions on this token: {granted}")
            missing = [p for p in NEEDED_PERMS if p not in granted]
            if missing:
                print(f"  Still missing: {missing}")
                print()
                print("  → Go back to Graph API Explorer and regenerate with those permissions.")
        else:
            for pg in pages:
                pg_name = pg.get("name")
                pg_id = pg.get("id")
                print(f"\n  Facebook Page: {pg_name} (ID: {pg_id})")
                update_env("META_PAGE_ID", pg_id)

                ig = pg.get("instagram_business_account", {})
                if ig:
                    ig_id = ig.get("id")
                    print(f"  Instagram Business Account ID: {ig_id}")
                    update_env("META_INSTAGRAM_BUSINESS_ACCOUNT_ID", ig_id)
                else:
                    print("  ⚠️  No Instagram Business Account linked to this Page.")
                    print("     Mobile: Profile → Settings & Privacy → Account type")
                    print("     → Switch to Professional account, then link to Facebook Page.")

        # Exchange for long-lived token (60 days)
        app_id = os.getenv("META_APP_ID", "")
        app_secret = os.getenv("META_APP_SECRET", "")
        if app_id and app_secret:
            ll = graph_api(
                f"oauth/access_token?grant_type=fb_exchange_token"
                f"&client_id={app_id}&client_secret={app_secret}"
                f"&fb_exchange_token={new_token}",
                new_token,
            )
            ll_token = ll.get("access_token")
            if ll_token:
                expires_days = int(ll.get("expires_in", 0)) // 86400
                print(f"\n  Long-lived token obtained (~{expires_days} days)")
                update_env("META_ACCESS_TOKEN", ll_token)
            else:
                print(f"\n  Long-lived exchange failed: {ll}")

        print()
        print("=" * 60)
        print("Done! Check .env for updated values.")
        print("Screenshots: /tmp/fb_setup/")
        print("=" * 60)

        # Keep browser open briefly for review
        time.sleep(5)
        browser.close()


if __name__ == "__main__":
    main()
