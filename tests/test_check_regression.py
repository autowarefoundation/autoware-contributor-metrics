"""Tests for the pre-publish regression guard.

The guard exists to stop a degraded snapshot from being published (and cached)
when a fetch failure silently drops repositories — the failure mode that lost
16 repositories and 843 unique stars from the dashboard.
"""
import json

import check_regression as cr


def write(directory, name, obj):
    directory.mkdir(parents=True, exist_ok=True)
    (directory / name).write_text(json.dumps(obj))


def stars_payload(repos, total):
    payload = {
        f"{r}_stars_history": [{"date": "2026-01-01", "star_count": 1}] for r in repos
    }
    payload["total_stars_history"] = [{"date": "2026-01-01", "star_count": total}]
    return payload


def test_dropped_repository_series_is_a_regression(tmp_path):
    base, res = tmp_path / "base", tmp_path / "res"
    write(base, "stars_history.json", stars_payload(["a", "b", "c"], 100))
    write(res, "stars_history.json", stars_payload(["a", "b"], 100))

    violations = cr.compare(res, base, tolerance=0.02)

    assert [v.metric for v in violations] == ["repo_series"]
    assert violations[0].previous == 3 and violations[0].current == 2


def test_large_total_drop_is_a_regression(tmp_path):
    """The real incident: 14,149 -> 13,306 unique stars."""
    base, res = tmp_path / "base", tmp_path / "res"
    write(base, "stars_history.json", stars_payload(["a", "b"], 14149))
    write(res, "stars_history.json", stars_payload(["a", "b"], 13306))

    violations = cr.compare(res, base, tolerance=0.02)

    assert any(v.metric == "total_stars" for v in violations)


def test_small_drop_within_tolerance_is_allowed(tmp_path):
    """Users unstarring repos causes small legitimate decreases."""
    base, res = tmp_path / "base", tmp_path / "res"
    write(base, "stars_history.json", stars_payload(["a", "b"], 10000))
    write(res, "stars_history.json", stars_payload(["a", "b"], 9950))  # -0.5%

    assert cr.compare(res, base, tolerance=0.02) == []


def test_growth_is_never_a_regression(tmp_path):
    base, res = tmp_path / "base", tmp_path / "res"
    write(base, "stars_history.json", stars_payload(["a", "b"], 10000))
    write(res, "stars_history.json", stars_payload(["a", "b", "c"], 10500))

    assert cr.compare(res, base, tolerance=0.02) == []


def test_repo_series_drop_is_flagged_even_within_tolerance(tmp_path):
    """A vanished repository is always wrong, regardless of tolerance."""
    base, res = tmp_path / "base", tmp_path / "res"
    write(base, "stars_history.json", stars_payload([f"r{i}" for i in range(100)], 100))
    write(res, "stars_history.json", stars_payload([f"r{i}" for i in range(99)], 100))

    violations = cr.compare(res, base, tolerance=0.5)

    assert any(v.metric == "repo_series" for v in violations)


def test_missing_baseline_skips_guard(tmp_path):
    res = tmp_path / "res"
    write(res, "stars_history.json", stars_payload(["a"], 10))

    assert cr.compare(res, tmp_path / "does_not_exist", tolerance=0.02) == []


def test_other_metric_files_are_checked(tmp_path):
    base, res = tmp_path / "base", tmp_path / "res"
    write(base, "arxiv_mentions_history.json", {"total_papers": 60})
    write(res, "arxiv_mentions_history.json", {"total_papers": 12})

    violations = cr.compare(res, base, tolerance=0.02)

    assert any(v.metric == "total_papers" for v in violations)


def test_update_baseline_copies_results(tmp_path):
    base, res = tmp_path / "base", tmp_path / "res"
    payload = stars_payload(["a"], 10)
    write(res, "stars_history.json", payload)

    cr.update_baseline(res, base)

    assert json.loads((base / "stars_history.json").read_text()) == payload
