"""Best Committer counts only merged PRs that another person reviewed.

The rule follows the maintainers' position in
https://github.com/autowarefoundation/autoware-contributor-metrics/issues/7#issuecomment-4033621189
"""
import json

import calculate_rankings as cr


def pr(author, merged_at="2026-10-01T00:00:00Z", reviewers=(), commenters=()):
    return {"node": {
        "author": {"login": author},
        "createdAt": "2026-09-30T00:00:00Z",
        "mergedAt": merged_at,
        "reviews": {"edges": [
            {"node": {"author": {"login": r}, "createdAt": "2026-09-30T12:00:00Z"}}
            for r in reviewers
        ]},
        "comments": {"edges": [
            {"node": {"author": {"login": c}, "createdAt": "2026-09-30T12:00:00Z"}}
            for c in commenters
        ]},
    }}


def committer_counts(tmp_path, prs):
    path = tmp_path / "repo_prs.json"
    path.write_text(json.dumps(prs))
    calc = cr.RankingCalculator()
    calc.process_prs_and_reviews(str(path))
    return {a: sum(m.values()) for a, m in calc.code_contributions.items()}, calc


def test_peer_reviewed_merged_pr_counts(tmp_path):
    counts, _ = committer_counts(tmp_path, [pr("alice", reviewers=["bob"])])
    assert counts == {"alice": 1}


def test_unreviewed_merged_pr_does_not_count(tmp_path):
    counts, _ = committer_counts(tmp_path, [pr("alice")])
    assert counts == {}


def test_self_review_does_not_count(tmp_path):
    counts, _ = committer_counts(tmp_path, [pr("alice", reviewers=["alice"])])
    assert counts == {}


def test_bot_review_does_not_count(tmp_path):
    counts, _ = committer_counts(
        tmp_path, [pr("alice", reviewers=["copilot-pull-request-reviewer", "coderabbitai[bot]"])]
    )
    assert counts == {}


def test_comment_alone_is_not_a_review(tmp_path):
    counts, _ = committer_counts(tmp_path, [pr("alice", commenters=["bob"])])
    assert counts == {}


def test_unmerged_pr_does_not_count_even_when_reviewed(tmp_path):
    counts, _ = committer_counts(tmp_path, [pr("alice", merged_at=None, reviewers=["bob"])])
    assert counts == {}


def test_reviewer_credit_is_unchanged(tmp_path):
    """The rule changes Best Committer only. The reviewer still gets credit."""
    _, calc = committer_counts(tmp_path, [pr("alice", reviewers=["bob"]), pr("carol", reviewers=["bob"])])
    assert sum(calc.review_contributions["bob"].values()) == 2
