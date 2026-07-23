#!/usr/bin/env python3
"""Fetch Google Trends interest-over-time for the "Autoware" keyword.

Uses pytrends to query Google Trends for the worldwide monthly relative
search interest for "Autoware". Values are normalized 0-100 against the
peak month in the requested range, and represent relative search interest,
not absolute search volume.

Google rate-limits pytrends aggressively. On fetch failure this script falls
back to the most recent successful payload cached under
cache/raw_google_trends_data/, so the dashboard keeps showing the previous
snapshot instead of dropping the file from the deployed Pages artifact.
"""

import datetime
import shutil
import time
from pathlib import Path

from utils import write_json_output

OUTPUT_FILE = "results/google_trends_history.json"
CACHE_DIR = Path("cache/raw_google_trends_data")
CACHE_FILE = CACHE_DIR / "google_trends_history.json"

KEYWORD = "Autoware"
START_DATE = "2018-01-01"
GEO = ""  # worldwide
HL = "en-US"
TZ = 540  # JST
MAX_RETRIES = 4


def fetch_trends(end_date: str) -> list[dict]:
    """Fetch monthly interest-over-time for the Autoware keyword.

    Returns a list of {month, interest, is_partial} dicts.
    """
    # Imported lazily so the module stays importable (and unit-testable)
    # without pytrends installed; only the actual fetch needs it.
    from pytrends.request import TrendReq

    timeframe = f"{START_DATE} {end_date}"
    last_err: Exception | None = None
    for attempt in range(MAX_RETRIES):
        try:
            pytrends = TrendReq(hl=HL, tz=TZ, timeout=(10, 30))
            pytrends.build_payload(kw_list=[KEYWORD], timeframe=timeframe, geo=GEO)
            df = pytrends.interest_over_time()
            if df.empty:
                raise RuntimeError("Empty interest_over_time result")
            rows = []
            for ts, row in df.iterrows():
                rows.append({
                    "month": ts.strftime("%Y-%m"),
                    "interest": int(row[KEYWORD]),
                    "is_partial": bool(row.get("isPartial", False)),
                })
            return rows
        except Exception as e:
            wait = 2 ** attempt * 5
            print(f"  Error (attempt {attempt + 1}): {e}. Retrying in {wait}s...")
            last_err = e
            time.sleep(wait)
    raise RuntimeError(f"Failed to fetch Google Trends data: {last_err}")


def restore_from_cache(reason: str) -> bool:
    """Copy the cached payload to OUTPUT_FILE. Returns True on success."""
    if not CACHE_FILE.exists():
        print(f"  No cached fallback at {CACHE_FILE} ({reason})")
        return False
    Path(OUTPUT_FILE).parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(CACHE_FILE, OUTPUT_FILE)
    print(f"  Restored previous Google Trends snapshot from cache ({reason})")
    return True


def write_placeholder(end_date: str, reason: str) -> None:
    """Write an empty-but-valid output so the pipeline can finish.

    Used only when the live fetch failed *and* there is no cached snapshot to
    fall back on (e.g. a cleared-cache run while Google is rate-limiting). This
    keeps the downstream ``cp`` + deploy alive instead of aborting the whole
    job on one flaky external service. It is intentionally NOT written to
    CACHE_FILE, so a later run can still fall back to a genuine snapshot.
    """
    output = {
        "keyword": KEYWORD,
        "geo": GEO or "worldwide",
        "monthly": [],
        "last_updated": end_date,
        "note": (
            "Google Trends data was unavailable at build time and no cached "
            "snapshot existed to fall back on. This empty placeholder keeps the "
            "pipeline running; it self-heals on the next successful fetch."
        ),
        "error": reason,
    }
    write_json_output(output, OUTPUT_FILE)
    print(f"  Wrote empty Google Trends placeholder ({reason})")


def main() -> None:
    today = datetime.date.today()
    end_date = today.strftime("%Y-%m-%d")
    CACHE_DIR.mkdir(parents=True, exist_ok=True)

    print(f"Fetching Google Trends for '{KEYWORD}' from {START_DATE} to {end_date}...")
    try:
        rows = fetch_trends(end_date)
    except Exception as e:
        print(f"Fetch failed: {e}")
        if restore_from_cache(reason=str(e)):
            return
        write_placeholder(end_date, reason=str(e))
        return

    output = {
        "keyword": KEYWORD,
        "geo": GEO or "worldwide",
        "monthly": rows,
        "last_updated": end_date,
        "note": (
            "Values are Google Trends relative interest (0-100), not absolute "
            "search volume. The 100 represents the peak month in the requested range."
        ),
    }
    write_json_output(output, OUTPUT_FILE)
    shutil.copyfile(OUTPUT_FILE, CACHE_FILE)

    print(f"\nDone! Generated {OUTPUT_FILE}")
    print(f"Months collected: {len(rows)}")
    if rows:
        print(f"Range: {rows[0]['month']} to {rows[-1]['month']}")
        peak = max(rows, key=lambda r: r["interest"])
        print(f"Peak: {peak['month']} (interest={peak['interest']})")
        print(f"Latest: {rows[-1]}")


if __name__ == "__main__":
    main()
