"""Tests for the committed archive of unlistable repositories' stargazers.

This data cannot be re-fetched, so the loader is deliberately strict where the
rest of the pipeline is forgiving: every way the file can be wrong has to raise
rather than quietly yield fewer repositories. Silent degradation is the exact
failure that made the archive necessary in the first place.
"""
import json

import pytest

import frozen_star_history as fsh


def write_archive(tmp_path, payload):
    path = tmp_path / "frozen_star_history.json"
    path.write_text(json.dumps(payload))
    return str(path)


def valid_payload(**overrides):
    payload = {
        "captured_at": "2025-12-04",
        "reference": "https://github.blog/changelog/whatever",
        "repositories": {
            "autoware_ai": [["alice", "2019-03-04"], ["bob", "2020-01-31"]],
        },
    }
    payload.update(overrides)
    return payload


def test_loads_capture_date_and_records(tmp_path):
    archive = fsh.load_frozen_star_history(write_archive(tmp_path, valid_payload()))

    assert archive.captured_at == "2025-12-04"
    assert archive.repositories == {
        "autoware_ai": [("alice", "2019-03-04"), ("bob", "2020-01-31")]
    }


def test_records_keep_their_original_order(tmp_path):
    """Order mirrors the live cache these records stand in for."""
    payload = valid_payload(repositories={
        "autoware_ai": [["zoe", "2019-03-04"], ["adam", "2019-03-05"]],
    })

    archive = fsh.load_frozen_star_history(write_archive(tmp_path, payload))

    assert [login for login, _ in archive.repositories["autoware_ai"]] == ["zoe", "adam"]


def test_missing_file_raises(tmp_path):
    """Never degrade to "no frozen history": that is how the data was lost."""
    with pytest.raises(FileNotFoundError):
        fsh.load_frozen_star_history(str(tmp_path / "absent.json"))


def test_malformed_json_raises(tmp_path):
    path = tmp_path / "frozen_star_history.json"
    path.write_text("{ not json")

    with pytest.raises(json.JSONDecodeError):
        fsh.load_frozen_star_history(str(path))


@pytest.mark.parametrize("payload", [
    pytest.param([], id="top level is not an object"),
    pytest.param({"repositories": {}}, id="captured_at missing"),
    pytest.param({"captured_at": "", "repositories": {}}, id="captured_at empty"),
    pytest.param({"captured_at": "yesterday", "repositories": {}}, id="captured_at not a date"),
    pytest.param({"captured_at": "2025-12-04"}, id="repositories missing"),
    pytest.param({"captured_at": "2025-12-04", "repositories": []}, id="repositories not an object"),
])
def test_malformed_envelope_raises(tmp_path, payload):
    with pytest.raises(ValueError):
        fsh.load_frozen_star_history(write_archive(tmp_path, payload))


@pytest.mark.parametrize("records", [
    pytest.param("alice", id="records not a list"),
    pytest.param([["alice"]], id="record missing the date"),
    pytest.param([["alice", "2019-03-04", "extra"]], id="record has a third field"),
    pytest.param([["", "2019-03-04"]], id="login empty"),
    pytest.param([[None, "2019-03-04"]], id="login not a string"),
    pytest.param([["alice", "2019-03-04T00:00:00Z"]], id="date is a timestamp"),
    pytest.param([["alice", "04/03/2019"]], id="date is not ISO"),
    pytest.param([["alice", "2019-02-30"]], id="date does not exist"),
])
def test_malformed_record_raises(tmp_path, records):
    payload = valid_payload(repositories={"autoware_ai": records})

    with pytest.raises(ValueError):
        fsh.load_frozen_star_history(write_archive(tmp_path, payload))


def test_error_message_names_the_repository(tmp_path):
    """A 940-record file is unreadable without knowing which entry is wrong."""
    payload = valid_payload(repositories={
        "autoware_ai": [["alice", "2019-03-04"]],
        "autoware_ai_perception": [["bob", "nonsense"]],
    })

    with pytest.raises(ValueError, match="autoware_ai_perception"):
        fsh.load_frozen_star_history(write_archive(tmp_path, payload))


def test_unknown_repositories_are_reported_not_fatal(tmp_path):
    """A rename orphans an entry. Worth noticing, not worth failing over."""
    payload = valid_payload(repositories={
        "autoware_ai": [["alice", "2019-03-04"]],
        "autoware_vision_pilot": [["bob", "2025-01-01"]],
    })
    archive = fsh.load_frozen_star_history(write_archive(tmp_path, payload))

    unknown = archive.unknown_repositories({"autoware_ai", "vision_pilot"})

    assert unknown == ["autoware_vision_pilot"]


def test_the_committed_archive_is_valid():
    """The real file, loaded the way the pipeline loads it."""
    archive = fsh.load_frozen_star_history()

    assert archive.captured_at == "2025-12-04"
    assert len(archive.repositories) == 12
    assert sum(len(r) for r in archive.repositories.values()) == 940
    assert all(repo.startswith("autoware_ai") for repo in archive.repositories)
