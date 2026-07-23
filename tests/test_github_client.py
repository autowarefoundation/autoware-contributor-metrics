"""Tests for GitHubGraphQLClient retry/backoff behavior.

Focus: transient GraphQL server errors ("Something went wrong while executing
your query ...") must be retried with backoff instead of failing on the first
occurrence, while genuinely permanent GraphQL errors must still fail fast.
"""
from unittest import mock

import pytest
import requests

import github_client
from github_client import GitHubGraphQLClient, _looks_transient


class FakeResponse:
    """Minimal stand-in for requests.Response used by execute_query."""

    def __init__(self, json_data, status_code=200, remaining=5000, reset=0):
        self._json = json_data
        self.status_code = status_code
        self.headers = {
            "X-RateLimit-Remaining": str(remaining),
            "X-RateLimit-Reset": str(reset),
        }

    def json(self):
        return self._json

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.exceptions.HTTPError(f"status {self.status_code}")


def make_client(**overrides):
    """Client with zero backoff so tests run instantly."""
    params = dict(
        token="test-token",
        max_retries=4,
        base_backoff=0,
        max_backoff=0,
        backoff_jitter=0,
        request_delay=0,
    )
    params.update(overrides)
    return GitHubGraphQLClient(**params)


TRANSIENT_ERR = {
    "errors": [{
        "message": (
            "Something went wrong while executing your query on "
            "2026-07-23T17:51:26Z. Please include `440B:FC98C:E2A118` when "
            "reporting this issue."
        )
    }]
}
OK = {"data": {"ok": True}}


def test_transient_graphql_error_is_retried_then_succeeds():
    client = make_client()
    responses = [FakeResponse(TRANSIENT_ERR), FakeResponse(OK)]
    with mock.patch.object(github_client.requests, "post", side_effect=responses) as post, \
            mock.patch.object(github_client.time, "sleep"):
        result = client.execute_query("query {}", {})
    assert result == OK
    assert post.call_count == 2


def test_transient_graphql_error_exhausts_retries_then_raises():
    client = make_client()
    with mock.patch.object(github_client.requests, "post",
                           return_value=FakeResponse(TRANSIENT_ERR)) as post, \
            mock.patch.object(github_client.time, "sleep"):
        with pytest.raises(Exception) as excinfo:
            client.execute_query("query {}", {})
    assert post.call_count == client.max_retries
    assert "retries" in str(excinfo.value).lower()


def test_non_transient_graphql_error_fails_fast_without_retry():
    client = make_client()
    err = {"errors": [{"message": "Field 'bogus' doesn't exist on type 'Query'"}]}
    with mock.patch.object(github_client.requests, "post",
                           return_value=FakeResponse(err)) as post, \
            mock.patch.object(github_client.time, "sleep"):
        with pytest.raises(Exception):
            client.execute_query("query {}", {})
    assert post.call_count == 1


def test_graphql_rate_limit_error_is_retried():
    client = make_client()
    rl = {"errors": [{"message": "API rate limit exceeded for user"}]}
    responses = [FakeResponse(rl), FakeResponse(OK)]
    with mock.patch.object(github_client.requests, "post", side_effect=responses) as post, \
            mock.patch.object(github_client.time, "sleep"):
        result = client.execute_query("q", {})
    assert result == OK
    assert post.call_count == 2


def test_persistent_network_error_raises_instead_of_exiting():
    """A give-up on network errors must raise (so the caller can skip one repo),
    not sys.exit the whole process."""
    client = make_client()
    with mock.patch.object(github_client.requests, "post",
                           side_effect=requests.exceptions.ConnectionError("boom")), \
            mock.patch.object(github_client.time, "sleep"):
        with pytest.raises(Exception):
            client.execute_query("q", {})


def test_looks_transient_signatures():
    assert _looks_transient("something went wrong while executing your query")
    assert _looks_transient("service_unavailable")
    assert _looks_transient("the request timed out")
    assert _looks_transient("internal error occurred")
    assert not _looks_transient("field 'x' doesn't exist")
    assert not _looks_transient("could not resolve to a repository with the name")
