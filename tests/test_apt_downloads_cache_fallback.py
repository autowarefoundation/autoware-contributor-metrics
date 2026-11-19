"""A failed AWStats fetch must fall back to the cached page, so that one
server error does not drop a whole month from the cumulative total."""
import pytest

import get_apt_downloads as ad


@pytest.fixture
def cache_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(ad, "CACHE_DIR", str(tmp_path))
    monkeypatch.setattr(ad.time, "sleep", lambda _: None)
    return tmp_path


def fetch_returns(monkeypatch, value):
    calls = []

    def fake_fetch(year, month):
        calls.append((year, month))
        return value

    monkeypatch.setattr(ad, "fetch_awstats_page", fake_fetch)
    return calls


def test_failed_fetch_of_current_month_uses_the_cache(cache_dir, monkeypatch):
    (cache_dir / "2026-11.html").write_text("cached")
    fetch_returns(monkeypatch, None)
    assert ad.load_month_html(2026, 11, use_cache=True, is_current=True) == "cached"


def test_failed_fetch_in_full_mode_uses_the_cache(cache_dir, monkeypatch):
    (cache_dir / "2026-10.html").write_text("cached")
    fetch_returns(monkeypatch, None)
    assert ad.load_month_html(2026, 10, use_cache=False, is_current=False) == "cached"


def test_failed_fetch_without_cache_returns_none(cache_dir, monkeypatch):
    fetch_returns(monkeypatch, None)
    assert ad.load_month_html(2026, 11, use_cache=True, is_current=True) is None


def test_successful_fetch_of_current_month_replaces_the_cache(cache_dir, monkeypatch):
    (cache_dir / "2026-11.html").write_text("old")
    fetch_returns(monkeypatch, "new")
    assert ad.load_month_html(2026, 11, use_cache=True, is_current=True) == "new"
    assert (cache_dir / "2026-11.html").read_text() == "new"


def test_cached_past_month_is_not_fetched(cache_dir, monkeypatch):
    (cache_dir / "2026-10.html").write_text("cached")
    calls = fetch_returns(monkeypatch, "new")
    assert ad.load_month_html(2026, 10, use_cache=True, is_current=False) == "cached"
    assert calls == []
