# SJMB Scraper — Pivot to Oracle Cloud Free Tier + Playwright

## Context

The existing approaches are blocked:

1. **Original GitHub Actions + Python (mbasic.facebook.com)** — Azure datacenter IPs trigger Facebook's session-hijacking detection; cookies invalidated within minutes. Cron disabled in `.github/workflows/scrape.yml`.
2. **Cloudflare Workers + node-html-parser** (current `src/worker.js`) — Deployed and running, but `mbasic.facebook.com/groups/{id}` no longer serves group post HTML for any User-Agent in 2026. Confirmed directly: Chrome Mobile UA, Nokia UA, iOS Safari 9 UA, and `python-requests` UA, against five URL variants (`/groups/{id}`, `/browse/group/recent/?id=`, `?v=feed`, `?ref=group_browse`, `/posts/`) all returned an `unsupported-interstitial` page with zero permalinks. mbasic is dead for group content. Workers also cannot execute JS, so `m.facebook.com` (React SPA) is unreachable from a Worker.
3. **Apify, Bright Data, ScrapingBee, etc.** — All charge >$5/mo for a 10-minute cron over a month (~4,320 runs).

User constraints (confirmed): free only, no home machine, some maintenance OK.

The viable path is a **free-forever cloud VM with a stable IP** running a **real headless browser** that can render `m.facebook.com`. **Oracle Cloud Always Free** is the only credible "free forever" general-purpose VM offering in 2026 (AWS/GCP/Azure free tiers expire after 12 months; Fly.io and Render dropped/restricted free compute in 2024). Oracle's free tier includes 2× AMD VMs (1/8 OCPU, 1 GB RAM each) and up to 4× Ampere ARM cores / 24 GB RAM, with no time limit.

Intended outcome: a Playwright-driven scraper running every 10 minutes on a free Oracle VM, pulling the Ticketbridge group via a logged-in Chromium session, matching the same keywords as today, and emailing alerts via the existing Resend integration. Same keyword set, same email format, same dedup behaviour — only the runtime and rendering layer change.

## Recommended Approach

### Architecture

```
┌──────────────────────────────────────────────────┐
│  Oracle Cloud Always Free VM (Ampere ARM, UK)    │
│  ┌────────────────────────────────────────────┐  │
│  │  systemd timer: every 10 min               │  │
│  │  └─ python scraper.py                      │  │
│  │     ├─ playwright launches Chromium        │  │
│  │     ├─ load cookies.json                   │  │
│  │     ├─ goto m.facebook.com/groups/{id}     │  │
│  │     ├─ wait for posts to render            │  │
│  │     ├─ extract permalink + author + text   │  │
│  │     ├─ filter against seen.json (cap 500)  │  │
│  │     ├─ matchesKeywords() — port from JS    │  │
│  │     └─ POST to Resend API on match         │  │
│  └────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────┘
```

State (cookies, seen IDs, secrets) lives on disk in `/home/ubuntu/sjmb-scraper/state/` — no external KV needed since we have a persistent VM.

### Component breakdown

**`scraper.py`** — single-file script, run by systemd timer. Reuses logic from `src/worker.js`:
- Keyword list and `SELL_INTENT` exclusion: copy verbatim from `src/worker.js:6-20` and the WTB exclusion from `src/worker.js:66-75`.
- Group ID `257070261826425` and `MAX_SEEN = 500`: same as `src/worker.js:3-4`.
- Email body format: copy verbatim from `src/worker.js:182-197`.

**`cookies.json`** — Cookie-Editor export (same format the existing `.dev.vars` uses). Stored at `/home/ubuntu/sjmb-scraper/state/cookies.json`, mode 600.

**`state/seen.json`** — JSON list of post IDs, capped at 500. Replaces Cloudflare KV.

**`.env`** — contains `RESEND_API_KEY`, `NOTIFY_EMAIL`. Mode 600.

**`sjmb-scraper.service`** + **`sjmb-scraper.timer`** — systemd units. Timer runs every 10 minutes; service runs `scraper.py` once and exits.

### Why Oracle Always Free specifically

- Genuinely no time limit (vs. AWS/GCP 12-month trials).
- Static public IPv4 — Facebook can build trust on this single IP over time, unlike GitHub Actions which rotated through Azure's pool.
- 1 GB RAM is sufficient for a single headless Chromium tab (~400 MB peak).
- UK / EU regions available (Heathrow, Frankfurt) — closer to actual user IP geolocation, less suspicious to Facebook.
- ARM Ampere shape has wider Chromium support than the AMD micro shape; provision Ampere first.

### Why Playwright + `m.facebook.com` (not Selenium, not `www.facebook.com`)

- Playwright is the modern Selenium replacement; less detectable, easier to install (`playwright install chromium` bundles the browser).
- `m.facebook.com` renders a smaller DOM than `www.facebook.com` (no left/right sidebars, no chat) — faster, less RAM, less code surface to break.
- Real Chromium handles JS rendering, cookies, redirects natively. The "Error" / interstitial page hit on mbasic is not served to a real browser session.

### Risks (in priority order)

1. **Oracle capacity in EU regions** — Ampere instances are sometimes "out of capacity" in popular regions. Mitigation: try UK South first; fall back to Frankfurt or US East. Worst case use the AMD micro shape (1 GB RAM is tight but workable for one tab).
2. **Oracle reclaims idle "always free" instances** — happens for instances with <20% CPU for 7 days. A 10-minute Playwright cron easily clears that bar. Document this so future-Ben knows.
3. **Facebook still detects + blocks the new IP** — possible but much less likely than GitHub Actions. Stable IP + real Chromium + valid cookies + EU geo is the strongest free signal we can produce. Mitigation if it happens: rotate cookies more often, lower frequency to every 30 min, add `playwright-stealth`.
4. **Cookie expiry** — same risk as today. Existing `isLoggedOut` detection logic ports over; on detection send the same "session expired" email and stop.
5. **`m.facebook.com` DOM changes** — the parser will need occasional updates. Factor parsing into a single function with clear selectors so updates are localised.
6. **Account flagged for automation** — small but real. Mitigation: use the existing throwaway-style account if possible; don't hammer (10 min is conservative); add jittered delay (±60s) to avoid clockwork-perfect timing.

### Files to be created

- `scraper/scraper.py` — main script
- `scraper/requirements.txt` — `playwright`, `requests`
- `scraper/sjmb-scraper.service` — systemd unit
- `scraper/sjmb-scraper.timer` — systemd timer (every 10 min, with `RandomizedDelaySec=60`)
- `scraper/README.md` — Oracle setup + deployment runbook (replaces the speculative `docs/superpowers/specs/2026-05-09-cloudflare-workers-design.md` for ops)

### Files to be modified

- `README.md` — update to describe the Oracle deployment as the live path; mark the Cloudflare Worker as deprecated (kept in tree for reference, but no longer the active scraper).

### Files to be removed/retired (not deleted yet — keep one commit for history)

- `src/worker.js`, `src/worker.test.js`, `wrangler.toml`, `package.json`, `.dev.vars` — keep in repo for now; remove in a follow-up commit once Oracle deployment is verified working for 48+ hours.

### Reusable logic from existing code

| From | Lines | Reuse as |
|---|---|---|
| `src/worker.js:6-20` | KEYWORDS + SELL_INTENT | Copy as Python lists in `scraper.py` |
| `src/worker.js:66-75` | `matchesKeywords` | Port to Python; logic identical |
| `src/worker.js:108-126` | Resend POST | Port to Python `requests.post` |
| `src/worker.js:103-106` | `saveSeen` slice cap | Port; write to `state/seen.json` |
| `src/worker.js:131-147` | `isLoggedOut` + email body | Port detection; reuse email body verbatim |
| `src/worker.js:182-197` | Notification email body | Copy verbatim |

Parsing logic in `src/worker.js:32-64` (mbasic-specific permalink anchors) does **not** port — `m.facebook.com` has different markup. Write fresh selectors against `m.facebook.com` post containers (`article` elements with `data-ft` attributes, last verified pattern in 2025 community scrapers).

## Implementation Outline

1. **Provision Oracle VM** — manual, runbook in `scraper/README.md`. Sign up, provision Ampere ARM 1 OCPU / 6 GB Ubuntu 22.04 in UK South, open SSH, set up `ubuntu` user.
2. **Install Playwright** — `apt install python3-pip`, `pip install playwright requests`, `playwright install chromium --with-deps`.
3. **Port scraper to Python + Playwright** — single `scraper.py` ~150 lines. Headless Chromium, load cookies, navigate, wait for `article[data-ft]`, extract posts, dedupe, match, email.
4. **Wire systemd** — `sjmb-scraper.service` (Type=oneshot, runs `scraper.py`), `sjmb-scraper.timer` (`OnCalendar=*:0/10`, `RandomizedDelaySec=60`).
5. **Deploy state** — scp `cookies.json` + `.env` to VM, mode 600.
6. **Verify end-to-end** — manually run `systemctl start sjmb-scraper.service`, check `journalctl -u sjmb-scraper`, confirm posts parsed and (after first run) test alert email by injecting a known post ID with a keyword.
7. **Decommission Cloudflare Worker** — only after 48h of clean Oracle runs: `wrangler delete`, remove `wrangler.toml`/`src/worker.js`/etc.

## Verification

End-to-end test sequence after deployment:

1. **Login check**: `ssh oracle` → `cd ~/sjmb-scraper && python3 scraper.py --once --debug` → expect post count > 0 and "first run, marking N posts seen, no email".
2. **Dedup check**: re-run immediately → expect "0 new posts".
3. **Keyword match**: temporarily add a unique test keyword (e.g. `"sjmb-test-marker-xyz"`), find a recent post with that string and verify email arrives at `ben@weiss.org.uk`.
4. **Logged-out detection**: temporarily corrupt one byte of `cookies.json` → run → expect "session expired" email, no crash.
5. **Timer check**: `systemctl list-timers sjmb-scraper.timer` → confirm next-run within 10 min. Wait one tick, then `journalctl -u sjmb-scraper.service --since "15 min ago"` → confirm clean run.
6. **48-hour soak**: `journalctl -u sjmb-scraper -S "2 days ago" | grep -E "(error|fail|expired)"` → confirm no recurring errors before retiring the Worker.

## Critical files to read before implementing

- `/Users/benweiss/sjmb-scraper/src/worker.js` — keywords, email body, dedup logic to port
- `/Users/benweiss/sjmb-scraper/.dev.vars` — current cookie format (Cookie-Editor JSON)
- `/Users/benweiss/sjmb-scraper/docs/superpowers/specs/2026-05-09-cloudflare-workers-design.md` — original design context (what we're pivoting away from and why)

## Current deployed state (as of 2026-05-09)

- Cloudflare Worker `sjmb-scraper.sjmb.workers.dev` is live, cron every 10 min, but produces no useful work because mbasic returns the interstitial page. Safe to leave running until decommission.
- KV namespace `SEEN_POSTS_KV` id `9e883983a7ed49c2bedcf1737265bb9c` — will be deleted with `wrangler delete` during decommission.
- Secrets set on Worker: `FB_COOKIES`, `RESEND_API_KEY`, `NOTIFY_EMAIL`. Same values needed on Oracle VM.
- GitHub Actions workflow `.github/workflows/scrape.yml` — push trigger removed, cron disabled, only `workflow_dispatch:` left.
