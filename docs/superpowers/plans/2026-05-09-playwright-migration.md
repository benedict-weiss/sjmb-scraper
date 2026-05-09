# Playwright Migration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the `requests`+mbasic fetch layer with Playwright/Chromium so the scraper can render the full Facebook React app and authenticate via cookie injection.

**Architecture:** `fetch_group_page` uses `sync_playwright` to launch headless Chromium, injects the raw Cookie-Editor JSON list via `add_cookies`, navigates to `facebook.com/groups/{GROUP_ID}` with `networkidle`, and returns the rendered HTML. `load_cookies` returns the raw list (not a name→value dict) since Playwright accepts that format directly. Everything else (email, seen-post tracking, git commit, keyword matching) is unchanged.

**Tech Stack:** Python 3.12, `playwright==1.52.0`, `beautifulsoup4`, `smtplib`, GitHub Actions ubuntu-latest

---

## File Map

| File | Change |
|------|--------|
| `requirements.txt` | Add `playwright==1.52.0`, remove `requests==2.32.3` |
| `.github/workflows/scraper.yml` | Add `playwright install chromium --with-deps` step |
| `scraper.py` | Rewrite `fetch_group_page`, update `load_cookies` signature, fix `is_logged_out`, clean up imports and `main()` retry |
| `tests/test_scraper.py` | Update `test_load_cookies_parses_json_list`, replace `test_fetch_group_page_returns_html`, add `test_fetch_group_page_passes_cookies_to_playwright`, add `test_is_logged_out_staticcontentonly_not_triggered` |

---

## Task 1: Update dependencies and workflow

**Files:**
- Modify: `requirements.txt`
- Modify: `.github/workflows/scraper.yml`

- [ ] **Step 1: Update requirements.txt**

Replace the file contents with:

```
playwright==1.52.0
beautifulsoup4==4.13.4
pytest==8.3.5
```

(`requests` is removed — it is only used by `fetch_group_page` which is being replaced.)

- [ ] **Step 2: Add Playwright install step to workflow**

In `.github/workflows/scraper.yml`, add a new step after `pip install -r requirements.txt`:

```yaml
      - name: Install Playwright browsers
        run: playwright install chromium --with-deps
```

The full `jobs.scrape.steps` block should read:

```yaml
    steps:
      - uses: actions/checkout@v4
        with:
          token: ${{ secrets.GITHUB_TOKEN }}

      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"

      - name: Install dependencies
        run: pip install -r requirements.txt

      - name: Install Playwright browsers
        run: playwright install chromium --with-deps

      - name: Run scraper
        env:
          FB_COOKIES: ${{ secrets.FB_COOKIES }}
          GMAIL_ADDRESS: ${{ secrets.GMAIL_ADDRESS }}
          GMAIL_APP_PASSWORD: ${{ secrets.GMAIL_APP_PASSWORD }}
          NOTIFY_EMAIL: ${{ secrets.NOTIFY_EMAIL }}
        run: python scraper.py
```

- [ ] **Step 3: Commit**

```bash
git add requirements.txt .github/workflows/scraper.yml
git commit -m "chore: replace requests with playwright, add browser install step"
```

---

## Task 2: Rewrite load_cookies and fetch_group_page (TDD)

**Files:**
- Modify: `tests/test_scraper.py`
- Modify: `scraper.py`

These two functions are coupled — `load_cookies` must return a list for Playwright's `add_cookies`, and `fetch_group_page` must accept that list — so they are updated together.

- [ ] **Step 1: Write failing tests**

In `tests/test_scraper.py`, replace the existing `test_load_cookies_parses_json_list` test and the existing `test_fetch_group_page_returns_html` test, and add one new test. The import block at the top of the test file must import `fetch_group_page` and `load_cookies` from `scraper` (already present). Add `sync_playwright` to the scraper import list — it will be patched.

Replace:

```python
def test_load_cookies_parses_json_list(monkeypatch):
    raw = '[{"name": "c_user", "value": "12345"}, {"name": "xs", "value": "abc"}]'
    monkeypatch.setenv("FB_COOKIES", raw)
    cookies = load_cookies()
    assert cookies == {"c_user": "12345", "xs": "abc"}
```

With:

```python
def test_load_cookies_parses_json_list(monkeypatch):
    raw = '[{"name": "c_user", "value": "12345"}, {"name": "xs", "value": "abc"}]'
    monkeypatch.setenv("FB_COOKIES", raw)
    cookies = load_cookies()
    assert cookies == [{"name": "c_user", "value": "12345"}, {"name": "xs", "value": "abc"}]
```

Replace:

```python
def test_fetch_group_page_returns_html(monkeypatch):
    raw = '[{"name": "c_user", "value": "12345"}]'
    monkeypatch.setenv("FB_COOKIES", raw)
    mock_resp = MagicMock()
    mock_resp.text = "<html>group content</html>"
    mock_resp.raise_for_status = MagicMock()

    with patch("scraper.requests.get", return_value=mock_resp) as mock_get:
        html = fetch_group_page({"c_user": "12345"})
        assert html == "<html>group content</html>"
        mock_get.assert_called_once()
        call_kwargs = mock_get.call_args
        assert "mbasic.facebook.com" in call_kwargs[0][0]
```

With:

```python
def _make_playwright_mock(html: str):
    mock_page = MagicMock()
    mock_page.content.return_value = html

    mock_context = MagicMock()
    mock_context.new_page.return_value = mock_page

    mock_browser = MagicMock()
    mock_browser.new_context.return_value = mock_context

    mock_pw = MagicMock()
    mock_pw.chromium.launch.return_value = mock_browser

    mock_sync_playwright = MagicMock()
    mock_sync_playwright.return_value.__enter__ = MagicMock(return_value=mock_pw)
    mock_sync_playwright.return_value.__exit__ = MagicMock(return_value=False)

    return mock_sync_playwright, mock_context, mock_page


def test_fetch_group_page_returns_html():
    mock_sync_playwright, _, _ = _make_playwright_mock("<html>group content</html>")
    cookies = [{"name": "c_user", "value": "12345", "domain": ".facebook.com"}]

    with patch("scraper.sync_playwright", mock_sync_playwright):
        html = fetch_group_page(cookies)

    assert html == "<html>group content</html>"


def test_fetch_group_page_passes_cookies_to_playwright():
    cookies = [{"name": "c_user", "value": "12345", "domain": ".facebook.com"}]
    mock_sync_playwright, mock_context, _ = _make_playwright_mock("<html>ok</html>")

    with patch("scraper.sync_playwright", mock_sync_playwright):
        fetch_group_page(cookies)

    mock_context.add_cookies.assert_called_once_with(cookies)
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd /Users/benweiss/sjmb-scraper
pip install -r requirements.txt -q
pytest tests/test_scraper.py::test_load_cookies_parses_json_list tests/test_scraper.py::test_fetch_group_page_returns_html tests/test_scraper.py::test_fetch_group_page_passes_cookies_to_playwright -v
```

Expected: FAIL — `test_load_cookies_parses_json_list` fails because current `load_cookies` returns a dict, `test_fetch_group_page_*` fail because `scraper.sync_playwright` doesn't exist yet.

- [ ] **Step 3: Update scraper.py — imports**

At the top of `scraper.py`, replace:

```python
import requests
```

With:

```python
from playwright.sync_api import sync_playwright
```

And remove `import time` (it is only used in the retry block which will be removed in Task 4).

- [ ] **Step 4: Update load_cookies in scraper.py**

Replace:

```python
def load_cookies() -> dict[str, str]:
    raw = os.environ["FB_COOKIES"]
    cookies_list = json.loads(raw)
    return {c["name"]: c["value"] for c in cookies_list}
```

With:

```python
def load_cookies() -> list[dict]:
    raw = os.environ["FB_COOKIES"]
    return json.loads(raw)
```

- [ ] **Step 5: Rewrite fetch_group_page in scraper.py**

Replace:

```python
def fetch_group_page(cookies: dict[str, str]) -> str:
    url = f"https://mbasic.facebook.com/groups/{GROUP_ID}"
    headers = {
        "User-Agent": "Nokia3310/1.0 (SymbianOS; Series40) NokiaBrowser/1.0",
    }
    resp = requests.get(url, cookies=cookies, headers=headers, timeout=30)
    resp.raise_for_status()
    print(f"Fetched URL: {resp.url} (status {resp.status_code})")
    return resp.text
```

With:

```python
def fetch_group_page(cookies: list[dict]) -> str:
    url = f"https://www.facebook.com/groups/{GROUP_ID}"
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context()
        context.add_cookies(cookies)
        page = context.new_page()
        page.goto(url, wait_until="networkidle")
        html = page.content()
        browser.close()
    return html
```

- [ ] **Step 6: Run tests to verify they pass**

```bash
pytest tests/test_scraper.py::test_load_cookies_parses_json_list tests/test_scraper.py::test_fetch_group_page_returns_html tests/test_scraper.py::test_fetch_group_page_passes_cookies_to_playwright -v
```

Expected: All 3 PASS.

- [ ] **Step 7: Run full test suite to check for regressions**

```bash
pytest tests/ -v
```

Expected: All tests PASS. (The `test_load_cookies_missing_env` test still passes since `KeyError` is still raised. The `test_main_*` tests patch `fetch_group_page` directly so are unaffected.)

- [ ] **Step 8: Commit**

```bash
git add scraper.py tests/test_scraper.py
git commit -m "feat: replace requests fetch with Playwright/Chromium"
```

---

## Task 3: Fix is_logged_out and clean up main()

**Files:**
- Modify: `scraper.py`
- Modify: `tests/test_scraper.py`

- [ ] **Step 1: Add a regression test for the staticcontentonly false positive**

In `tests/test_scraper.py`, add after `test_is_logged_out_false`:

```python
def test_is_logged_out_false_for_react_app():
    # staticcontentonly appeared in mbasic redirect HTML — should NOT trigger
    # logged-out when the full React app is served to an authenticated user
    react_html = '<html><head></head><body data-staticcontentonly="1">feed content</body></html>'
    assert is_logged_out(react_html) is False
```

- [ ] **Step 2: Run that test to verify it fails**

```bash
pytest tests/test_scraper.py::test_is_logged_out_false_for_react_app -v
```

Expected: FAIL — current `is_logged_out` returns `True` for HTML containing `staticcontentonly`.

- [ ] **Step 3: Remove the staticcontentonly check from is_logged_out**

Replace:

```python
def is_logged_out(html: str) -> bool:
    lower = html.lower()
    if "log in" in lower and "create new account" in lower:
        return True
    # FB redirected to JS app instead of mbasic — cookies expired/invalid
    if '"staticcontentonly"' in lower:
        return True
    return False
```

With:

```python
def is_logged_out(html: str) -> bool:
    lower = html.lower()
    return "log in" in lower and "create new account" in lower
```

- [ ] **Step 4: Clean up main() — remove requests retry and unused import**

The retry block in `main()` catches `requests.RequestException`, which no longer exists. Remove it. Also remove the `import time` line (already done in Task 2 Step 3 — verify it's gone).

Replace in `main()`:

```python
    try:
        html = fetch_group_page(cookies)
    except requests.RequestException:
        time.sleep(10)
        html = fetch_group_page(cookies)
```

With:

```python
    html = fetch_group_page(cookies)
```

- [ ] **Step 5: Run full test suite**

```bash
pytest tests/ -v
```

Expected: All tests PASS.

- [ ] **Step 6: Commit**

```bash
git add scraper.py tests/test_scraper.py
git commit -m "fix: remove mbasic-specific staticcontentonly check, drop requests retry"
```

---

## Task 4: Trigger workflow and verify

**Files:** None — this is a verification task.

- [ ] **Step 1: Push and trigger manual run**

```bash
git push
gh workflow run "SJMB Ticket Scraper" --repo benedict-weiss/sjmb-scraper
```

- [ ] **Step 2: Wait for run to complete (allow ~90s for Playwright browser install)**

```bash
sleep 90 && gh run list --repo benedict-weiss/sjmb-scraper --limit 1
```

- [ ] **Step 3: Check output**

```bash
gh run view --repo benedict-weiss/sjmb-scraper $(gh run list --repo benedict-weiss/sjmb-scraper --limit 1 --json databaseId --jq '.[0].databaseId') --log 2>&1 | grep -E "First run|Warning|Notified|Logged out|no posts"
```

**Success:** `First run: marked N posts as seen, no emails sent` — means cookies work and posts were parsed.

**Partial success — posts not parsed:** Output shows `Warning: no posts parsed` with an HTML snippet. This means authentication worked but `parse_posts` regex doesn't match the React app's HTML. Note the HTML structure from the snippet and open a follow-up task to update `parse_posts`.

**Failure — logged out:** Output shows `Logged out detected`. Cookies need to be re-exported.

- [ ] **Step 4: Confirm seen_posts.json was committed**

```bash
gh api repos/benedict-weiss/sjmb-scraper/commits --jq '.[0] | {sha: .sha[0:7], message: .commit.message}'
```

Expected: most recent commit message is `chore: update seen posts [skip ci]`.
