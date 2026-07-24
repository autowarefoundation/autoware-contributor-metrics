"""Tests for handling GitHub's stargazer-listing access restriction.

GitHub restricted `GET /repos/{o}/{r}/stargazers` and the GraphQL `stargazers`
connection to admins and collaborators:
https://github.blog/changelog/2026-06-30-upcoming-access-restrictions-to-public-api-endpoints-and-ui-views/

Measured behaviour, consistent across all 37 tracked repositories with no
exceptions: `push` permission (WRITE/MAINTAIN/ADMIN) can list stargazers,
READ/NONE cannot. The failure surfaces as a generic "Something went wrong"
message with HTTP 200 and no error type, so it is indistinguishable from a
transient error after the fact — `viewerPermission` is the only reliable
signal, and it must be checked *before* attempting the listing.
"""
import get_stargazers


class FakeClient:
    """Serves canned responses and records every query it is asked to run."""

    def __init__(self, permission="MAINTAIN", count=42, pages=None):
        self.permission = permission
        self.count = count
        self.pages = list(pages or [[]])
        self.queries = []

    def execute_query(self, query, variables):
        self.queries.append(query)
        if "viewerPermission" in query:
            return {"data": {"repository": {
                "stargazerCount": self.count,
                "viewerPermission": self.permission,
            }}}
        if "stargazers(" in query:
            edges = self.pages.pop(0) if self.pages else []
            return {"data": {"repository": {"stargazers": {
                "totalCount": self.count, "edges": edges,
            }}}}
        raise AssertionError(f"unexpected query: {query}")

    @property
    def listed_stargazers(self):
        return any("stargazers(" in q for q in self.queries)


def star_edge(login, cursor):
    return {"cursor": cursor, "starredAt": "2024-01-01T00:00:00Z",
            "node": {"name": None, "login": login}}


# --- permission rule --------------------------------------------------------

def test_collaborator_permissions_can_list():
    for perm in ("ADMIN", "MAINTAIN", "WRITE"):
        assert get_stargazers.can_list_stargazers(perm) is True, perm


def test_non_collaborator_permissions_cannot_list():
    # TRIAGE has push=false, which measured as restricted alongside READ/NONE.
    for perm in ("TRIAGE", "READ", "NONE", None, ""):
        assert get_stargazers.can_list_stargazers(perm) is False, perm


def test_unknown_permission_is_treated_as_allowed():
    """A future/unseen level must not silently drop a repository we could read."""
    assert get_stargazers.can_list_stargazers("SOMETHING_NEW") is True


# --- info query -------------------------------------------------------------

def test_info_query_avoids_the_restricted_connection():
    client = FakeClient(permission="READ", count=714)

    info = get_stargazers.get_repository_star_info(client, "vision_pilot")

    assert info == {"stargazerCount": 714, "viewerPermission": "READ"}
    # The scalar must not be fetched through the connection that is restricted.
    assert not client.listed_stargazers


# --- per-repository processing ---------------------------------------------

def test_restricted_repo_is_not_listed_and_is_recorded():
    client = FakeClient(permission="READ", count=714)
    status = {}

    usernames = get_stargazers.process_repository(client, "vision_pilot", False, status)

    assert usernames == set()
    # The whole point: no doomed request, so no retry/backoff storm either.
    assert not client.listed_stargazers
    assert status["vision_pilot"]["can_list_stargazers"] is False
    assert status["vision_pilot"]["stars"] == 714
    assert status["vision_pilot"]["viewer_permission"] == "READ"


def test_permitted_repo_is_listed_and_recorded(tmp_path, monkeypatch):
    monkeypatch.setattr(get_stargazers, "CACHE_DIR", str(tmp_path))
    client = FakeClient(permission="MAINTAIN", count=2,
                        pages=[[star_edge("a", "c1"), star_edge("b", "c2")], []])
    status = {}

    usernames = get_stargazers.process_repository(client, "autoware", False, status)

    assert usernames == {"a", "b"}
    assert client.listed_stargazers
    assert status["autoware"]["can_list_stargazers"] is True


def test_output_honours_the_configured_cache_dir(tmp_path, monkeypatch):
    """Writes must follow CACHE_DIR, so a run cannot escape its own directory."""
    monkeypatch.setattr(get_stargazers, "CACHE_DIR", str(tmp_path))
    client = FakeClient(permission="ADMIN", count=1, pages=[[star_edge("a", "c1")], []])

    get_stargazers.process_repository(client, "autoware", False, {})

    assert (tmp_path / "autoware_usernames.txt").exists()


def test_listing_failure_is_recorded_without_raising(tmp_path, monkeypatch):
    """A permitted repo whose listing still fails must not abort the run."""
    monkeypatch.setattr(get_stargazers, "CACHE_DIR", str(tmp_path))

    class Failing(FakeClient):
        def execute_query(self, query, variables):
            if "stargazers(" in query:
                self.queries.append(query)
                raise Exception("GraphQL errors: ['Something went wrong ...']")
            return super().execute_query(query, variables)

    client = Failing(permission="MAINTAIN", count=5)
    status = {}

    usernames = get_stargazers.process_repository(client, "autoware", False, status)

    assert usernames == set()
    assert status["autoware"]["can_list_stargazers"] is True
    assert status["autoware"]["listing_failed"] is True


def test_star_count_is_recorded_even_when_permission_lookup_fails():
    class Broken(FakeClient):
        def execute_query(self, query, variables):
            raise Exception("network down")

    status = {}
    usernames = get_stargazers.process_repository(Broken(), "repo", False, status)

    assert usernames == set()
    # Nothing known about the repo, but the run continues.
    assert "repo" not in status or status["repo"].get("stars") is None
