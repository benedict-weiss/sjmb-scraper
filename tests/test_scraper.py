import json
from pathlib import Path

import pytest
from scraper import load_seen, matches_keywords, save_seen


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
