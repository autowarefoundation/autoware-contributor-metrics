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


def activity_payload(prs_repos, issue_repos):
    payload = {f"{r}_merged_prs_history": [] for r in prs_repos}
    payload.update({f"{r}_resolved_issues_history": [] for r in issue_repos})
    payload["total_merged_prs_history"] = []
    payload["total_resolved_issues_history"] = []
    return payload


def test_repository_leaving_the_tracked_list_is_not_a_regression(tmp_path):
    """The real case: openadkit fell out of the top 25 and autoware_off-road_sim,
    which has pull requests but no issues, took its place (72 -> 71 series)."""
    base, res = tmp_path / "base", tmp_path / "res"
    write(base, "activity_history.json",
          activity_payload(["a", "openadkit"], ["a", "openadkit"]))
    write(res, "activity_history.json",
          activity_payload(["a", "off_road"], ["a"]))

    assert cr.compare(res, base, tolerance=0.02, tracked={"a", "off_road"}) == []


def test_tracked_repository_losing_a_series_is_a_regression(tmp_path):
    base, res = tmp_path / "base", tmp_path / "res"
    write(base, "activity_history.json", activity_payload(["a", "b"], ["a", "b"]))
    write(res, "activity_history.json", activity_payload(["a", "b"], ["a"]))

    violations = cr.compare(res, base, tolerance=0.02, tracked={"a", "b"})

    assert [v.metric for v in violations] == ["repo_series"]
    assert "b_resolved_issues_history" in violations[0].detail


def test_new_series_cannot_hide_a_lost_one(tmp_path):
    """A plain count stays equal here, but a tracked series still vanished."""
    base, res = tmp_path / "base", tmp_path / "res"
    write(base, "commits_history.json",
          {"a_commits_history": [], "b_commits_history": []})
    write(res, "commits_history.json",
          {"a_commits_history": [], "c_commits_history": []})

    violations = cr.compare(res, base, tolerance=0.02, tracked={"a", "b", "c"})

    assert len(violations) == 1
    assert violations[0].detail == "missing: b_commits_history"


def test_total_series_are_not_repositories(tmp_path):
    base, res = tmp_path / "base", tmp_path / "res"
    write(base, "activity_history.json", activity_payload(["a"], ["a"]))
    write(res, "activity_history.json", activity_payload(["a"], ["a"]))

    assert cr.compare(res, base, tolerance=0.02, tracked={"a"}) == []


def test_missing_repository_list_requires_every_series(tmp_path):
    assert cr.load_tracked(tmp_path / "absent.json") is None

    path = tmp_path / "repositories.json"
    path.write_text(json.dumps({"repositories": ["a", "b"]}))
    assert cr.load_tracked(path) == {"a", "b"}
