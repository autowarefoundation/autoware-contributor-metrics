import datetime
from typing import Dict, List, NamedTuple, Set, Tuple
from collections import defaultdict
from pathlib import Path
from frozen_star_history import FrozenStarHistory, load_frozen_star_history
from repositories import REPOSITORIES, load_org_metadata
from utils import parse_github_datetime, load_json_file, generate_cumulative_history, write_json_output


CACHE_DIR = "cache/raw_stargazer_data"
ACCESS_STATUS_FILE = "cache/raw_stargazer_data/access_status.json"
ACCESS_RESTRICTION_URL = (
    "https://github.blog/changelog/2026-06-30-upcoming-access-restrictions-"
    "to-public-api-endpoints-and-ui-views/"
)


def build_access_metadata(access_status: Dict, history_repos: set,
                          frozen_repos: set = frozenset(),
                          frozen_captured_at: str = None) -> Dict:
    """Summarise which repositories GitHub let us list stargazers for.

    Returned verbatim to the dashboard so the page can explain, from the data
    itself, why some repositories have a current star count but no history.
    Returns None when nothing is known, so an older cache simply shows no note.

    Restricted repositories fall into two groups that the page has to describe
    differently: those whose history is frozen at the archive's capture date,
    and those that have no history at all. Both are derived from what this run
    produced rather than hardcoded, so they correct themselves if access
    changes.
    """
    if not access_status:
        return None

    restricted = sorted(
        repo for repo, s in access_status.items()
        if not s.get("can_list_stargazers", True)
    )
    frozen = [repo for repo in restricted if repo in frozen_repos]
    metadata = {
        "restricted_repos": restricted,
        "restricted_repo_count": len(restricted),
        "frozen_history_repos": frozen,
        "no_history_repos": [repo for repo in restricted if repo not in history_repos],
        "history_repo_count": len(history_repos),
        "tracked_repo_count": len(access_status),
        "reference": ACCESS_RESTRICTION_URL,
    }
    # Only when something is actually frozen: the note must not offer a capture
    # date for records that do not exist.
    if frozen and frozen_captured_at:
        metadata["frozen_captured_at"] = frozen_captured_at
    return metadata


class StarsHistoryAnalyzer:
    """Class to analyze and generate star history from stargazer data"""

    def extract_stargazers_info(self, stargazers_data: List[Dict]) -> List[Tuple[str, datetime.date]]:
        """Extract (username, date) tuples from stargazer data"""
        stargazers_info = []

        for edge in stargazers_data:
            try:
                starred_at = edge.get("starredAt")
                username = edge.get("node", {}).get("login") if edge.get("node") else None

                if starred_at and username:
                    d = parse_github_datetime(starred_at)
                    if d:
                        day = datetime.date(d.year, d.month, d.day)
                        stargazers_info.append((username, day))
            except (ValueError, KeyError):
                continue

        return stargazers_info

    def count_stars_per_day(self, stargazers_info: List[Tuple[str, datetime.date]]) -> Dict[datetime.date, int]:
        """Count how many stars were added on each day"""
        stars_per_day = defaultdict(int)

        for _, day in stargazers_info:
            stars_per_day[day] += 1

        return dict(stars_per_day)

    def generate_total_history(self, all_stargazers: List[List[Tuple[str, datetime.date]]]) -> List[Dict]:
        """Generate cumulative total star history from all repositories, counting unique stargazers"""
        # Collect all unique stargazers across all repositories
        # Key: username, Value: earliest star date
        unique_stargazers = {}

        for stargazers_info in all_stargazers:
            for username, day in stargazers_info:
                if username not in unique_stargazers or unique_stargazers[username] > day:
                    unique_stargazers[username] = day

        # Count unique stars per day (each stargazer only counted once at their earliest date)
        stars_per_day = defaultdict(int)
        for username, day in unique_stargazers.items():
            stars_per_day[day] += 1

        return generate_cumulative_history(dict(stars_per_day), "star_count")


class StarHistories(NamedTuple):
    """Everything the per-repository pass produces."""

    series: Dict[str, List[Dict]]      # "<repo>_stars_history" -> cumulative history
    total: List[Dict]                  # total_stars_history, unique people
    history_repos: Set[str]            # repositories that got a series at all
    frozen_sources: Dict[str, Dict]    # only the repositories served from the archive
    unique_count: int


def build_star_histories(repositories: List[str], frozen: FrozenStarHistory,
                         cache_dir: str = CACHE_DIR) -> StarHistories:
    """Build each repository's series from the live cache, or from the archive.

    A live cache file wins outright and is never merged with the archive.
    `fetch_with_cache` performs a full fetch whenever there is no cursor, so a
    live file is always a complete listing; folding a stale archive into it
    could only resurrect people who have since unstarred, or count them twice.

    Archived records feed the unique-people total as well as their own series.
    They are real people with real dates, and `generate_total_history` already
    keeps the earliest date when someone appears in more than one repository.
    """
    analyzer = StarsHistoryAnalyzer()

    all_stargazers_info = []
    series = {}
    history_repos = set()
    frozen_sources = {}

    for repository in repositories:
        print(f"Processing {repository}...")
        stargazers_data = load_json_file(str(Path(cache_dir) / f"{repository}_stargazers.json"))

        if stargazers_data:
            stargazers_info = analyzer.extract_stargazers_info(stargazers_data)
        elif repository in frozen.repositories:
            records = frozen.repositories[repository]
            stargazers_info = [
                (login, datetime.date.fromisoformat(day)) for login, day in records
            ]
            frozen_sources[repository] = {
                "source": "frozen",
                "last_star_at": max(day for _, day in records),
            }
            print(f"  no live cache; using {len(records)} archived records "
                  f"frozen at {frozen.captured_at}")
        else:
            continue

        history_repos.add(repository)
        all_stargazers_info.append(stargazers_info)
        series[f"{repository}_stars_history"] = generate_cumulative_history(
            analyzer.count_stars_per_day(stargazers_info), "star_count"
        )

    print("Generating total stars history (counting unique stargazers)...")
    return StarHistories(
        series=series,
        total=analyzer.generate_total_history(all_stargazers_info),
        history_repos=history_repos,
        frozen_sources=frozen_sources,
        unique_count=len({
            username for stargazers_info in all_stargazers_info
            for username, _ in stargazers_info
        }),
    )


def main():
    """Main function to process star history"""
    print("Processing star history...")

    repositories = REPOSITORIES

    # Raises rather than degrading if the archive is gone: see data/README.md.
    frozen = load_frozen_star_history()
    unknown = frozen.unknown_repositories(repositories)
    if unknown:
        print(f"Warning: archived repositories no longer tracked (renamed?): "
              f"{', '.join(unknown)}")

    built = build_star_histories(repositories, frozen)

    output_data = dict(built.series)
    output_data["total_stars_history"] = built.total

    # Which repositories could not be re-read this run and are therefore
    # serving records frozen at the archive's capture date. Absence means live.
    if built.frozen_sources:
        output_data["star_history_sources"] = built.frozen_sources

    # Current per-repository star counts, from the `stargazerCount` scalar.
    # These cover every repository, including the ones whose stargazer list
    # GitHub cannot enumerate and which therefore have no history above. They
    # are deliberately NOT folded into total_stars_history: that series counts
    # unique *people*, and a bare count carries no identities to deduplicate by.
    counts = load_json_file("cache/raw_stargazer_data/current_counts.json")
    if isinstance(counts, dict) and counts:
        output_data["current_star_counts"] = counts
        output_data["total_current_stars"] = sum(counts.values())
        print(f"Current star counts: {len(counts)} repositories, "
              f"{sum(counts.values())} stars total (sum, not unique)")

    # Organization-wide star total, computed by fetch_repositories.py from the
    # full repository listing. Carried through here so the dashboard reads every
    # star figure from one file. It is a strictly larger set than the tracked
    # repositories above, hence a separate key: `total_current_stars` must keep
    # equalling the sum of `current_star_counts`.
    org_meta = load_org_metadata()
    if isinstance(org_meta.get("org_star_total"), int):
        output_data["org_star_total"] = org_meta["org_star_total"]
        output_data["org_repo_count"] = org_meta.get("org_repo_count")
        print(f"Organization-wide stars: {org_meta['org_star_total']} across "
              f"{org_meta.get('org_repo_count')} public repositories")

    # Why some repositories have a count but no history, or a history that
    # stops, carried with the data so the dashboard can say so without
    # hardcoding today's repository list.
    access_meta = build_access_metadata(
        load_json_file(ACCESS_STATUS_FILE),
        built.history_repos,
        frozen_repos=set(built.frozen_sources),
        frozen_captured_at=frozen.captured_at,
    )
    if access_meta:
        output_data["stargazer_access"] = access_meta
        if access_meta["frozen_history_repos"]:
            print(f"Frozen at {frozen.captured_at}: "
                  f"{', '.join(access_meta['frozen_history_repos'])}")
        if access_meta["no_history_repos"]:
            print(f"Restricted with no history at all: "
                  f"{', '.join(access_meta['no_history_repos'])}")

    output_file = "results/stars_history.json"
    write_json_output(output_data, output_file)

    print(f"\nDone! Generated {output_file}")
    print(f"Processed {len(repositories)} repositories")
    print(f"Total unique stargazers: {built.unique_count}")
    print(f"Total entries in history: {len(built.total)}")

if __name__ == "__main__":
    main()
