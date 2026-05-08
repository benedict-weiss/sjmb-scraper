# SJMB Ticket Scraper Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a GitHub Actions cron job that monitors the Ticketbridge Facebook group every 10 minutes and emails when SJMB ticket listings appear.

**Architecture:** A single Python script (`scraper.py`) fetches `mbasic.facebook.com` with Facebook session cookies, parses posts with BeautifulSoup, matches keywords, and sends Gmail SMTP alerts. State (seen post IDs) is persisted as `seen_posts.json` committed back to the repo after each run.

**Tech Stack:** Python 3.12, `requests`, `beautifulsoup4`, `smtplib` (stdlib), GitHub Actions

---

## File Map

| File | Action | Purpose |
|------|--------|---------|
| `requirements.txt` | Create | `requests`, `beautifulsoup4` |
| `seen_posts.json` | Create | Initial empty state `[]` |
| `.gitignore` | Create | Exclude `.env`, `__pycache__`, `.pytest_cache` |
| `scraper.py` | Create | All scraping, parsing, matching, email, state logic |
| `tests/test_scraper.py` | Create | Full test suite with fixtures and mocks |
| `.github/workflows/scrape.yml` | Create | Cron workflow, secrets injection, commit-back |

---

## Task 1: Project Scaffold

**Files:**
- Create: `requirements.txt`
- Create: `seen_posts.json`
- Create: `.gitignore`
- Create: `tests/__init__.py`

- [ ] **Step 1: Create `requirements.txt`**

```
requests==2.32.3
beautifulsoup4==4.13.4
pytest==8.3.5
```

- [ ] **Step 2: Create `seen_posts.json`**

```json
[]
```

- [ ] **Step 3: Create `.gitignore`**

```
.env
__pycache__/
.pytest_cache/
*.pyc
```

- [ ] **Step 4: Create `tests/__init__.py`**

Empty file — just `touch tests/__init__.py`.

- [ ] **Step 5: Install dependencies**

```bash
pip install -r requirements.txt
```

Expected: packages install without errors.

- [ ] **Step 6: Commit**

```bash
git add requirements.txt seen_posts.json .gitignore tests/__init__.py
git commit -m "chore: project scaffold"
```

---

## Task 2: Keyword Matching

**Files:**
- Create: `scraper.py` (initial — keyword function only)
- Create: `tests/test_scraper.py` (initial — keyword tests only)

- [ ] **Step 1: Write the failing tests**

`tests/test_scraper.py`:

```python
import pytest
from scraper import matches_keywords


def test_matches_wts():
    assert matches_keywords("WTS 2 SJMB tickets £180 each") == "wts"


def test_matches_wts_lowercase():
    assert matches_keywords("wts 1 johns mb") == "wts"


def test_matches_selling():
    assert matches_keywords("selling my ticket, can't go anymore") == "selling"


def test_matches_sjmb():
    assert matches_keywords("Anyone want SJMB? Selling") == "sjmb"


def test_matches_johns_mb():
    assert matches_keywords("1x johns mb ticket available") == "johns mb"


def test_matches_johns_mb_apostrophe():
    assert matches_keywords("john's mb ticket for sale") == "john's mb"


def test_no_match_wtb_only():
    assert matches_keywords("WTB 1 johns mb please") is None


def test_no_match_unrelated():
    assert matches_keywords("Anyone going to Pembroke May Ball?") is None


def test_matches_returns_first_keyword():
    # WTS appears before SJMB in keyword list
    result = matches_keywords("WTS SJMB ticket")
    assert result in ("wts", "sjmb")  # either is valid — just not None
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_scraper.py -v
```

Expected: `ModuleNotFoundError: No module named 'scraper'`

- [ ] **Step 3: Create `scraper.py` with keyword matching**

```python
import json
import os
import re
import smtplib
import subprocess
import time
from email.mime.text import MIMEText
from pathlib import Path

import requests
from bs4 import BeautifulSoup

GROUP_ID = "YOUR_GROUP_ID_HERE"  # Replace: find in the URL at facebook.com/groups/...
SEEN_POSTS_FILE = Path("seen_posts.json")
MAX_SEEN = 500

KEYWORDS = [
    "wts",
    "selling",
    "for sale",
    "ticket available",
    "sjmb",
    "st john's may ball",
    "john's may ball",
    "johns may ball",
    "johns mb",
    "john's mb",
    "johns ball",
]


def matches_keywords(text: str) -> str | None:
    """Return the first matched keyword (lowercase) or None."""
    text_lower = text.lower()
    for kw in KEYWORDS:
        if kw in text_lower:
            return kw
    return None
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/test_scraper.py -v
```

Expected: all 9 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add scraper.py tests/test_scraper.py
git commit -m "feat: keyword matching"
```

---

## Task 3: State Management

**Files:**
- Modify: `scraper.py` — add `load_seen`, `save_seen`
- Modify: `tests/test_scraper.py` — add state tests

- [ ] **Step 1: Write failing tests**

Append to `tests/test_scraper.py`:

```python
import json
from pathlib import Path
from scraper import load_seen, save_seen


def test_load_seen_missing_file(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    assert load_seen() == []


def test_load_seen_existing_file(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "seen_posts.json").write_text('["111", "222"]')
    assert load_seen() == ["111", "222"]


def test_save_seen_writes_file(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    save_seen(["aaa", "bbb"])
    data = json.loads((tmp_path / "seen_posts.json").read_text())
    assert data == ["aaa", "bbb"]


def test_save_seen_trims_to_500(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    ids = [str(i) for i in range(600)]
    save_seen(ids)
    data = json.loads((tmp_path / "seen_posts.json").read_text())
    assert len(data) == 500
    assert data[0] == "100"  # oldest 100 trimmed
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_scraper.py::test_load_seen_missing_file -v
```

Expected: `ImportError: cannot import name 'load_seen'`

- [ ] **Step 3: Add state functions to `scraper.py`**

Append after `matches_keywords`:

```python
def load_seen() -> list[str]:
    if not SEEN_POSTS_FILE.exists():
        return []
    return json.loads(SEEN_POSTS_FILE.read_text())


def save_seen(seen: list[str]) -> None:
    trimmed = seen[-MAX_SEEN:]
    SEEN_POSTS_FILE.write_text(json.dumps(trimmed, indent=2))
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/test_scraper.py -v
```

Expected: all tests PASS.

- [ ] **Step 5: Commit**

```bash
git add scraper.py tests/test_scraper.py
git commit -m "feat: state management (seen_posts.json)"
```

---

## Task 4: HTML Parsing

**Files:**
- Modify: `scraper.py` — add `parse_posts`, `is_logged_out`
- Modify: `tests/test_scraper.py` — add parsing tests with fixture HTML

- [ ] **Step 1: Write failing tests**

Append to `tests/test_scraper.py`:

```python
from scraper import parse_posts, is_logged_out

FIXTURE_HTML = """
<html><body>
<div>
  <div>
    <strong><a href="/sarah.jones">Sarah Jones</a></strong>
    <div>WTS 2 SJMB tickets £180 each dm me</div>
    <div><abbr>2 hours ago</abbr></div>
    <div><a href="/groups/123456789/permalink/987654321/?ref=m_notif">Full Story</a></div>
  </div>
  <div>
    <strong><a href="/alex.laddle">Alex Laddle</a></strong>
    <div>wtb 1 johns mb</div>
    <div><abbr>4 hours ago</abbr></div>
    <div><a href="/groups/123456789/permalink/111222333/?ref=m_notif">Full Story</a></div>
  </div>
</div>
</body></html>
"""

LOGGED_OUT_HTML = """
<html><body>
<div>Log In</div>
<div>Create New Account</div>
</body></html>
"""


def test_parse_posts_returns_two_posts():
    posts = parse_posts(FIXTURE_HTML)
    assert len(posts) == 2


def test_parse_posts_extracts_id():
    posts = parse_posts(FIXTURE_HTML)
    ids = {p["id"] for p in posts}
    assert "987654321" in ids
    assert "111222333" in ids


def test_parse_posts_extracts_author():
    posts = parse_posts(FIXTURE_HTML)
    authors = {p["author"] for p in posts}
    assert "Sarah Jones" in authors


def test_parse_posts_extracts_text():
    posts = parse_posts(FIXTURE_HTML)
    sarah = next(p for p in posts if p["author"] == "Sarah Jones")
    assert "WTS" in sarah["text"]
    assert "SJMB" in sarah["text"]


def test_parse_posts_extracts_timestamp():
    posts = parse_posts(FIXTURE_HTML)
    sarah = next(p for p in posts if p["author"] == "Sarah Jones")
    assert sarah["timestamp"] == "2 hours ago"


def test_parse_posts_builds_full_url():
    posts = parse_posts(FIXTURE_HTML)
    sarah = next(p for p in posts if p["author"] == "Sarah Jones")
    assert sarah["url"].startswith("https://www.facebook.com")
    assert "987654321" in sarah["url"]


def test_parse_posts_no_duplicate_ids():
    posts = parse_posts(FIXTURE_HTML)
    ids = [p["id"] for p in posts]
    assert len(ids) == len(set(ids))


def test_is_logged_out_true():
    assert is_logged_out(LOGGED_OUT_HTML) is True


def test_is_logged_out_false():
    assert is_logged_out(FIXTURE_HTML) is False
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_scraper.py::test_parse_posts_returns_two_posts -v
```

Expected: `ImportError: cannot import name 'parse_posts'`

- [ ] **Step 3: Add `parse_posts` and `is_logged_out` to `scraper.py`**

Append after `save_seen`:

```python
def is_logged_out(html: str) -> bool:
    lower = html.lower()
    return "log in" in lower and "create new account" in lower


def parse_posts(html: str) -> list[dict]:
    soup = BeautifulSoup(html, "html.parser")
    posts = []
    seen_ids: set[str] = set()

    for link in soup.find_all("a", href=re.compile(r"/permalink/\d+/")):
        href = link["href"]
        m = re.search(r"/permalink/(\d+)/", href)
        if not m:
            continue
        post_id = m.group(1)
        if post_id in seen_ids:
            continue
        seen_ids.add(post_id)

        # Walk up to a container that has an <strong> author tag
        container = link.parent
        for _ in range(6):
            if container is None:
                break
            if container.find("strong"):
                break
            container = container.parent

        if container is None:
            continue

        author_tag = container.find("strong")
        author = author_tag.get_text(strip=True) if author_tag else "Unknown"
        abbr = container.find("abbr")
        timestamp = abbr.get_text(strip=True) if abbr else ""
        text = container.get_text(separator=" ", strip=True)
        post_url = (
            f"https://www.facebook.com/groups/{GROUP_ID}/permalink/{post_id}/"
        )

        posts.append(
            {
                "id": post_id,
                "author": author,
                "text": text,
                "timestamp": timestamp,
                "url": post_url,
            }
        )

    return posts
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/test_scraper.py -v
```

Expected: all tests PASS.

- [ ] **Step 5: Commit**

```bash
git add scraper.py tests/test_scraper.py
git commit -m "feat: HTML parsing and session detection"
```

---

## Task 5: HTTP Fetching and Cookie Loading

**Files:**
- Modify: `scraper.py` — add `load_cookies`, `fetch_group_page`
- Modify: `tests/test_scraper.py` — add fetching tests

- [ ] **Step 1: Write failing tests**

Append to `tests/test_scraper.py`:

```python
import os
from unittest.mock import MagicMock, patch
from scraper import load_cookies, fetch_group_page


def test_load_cookies_parses_json_list(monkeypatch):
    raw = '[{"name": "c_user", "value": "12345"}, {"name": "xs", "value": "abc"}]'
    monkeypatch.setenv("FB_COOKIES", raw)
    cookies = load_cookies()
    assert cookies == {"c_user": "12345", "xs": "abc"}


def test_load_cookies_missing_env(monkeypatch):
    monkeypatch.delenv("FB_COOKIES", raising=False)
    with pytest.raises(KeyError):
        load_cookies()


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

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_scraper.py::test_load_cookies_parses_json_list -v
```

Expected: `ImportError: cannot import name 'load_cookies'`

- [ ] **Step 3: Add `load_cookies` and `fetch_group_page` to `scraper.py`**

Append after `parse_posts`:

```python
def load_cookies() -> dict[str, str]:
    raw = os.environ["FB_COOKIES"]
    cookies_list = json.loads(raw)
    return {c["name"]: c["value"] for c in cookies_list}


def fetch_group_page(cookies: dict[str, str]) -> str:
    url = f"https://mbasic.facebook.com/groups/{GROUP_ID}"
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) "
            "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.0 Mobile/15E148 Safari/604.1"
        )
    }
    resp = requests.get(url, cookies=cookies, headers=headers, timeout=30)
    resp.raise_for_status()
    return resp.text
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/test_scraper.py -v
```

Expected: all tests PASS.

- [ ] **Step 5: Commit**

```bash
git add scraper.py tests/test_scraper.py
git commit -m "feat: HTTP fetching and cookie loading"
```

---

## Task 6: Email Sending

**Files:**
- Modify: `scraper.py` — add `send_email`
- Modify: `tests/test_scraper.py` — add email tests

- [ ] **Step 1: Write failing tests**

Append to `tests/test_scraper.py`:

```python
from unittest.mock import patch, MagicMock
from scraper import send_email


def test_send_email_calls_smtp(monkeypatch):
    monkeypatch.setenv("GMAIL_ADDRESS", "sender@gmail.com")
    monkeypatch.setenv("GMAIL_APP_PASSWORD", "apppassword")
    monkeypatch.setenv("NOTIFY_EMAIL", "notify@example.com")

    with patch("scraper.smtplib.SMTP_SSL") as mock_smtp_class:
        mock_server = MagicMock()
        mock_smtp_class.return_value.__enter__ = MagicMock(return_value=mock_server)
        mock_smtp_class.return_value.__exit__ = MagicMock(return_value=False)

        send_email("Test Subject", "Test body")

        mock_smtp_class.assert_called_once_with("smtp.gmail.com", 465)
        mock_server.login.assert_called_once_with("sender@gmail.com", "apppassword")
        mock_server.send_message.assert_called_once()
        sent_msg = mock_server.send_message.call_args[0][0]
        assert sent_msg["Subject"] == "Test Subject"
        assert sent_msg["To"] == "notify@example.com"
```

- [ ] **Step 2: Run test to verify it fails**

```bash
pytest tests/test_scraper.py::test_send_email_calls_smtp -v
```

Expected: `ImportError: cannot import name 'send_email'`

- [ ] **Step 3: Add `send_email` to `scraper.py`**

Append after `fetch_group_page`:

```python
def send_email(subject: str, body: str) -> None:
    address = os.environ["GMAIL_ADDRESS"]
    password = os.environ["GMAIL_APP_PASSWORD"]
    notify = os.environ["NOTIFY_EMAIL"]

    msg = MIMEText(body)
    msg["Subject"] = subject
    msg["From"] = address
    msg["To"] = notify

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(address, password)
        server.send_message(msg)
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/test_scraper.py -v
```

Expected: all tests PASS.

- [ ] **Step 5: Commit**

```bash
git add scraper.py tests/test_scraper.py
git commit -m "feat: Gmail SMTP email sending"
```

---

## Task 7: Main Orchestration

**Files:**
- Modify: `scraper.py` — add `commit_seen`, `main`
- Modify: `tests/test_scraper.py` — add integration-style orchestration test

- [ ] **Step 1: Write failing tests**

Append to `tests/test_scraper.py`:

```python
from unittest.mock import patch, call
from scraper import main

MATCH_HTML = """
<html><body>
<div>
  <div>
    <strong><a href="/sarah">Sarah Jones</a></strong>
    <div>WTS 2 SJMB tickets £180 each dm me</div>
    <div><abbr>2 hours ago</abbr></div>
    <div><a href="/groups/123456789/permalink/987654321/?ref=m_notif">Full Story</a></div>
  </div>
</div>
</body></html>
"""

NO_MATCH_HTML = """
<html><body>
<div>
  <div>
    <strong><a href="/bob">Bob Smith</a></strong>
    <div>WTB 1 Pembroke MB please!</div>
    <div><abbr>1 hour ago</abbr></div>
    <div><a href="/groups/123456789/permalink/555666777/?ref=m_notif">Full Story</a></div>
  </div>
</div>
</body></html>
"""


def test_main_sends_email_for_match(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    # Pre-populate seen_posts.json so this isn't treated as first run
    (tmp_path / "seen_posts.json").write_text('["000000000"]')
    monkeypatch.setenv("FB_COOKIES", '[{"name": "c_user", "value": "1"}]')
    monkeypatch.setenv("GMAIL_ADDRESS", "a@gmail.com")
    monkeypatch.setenv("GMAIL_APP_PASSWORD", "pw")
    monkeypatch.setenv("NOTIFY_EMAIL", "me@example.com")

    with patch("scraper.fetch_group_page", return_value=MATCH_HTML), \
         patch("scraper.send_email") as mock_email, \
         patch("scraper.commit_seen"):
        main()

    mock_email.assert_called_once()
    subject, body = mock_email.call_args[0]
    assert "Sarah Jones" in subject
    assert "SJMB Ticket Alert" in subject
    assert "WTS" in body or "wts" in body


def test_main_no_email_for_no_match(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("FB_COOKIES", '[{"name": "c_user", "value": "1"}]')
    monkeypatch.setenv("GMAIL_ADDRESS", "a@gmail.com")
    monkeypatch.setenv("GMAIL_APP_PASSWORD", "pw")
    monkeypatch.setenv("NOTIFY_EMAIL", "me@example.com")

    with patch("scraper.fetch_group_page", return_value=NO_MATCH_HTML), \
         patch("scraper.send_email") as mock_email, \
         patch("scraper.commit_seen"):
        main()

    mock_email.assert_not_called()


def test_main_skips_already_seen(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "seen_posts.json").write_text('["987654321"]')
    monkeypatch.setenv("FB_COOKIES", '[{"name": "c_user", "value": "1"}]')
    monkeypatch.setenv("GMAIL_ADDRESS", "a@gmail.com")
    monkeypatch.setenv("GMAIL_APP_PASSWORD", "pw")
    monkeypatch.setenv("NOTIFY_EMAIL", "me@example.com")

    with patch("scraper.fetch_group_page", return_value=MATCH_HTML), \
         patch("scraper.send_email") as mock_email, \
         patch("scraper.commit_seen"):
        main()

    mock_email.assert_not_called()


def test_main_sends_session_expired_email(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("FB_COOKIES", '[{"name": "c_user", "value": "1"}]')
    monkeypatch.setenv("GMAIL_ADDRESS", "a@gmail.com")
    monkeypatch.setenv("GMAIL_APP_PASSWORD", "pw")
    monkeypatch.setenv("NOTIFY_EMAIL", "me@example.com")

    logged_out = "<html><body>Log In Create New Account</body></html>"

    with patch("scraper.fetch_group_page", return_value=logged_out), \
         patch("scraper.send_email") as mock_email, \
         patch("scraper.commit_seen"):
        main()

    mock_email.assert_called_once()
    subject = mock_email.call_args[0][0]
    assert "expired" in subject.lower() or "session" in subject.lower()
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_scraper.py::test_main_sends_email_for_match -v
```

Expected: `ImportError: cannot import name 'main'`

- [ ] **Step 3: Add `commit_seen` and `main` to `scraper.py`**

Append after `send_email`:

```python
def commit_seen() -> None:
    subprocess.run(["git", "config", "user.email", "github-actions@github.com"], check=True)
    subprocess.run(["git", "config", "user.name", "github-actions"], check=True)
    subprocess.run(["git", "add", "seen_posts.json"], check=True)
    diff = subprocess.run(["git", "diff", "--cached", "--quiet"])
    if diff.returncode != 0:
        subprocess.run(
            ["git", "commit", "-m", "chore: update seen posts [skip ci]"],
            check=True,
        )
        subprocess.run(["git", "push"], check=True)


def main() -> None:
    cookies = load_cookies()

    try:
        html = fetch_group_page(cookies)
    except requests.RequestException:
        time.sleep(10)
        html = fetch_group_page(cookies)

    if is_logged_out(html):
        send_email(
            "SJMB Scraper: Facebook session expired",
            "Your Facebook session cookies have expired.\n\nPlease refresh the FB_COOKIES GitHub secret:\n"
            "1. Log into Facebook in Chrome\n"
            "2. Export cookies with Cookie-Editor extension\n"
            "3. Update the FB_COOKIES secret in your GitHub repository settings",
        )
        return

    posts = parse_posts(html)
    if not posts:
        print("Warning: no posts parsed — HTML structure may have changed")
        return

    seen = load_seen()
    first_run = len(seen) == 0
    seen_set = set(seen)

    new_matches: list[tuple[dict, str]] = []
    for post in posts:
        if post["id"] in seen_set:
            continue
        kw = matches_keywords(post["text"])
        if kw:
            new_matches.append((post, kw))

    all_ids = seen + [p["id"] for p in posts if p["id"] not in seen_set]
    save_seen(all_ids)
    commit_seen()

    if first_run:
        print(f"First run: marked {len(posts)} posts as seen, no emails sent")
        return

    for post, kw in new_matches:
        body = (
            f"New post in Ticketbridge matching your keywords:\n\n"
            f"Poster: {post['author']}\n"
            f"Posted: {post['timestamp']}\n"
            f"Matched keyword: {kw}\n\n"
            f"Post text:\n\"{post['text']}\"\n\n"
            f"View post: {post['url']}\n\n"
            f"---\n"
            f"Keywords active: WTS, selling, for sale, SJMB, St John's May Ball, Johns MB, johns mb"
        )
        send_email(f"SJMB Ticket Alert — {post['author']}", body)
        print(f"Notified: {post['author']} ({kw})")


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run full test suite**

```bash
pytest tests/test_scraper.py -v
```

Expected: all tests PASS.

- [ ] **Step 5: Commit**

```bash
git add scraper.py tests/test_scraper.py
git commit -m "feat: main orchestration"
```

---

## Task 8: GitHub Actions Workflow

**Files:**
- Create: `.github/workflows/scrape.yml`

> **Note:** Before this step, find the Ticketbridge group ID. Navigate to the group in Chrome, the URL will be `facebook.com/groups/<GROUP_ID>`. If it shows a name slug (e.g. `ticketbridge`), open the mbasic URL directly: `mbasic.facebook.com/groups/ticketbridge` — the page HTML will contain the numeric group ID in permalink links. Update `GROUP_ID` in `scraper.py` before proceeding.

- [ ] **Step 1: Create `.github/workflows/scrape.yml`**

```yaml
name: SJMB Ticket Scraper

on:
  schedule:
    - cron: "*/10 * * * *"
  workflow_dispatch:

permissions:
  contents: write

jobs:
  scrape:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with:
          token: ${{ secrets.GITHUB_TOKEN }}

      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"

      - name: Install dependencies
        run: pip install -r requirements.txt

      - name: Run scraper
        env:
          FB_COOKIES: ${{ secrets.FB_COOKIES }}
          GMAIL_ADDRESS: ${{ secrets.GMAIL_ADDRESS }}
          GMAIL_APP_PASSWORD: ${{ secrets.GMAIL_APP_PASSWORD }}
          NOTIFY_EMAIL: ${{ secrets.NOTIFY_EMAIL }}
        run: python scraper.py
```

- [ ] **Step 2: Commit**

```bash
git add .github/workflows/scrape.yml
git commit -m "feat: GitHub Actions cron workflow"
```

---

## Task 9: Secrets Setup and Smoke Test

> This task is manual — follow these steps before pushing to GitHub.

- [ ] **Step 1: Get Facebook cookies**

  1. Log into Facebook in Chrome
  2. Install [Cookie-Editor](https://cookie-editor.com/) Chrome extension
  3. Navigate to `facebook.com`
  4. Open Cookie-Editor → click "Export" → "Export as JSON"
  5. Copy the entire JSON string

- [ ] **Step 2: Get Gmail App Password**

  1. Go to [myaccount.google.com/apppasswords](https://myaccount.google.com/apppasswords)
  2. Create a new App Password for "Mail"
  3. Copy the 16-character password (no spaces)

- [ ] **Step 3: Create a GitHub repository and add secrets**

  ```bash
  gh repo create sjmb-scraper --private --source=. --push
  ```

  Then add secrets:

  ```bash
  gh secret set FB_COOKIES    # paste the JSON string from Cookie-Editor
  gh secret set GMAIL_ADDRESS # your Gmail address
  gh secret set GMAIL_APP_PASSWORD  # the 16-char App Password
  gh secret set NOTIFY_EMAIL  # email to receive alerts (can be same as GMAIL_ADDRESS)
  ```

- [ ] **Step 4: Trigger a manual run to verify**

  ```bash
  gh workflow run scrape.yml
  ```

  Then watch it:

  ```bash
  gh run watch
  ```

  Expected: workflow completes with exit 0. Check that `seen_posts.json` has been updated in the repo (via `gh run view --log` or the GitHub UI).

- [ ] **Step 5: Verify email delivery**

  Temporarily add a keyword that matches a current post (e.g., `wtb` — since there's a "wtb 1 johns mb" post visible in the screenshot), trigger another manual run, and confirm the email arrives at `NOTIFY_EMAIL`. Remove the temp keyword after confirming.

---

## Self-Review Notes

- **Spec coverage:** All sections covered — auth (cookie loading), fetch, parse, keyword match, state, email, error handling (session expiry, no posts), cron schedule, commit-back.
- **First-run behaviour:** `main()` marks all current posts seen on first run (since seen list is empty, all posts get added to `seen` before the new-matches loop — wait, actually there's a subtle bug here: the new_matches loop runs *before* save_seen, so posts not in `seen_set` at the start WILL be checked. On first run with empty state, ALL posts get keyword-checked. Let me re-examine...

Actually looking at the `main()` code:
```python
seen = load_seen()       # [] on first run
seen_set = set(seen)     # {} on first run

for post in posts:
    if post["id"] in seen_set:   # False for all on first run
        continue
    kw = matches_keywords(...)   # all posts get checked!
```

This means on first run, all existing matching posts WILL trigger emails. The spec says: "On first run (empty file): treats all current posts as seen — no flood of historical notifications."

To fix this, on first run (when `seen` is empty), we should skip sending emails and just populate `seen_posts.json`. The fix:

```python
first_run = len(seen) == 0

# ... after building new_matches ...

all_ids = seen + [p["id"] for p in posts if p["id"] not in seen_set]
save_seen(all_ids)
commit_seen()

if not first_run:
    for post, kw in new_matches:
        # send email
```

**This must be fixed in Task 7 Step 3.** Update the `main()` function accordingly.
