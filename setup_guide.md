Setup Plan — Real Credentials, Step by Step                                                                                               
                                                                                                                                            
  We'll do this in order. Each step is independent. Start → test → confirm → move to next.                                                  

  ┌─────┬──────────────────────┬──────────────┬────────────────────────────────┐
  │  #  │     Integration      │     Time     │         What you need          │
  ├─────┼──────────────────────┼──────────────┼────────────────────────────────┤
  │ 1   │ Gmail                │ 15 min       │ Google Cloud Console access    │
  ├─────┼──────────────────────┼──────────────┼────────────────────────────────┤
  │ 2   │ WhatsApp             │ 5 min        │ Your phone, WhatsApp installed │
  ├─────┼──────────────────────┼──────────────┼────────────────────────────────┤
  │ 3   │ LinkedIn             │ 10 min       │ LinkedIn Developer Portal      │
  ├─────┼──────────────────────┼──────────────┼────────────────────────────────┤
  │ 4   │ Facebook + Instagram │ 15 min       │ Meta Developer account         │
  ├─────┼──────────────────────┼──────────────┼────────────────────────────────┤
  │ 5   │ Twitter/X            │ 10 min       │ X Developer account            │
  ├─────┼──────────────────────┼──────────────┼────────────────────────────────┤
  │ 6   │ Odoo                 │ skip for now │ Needs a running Odoo instance  │
  └─────┴──────────────────────┴──────────────┴────────────────────────────────┘

  ---
  Step 1 — Gmail

  You do this in the browser:

  1. Go to https://console.cloud.google.com
  2. Create a new project → name it ai-employee
  3. APIs & Services → Library → search Gmail API → Enable
  4. APIs & Services → OAuth consent screen → External → fill:
    - App name: AI Employee
    - Support email: your Gmail
    - Add your Gmail as a Test user
  5. APIs & Services → Credentials → Create Credentials → OAuth client ID → Desktop app → Download JSON
  6. Save the downloaded file here:
  mkdir -p ~/.config/ai-employee
  mv ~/Downloads/client_secret_*.json ~/.config/ai-employee/client_secret.json

  Then come back and tell me you've done that — I'll run the auth flow from here.

  ---
  Step 2 — WhatsApp (after Gmail)

  Nothing to set up in advance. Just have your phone ready to scan a QR code.

  ---
  Step 3 — LinkedIn (after WhatsApp)

  Go to https://developer.linkedin.com → My Apps → Create app. Come back with the app created.

  ---
  Start with Gmail Step 1 above. Tell me when you have the client_secret.json file downloaded and moved to ~/.config/ai-employee/.

   Gmail is fully working end to end. Here's the summary so far:                                                                             
                                                                                                                                            
  ---                                                                                                                                       
  Gmail ✅ DONE                                                                                                                             
  - OAuth credentials: ~/.config/ai-employee/gmail_credentials.json                                                                         
  - DEV_MODE=false, DRY_RUN=true (reads real inbox, won't send anything yet)                                                                
  - 13 real emails written to vault as .md action files                                                                                     
  - Obsidian will show them live if you open the vault
                                                                                                                                            
  ---                                                                                                                                       
  Next: WhatsApp                                                                                                                            
                                                                                                                                            
  Run this to install the Chromium browser for Playwright (if not already):                                                                 

  uv run playwright install chromium

  Once that's done, I'll launch the WhatsApp session — you'll scan a QR code with your phone. Ready?


  Next: LinkedIn

  Do this in the browser:

  1. Go to https://developer.linkedin.com
  2. Click My Apps → Create App
  3. Fill in:
    - App name: AI Employee
    - LinkedIn Page: your personal profile URL (or create a company page)
    - App logo: any image
  4. Click Create App
  5. Go to the app → Auth tab
  6. Under OAuth 2.0 tools → click Request access for Share on LinkedIn (w/ OpenID)
  7. Once approved, go to Auth tab → OAuth 2.0 tools → generate a token with scopes: w_member_social, openid, profile
  8. Copy the Access Token

  Tell me when you have the access token.

  ● LinkedIn doesn't allow personal profile URLs — it needs a Company Page. Quickest fix: create a free LinkedIn Page in 2 minutes.           
                                                                                                                                            
  Do this:                                                                                                                                  
                                                                                                                                            
  1. Go to https://www.linkedin.com/company/setup/new/                                                                                      
  2. Fill in:                                                                                                                               
    - Name: AI Employee (or your business name)
    - LinkedIn public URL: anything, e.g. ai-employee-ashfaq
    - Company type: Self-employed
    - Industry: Technology
    - Company size: 1 employee
  3. Click Create Page
  4. Copy the new page URL (e.g. https://www.linkedin.com/company/ai-employee-ashfaq)

  Then go back to the app creation form and paste that company page URL (not your personal profile).

  Tell me when the page is created.

  ● Good — app is created. I can see you're on the Auth tab. Do these steps in order:                                                         
                                                                                                                                            
  Step 1 — Add a redirect URL (required before generating a token)                                                                          
  1. Click the pencil icon ✏️  next to Authorized redirect URLs                                                                              
  2. Add: http://localhost:8080/callback                                                                                                    
  3. Click Update                                                                                                                           

  Step 2 — Request the posting product                                                                                                      
  1. Click the Products tab (top nav)                                                                                                       
  2. Find Share on LinkedIn → click Request access
  3. Also request Sign In with LinkedIn using OpenID Connect
  4. Come back here once both show "Added" or "Pending"

  Step 3 — Generate access token
  1. Back on Auth tab → scroll down past OAuth 2.0 scopes
  2. You'll see OAuth 2.0 tools section → click Request access token
  3. Select scopes: openid, profile, w_member_social
  4. Click Request access token → it opens a browser → authorize
  5. Copy the Access Token value

  The scopes are perfect — openid, profile, w_member_social, email are all there. Redirect URL is set too. ✅                               
                                                                                                                                            
  The token generator is on a separate page. Go directly to:                                                                                
                                                                                                                                            
  https://www.linkedin.com/developers/tools/oauth/token-generator                                                                           
                                                                                                                                            
  1. Select your app AI-Employee from the dropdown                                                                                          
  2. Check all 4 scopes: openid, profile, w_member_social, email
  3. Click Request access token
  4. A browser popup will ask you to authorize — click Allow
  5. Copy the Access Token (it's a long string starting with AQ...)

  Paste the token here (or in your .env) and I'll wire it up.

   Check your LinkedIn profile — you should see the post there right now.                                                                    
                                                         
  ---                                                                                                                                       
  Progress:                                                                                                                                 

  ┌─────┬──────────────────────┬───────────────────────────────┐
  │  #  │     Integration      │            Status             │
  ├─────┼──────────────────────┼───────────────────────────────┤
  │ 1   │ Gmail                │ ✅ Live                       │
  ├─────┼──────────────────────┼───────────────────────────────┤
  │ 2   │ WhatsApp             │ ✅ Live                       │
  ├─────┼──────────────────────┼───────────────────────────────┤
  │ 3   │ LinkedIn             │ ✅ Live — real post confirmed │
  ├─────┼──────────────────────┼───────────────────────────────┤
  │ 4   │ Facebook + Instagram │ ⏳ Next                       │
  ├─────┼──────────────────────┼───────────────────────────────┤
  │ 5   │ Twitter/X            │ ⏳ Pending                    │
  └─────┴──────────────────────┴───────────────────────────────┘

  ---
  

    Gmail — 6 sections                                                                                                                                                                                                                                                                    
  ┌─────┬───────────────────────────────────────────┬───────────────────────────────────┐                                                   
  │  #  │                   Test                    │              Result               │                                                     ├─────┼───────────────────────────────────────────┼───────────────────────────────────┤                                                     │ 1   │ search_email (reads live inbox)           │ ✅ 5 messages returned            │                                                     ├─────┼───────────────────────────────────────────┼───────────────────────────────────┤                                                     │ 2   │ draft_email (live draft)                  │ ✅ Draft ID r-1381859136340267213 │                                                     ├─────┼───────────────────────────────────────────┼───────────────────────────────────┤                                                     │ 3   │ Approval gate — send blocked without file │ ✅ Correctly rejected             │                                                   
  ├─────┼───────────────────────────────────────────┼───────────────────────────────────┤
  │ 4   │ Live send_email to self                   │ ✅ Message ID 19c96c9f6b2265cc    │
  ├─────┼───────────────────────────────────────────┼───────────────────────────────────┤
  │ 5   │ Rate limiter blocks at 10/hour            │ ✅ Blocked on attempt 10          │
  ├─────┼───────────────────────────────────────────┼───────────────────────────────────┤
  │ 6   │ Audit log — 13 email entries              │ ✅                                │
  └─────┴───────────────────────────────────────────┴───────────────────────────────────┘

  WhatsApp — 6 sections

  ┌─────┬─────────────────────────────────────────────────────┬───────────────┐
  │  #  │                        Test                         │    Result     │
  ├─────┼─────────────────────────────────────────────────────┼───────────────┤
  │ 7   │ Keyword loading from Company_Handbook.md            │ ✅ 7 keywords │
  ├─────┼─────────────────────────────────────────────────────┼───────────────┤
  │ 8   │ check_for_updates() returns [] in dev_mode          │ ✅            │
  ├─────┼─────────────────────────────────────────────────────┼───────────────┤
  │ 9   │ create_action_file() writes WHATSAPP_*.md           │ ✅            │
  ├─────┼─────────────────────────────────────────────────────┼───────────────┤
  │ 10  │ api_whatsapp() lists action files                   │ ✅            │
  ├─────┼─────────────────────────────────────────────────────┼───────────────┤
  │ 11  │ api_whatsapp_reply() creates APPROVAL_wa_reply_*.md │ ✅            │
  ├─────┼─────────────────────────────────────────────────────┼───────────────┤
  │ 12  │ Approval file fields validated                      │ ✅            │
  └─────┴─────────────────────────────────────────────────────┴───────────────┘

  Note: WhatsApp is inbound-only (Playwright reads WhatsApp Web). Outbound replies go through the HITL approval flow (Pending_Approval/) —  
  not a direct send API.

✻ Cooked for 3m 53s

❯ so what should be standard / ideal what's app flow?                                                                                           
● Good question. Let me map out the current state vs the ideal, so you can make an informed decision.
                                                                                                                                              ---
  Current implementation                                                                                                                       
  Playwright browser (headless) → scrapes WhatsApp Web → creates WHATSAPP_*.md                                                              
                                                                ↓
                                                      Human reviews in dashboard
                                                                ↓
                                           api_whatsapp_reply() → APPROVAL_*.md
                                                                ↓
                                                (nothing — no actual send)

  Problems:
  - No outbound send at all — the HITL approval creates a file but nothing delivers it
  - Session expires whenever WhatsApp Web logs out (QR scan needed)
  - Needs a headed browser (breaks on headless servers)
  - Fragile DOM selectors break with WhatsApp Web UI updates
  - Can't run reliably in the cloud

  ---
  Ideal / standard flow

  The correct architecture uses the WhatsApp Business Cloud API (Meta's official API — same developer portal you already have):

  Inbound (webhook):
    WhatsApp user sends message
          → Meta Cloud API fires webhook → /webhook endpoint in your server
          → Parse message → create WHATSAPP_*.md in Needs_Action
          → Claude evaluates → drafts reply → places in Pending_Approval

  Outbound (send):
    Human approves in dashboard  (or Claude auto-approves for low-risk replies)
          → POST /messages to graph.facebook.com/v21.0/{PHONE_ID}/messages
          → Message delivered to user

  What you already have that makes this possible:
  - META_ACCESS_TOKEN ✅
  - META_APP_ID + META_APP_SECRET ✅
  - Facebook Business account ✅

  What's missing:
  - A WhatsApp Business phone number connected to your Meta app
  - A running webhook endpoint (HTTPS) to receive inbound messages
  - A whatsapp_client.py send method (trivial to add — same Graph API pattern as Facebook/Instagram)

  ---
  The two realistic paths

  ┌─────────────────┬───────────────────────────────────────┬────────────────────────────────────────────────────────────┐
  │                 │       Path A — Keep Playwright        │               Path B — WhatsApp Business API               │
  ├─────────────────┼───────────────────────────────────────┼────────────────────────────────────────────────────────────┤
  │ Cost            │ Free                                  │ Free up to 1,000 conversations/month                       │
  ├─────────────────┼───────────────────────────────────────┼────────────────────────────────────────────────────────────┤
  │ Setup           │ Already done                          │ Need to connect a phone number (~10 min in Meta dashboard) │
  ├─────────────────┼───────────────────────────────────────┼────────────────────────────────────────────────────────────┤
  │ Reliability     │ Fragile (session expiry, DOM changes) │ Rock solid (official API)                                  │
  ├─────────────────┼───────────────────────────────────────┼────────────────────────────────────────────────────────────┤
  │ Outbound send   │ ❌ Not implemented                    │ ✅ Simple REST call                                        │
  ├─────────────────┼───────────────────────────────────────┼────────────────────────────────────────────────────────────┤
  │ Inbound         │ Polling (30s delay)                   │ Webhook (real-time)                                        │
  ├─────────────────┼───────────────────────────────────────┼────────────────────────────────────────────────────────────┤
  │ Cloud-ready     │ ❌ Needs display                      │ ✅ Pure HTTP                                               │
  ├─────────────────┼───────────────────────────────────────┼────────────────────────────────────────────────────────────┤
  │ Personal number │ Uses your own number                  │ Needs a dedicated business number                          │
  └─────────────────┴───────────────────────────────────────┴────────────────────────────────────────────────────────────┘

  ---
  What I'd recommend

  Path B — switch to WhatsApp Business API. You already own the Meta app. The steps are:

  1. Go to your Meta app → WhatsApp → Getting Started → get a free test phone number (Meta gives you one for development)
  2. Add WHATSAPP_PHONE_ID and WHATSAPP_VERIFY_TOKEN to .env
  3. Add a whatsapp_client.py (same 15-line pattern as facebook_client.py) with a send_message() method
  4. Replace whatsapp_watcher.py with a webhook handler (FastAPI endpoint — 20 lines)
  5. The HITL approval file already exists — just wire it to whatsapp_client.send_message() instead of doing nothing

  Want me to implement Path B? I'd need you to grab the Phone Number ID from your Meta app's WhatsApp section first — everything else I can 
  build from what's alr
  eady there.