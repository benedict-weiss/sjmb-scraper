# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What This Is

A GitHub Actions cron job that scrapes the Ticketbridge Facebook group every 10 minutes, looking for St John's May Ball ticket listings. Matching posts trigger Gmail SMTP email alerts. State is persisted by committing `seen_posts.json` back to the repo after each run.

## Running the Scraper Locally

```bash
pip install -r requirements.txt
FB_COOKIES='...' GMAIL_ADDRESS='...' GMAIL_APP_PASSWORD='...' NOTIFY_EMAIL='...' python scraper.py
```

## Architecture

Single-file scraper (`scraper.py`) triggered by `.github/workflows/scrape.yml`. No web framework, no database — intentionally minimal.

**Data flow:**
1. Fetch `mbasic.facebook.com/groups/<group_id>` with Facebook session cookies as a request header
2. Parse HTML with BeautifulSoup to extract posts (ID, author, text, timestamp)
3. Case-insensitive keyword match against the post text
4. Load `seen_posts.json`, skip already-seen post IDs
5. Send one Gmail SMTP email per new matching post
6. Write updated `seen_posts.json` (capped at 500 IDs), commit back to repo

## Key Design Decisions

- **mbasic.facebook.com** — server-rendered HTML, no JavaScript required, stable interface, no headless browser needed
- **Cookie auth** — session cookies stored in `FB_COOKIES` GitHub secret; must be refreshed manually every ~90 days. Export from Chrome using Cookie-Editor extension.
- **Commit-based state** — `seen_posts.json` is committed after each run; no external database
- **First-run behaviour** — if `seen_posts.json` is missing or empty, all posts on the current page are marked seen without emailing (prevents notification flood on setup)

## Required GitHub Secrets

| Secret | Description |
|--------|-------------|
| `FB_COOKIES` | Facebook session cookies as JSON string |
| `GMAIL_ADDRESS` | Sending Gmail address |
| `GMAIL_APP_PASSWORD` | Gmail App Password |
| `NOTIFY_EMAIL` | Alert destination address |

## Keywords

Defined in `scraper.py` as a list — edit there to add/remove terms. Current set targets sell-intent (`WTS`, `selling`, `for sale`) and event terms (`SJMB`, `Johns MB`, `St John's May Ball`, etc.). Matching is case-insensitive OR logic.

## Error Handling

- Cookies expired (Facebook redirects to login): sends a warning email then exits 0
- No posts parsed: logs to Actions output, does not email
- SMTP failure: raises, fails the run, does not commit state
