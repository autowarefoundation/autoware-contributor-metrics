#!/usr/bin/env python3
"""
Fetch and filter repositories from Autoware Foundation based on defined rules.

Rules:
- Fetch all repositories from autowarefoundation organization
- Exclude archived repositories
- Exclude repositories not updated within 2 years (except autoware_ai legacy repos)
- Select top 25 by composite score (stars + forks)
- Include all autoware_ai legacy repositories for historical tracking
"""

import os
import sys
import argparse
import requests
import json
import time
from datetime import datetime, timedelta
from typing import List, Dict, Any
from pathlib import Path


class GitHubRepoFetcher:
    """Client for fetching repository information from GitHub GraphQL API"""

    def __init__(self, token: str = None):
        self.token = token or os.getenv("GITHUB_TOKEN")
        if not self.token:
            raise ValueError("GITHUB_TOKEN is required. Provide it as an argument or set it as an environment variable.")

        self.base_url = "https://api.github.com/graphql"
        self.headers = {"Authorization": f"Bearer {self.token}"}
        self.rate_limit_wait = 1

    def execute_query(self, query: str, variables: Dict[str, Any] = None) -> Dict[str, Any]:
        """Execute a GraphQL query with rate limiting and error handling"""
        payload = {"query": query}
        if variables:
            payload["variables"] = variables

        max_retries = 5
        retry_delay = 1
        for attempt in range(max_retries):
            try:
                resp = requests.post(
                    self.base_url,
                    json=payload,
                    headers=self.headers,
                    timeout=60
                )

                remaining = int(resp.headers.get('X-RateLimit-Remaining', 0))
                reset_time = int(resp.headers.get('X-RateLimit-Reset', 0))

                if remaining < 10:
                    wait_time = max(reset_time - int(time.time()), 0) + 1
                    if wait_time > 0:
                        print(f"Rate limit low ({remaining} remaining). Waiting {wait_time} seconds...")
                        time.sleep(wait_time)

                if resp.status_code == 403:
                    wait_time = max(reset_time - int(time.time()), 0) + 1
                    if attempt < max_retries - 1:
                        print(f"Rate limit exceeded. Waiting {wait_time} seconds before retry {attempt + 1}/{max_retries}...")
                        time.sleep(wait_time)
                        continue
                    else:
                        raise Exception(f"Rate limit exceeded after {max_retries} retries")

                resp.raise_for_status()
                data = resp.json()

                if 'errors' in data:
                    error_messages = [err.get('message', 'Unknown error') for err in data['errors']]
                    raise Exception(f"GraphQL errors: {error_messages}")

                time.sleep(self.rate_limit_wait)
                return data

            except requests.exceptions.RequestException as e:
                if attempt < max_retries - 1:
                    print(f"Request failed: {e}. Retrying in {retry_delay * (2 ** attempt)} seconds...")
                    time.sleep(retry_delay * (2 ** attempt))
                    continue
                else:
                    print(f"Request failed after {max_retries} attempts: {e}")
                    sys.exit(1)

        raise Exception("Unexpected error in execute_query")

    def fetch_all_repositories(self) -> List[Dict]:
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
            data = self.execute_query(query, {"cursor": cursor})

            repos = data["data"]["organization"]["repositories"]["nodes"]
            all_repos.extend(repos)

            page_info = data["data"]["organization"]["repositories"]["pageInfo"]
            if page_info["hasNextPage"]:
                cursor = page_info["endCursor"]
            else:
                break

        print(f"Fetched {len(all_repos)} repositories total")
        return all_repos


def filter_and_rank_repositories(repos: List[Dict], cutoff_years: int = 2) -> Dict:
    """
    Filter and rank repositories according to rules.

    Returns a dict with:
    - active: Top 25 active repositories by score
    - legacy: All autoware_ai repositories
    - all: Combined list (active + legacy, deduplicated)
    """
    cutoff_date = datetime.now() - timedelta(days=cutoff_years * 365)

    active_repos = []
    legacy_repos = []

    for repo in repos:
        name = repo["name"]
        is_archived = repo["isArchived"]
        stars = repo["stargazerCount"]
        forks = repo["forkCount"]
        score = stars + forks

        # Parse update date
        updated_at_str = repo.get("pushedAt") or repo.get("updatedAt")
        try:
            updated_at = datetime.strptime(updated_at_str, '%Y-%m-%dT%H:%M:%SZ')
        except (ValueError, TypeError):
            updated_at = None

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

        # Skip archived repositories
        if is_archived:
            continue

        # Skip repositories not updated within cutoff period
        if updated_at and updated_at < cutoff_date:
            continue

        active_repos.append(repo_info)

    # Sort active repos by score and take top 25
    active_repos.sort(key=lambda x: -x["score"])
    top_active = active_repos[:25]

    # Sort legacy repos by score
    legacy_repos.sort(key=lambda x: -x["score"])

    # Combine lists (active repos first, then legacy)
    all_repos = [r["name"] for r in top_active]
    for r in legacy_repos:
        if r["name"] not in all_repos:
            all_repos.append(r["name"])

    return {
        "active": top_active,
        "legacy": legacy_repos,
        "repositories": all_repos,
        "metadata": {
            "generated_at": datetime.now().strftime('%Y-%m-%dT%H:%M:%SZ'),
            "cutoff_years": cutoff_years,
            "total_fetched": len(repos),
            "active_count": len(top_active),
            "legacy_count": len(legacy_repos),
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
        client = GitHubRepoFetcher(token=args.token)
    except ValueError as e:
        print(f"Error: {e}")
        sys.exit(1)

    # Fetch all repositories
    repos = client.fetch_all_repositories()

    # Filter and rank
    result = filter_and_rank_repositories(repos, cutoff_years=args.cutoff_years)

    # Write output
    output_path = Path(args.output)
    output_path.parent.mkdir(exist_ok=True, parents=True)

    with open(output_path, 'w') as f:
        json.dump(result, f, indent=2)

    print(f"\nDone! Generated {output_path}")
    print(f"Active repositories (Top {len(result['active'])} by score):")
    for repo in result['active'][:10]:
        print(f"  - {repo['name']}: score={repo['score']} ({repo['stars']} stars + {repo['forks']} forks)")
    if len(result['active']) > 10:
        print(f"  ... and {len(result['active']) - 10} more")

    print(f"\nLegacy repositories: {len(result['legacy'])}")
    print(f"Total repositories in list: {len(result['repositories'])}")


if __name__ == "__main__":
    main()
