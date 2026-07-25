#!/usr/bin/env python3
"""Guard against publishing a regressed metrics snapshot.

A fetch failure can silently drop repositories from the generated history: the
per-repo cache file is simply absent, ``calculate_*`` skips it, and the result
is a valid-looking JSON that is missing data. Publishing that also *caches* it,
which is how a cleared-cache run permanently lost 16 repositories and 843
unique stars from the dashboard.

This script compares the freshly generated ``results/`` against the last
published snapshot and fails the job before the deploy when a metric went
backwards, so the previous good cache and the live site are left intact.

Two rules, reflecting how these metrics actually behave:

- **Series counts must never shrink.** A repository disappearing from the
  output is always a bug; the repository list does not shrink on its own.
- **Cumulative totals may dip slightly.** Users unstar repositories, so a small
  decrease is legitimate. Only drops beyond ``--tolerance`` are flagged.
"""

import argparse
import json
import shutil
import sys
from pathlib import Path
from typing import Any, Dict, List, NamedTuple


class Violation(NamedTuple):
    """One metric that moved backwards between snapshots."""
    file: str
    metric: str
    previous: float
    current: float

    def describe(self) -> str:
        delta = self.current - self.previous
        pct = (delta / self.previous * 100) if self.previous else 0.0
        return (
            f"  {self.file}: {self.metric} {self.previous} -> {self.current} "
            f"({delta:+g}, {pct:+.1f}%)"
        )


# Metrics whose value is a count of series/repositories: any decrease is a bug,
# so they are compared with zero tolerance.
COUNT_METRICS = {"repo_series", "current_count_repos"}


def _last(series: Any, field: str) -> float:
    """Last value of *field* in a time series, or 0 when unavailable."""
    if not isinstance(series, list) or not series:
        return 0
    last = series[-1]
    return last.get(field, 0) if isinstance(last, dict) else 0


def metrics_for(filename: str, data: Any) -> Dict[str, float]:
    """Extract the comparable metrics from one results file.

    Files not listed here (google_trends, rankings) are intentionally skipped:
    their values are relative or re-derived every run, so a decrease carries no
    signal.
    """
    if not isinstance(data, dict):
        return {}

    if filename == "stars_history.json":
        metrics = {
            "repo_series": sum(
                1 for k in data
                if k.endswith("_stars_history") and k != "total_stars_history"
            ),
            "total_stars": _last(data.get("total_stars_history"), "star_count"),
        }
        if isinstance(data.get("current_star_counts"), dict):
            metrics["current_count_repos"] = len(data["current_star_counts"])
            metrics["total_current_stars"] = data.get("total_current_stars", 0)
        # Guarded as a cumulative total, not a count: a partial organization
        # listing shows up as a large star drop, while a repository genuinely
        # being deleted or made private is a legitimate small one.
        if isinstance(data.get("org_star_total"), int):
            metrics["org_star_total"] = data["org_star_total"]
        return metrics
    if filename == "commits_history.json":
        return {"repo_series": sum(1 for k in data if k.endswith("_commits_history"))}
    if filename == "activity_history.json":
        return {"repo_series": sum(1 for k in data if k.endswith("_history"))}
    if filename == "contributors_history.json":
        return {
            k: _last(v, "contributors_count")
            for k, v in data.items() if isinstance(v, list)
        }
    if filename == "arxiv_mentions_history.json":
        return {"total_papers": data.get("total_papers", 0)}
    if filename == "arxiv_citations_history.json":
        return {"total_citations": data.get("total_citations", 0)}
    if filename == "apt_downloads.json":
        return {"cumulative_total": _last(data.get("cumulative"), "total")}
    return {}


def _load(path: Path) -> Any:
    try:
        with open(path) as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError):
        return None


def compare(results_dir: Path, baseline_dir: Path, tolerance: float = 0.02) -> List[Violation]:
    """Return every metric that regressed from *baseline_dir* to *results_dir*.

    An absent or empty baseline yields no violations: the first run has nothing
    to compare against and must be allowed through.
    """
    results_dir, baseline_dir = Path(results_dir), Path(baseline_dir)
    if not baseline_dir.is_dir():
        return []

    violations: List[Violation] = []
    for baseline_file in sorted(baseline_dir.glob("*.json")):
        name = baseline_file.name
        previous, current = _load(baseline_file), _load(results_dir / name)
        if previous is None or current is None:
            continue

        prev_metrics = metrics_for(name, previous)
        curr_metrics = metrics_for(name, current)
        for metric, prev_value in prev_metrics.items():
            curr_value = curr_metrics.get(metric, 0)
            allowed = 0.0 if metric in COUNT_METRICS else prev_value * tolerance
            if curr_value < prev_value - allowed:
                violations.append(Violation(name, metric, prev_value, curr_value))
    return violations


def update_baseline(results_dir: Path, baseline_dir: Path) -> None:
    """Snapshot the published results so the next run has something to compare."""
    results_dir, baseline_dir = Path(results_dir), Path(baseline_dir)
    baseline_dir.mkdir(parents=True, exist_ok=True)
    for f in results_dir.glob("*.json"):
        shutil.copyfile(f, baseline_dir / f.name)
    print(f"Updated regression baseline in {baseline_dir}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Guard against publishing a regressed snapshot")
    parser.add_argument("--results", default="results", help="freshly generated results directory")
    parser.add_argument("--baseline", default="cache/last_published",
                        help="last published snapshot to compare against")
    parser.add_argument("--tolerance", type=float, default=0.02,
                        help="fractional decrease tolerated for cumulative totals")
    parser.add_argument("--update", action="store_true",
                        help="snapshot results into the baseline instead of comparing")
    parser.add_argument("--allow-regression", action="store_true",
                        help="report regressions but exit 0 (manual override)")
    args = parser.parse_args()

    if args.update:
        update_baseline(Path(args.results), Path(args.baseline))
        return

    violations = compare(Path(args.results), Path(args.baseline), args.tolerance)
    if not violations:
        print("Regression guard: no metric went backwards.")
        return

    print("Regression guard: metrics went backwards versus the last published snapshot:")
    for v in violations:
        print(v.describe())

    if args.allow_regression:
        print("\n--allow-regression set; publishing anyway.")
        return

    print(
        "\nRefusing to publish. This usually means a fetch failed and its "
        "repositories were silently dropped.\nThe previous cache and the live "
        "site are left untouched. Re-run once the upstream API recovers, or "
        "re-run with the allow_regression input if the drop is expected."
    )
    sys.exit(1)


if __name__ == "__main__":
    main()
