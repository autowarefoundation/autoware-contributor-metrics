"""Tests for recording current star counts via the `stargazerCount` scalar.

GitHub fails every `stargazers(...)` connection query for some repositories but
still reports `stargazerCount` correctly. Recording that scalar keeps an
accurate current number for those repositories even though their per-date
history cannot be rebuilt.
"""
import check_regression as cr

# Reading the scalar count is covered by tests/test_stargazer_access.py, which
# owns the restricted-listing behaviour it is paired with.

# --- regression guard coverage of the current-count metrics -----------------

def _stars(counts_map, total):
    return {
        "total_stars_history": [{"date": "2026-01-01", "star_count": 1}],
        "current_star_counts": counts_map,
        "total_current_stars": total,
    }


def test_guard_flags_a_dropped_current_count_repo(tmp_path):
    import json
    base, res = tmp_path / "base", tmp_path / "res"
    for d, payload in ((base, _stars({"a": 5, "b": 5}, 10)), (res, _stars({"a": 5}, 5))):
        d.mkdir(parents=True, exist_ok=True)
        (d / "stars_history.json").write_text(json.dumps(payload))

    violations = cr.compare(res, base, tolerance=0.02)

    assert any(v.metric == "current_count_repos" for v in violations)


def test_guard_allows_current_counts_appearing_for_the_first_time(tmp_path):
    """An older baseline has no current_star_counts; adding them is growth."""
    import json
    base, res = tmp_path / "base", tmp_path / "res"
    base.mkdir(parents=True)
    (base / "stars_history.json").write_text(json.dumps(
        {"total_stars_history": [{"date": "2026-01-01", "star_count": 1}]}))
    res.mkdir(parents=True)
    (res / "stars_history.json").write_text(json.dumps(_stars({"a": 5}, 5)))

    assert cr.compare(res, base, tolerance=0.02) == []
