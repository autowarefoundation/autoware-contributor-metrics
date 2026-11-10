#!/usr/bin/env python3
"""
Fetch and filter repositories from Autoware Foundation based on defined rules.

Rules:
- Fetch all repositories from autowarefoundation organization
- Exclude private repositories (the dashboard is public)
- Exclude archived repositories and forks (except INCLUDED_FORKS)
- Exclude EXCLUDED_REPOSITORIES by name
- Exclude repositories not pushed to within 2 years (except autoware_ai legacy repos)
- Track every remaining repository, ordered by composite score (stars + forks)
- Include all autoware_ai legacy repositories for historical tracking

An earlier version kept only the top 25 by score. That cap left out repositories
with heavy activity but few stars, and two repositories near 25th place could
swap on any day.
"""

import sys
import argparse
from datetime import datetime, timedelta
from typing import List, Dict

from github_client import GitHubGraphQLClient
from utils import parse_github_datetime, write_json_output

# Forks that the foundation develops on, so their activity is foundation work.
# alpamayo-autoware is a fork of NVlabs/alpamayo.
INCLUDED_FORKS = {"alpamayo-autoware"}

# Repositories whose activity is not real project work.
EXCLUDED_REPOSITORIES = {
    # "A dummy repository for testing release process". Its test PRs would
    # count as merged PRs.
    "autoware_dummy_repository",
}


def fetch_all_repositories(client: GitHubGraphQLClient) -> List[Dict]:
    """Fetch all repositories from autowarefoundation organization"""
    print("Fetching repositories from autowarefoundation...")

    all_repos = []
    cursor = None
    page = 0

    query = """
    query($cursor: String) {
        organization(login: "autowarefoundation") {
            repositories(first: 100, after: $cursor) {
                pageInfo {
                    hasNextPage
                    endCursor
                }
                nodes {
                    name
                    isArchived
                    isFork
                    isPrivate
                    stargazerCount
                    forkCount
                    pushedAt
                    updatedAt
                }
            }
        }
    }
    """

    while True:
        page += 1
        print(f"Fetching page {page}...")
        data = client.execute_query(query, {"cursor": cursor})

        repos = data["data"]["organization"]["repositories"]["nodes"]
        all_repos.extend(repos)

        page_info = data["data"]["organization"]["repositories"]["pageInfo"]
        if page_info["hasNextPage"]:
            cursor = page_info["endCursor"]
        else:
            break

    print(f"Fetched {len(all_repos)} repositories total")
    return all_repos


def summarize_org_stars(repos: List[Dict]) -> Dict:
    """Star total across every public repository in the organization.

    This is what the dashboard shows as *Total Stars*, so the figure answers
    "how many stars does Autoware Foundation have" rather than "how many do the
    repositories we chart have". It is computed here because this is the only
    script that already pages the whole organization; deriving it costs no
    extra API calls.

    Private repositories are excluded so the number stays reproducible: a token
    with broader access would otherwise report a total the public site cannot
    account for.
    """
    public = [r for r in repos if not r.get("isPrivate")]
    return {
        "org_star_total": sum(r["stargazerCount"] for r in public),
        "org_repo_count": len(public),
    }


def filter_and_rank_repositories(repos: List[Dict], cutoff_years: int = 2) -> Dict:
    """
    Filter and rank repositories according to rules.

    Returns a dict with:
    - active: All active repositories, sorted by score
    - legacy: All autoware_ai repositories
    - all: Combined list (active + legacy, deduplicated)
    """
    cutoff_date = datetime.now() - timedelta(days=cutoff_years * 365)

    active_repos = []
    legacy_repos = []

    for repo in repos:
        # The dashboard is public. A token that can see private repositories
        # must not publish their activity.
        if repo.get("isPrivate"):
            continue

        name = repo["name"]
        if name in EXCLUDED_REPOSITORIES:
            continue
        is_archived = repo["isArchived"]
        stars = repo["stargazerCount"]
        forks = repo["forkCount"]
        score = stars + forks

        # Parse update date
        updated_at_str = repo.get("pushedAt") or repo.get("updatedAt")
        updated_at = parse_github_datetime(updated_at_str)

        repo_info = {
            "name": name,
            "stars": stars,
            "forks": forks,
            "score": score,
            "is_archived": is_archived,
            "updated_at": updated_at_str,
        }

        # Check if it's a legacy autoware_ai repository
        if name.startswith("autoware_ai"):
            legacy_repos.append(repo_info)
            continue

        # Skip archived repositories and forks
        if is_archived or (repo.get("isFork") and name not in INCLUDED_FORKS):
            continue

        # Skip repositories not updated within cutoff period
        if updated_at and updated_at < cutoff_date:
            continue

        active_repos.append(repo_info)

    # Sort by score, then name, so the order is stable between runs
    active_repos.sort(key=lambda x: (-x["score"], x["name"]))
    legacy_repos.sort(key=lambda x: (-x["score"], x["name"]))

    # Combine lists (active repos first, then legacy)
    all_repos = [r["name"] for r in active_repos]
    for r in legacy_repos:
        if r["name"] not in all_repos:
            all_repos.append(r["name"])

    return {
        "active": active_repos,
        "legacy": legacy_repos,
        "repositories": all_repos,
        "metadata": {
            "generated_at": datetime.now().strftime('%Y-%m-%dT%H:%M:%SZ'),
            "cutoff_years": cutoff_years,
            "total_fetched": len(repos),
            "active_count": len(active_repos),
            "legacy_count": len(legacy_repos),
            **summarize_org_stars(repos),
        }
    }


def main():
    parser = argparse.ArgumentParser(
        description="Fetch and filter Autoware Foundation repositories"
    )
    parser.add_argument(
        "--token",
        type=str,
        help="GitHub token for API authentication (default: read from GITHUB_TOKEN env var)"
    )
    parser.add_argument(
        "--cutoff-years",
        type=int,
        default=2,
        help="Exclude repos not updated within this many years (default: 2)"
    )
    parser.add_argument(
        "--output",
        type=str,
        default="public/repositories.json",
        help="Output file path (default: public/repositories.json)"
    )
    args = parser.parse_args()

    try:
        client = GitHubGraphQLClient(token=args.token)
    except ValueError as e:
        print(f"Error: {e}")
        sys.exit(1)

    # Fetch all repositories
    repos = fetch_all_repositories(client)

    # Filter and rank
    result = filter_and_rank_repositories(repos, cutoff_years=args.cutoff_years)

    # Write output
    write_json_output(result, args.output)

    print(f"\nDone! Generated {args.output}")
    print(f"Active repositories ({len(result['active'])}, by score):")
    for repo in result['active'][:10]:
        print(f"  - {repo['name']}: score={repo['score']} ({repo['stars']} stars + {repo['forks']} forks)")
    if len(result['active']) > 10:
        print(f"  ... and {len(result['active']) - 10} more")

    print(f"\nLegacy repositories: {len(result['legacy'])}")
    print(f"Total repositories in list: {len(result['repositories'])}")
    print(f"Organization-wide stars: {result['metadata']['org_star_total']} "
          f"across {result['metadata']['org_repo_count']} public repositories")


if __name__ == "__main__":
    main()
