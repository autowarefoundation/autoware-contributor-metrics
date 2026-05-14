#!/usr/bin/env python3
"""Fetch arXiv papers mentioning Autoware and aggregate yearly counts.

Queries the arXiv API for papers containing "autoware" in title, abstract,
or full-text fields, caches the raw entries, and produces a yearly
time-series of new submissions plus a cumulative total.
"""

import argparse
import datetime
import time
import xml.etree.ElementTree as ET
from collections import defaultdict
from pathlib import Path

import requests

from utils import write_json_output, load_json_file

ARXIV_API_URL = "http://export.arxiv.org/api/query"
ATOM_NS = {"atom": "http://www.w3.org/2005/Atom"}

CACHE_FILE = "cache/raw_arxiv_data/papers.json"
OUTPUT_FILE = "results/arxiv_mentions_history.json"

SEARCH_QUERY = "all:autoware"
PAGE_SIZE = 200
REQUEST_DELAY_SEC = 3.5
MAX_RETRIES = 5
START_MONTH = "2018-01"


def fetch_page(start: int, max_results: int) -> str:
    """Fetch one page of results from arXiv API. Returns Atom XML text."""
    params = {
        "search_query": SEARCH_QUERY,
        "start": start,
        "max_results": max_results,
        "sortBy": "submittedDate",
        "sortOrder": "ascending",
    }
    for attempt in range(MAX_RETRIES):
        try:
            resp = requests.get(ARXIV_API_URL, params=params, timeout=60)
            resp.raise_for_status()
            return resp.text
        except requests.exceptions.RequestException as e:
            wait = 2 ** attempt * REQUEST_DELAY_SEC
            print(f"  Error (attempt {attempt + 1}): {e}. Retrying in {wait:.1f}s...")
            time.sleep(wait)
    raise RuntimeError(f"Failed to fetch arXiv page at start={start} after {MAX_RETRIES} retries")


def parse_entries(xml_text: str) -> list[dict]:
    """Parse arXiv Atom XML and extract paper entries."""
    root = ET.fromstring(xml_text)
    entries = []
    for entry in root.findall("atom:entry", ATOM_NS):
        id_url = entry.findtext("atom:id", default="", namespaces=ATOM_NS)
        title = (entry.findtext("atom:title", default="", namespaces=ATOM_NS) or "").strip()
        published = entry.findtext("atom:published", default="", namespaces=ATOM_NS)
        updated = entry.findtext("atom:updated", default="", namespaces=ATOM_NS)
        summary = (entry.findtext("atom:summary", default="", namespaces=ATOM_NS) or "").strip()
        authors = [
            a.findtext("atom:name", default="", namespaces=ATOM_NS)
            for a in entry.findall("atom:author", ATOM_NS)
        ]
        # arxiv_id like "2106.12345" extracted from "http://arxiv.org/abs/2106.12345v2"
        arxiv_id = id_url.rsplit("/", 1)[-1].split("v")[0] if id_url else ""
        if not arxiv_id or not published:
            continue
        entries.append({
            "arxiv_id": arxiv_id,
            "title": title,
            "summary": summary,
            "published": published,
            "updated": updated,
            "authors": authors,
        })
    return entries


def fetch_all(known_ids: set[str]) -> list[dict]:
    """Fetch all matching entries, skipping those already in known_ids when possible."""
    all_entries: list[dict] = []
    start = 0
    while True:
        print(f"Fetching arXiv start={start}...")
        xml_text = fetch_page(start, PAGE_SIZE)
        entries = parse_entries(xml_text)
        if not entries:
            print("  No more entries.")
            break
        new_count = sum(1 for e in entries if e["arxiv_id"] not in known_ids)
        all_entries.extend(entries)
        print(f"  Got {len(entries)} entries ({new_count} new)")
        if len(entries) < PAGE_SIZE:
            break
        start += PAGE_SIZE
        time.sleep(REQUEST_DELAY_SEC)
    return all_entries


def aggregate_yearly(papers: list[dict]) -> dict[int, int]:
    """Count papers per year based on the published date."""
    counts: dict[int, int] = defaultdict(int)
    start_year = int(START_MONTH[:4])
    for p in papers:
        pub = p.get("published", "")
        if len(pub) < 4:
            continue
        try:
            year = int(pub[:4])
        except ValueError:
            continue
        if year < start_year:
            continue
        counts[year] += 1
    return dict(counts)


def fill_missing_years(counts: dict[int, int], end_year: int) -> list[dict]:
    """Return a sorted yearly list with zeros filled in for gaps."""
    if not counts:
        return []
    start_year = int(START_MONTH[:4])
    end = max(end_year, max(counts.keys()))
    out = []
    cumulative = 0
    for year in range(start_year, end + 1):
        c = counts.get(year, 0)
        cumulative += c
        out.append({"year": year, "count": c, "cumulative": cumulative})
    return out


def main() -> None:
    parser = argparse.ArgumentParser(description="Fetch arXiv papers mentioning Autoware")
    parser.add_argument(
        "--use-cache", action="store_true",
        help="Reuse cached papers and only append new entries since last fetch",
    )
    args = parser.parse_args()

    Path(CACHE_FILE).parent.mkdir(parents=True, exist_ok=True)

    cached = load_json_file(CACHE_FILE) if args.use_cache else []
    cached_by_id: dict[str, dict] = {p["arxiv_id"]: p for p in cached if isinstance(p, dict)}
    known_ids = set(cached_by_id.keys())
    print(f"Loaded {len(known_ids)} cached papers")

    fetched = fetch_all(known_ids)
    for e in fetched:
        cached_by_id[e["arxiv_id"]] = e

    papers = sorted(cached_by_id.values(), key=lambda x: x.get("published", ""))
    write_json_output(papers, CACHE_FILE)
    print(f"Cached {len(papers)} total papers")

    today = datetime.date.today()
    yearly_counts = aggregate_yearly(papers)
    yearly_history = fill_missing_years(yearly_counts, today.year)

    output = {
        "yearly": yearly_history,
        "total_papers": len(papers),
        "last_updated": today.strftime("%Y-%m-%d"),
        "query": SEARCH_QUERY,
    }
    write_json_output(output, OUTPUT_FILE)
    print(f"\nDone! Generated {OUTPUT_FILE}")
    print(f"Total papers mentioning Autoware: {len(papers)}")
    if yearly_history:
        latest = yearly_history[-1]
        print(f"Latest year {latest['year']}: {latest['count']} new, {latest['cumulative']} cumulative")


if __name__ == "__main__":
    main()
