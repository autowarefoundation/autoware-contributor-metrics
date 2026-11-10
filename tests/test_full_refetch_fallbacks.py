"""The Monday full re-fetch must not fail on arXiv, and the incremental fetch
must find new discussions."""
import get_arxiv_mentions as am
import get_contributors as gc


def paper(arxiv_id, published="2026-01-01T00:00:00Z", title="t"):
    return {"arxiv_id": arxiv_id, "published": published, "title": title}


def ids(papers):
    return [p["arxiv_id"] for p in papers]


def test_complete_full_refetch_replaces_the_cache():
    out = am.merge_papers([paper("old")], [paper("new")], complete=True, use_cache=False)
    assert ids(out) == ["new"]


def test_failed_full_refetch_keeps_the_cache():
    out = am.merge_papers([paper("a"), paper("b")], [], complete=False, use_cache=False)
    assert ids(out) == ["a", "b"]


def test_partial_full_refetch_merges_onto_the_cache():
    cached = [paper("a", title="old"), paper("b")]
    fetched = [paper("a", title="new")]
    out = am.merge_papers(cached, fetched, complete=False, use_cache=False)
    assert ids(out) == ["a", "b"]
    assert out[0]["title"] == "new"


def test_incremental_fetch_merges_and_sorts_by_date():
    cached = [paper("b", published="2025-01-01T00:00:00Z")]
    fetched = [paper("a", published="2024-01-01T00:00:00Z")]
    out = am.merge_papers(cached, fetched, complete=True, use_cache=True)
    assert ids(out) == ["a", "b"]


def edge(created_at):
    return {"cursor": created_at, "node": {"createdAt": created_at}}


def test_cache_in_creation_order_is_ascending():
    edges = [edge("2026-01-01T00:00:00Z"), edge("2026-01-01T00:00:00Z"), edge("2026-02-01T00:00:00Z")]
    assert gc.is_created_ascending(edges)


def test_cache_in_update_order_is_not_ascending():
    edges = [edge("2026-02-01T00:00:00Z"), edge("2026-01-01T00:00:00Z")]
    assert not gc.is_created_ascending(edges)


def test_empty_cache_is_ascending():
    assert gc.is_created_ascending([])
