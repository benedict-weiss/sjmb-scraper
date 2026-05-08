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
