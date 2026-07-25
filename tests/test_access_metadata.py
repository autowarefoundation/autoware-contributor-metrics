"""Tests for the access metadata published alongside star history.

The dashboard has to explain why some repositories have a current star count
but no history line, so the reason has to travel with the data rather than be
hardcoded in the page. It is derived from what actually happened in the run,
which means it disappears by itself if the token later gains access.
"""
import calculate_stargazers_history as calc


def status(permission, can_list, stars=10, failed=False):
    return {"stars": stars, "viewer_permission": permission,
            "can_list_stargazers": can_list, "listing_failed": failed}


def test_restricted_repos_are_reported():
    access = {
        "autoware": status("MAINTAIN", True),
        "vision_pilot": status("READ", False, stars=714),
        "agnocast": status("READ", False, stars=194),
    }

    meta = calc.build_access_metadata(access, history_repos={"autoware"})

    assert meta["restricted_repos"] == ["agnocast", "vision_pilot"]
    assert meta["restricted_repo_count"] == 2
    assert meta["history_repo_count"] == 1
    assert meta["tracked_repo_count"] == 3
    assert "github.blog" in meta["reference"]


def test_no_restrictions_reports_none():
    access = {"autoware": status("MAINTAIN", True), "AWSIM": status("WRITE", True)}

    meta = calc.build_access_metadata(access, history_repos={"autoware", "AWSIM"})

    assert meta["restricted_repos"] == []
    assert meta["restricted_repo_count"] == 0


def test_a_permitted_repo_that_failed_is_not_called_restricted():
    """A failed fetch is a different problem from being denied access."""
    access = {"autoware": status("MAINTAIN", True, failed=True)}

    meta = calc.build_access_metadata(access, history_repos=set())

    assert meta["restricted_repos"] == []


def test_without_an_archive_every_restricted_repo_has_no_history():
    """The default caller passes no frozen set; nothing may be claimed frozen."""
    access = {
        "autoware": status("MAINTAIN", True),
        "vision_pilot": status("READ", False, stars=714),
    }

    meta = calc.build_access_metadata(access, history_repos={"autoware"})

    assert meta["frozen_history_repos"] == []
    assert meta["no_history_repos"] == ["vision_pilot"]
    assert "frozen_captured_at" not in meta


def test_missing_access_status_yields_no_metadata():
    """Older caches have no access file; the page must simply show no notice."""
    assert calc.build_access_metadata({}, history_repos={"autoware"}) is None
    assert calc.build_access_metadata(None, history_repos={"autoware"}) is None
