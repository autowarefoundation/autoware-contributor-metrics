#!/usr/bin/env python3
"""Fetch citation counts from OpenAlex for Autoware-mentioning arXiv papers.

For each paper in cache/raw_arxiv_data/papers.json, queries OpenAlex via
the arXiv DOI form (10.48550/arXiv.<id>) and stores the work record. Then
aggregates counts_by_year across all papers into a yearly time series.
"""

import argparse
import datetime
import os
import time
from collections import defaultdict

import requests

from utils import write_json_output, load_json_file

PAPERS_CACHE = "cache/raw_arxiv_data/papers.json"
WORKS_CACHE = "cache/raw_arxiv_data/openalex_works.json"
OUTPUT_FILE = "results/arxiv_citations_history.json"

OPENALEX_DOI_URL = "https://api.openalex.org/works/doi:10.48550/arXiv.{arxiv_id}"
REQUEST_DELAY_SEC = 0.15  # ~7 req/sec, well under polite-pool limit
MAX_RETRIES = 4
START_YEAR = 2018


def build_session() -> requests.Session:
    """Build a requests session with the OpenAlex polite-pool User-Agent."""
    s = requests.Session()
    mailto = os.environ.get("OPENALEX_MAILTO", "yutaka.kondo@youtalk.jp")
    s.headers["User-Agent"] = f"autoware-contributor-metrics (mailto:{mailto})"
    return s


def fetch_work(session: requests.Session, arxiv_id: str) -> dict | None:
    """Fetch one OpenAlex work for an arXiv ID. Returns None on 404 / hard error."""
    url = OPENALEX_DOI_URL.format(arxiv_id=arxiv_id)
    for attempt in range(MAX_RETRIES):
        try:
            resp = session.get(url, timeout=30)
            if resp.status_code == 404:
                return None
            if resp.status_code == 429:
                wait = (attempt + 1) * 5
                print(f"  Rate limited. Waiting {wait}s...")
                time.sleep(wait)
                continue
            resp.raise_for_status()
            return resp.json()
        except requests.exceptions.RequestException as e:
            wait = 2 ** attempt
            print(f"  Error for {arxiv_id} (attempt {attempt + 1}): {e}. Retrying in {wait}s...")
            time.sleep(wait)
    return None


def slim_work(work: dict) -> dict:
    """Keep only the fields we need from the OpenAlex work record."""
    return {
        "openalex_id": work.get("id"),
        "title": work.get("title"),
        "cited_by_count": work.get("cited_by_count", 0),
        "publication_year": work.get("publication_year"),
        "counts_by_year": work.get("counts_by_year", []),
    }


def aggregate_yearly(works_by_id: dict[str, dict]) -> list[dict]:
    """Aggregate counts_by_year across all works into a sorted yearly series."""
    totals: dict[int, int] = defaultdict(int)
    for work in works_by_id.values():
        for entry in work.get("counts_by_year", []) or []:
            year = entry.get("year")
            count = entry.get("cited_by_count", 0)
            if isinstance(year, int) and year >= START_YEAR:
                totals[year] += count

    if not totals:
        return []

    end_year = max(totals.keys())
    out = []
    cumulative = 0
    for year in range(START_YEAR, end_year + 1):
        c = totals.get(year, 0)
        cumulative += c
        out.append({"year": year, "citations": c, "cumulative": cumulative})
    return out


def top_cited(works_by_id: dict[str, dict], papers_by_id: dict[str, dict], n: int = 10) -> list[dict]:
    """Return top-N cited papers with arXiv IDs and titles."""
    rows = []
    for arxiv_id, work in works_by_id.items():
        rows.append({
            "arxiv_id": arxiv_id,
            "title": papers_by_id.get(arxiv_id, {}).get("title") or work.get("title"),
            "cited_by_count": work.get("cited_by_count", 0),
            "publication_year": work.get("publication_year"),
        })
    rows.sort(key=lambda r: r["cited_by_count"], reverse=True)
    return rows[:n]


def main() -> None:
    parser = argparse.ArgumentParser(description="Fetch citation counts from OpenAlex")
    parser.add_argument(
        "--use-cache", action="store_true",
        help="Skip OpenAlex lookup for papers already cached",
    )
    parser.add_argument(
        "--refresh-all", action="store_true",
        help="Re-fetch all papers from OpenAlex even if cached",
    )
    args = parser.parse_args()

    papers = load_json_file(PAPERS_CACHE)
    if not papers:
        raise SystemExit(f"No papers in {PAPERS_CACHE}. Run get_arxiv_mentions.py first.")
    papers_by_id = {p["arxiv_id"]: p for p in papers}
    print(f"Loaded {len(papers)} papers")

    cached = load_json_file(WORKS_CACHE) if not args.refresh_all else {}
    if not isinstance(cached, dict):
        cached = {}
    print(f"Loaded {len(cached)} cached OpenAlex works")

    session = build_session()
    works_by_id: dict[str, dict] = dict(cached)
    not_found: list[str] = []

    to_fetch = [pid for pid in papers_by_id if pid not in works_by_id or not args.use_cache]
    if args.use_cache and not args.refresh_all:
        to_fetch = [pid for pid in papers_by_id if pid not in works_by_id]

    print(f"Fetching {len(to_fetch)} works from OpenAlex...")
    for i, arxiv_id in enumerate(to_fetch, 1):
        if i % 10 == 0 or i == len(to_fetch):
            print(f"  [{i}/{len(to_fetch)}] {arxiv_id}")
        work = fetch_work(session, arxiv_id)
        if work is None:
            not_found.append(arxiv_id)
            continue
        works_by_id[arxiv_id] = slim_work(work)
        time.sleep(REQUEST_DELAY_SEC)

    write_json_output(works_by_id, WORKS_CACHE)
    print(f"Cached {len(works_by_id)} OpenAlex works ({len(not_found)} not found)")

    yearly = aggregate_yearly(works_by_id)
    top = top_cited(works_by_id, papers_by_id, n=10)
    total_citations = sum(w.get("cited_by_count", 0) for w in works_by_id.values())

    output = {
        "yearly": yearly,
        "top_cited_papers": top,
        "total_citations": total_citations,
        "papers_with_data": len(works_by_id),
        "papers_not_found": not_found,
        "last_updated": datetime.date.today().strftime("%Y-%m-%d"),
        "source": "OpenAlex (via arXiv DOI)",
    }
    write_json_output(output, OUTPUT_FILE)

    print(f"\nDone! Generated {OUTPUT_FILE}")
    print(f"Total citations across all Autoware-mentioning arXiv papers: {total_citations}")
    if yearly:
        latest = yearly[-1]
        print(f"Latest year {latest['year']}: {latest['citations']} new, {latest['cumulative']} cumulative")
    print(f"\nTop 5 cited papers:")
    for row in top[:5]:
        print(f"  {row['cited_by_count']:>4}  {row['arxiv_id']}  {(row['title'] or '')[:70]}")


if __name__ == "__main__":
    main()
