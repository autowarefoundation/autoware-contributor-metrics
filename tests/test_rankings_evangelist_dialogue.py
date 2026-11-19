"""Best Evangelist counts only issues and discussions that another person
commented on or reacted to."""
import json

import calculate_rankings as cr


def thread(author, commenters=(), reactors=None):
    node = {
        "author": {"login": author} if author else None,
        "createdAt": "2026-10-01T00:00:00Z",
        "comments": {"edges": [
            {"node": {"author": {"login": c}, "createdAt": "2026-10-02T00:00:00Z"}}
            for c in commenters
        ]},
    }
    # Threads cached before the query requested reactions have no key at all.
    if reactors is not None:
        node["reactions"] = {"nodes": [{"user": {"login": r} if r else None} for r in reactors]}
    return {"node": node}


def evangelist_counts(tmp_path, threads):
    path = tmp_path / "repo_issues.json"
    path.write_text(json.dumps(threads))
    calc = cr.RankingCalculator()
    calc.process_issues_discussions(str(path))
    return {a: sum(m.values()) for a, m in calc.community_contributions.items()}


def test_thread_with_peer_comment_counts_post_and_all_comments(tmp_path):
    counts = evangelist_counts(tmp_path, [thread("alice", commenters=["bob", "alice"])])
    assert counts == {"alice": 2, "bob": 1}


def test_thread_without_comments_does_not_count(tmp_path):
    assert evangelist_counts(tmp_path, [thread("alice")]) == {}


def test_author_talking_to_self_does_not_count(tmp_path):
    assert evangelist_counts(tmp_path, [thread("alice", commenters=["alice", "alice"])]) == {}


def test_bot_comment_does_not_count_as_peer(tmp_path):
    counts = evangelist_counts(
        tmp_path, [thread("alice", commenters=["github-actions[bot]", "stale"])]
    )
    assert counts == {}


def test_thread_with_deleted_author_counts_commenters(tmp_path):
    assert evangelist_counts(tmp_path, [thread(None, commenters=["bob"])]) == {"bob": 1}


def test_peer_reaction_counts_the_thread_but_not_the_reactor(tmp_path):
    assert evangelist_counts(tmp_path, [thread("alice", reactors=["bob"])]) == {"alice": 1}


def test_self_bot_and_deleted_user_reactions_do_not_count(tmp_path):
    counts = evangelist_counts(
        tmp_path, [thread("alice", reactors=["alice", "github-actions[bot]", None])]
    )
    assert counts == {}


def test_thread_without_reactions_key_still_uses_comments(tmp_path):
    assert evangelist_counts(tmp_path, [thread("alice", commenters=["bob"])]) == {"alice": 1, "bob": 1}
