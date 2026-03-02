#!/usr/bin/env python3
"""
Opens Graph API Explorer in a headed browser so you can regenerate the
Facebook token with the missing Pages permissions.

Usage:  uv run python scripts/fix_fb_permissions.py
"""
import os, json, time, re
from pathlib import Path
from playwright.sync_api import sync_playwright

APP_ID = os.getenv("META_APP_ID", "")
ENV_FILE = Path(__file__).parent.parent / ".env"

MISSING_PERMS = [
    "pages_show_list",
    "pages_manage_posts",
    "pages_read_engagement",
]

EXPLORER_URL = "https://developers.facebook.com/tools/explorer/"


def update_env(key: str, value: str):
    text = ENV_FILE.read_text()
    if re.search(rf"^{key}=", text, re.MULTILINE):
        text = re.sub(rf"^{key}=.*$", f"{key}={value}", text, flags=re.MULTILINE)
    else:
        text += f"\n{key}={value}"
    ENV_FILE.write_text(text)
    print(f"  ✅ {key} written to .env")


def main():
    print("=" * 60)
    print("Facebook Graph API Explorer — Permission Fixer")
    print("=" * 60)
    print()
    print("Opening Graph API Explorer in a headed browser...")
    print(f"You need to add these permissions: {', '.join(MISSING_PERMS)}")
    print()

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False, slow_mo=300)
        ctx = browser.new_context(viewport={"width": 1280, "height": 900})
        page = ctx.new_page()

        print(f"Navigating to {EXPLORER_URL} ...")
        page.goto(EXPLORER_URL)
        page.wait_for_load_state("domcontentloaded")
        time.sleep(3)

        print()
        print("━" * 60)
        print("INSTRUCTIONS (do these in the browser window):")
        print("━" * 60)
        print()
        print("1. Make sure your app is selected in the top dropdown")
        print("   (AI Employee app)")
        print()
        print("2. Click 'Add a Permission' and add:")
        for p_name in MISSING_PERMS:
            print(f"   • {p_name}")
        print()
        print("3. Click 'Generate Access Token' → authorize popup")
        print()
        print("Waiting up to 5 minutes for a new token to appear...")
        print("(Script auto-captures the token when it changes)")
        print("━" * 60)

        current_token = os.getenv("META_ACCESS_TOKEN", "")
        new_token = None
        deadline = time.time() + 300

        while time.time() < deadline:
            try:
                token_input = page.locator('input[aria-label="Access Token"]').first
                if token_input.is_visible():
                    val = token_input.input_value()
                    if val and len(val) > 50 and val != current_token:
                        new_token = val
                        print(f"\n  Token captured! ({len(val)} chars)")
                        break
            except Exception:
                pass
            time.sleep(2)

        if not new_token:
            print("\nToken unchanged after 5 minutes.")
            print("Please copy the token manually from the browser, then")
            print("paste it below and press Enter:")
            # Since this runs interactively in a terminal (not via Bash tool),
            # we keep a browser open for the user to manually copy the token.
            # When running via this script from the terminal, stdin works fine.
            try:
                manual = input("Token: ").strip()
                if manual and len(manual) > 50:
                    new_token = manual
            except (EOFError, KeyboardInterrupt):
                pass

        if new_token and len(new_token) > 50:
            print(f"\nNew token: {new_token[:40]}...")
            update_env("META_ACCESS_TOKEN", new_token)

            # Discover Page ID and Instagram Business Account ID
            print("\nDiscovering Page ID and Instagram Business Account ID...")
            import urllib.request

            def graph(path):
                url = f"https://graph.facebook.com/v21.0/{path}&access_token={new_token}"
                try:
                    res = urllib.request.urlopen(url, timeout=10)
                    return json.loads(res.read())
                except Exception as e:
                    return {"error": str(e)}

            accounts = graph("me/accounts?fields=id,name,instagram_business_account")
            pages = accounts.get("data", [])
            if not pages:
                print("  ⚠️  No Facebook Pages found.")
                print("     Ensure you have a Facebook Page and Instagram is")
                print("     set to Business/Creator and linked to that Page.")
            else:
                for pg in pages:
                    print(f"\n  Facebook Page: {pg.get('name')} (ID: {pg.get('id')})")
                    update_env("META_PAGE_ID", pg["id"])
                    ig = pg.get("instagram_business_account", {})
                    if ig:
                        ig_id = ig.get("id")
                        print(f"  Instagram Business Account ID: {ig_id}")
                        update_env("META_INSTAGRAM_BUSINESS_ACCOUNT_ID", ig_id)
                    else:
                        print("  ⚠️  No Instagram Business Account linked.")
                        print("     Instagram app: Profile → Settings & Privacy")
                        print("     → Account type and tools → Switch to Professional account")
                        print("     Then link it to your Facebook Page.")

            # Exchange for long-lived token
            app_id = os.getenv("META_APP_ID", "")
            app_secret = os.getenv("META_APP_SECRET", "")
            if app_id and app_secret:
                ll_data = graph(
                    f"oauth/access_token?grant_type=fb_exchange_token"
                    f"&client_id={app_id}&client_secret={app_secret}"
                    f"&fb_exchange_token={new_token}"
                )
                ll_token = ll_data.get("access_token")
                if ll_token:
                    expires = ll_data.get("expires_in", "?")
                    print(f"\n  Long-lived token obtained (expires in {expires}s ≈ 60 days)")
                    update_env("META_ACCESS_TOKEN", ll_token)
                else:
                    print(f"  Long-lived exchange failed: {ll_data}")
        else:
            print("\n⚠️  No token captured. Run again from a terminal with stdin.")

        print("\n✅ Done — browser stays open for review. Close it when ready.")
        time.sleep(10)
        browser.close()


if __name__ == "__main__":
    if ENV_FILE.exists():
        for line in ENV_FILE.read_text().splitlines():
            if "=" in line and not line.startswith("#"):
                k, _, v = line.partition("=")
                os.environ.setdefault(k.strip(), v.strip())
    main()
