# Design: Cloudflare Workers Scraper

Date: 2026-05-09

## Context

GitHub Actions (Azure IPs) triggered Facebook's session-hijacking detection and
invalidated the session cookies. Playwright from a datacenter IP cannot reliably
authenticate Facebook. Cloudflare Workers runs on Cloudflare's edge network — IPs
that Facebook treats differently from Azure/GCP/AWS — and can make simple HTTP
fetches with a `Cookie` header, which is the same approach as the original
`requests` implementation but without the IP reputation problem.

## Scope

Add a Cloudflare Worker to the existing repo alongside the current Python scraper.
Disable the GitHub Actions cron (keep the workflow for manual debugging). The Worker
is the new production runtime.

## Stack

- **Cloudflare Workers** — cron trigger, `fetch`, free tier
- **Cloudflare KV** — seen-post ID persistence, free tier (1K writes/day, 100K reads/day)
- **Resend** — transactional email API, free tier (3K emails/month, 100/day)
- **Wrangler CLI** — local dev and deployment

## Files

```
wrangler.toml          worker config: KV binding, cron, compatibility date
src/worker.js          all scraper logic
.github/workflows/scrape.yml   cron schedule removed (workflow_dispatch kept)
```

The Python scraper (`scraper.py`) is left unchanged as a reference/fallback.

## Cookie Handling

Cookies are stored in Cookie-Editor JSON format as a Worker Secret named
`FB_COOKIES`. On each run, the worker parses the JSON array and builds a
`Cookie: name=value; name2=value2` header string. No browser, no fingerprinting.

## Seen Posts

A single KV key `seen_posts` holds a JSON array of post ID strings, capped at 500.
Read at the start of each run, written back if any new posts are found.

## Email

Resend API (`https://api.resend.com/emails`) via a `fetch` POST. Secret:
`RESEND_API_KEY`. The `from` address uses Resend's default sender domain
(`onboarding@resend.dev`) for the free tier — no custom domain setup needed.

## Cron Schedule

`*/10 * * * *` — every 10 minutes, same as current.

## Secrets (set via `wrangler secret put`)

| Secret | Value |
|--------|-------|
| `FB_COOKIES` | Cookie-Editor JSON array |
| `RESEND_API_KEY` | Resend API key |
| `NOTIFY_EMAIL` | Email address to alert |

## worker.js Logic

Mirrors the Python scraper exactly:

1. Parse cookies → build `Cookie` header
2. `fetch` `https://mbasic.facebook.com/groups/{GROUP_ID}` with `Cookie` header and a Chrome mobile User-Agent
3. `isLoggedOut(html)` → check for "log in" + "create new account" → send session-expired email and exit
4. `parsePosts(html)` → find `/permalink/\d+/` links, extract author/text/timestamp
5. `matchesKeywords(text)` → same keyword list, same WTB exclusion
6. Load `seen_posts` from KV
7. On first run (seen empty): mark all current posts as seen, write KV, exit
8. For each unseen post matching keywords: send alert email via Resend
9. Write updated seen list to KV

## wrangler.toml

```toml
name = "sjmb-scraper"
main = "src/worker.js"
compatibility_date = "2025-01-01"

[triggers]
crons = ["*/10 * * * *"]

[[kv_namespaces]]
binding = "SEEN_POSTS_KV"
id = "<KV_NAMESPACE_ID>"
```

## Deployment

```bash
npm install -g wrangler
wrangler login
wrangler kv namespace create SEEN_POSTS_KV
# copy the id into wrangler.toml
wrangler secret put FB_COOKIES
wrangler secret put RESEND_API_KEY
wrangler secret put NOTIFY_EMAIL
wrangler deploy
```

## Risks

- **Cloudflare IPs may also trigger Facebook security**: if so, no free-tier
  solution exists; the user would need a residential proxy (~£5/month) or to
  accept the manual cookie re-export cadence on GitHub Actions.
- **mbasic.facebook.com availability**: Facebook has been progressively retiring
  mbasic; if it stops serving group posts entirely, `parsePosts` will return empty
  and the scraper will warn but not crash.
- **Resend free tier limits**: 100 emails/day is ample for ticket alerts.

## Out of Scope

- Custom Resend sender domain
- Cloudflare Workers deployment via GitHub Actions CI
- The Python scraper or existing GitHub Actions workflow (left as-is)
