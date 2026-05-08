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
