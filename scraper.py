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


def matches_keywords(text: str) -> str | None:
    """Return the first matched keyword (lowercase) or None.

    Excludes posts containing only 'wtb' (want to buy) without 'wts' (want to sell).
    """
    text_lower = text.lower()

    # Check if post has WTB but no WTS
    if "wtb" in text_lower and "wts" not in text_lower:
        return None

    for kw in KEYWORDS:
        if kw in text_lower:
            return kw
    return None
