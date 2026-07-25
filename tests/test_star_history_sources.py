"""Tests for where each repository's star history comes from.

Two sources feed the same series: the live cache, re-fetched every run, and the
committed archive for repositories GitHub no longer lets us list. Which one
wins, and what the published data says about it, is the whole point of the
archive — a frozen line that silently claims to be current would be worse than
the missing line it replaced.
"""
import json

import calculate_stargazers_history as calc
from frozen_star_history import FrozenStarHistory


def write_live(cache_dir, repository, records):
    """Write a live cache file in the shape get_stargazers.py produces."""
    cache_dir.mkdir(parents=True, exist_ok=True)
    edges = [
        {"cursor": f"c{i}", "starredAt": f"{date}T00:00:00Z",
         "node": {"name": None, "login": login}}
        for i, (login, date) in enumerate(records)
    ]
    (cache_dir / f"{repository}_stargazers.json").write_text(json.dumps(edges))


def frozen(**repositories):
    return FrozenStarHistory(captured_at="2025-12-04", repositories=repositories)


def final_count(series):
    return series[-1]["star_count"]


def test_live_only_repository_is_not_marked_frozen(tmp_path):
    write_live(tmp_path, "autoware", [("alice", "2024-01-01")])

    built = calc.build_star_histories(["autoware"], frozen(), cache_dir=tmp_path)

    assert final_count(built.series["autoware_stars_history"]) == 1
    assert built.history_repos == {"autoware"}
    assert built.frozen_sources == {}


def test_archive_supplies_a_repository_the_cache_lost(tmp_path):
    built = calc.build_star_histories(
        ["autoware_ai_perception"],
        frozen(autoware_ai_perception=[("alice", "2019-03-04"), ("bob", "2025-11-27")]),
        cache_dir=tmp_path,
    )

    assert final_count(built.series["autoware_ai_perception_stars_history"]) == 2
    assert built.history_repos == {"autoware_ai_perception"}
    assert built.frozen_sources == {
        "autoware_ai_perception": {"source": "frozen", "last_star_at": "2025-11-27"},
    }


def test_live_cache_wins_over_the_archive(tmp_path):
    """A live file is always a complete listing, so it replaces the archive
    outright. Merging could only resurrect people who have since unstarred."""
    write_live(tmp_path, "autoware_ai_utilities", [("alice", "2024-01-01")])

    built = calc.build_star_histories(
        ["autoware_ai_utilities"],
        frozen(autoware_ai_utilities=[("alice", "2024-01-01"), ("ghost", "2024-02-02")]),
        cache_dir=tmp_path,
    )

    assert final_count(built.series["autoware_ai_utilities_stars_history"]) == 1
    assert built.frozen_sources == {}


def test_a_repository_with_neither_source_is_skipped(tmp_path):
    built = calc.build_star_histories(["auto_e2e"], frozen(), cache_dir=tmp_path)

    assert built.series == {}
    assert built.history_repos == set()
    assert built.frozen_sources == {}


def test_frozen_people_join_the_unique_total(tmp_path):
    write_live(tmp_path, "autoware", [("alice", "2024-01-01")])

    built = calc.build_star_histories(
        ["autoware", "autoware_ai"],
        frozen(autoware_ai=[("bob", "2023-06-15")]),
        cache_dir=tmp_path,
    )

    assert final_count(built.total) == 2


def test_a_person_in_both_sources_is_counted_once_at_the_earlier_date(tmp_path):
    write_live(tmp_path, "autoware", [("alice", "2024-01-01")])

    built = calc.build_star_histories(
        ["autoware", "autoware_ai"],
        frozen(autoware_ai=[("alice", "2019-03-04")]),
        cache_dir=tmp_path,
    )

    assert final_count(built.total) == 1
    assert built.total[0]["date"] == "2019-03-04"


def test_the_archive_does_not_invent_repositories(tmp_path):
    """Only repositories still being tracked are read out of the archive."""
    built = calc.build_star_histories(
        ["autoware"],
        frozen(autoware_vision_pilot=[("alice", "2025-01-01")]),
        cache_dir=tmp_path,
    )

    assert built.series == {}


def test_access_metadata_splits_frozen_from_no_history():
    access = {
        "autoware": {"can_list_stargazers": True},
        "autoware_ai_perception": {"can_list_stargazers": False},
        "vision_pilot": {"can_list_stargazers": False},
        "auto_e2e": {"can_list_stargazers": False},
    }

    meta = calc.build_access_metadata(
        access,
        history_repos={"autoware", "autoware_ai_perception"},
        frozen_repos={"autoware_ai_perception"},
        frozen_captured_at="2025-12-04",
    )

    assert meta["restricted_repos"] == ["auto_e2e", "autoware_ai_perception", "vision_pilot"]
    assert meta["frozen_history_repos"] == ["autoware_ai_perception"]
    assert meta["no_history_repos"] == ["auto_e2e", "vision_pilot"]
    assert meta["frozen_captured_at"] == "2025-12-04"
    assert meta["history_repo_count"] == 2


def test_access_metadata_omits_the_capture_date_when_nothing_is_frozen():
    """The note must not offer a date for records that do not exist."""
    access = {"vision_pilot": {"can_list_stargazers": False}}

    meta = calc.build_access_metadata(access, history_repos=set(), frozen_repos=set(),
                                      frozen_captured_at="2025-12-04")

    assert meta["frozen_history_repos"] == []
    assert meta["no_history_repos"] == ["vision_pilot"]
    assert "frozen_captured_at" not in meta
