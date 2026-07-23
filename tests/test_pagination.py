"""Tests that pagination starts at the very first item.

Regression: each fetcher used to fetch ``X(first:1)``, take that first item's
cursor, and then paginate with ``after: <that cursor>``. Because ``after`` is
exclusive, the first stargazer / commit / issue of every repository was never
collected, undercounting every series by exactly one.
"""
import get_commits
import get_contributors
import get_stargazers


class FakeClient:
    """Returns the queued pages and records the variables of each call."""

    def __init__(self, pages, wrap):
        self.pages = list(pages)
        self.wrap = wrap
        self.calls = []

    def execute_query(self, query, variables):
        self.calls.append(variables)
        edges = self.pages.pop(0) if self.pages else []
        return self.wrap(edges)


def star_edge(login, cursor):
    return {"cursor": cursor, "starredAt": "2024-01-01T00:00:00Z",
            "node": {"name": None, "login": login}}


def wrap_stargazers(edges):
    return {"data": {"repository": {"stargazers": {"totalCount": len(edges), "edges": edges}}}}


def wrap_commits(edges):
    return {"data": {"repository": {"defaultBranchRef": {"target": {"history": {"edges": edges}}}}}}


def wrap_issues(edges):
    return {"data": {"repository": {"issues": {"totalCount": len(edges), "edges": edges}}}}


# --- stargazers -------------------------------------------------------------

def test_full_fetch_includes_the_first_stargazer():
    client = FakeClient([[star_edge("first", "c1"), star_edge("second", "c2")], []], wrap_stargazers)

    result = get_stargazers.get_stargazers(client, "repo")

    assert [e["node"]["login"] for e in result] == ["first", "second"]
    # Starts at the beginning rather than after the first stargazer's cursor.
    assert client.calls[0]["cursor"] is None


def test_stargazers_paginate_across_pages():
    client = FakeClient(
        [[star_edge("a", "c1")], [star_edge("b", "c2")], []], wrap_stargazers
    )

    result = get_stargazers.get_stargazers(client, "repo")

    assert [e["node"]["login"] for e in result] == ["a", "b"]
    assert [c["cursor"] for c in client.calls] == [None, "c1", "c2"]


def test_stargazers_incremental_resumes_from_cursor():
    client = FakeClient([[star_edge("new", "c9")], []], wrap_stargazers)

    get_stargazers.get_stargazers(client, "repo", start_cursor="cached-cursor")

    assert client.calls[0]["cursor"] == "cached-cursor"


def test_repository_without_stargazers_returns_empty():
    client = FakeClient([[]], wrap_stargazers)

    assert get_stargazers.get_stargazers(client, "repo") == []
    assert len(client.calls) == 1


# --- commits ----------------------------------------------------------------

def test_full_fetch_includes_the_first_commit():
    client = FakeClient(
        [[{"cursor": "c1", "node": {"oid": "aaa"}}, {"cursor": "c2", "node": {"oid": "bbb"}}], []],
        wrap_commits,
    )

    result = get_commits.get_commits(client, "repo")

    assert [e["node"]["oid"] for e in result] == ["aaa", "bbb"]
    assert client.calls[0]["cursor"] is None


def test_commits_without_default_branch_returns_empty():
    client = FakeClient([[]], lambda edges: {"data": {"repository": {"defaultBranchRef": None}}})

    assert get_commits.get_commits(client, "repo") == []


# --- contributors -----------------------------------------------------------

def test_full_fetch_includes_the_first_contributor_item():
    client = FakeClient(
        [[{"cursor": "c1", "node": {"title": "one"}}, {"cursor": "c2", "node": {"title": "two"}}], []],
        wrap_issues,
    )

    result = get_contributors.get_contributors(client, "issues", "repo")

    assert [e["node"]["title"] for e in result] == ["one", "two"]
    assert client.calls[0]["cursor"] is None


def test_contributors_incremental_resumes_from_cursor():
    client = FakeClient([[{"cursor": "c9", "node": {"title": "new"}}], []], wrap_issues)

    get_contributors.get_contributors(client, "issues", "repo", start_cursor="cached-cursor")

    assert client.calls[0]["cursor"] == "cached-cursor"
