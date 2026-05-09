# Design: Migrate fetch layer from requests+mbasic to Playwright

Date: 2026-05-09

## Context

`mbasic.facebook.com` is no longer usable for authenticated users: a modern-browser
UA gets forcibly redirected to `m.facebook.com` (React app, not parseable as plain
HTML), and a feature-phone UA causes Facebook to reject the session cookies. The fix
is to use Playwright to render the full React app with a real Chromium browser, then
parse the resulting HTML.

## Scope

Only the fetch layer changes. Email, seen-post tracking, git commit, and keyword
matching are untouched.

## Changes

### 1. `fetch_group_page` in `scraper.py`

Replace the `requests.get` call with a Playwright sync implementation:

```python
from playwright.sync_api import sync_playwright

def fetch_group_page(cookies: list[dict]) -> str:
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context()
        context.add_cookies(cookies)
        page = context.new_page()
        page.goto(f"https://www.facebook.com/groups/{GROUP_ID}", wait_until="networkidle")
        html = page.content()
        browser.close()
    return html
```

The signature changes from `cookies: dict[str, str]` (name→value mapping) to
`cookies: list[dict]` (the raw Cookie-Editor JSON list), since Playwright's
`add_cookies` expects that format directly.

`load_cookies` is updated accordingly — it no longer converts the list to a dict,
it returns the raw list.

`main` passes the list directly to `fetch_group_page`.

### 2. `is_logged_out` in `scraper.py`

Remove the `'"staticcontentonly"'` check (mbasic-specific false positive). Keep the
`"log in" + "create new account"` string check, which works on rendered HTML.

Add the debug print line: retain the `Fetched URL` print and the HTML snippet dump
until parse_posts is confirmed working.

### 3. `parse_posts` — provisional

Keep the existing `/permalink/\d+/` regex unchanged for the first run. This is a
known risk: the full React app may use different URL patterns. The debug HTML dump
will reveal whether the pattern matches. If not, update the regex in a follow-up
commit.

### 4. `requirements.txt`

Add `playwright==1.52.0`.

### 5. GitHub Actions workflow

Add after `pip install -r requirements.txt`:

```yaml
- name: Install Playwright browsers
  run: playwright install chromium --with-deps
```

### 6. Tests

`test_fetch_group_page_returns_html` — patch `sync_playwright` context manager
instead of `requests.get`. The test checks that the returned HTML is the string
from the mocked `page.content()`.

`test_fetch_group_page_passes_cookies_to_playwright` — new test asserting that
`add_cookies` is called with the parsed cookie list.

All other tests are unaffected.

## Risks

- `parse_posts` regex may not match the React-rendered HTML. Mitigated by the
  existing HTML debug dump, which will show us the structure on the first run.
- `networkidle` may time out if Facebook loads content via infinite scroll without
  settling. Fallback: use `domcontentloaded` + an explicit wait for a selector.
- Cookie expiry remains the user's responsibility (Cookie-Editor re-export).

## Out of scope

- Stealth mode / anti-bot fingerprinting
- Handling Facebook's 2FA or login challenges
- Parsing m.facebook.com if `parse_posts` needs a rewrite (tracked as follow-up)
