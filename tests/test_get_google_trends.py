"""Tests for get_google_trends resilience.

A Google Trends fetch failure (e.g. HTTP 429) must never abort the pipeline.
When there is a cached snapshot it is restored; when there is none (e.g. a
cleared-cache run) an empty placeholder is written so downstream `cp` + deploy
still succeed. The placeholder must NOT be written to the success cache.
"""
import json
from unittest import mock

import pytest

import get_google_trends as gt


@pytest.fixture
def tmp_paths(tmp_path, monkeypatch):
    out = tmp_path / "results" / "google_trends_history.json"
    cache_dir = tmp_path / "cache"
    cache_file = cache_dir / "google_trends_history.json"
    monkeypatch.setattr(gt, "OUTPUT_FILE", str(out))
    monkeypatch.setattr(gt, "CACHE_DIR", cache_dir)
    monkeypatch.setattr(gt, "CACHE_FILE", cache_file)
    return out, cache_dir, cache_file


def test_fetch_failure_without_cache_writes_placeholder_and_does_not_raise(tmp_paths, monkeypatch):
    out, cache_dir, cache_file = tmp_paths
    monkeypatch.setattr(gt, "fetch_trends", mock.Mock(side_effect=RuntimeError("429")))

    gt.main()  # must not raise

    assert out.exists()
    data = json.loads(out.read_text())
    assert data["monthly"] == []
    # The placeholder must not poison the "last successful snapshot" cache.
    assert not cache_file.exists()


def test_fetch_failure_with_cache_restores_snapshot(tmp_paths, monkeypatch):
    out, cache_dir, cache_file = tmp_paths
    cache_dir.mkdir(parents=True)
    snapshot = {
        "keyword": "Autoware",
        "monthly": [{"month": "2020-01", "interest": 42, "is_partial": False}],
    }
    cache_file.write_text(json.dumps(snapshot))
    monkeypatch.setattr(gt, "fetch_trends", mock.Mock(side_effect=RuntimeError("429")))

    gt.main()

    data = json.loads(out.read_text())
    assert data["monthly"][0]["interest"] == 42


def test_fetch_success_writes_output_and_caches(tmp_paths, monkeypatch):
    out, cache_dir, cache_file = tmp_paths
    rows = [{"month": "2021-05", "interest": 100, "is_partial": False}]
    monkeypatch.setattr(gt, "fetch_trends", mock.Mock(return_value=rows))

    gt.main()

    data = json.loads(out.read_text())
    assert data["monthly"] == rows
    assert cache_file.exists()  # a real fetch is cached for future fallback
