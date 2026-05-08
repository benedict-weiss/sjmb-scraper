# SJMB Ticket Scraper — Design Spec

**Date:** 2026-05-07  
**Status:** Approved

---

## Overview

A GitHub Actions-based scraper that monitors the Ticketbridge Facebook group for St John's May Ball ticket listings. When a post matching configured keywords is detected, it sends an email notification via Gmail SMTP. Runs every 10 minutes without any manual intervention.

---

## Architecture

```
GitHub Actions cron (every 10 min)
    └── scraper.py
          ├── Load FB cookies from GitHub secret
          ├── GET mbasic.facebook.com/groups/<group_id>
          ├── Parse HTML → extract posts (ID + text + author)
          ├── Filter by keywords (case-insensitive)
          ├── Load seen_posts.json from repo
          ├── New matches → send Gmail SMTP email per match
          ├── Update seen_posts.json (all visited IDs)
          └── Commit seen_posts.json back to repo
```

---

## Components

### Files

| File | Purpose |
|------|---------|
| `scraper.py` | Main scraper script |
| `.github/workflows/scrape.yml` | Cron workflow definition |
| `seen_posts.json` | State file — IDs of already-notified posts |
| `requirements.txt` | `requests`, `beautifulsoup4` |

### GitHub Secrets

| Secret | Description |
|--------|-------------|
| `FB_COOKIES` | Facebook session cookies exported as JSON string from browser |
| `GMAIL_ADDRESS` | Gmail address used to send alerts |
| `GMAIL_APP_PASSWORD` | Gmail App Password (not account password) |
| `NOTIFY_EMAIL` | Destination address for alerts |

---

## Scheduling

- GitHub Actions cron: `*/10 * * * *` (every 10 minutes)
- GitHub's free tier allows up to 2,000 minutes/month; each run takes ~15 seconds, so 4,320 runs/month × ~0.25 min = ~1,080 minutes/month — well within limits

---

## Scraping

- Target URL: `https://mbasic.facebook.com/groups/<group_id>`
- Authentication: pass `FB_COOKIES` as a `Cookie:` header on each request
- Parser: `BeautifulSoup` with `html.parser`
- Extract per post: post ID, author name, post text, relative timestamp, post URL (converted to full facebook.com URL for the notification link)

### Cookie Setup (manual, one-time)

1. Log into Facebook in Chrome
2. Install a cookie export extension (e.g. Cookie-Editor)
3. Export cookies for facebook.com as JSON
4. Store the JSON string in GitHub secret `FB_COOKIES`
5. Repeat when cookies expire (~90 days)

---

## Keyword Matching

Case-insensitive OR match. A post fires an alert if it contains **any** of:

**Sell-intent:**
- `WTS`
- `selling`
- `for sale`
- `ticket available`

**Event-specific:**
- `SJMB`
- `St John's May Ball`
- `John's May Ball`
- `Johns May Ball`
- `johns mb`
- `john's mb`
- `johns ball`

Posts containing only `WTB` (want to buy) with no sell-intent keywords are ignored.

---

## Email Notification

**Subject:** `SJMB Ticket Alert — [Poster Name]`

**Body:**
```
New post in Ticketbridge matching your keywords:

Poster: [name]
Posted: [relative time]
Matched keyword: [keyword]

Post text:
"[full post text]"

View post: https://www.facebook.com/groups/.../posts/...

---
Keywords active: WTS, selling, for sale, SJMB, St John's May Ball, Johns MB, johns mb
```

- One email per matching post
- Multiple matches in one run → multiple emails
- No digest batching (speed matters for ticket availability)

---

## State Management

- `seen_posts.json`: JSON array of post IDs already notified
- Capped at 500 entries; oldest trimmed when limit exceeded
- On first run (empty file): treats all current posts as seen — no flood of historical notifications
- File committed back to repo after every run that processes new posts

---

## Error Handling

| Scenario | Behaviour |
|----------|-----------|
| Facebook redirects to login (cookies expired) | Send warning email: `"SJMB Scraper: Facebook session expired — please refresh cookies"` then exit cleanly |
| HTML parsing finds no posts | Log warning to Actions output, do not email, exit 0 |
| Gmail SMTP failure | Raise exception, fail the Actions run (state file not committed) |
| Network timeout | Retry once after 10s; if still failing, fail the run |

---

## Out of Scope

- Telegram / Slack notifications (email only)
- Scraping comments on posts
- Auto-replying to sellers
- Any form of account automation beyond reading

