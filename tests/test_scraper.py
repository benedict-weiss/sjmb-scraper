import json
import os
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from scraper import load_seen, matches_keywords, save_seen
from scraper import parse_posts, is_logged_out
from scraper import load_cookies, fetch_group_page

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
    # wts is index 0 in KEYWORDS — always wins when multiple keywords match
    result = matches_keywords("WTS SJMB ticket")
    assert result == "wts"


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
