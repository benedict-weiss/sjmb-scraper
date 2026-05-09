import json
import os
import re
import smtplib
import subprocess
from email.mime.text import MIMEText
from pathlib import Path

from playwright.sync_api import sync_playwright
from bs4 import BeautifulSoup

GROUP_ID = "257070261826425"
SEEN_POSTS_FILE = Path("seen_posts.json")
MAX_SEEN = 500

SELL_INTENT = {"wts", "selling", "for sale", "ticket available"}

KEYWORDS = [
    "wts",
    "st john's may ball",
    "john's may ball",
    "johns may ball",
    "john's mb",
    "johns mb",
    "johns ball",
    "sjmb",
    "ticket available",
    "for sale",
    "selling",
]


def load_seen() -> list[str]:
    if not SEEN_POSTS_FILE.exists():
        return []
    try:
        return json.loads(SEEN_POSTS_FILE.read_text())
    except (json.JSONDecodeError, ValueError):
        return []


def save_seen(seen: list[str]) -> None:
    trimmed = seen[-MAX_SEEN:]
    SEEN_POSTS_FILE.write_text(json.dumps(trimmed, indent=2))


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


def matches_keywords(text: str) -> str | None:
    """Return the first matched keyword (lowercase) or None.

    Excludes posts that mention 'wtb' unless they also contain a sell-intent keyword.
    """
    text_lower = text.lower()

    # Exclude posts with WTB but lacking any sell-intent keyword
    if re.search(r'\bwtb\b', text_lower) and not any(si in text_lower for si in SELL_INTENT):
        return None

    for kw in KEYWORDS:
        if kw in text_lower:
            return kw
    return None


def load_cookies() -> list[dict]:
    raw = os.environ["FB_COOKIES"]
    try:
        return json.loads(raw)
    except json.JSONDecodeError as e:
        raise ValueError(f"FB_COOKIES is not valid JSON: {e}") from e


def fetch_group_page(cookies: list[dict]) -> str:
    url = f"https://www.facebook.com/groups/{GROUP_ID}"
    # Playwright only accepts specific fields and sameSite must be a string not null
    _PLAYWRIGHT_SAMESITE = {"Strict", "Lax", "None"}
    normalized = []
    for c in cookies:
        nc = {"name": c["name"], "value": c["value"], "domain": c["domain"], "path": c.get("path", "/")}
        if c.get("secure") is not None:
            nc["secure"] = c["secure"]
        if c.get("httpOnly") is not None:
            nc["httpOnly"] = c["httpOnly"]
        if c.get("sameSite") in _PLAYWRIGHT_SAMESITE:
            nc["sameSite"] = c["sameSite"]
        expires = c.get("expirationDate") or c.get("expires")
        if expires is not None:
            nc["expires"] = int(expires)
        normalized.append(nc)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context()
        context.add_cookies(normalized)
        page = context.new_page()
        page.goto(url, wait_until="networkidle", timeout=60000)
        html = page.content()
    return html


def send_email(subject: str, body: str) -> None:
    address = os.environ["GMAIL_ADDRESS"].encode("ascii", "ignore").decode()
    password = os.environ["GMAIL_APP_PASSWORD"].encode("ascii", "ignore").decode()
    notify = os.environ["NOTIFY_EMAIL"].encode("ascii", "ignore").decode()

    msg = MIMEText(body)
    msg["Subject"] = subject
    msg["From"] = address
    msg["To"] = notify

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(address, password)
        server.send_message(msg)


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

    from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
    try:
        html = fetch_group_page(cookies)
    except PlaywrightTimeoutError:
        print("Page load timed out — skipping this run")
        return

    if is_logged_out(html):
        print(f"Logged out detected. HTML snippet: {html[:500]!r}")
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
        print(f"HTML snippet: {html[:2000]!r}")
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
