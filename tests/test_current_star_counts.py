"""Tests for recording current star counts via the `stargazerCount` scalar.

GitHub fails every `stargazers(...)` connection query for some repositories but
still reports `stargazerCount` correctly. Recording that scalar keeps an
accurate current number for those repositories even though their per-date
history cannot be rebuilt.
"""
import check_regression as cr
import get_stargazers


class CountClient:
    """Answers stargazerCount queries; optionally fails for some repositories."""

    def __init__(self, counts, broken=()):
        self.counts = counts
        self.broken = set(broken)
        self.queried = []

    def execute_query(self, query, variables):
        repo = variables["repository"]
        self.queried.append(repo)
        if repo in self.broken:
            raise Exception("GraphQL errors: ['Something went wrong ...']")
        return {"data": {"repository": {"stargazerCount": self.counts[repo]}}}


def test_reads_the_scalar_count():
    client = CountClient({"vision_pilot": 710})

    assert get_stargazers.get_stargazer_count(client, "vision_pilot") == 710


def test_count_query_does_not_use_the_stargazers_connection():
    """The whole point: avoid the connection that is broken for these repos."""
    captured = {}

    class Recorder:
        def execute_query(self, query, variables):
            captured["query"] = query
            return {"data": {"repository": {"stargazerCount": 1}}}

    get_stargazers.get_stargazer_count(Recorder(), "repo")

    assert "stargazerCount" in captured["query"]
    assert "stargazers(" not in captured["query"]


# --- regression guard coverage of the new metrics ---------------------------

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
