# SJMB Ticket Scraper

Monitors the [Ticketbridge](https://www.facebook.com/groups/257070261826425) Facebook group for St John's May Ball ticket listings and sends email alerts.

Runs every 10 minutes via GitHub Actions.

## How it works

1. Fetches the Ticketbridge group page using `mbasic.facebook.com` with stored session cookies
2. Parses posts for keywords like `sjmb`, `wts`, `for sale`, `selling`, `st john's may ball`, etc.
3. Filters out WTB-only posts (want to buy, not sell)
4. Emails `NOTIFY_EMAIL` for any new matching posts
5. Persists seen post IDs to `seen_posts.json` and commits back to the repo

On the first run, all existing posts are marked as seen without sending any emails.

## Secrets required

Set these in **Settings → Secrets and variables → Actions**:

| Secret | Description |
|---|---|
| `FB_COOKIES` | JSON array of Facebook session cookies (exported via Cookie-Editor) |
| `GMAIL_ADDRESS` | Gmail address used to send alerts |
| `GMAIL_APP_PASSWORD` | Gmail [App Password](https://myaccount.google.com/apppasswords) |
| `NOTIFY_EMAIL` | Email address to receive alerts |

## Refreshing cookies

Facebook sessions expire periodically. When they do, a warning email is sent to `NOTIFY_EMAIL` with instructions:

1. Log into Facebook in Chrome
2. Export cookies using the [Cookie-Editor](https://cookie-editor.com/) extension (Export → JSON)
3. Update the `FB_COOKIES` secret in the repository settings

## Local development

```bash
pip install -r requirements.txt
export FB_COOKIES='[{"name":"c_user","value":"..."},...]'
export GMAIL_ADDRESS="you@gmail.com"
export GMAIL_APP_PASSWORD="xxxx xxxx xxxx xxxx"
export NOTIFY_EMAIL="you@example.com"
python scraper.py
```

Run tests:

```bash
pytest
```
