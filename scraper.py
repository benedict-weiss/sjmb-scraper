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
    return json.loads(SEEN_POSTS_FILE.read_text())


def save_seen(seen: list[str]) -> None:
    trimmed = seen[-MAX_SEEN:]
    SEEN_POSTS_FILE.write_text(json.dumps(trimmed, indent=2))


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
