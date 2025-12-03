import os
import sys
import argparse
import requests
import json
import time
from typing import List, Dict, Any, Set
from pathlib import Path
from repositories import REPOSITORIES


class GitHubStargazersClient:
    """Client for interacting with GitHub GraphQL API to get stargazers"""

    def __init__(self, token: str = None):
        # Use provided token, or fall back to environment variable
        self.token = token or os.getenv("GITHUB_TOKEN")
        if not self.token:
            raise ValueError("GITHUB_TOKEN is required. Provide it as an argument or set it as an environment variable.")

        self.base_url = "https://api.github.com/graphql"
        self.headers = {"Authorization": f"Bearer {self.token}"}
        self.rate_limit_wait = 1  # seconds between requests

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

                # Check rate limit headers
                remaining = int(resp.headers.get('X-RateLimit-Remaining', 0))
                reset_time = int(resp.headers.get('X-RateLimit-Reset', 0))

                # If we're about to hit the rate limit, wait before continuing
                if remaining < 10:
                    wait_time = max(reset_time - int(time.time()), 0) + 1
                    if wait_time > 0:
                        print(f"Rate limit low ({remaining} remaining). Waiting {wait_time} seconds...")
                        time.sleep(wait_time)

                # Check for rate limit errors
                if resp.status_code == 403:
                    remaining = int(resp.headers.get('X-RateLimit-Remaining', 0))
                    reset_time = int(resp.headers.get('X-RateLimit-Reset', 0))
                    wait_time = max(reset_time - int(time.time()), 0) + 1

                    if attempt < max_retries - 1:
                        print(f"Rate limit exceeded. Waiting {wait_time} seconds before retry {attempt + 1}/{max_retries}...")
                        time.sleep(wait_time)
                        continue
                    else:
                        raise Exception(f"Rate limit exceeded after {max_retries} retries")

                resp.raise_for_status()
                data = resp.json()

                # Check for GraphQL errors
                if 'errors' in data:
                    error_messages = [err.get('message', 'Unknown error') for err in data['errors']]
                    if 'rate limit' in str(error_messages).lower():
                        if attempt < max_retries - 1:
                            wait_time = retry_delay * (2 ** attempt)
                            print(f"GraphQL rate limit error. Waiting {wait_time} seconds before retry {attempt + 1}/{max_retries}...")
                            time.sleep(wait_time)
                            continue
                        else:
                            raise Exception(f"Rate limit exceeded after {max_retries} retries: {error_messages}")
                    else:
                        raise Exception(f"GraphQL errors: {error_messages}")

                # Add small delay between requests to avoid hitting rate limits
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

        # This should never be reached, but just in case
        raise Exception("Unexpected error in execute_query")

    def get_first_cursor(self, repository: str) -> str:
        """Get the first cursor for a repository"""
        query = """
        query($repository: String!) {
            repository(owner:"autowarefoundation", name:$repository) {
                stargazers(first:1) {
                    totalCount
                    edges {
                        cursor
                        starredAt
                        node {
                            name
                            login
                        }
                    }
                }
            }
        }
        """

        data = self.execute_query(query, {"repository": repository})
        edges = data["data"]["repository"]["stargazers"]["edges"]

        if not edges:
            return None
        return edges[0]["cursor"]

    def get_stargazers(self, repository: str, start_cursor: str = None) -> List[Dict]:
        """Retrieve all stargazers from a repository

        Args:
            repository: Repository name
            start_cursor: Optional cursor to start fetching from (for incremental updates)
        """
        if start_cursor:
            print(f"Retrieving new stargazers for {repository} (incremental update)...")
        else:
            print(f"Retrieving stargazers for {repository}...")

        # Use provided cursor or get the first one
        if start_cursor:
            cursor = start_cursor
        else:
            cursor = self.get_first_cursor(repository)
            if cursor is None:
                print(f"No stargazers found for {repository}")
                return []

        all_edges = []
        page_count = 0

        query = """
        query($cursor: String!, $repository: String!) {
            repository(owner:"autowarefoundation", name:$repository) {
                stargazers(first:100, after: $cursor) {
                    totalCount
                    edges {
                        cursor
                        starredAt
                        node {
                            name
                            login
                        }
                    }
                }
            }
        }
        """

        while cursor:
            print(f"Fetching page {page_count + 1} for {repository}...")
            data = self.execute_query(query, {"cursor": cursor, "repository": repository})

            edges = data["data"]["repository"]["stargazers"]["edges"]
            all_edges.extend(edges)
            page_count += 1

            if len(edges) > 0:
                cursor = edges[-1]["cursor"]
            else:
                cursor = None

        print(f"Retrieved {len(all_edges)} stargazers for {repository}")
        return all_edges


def get_usernames(stargazers: List[Dict]) -> Set[str]:
    """Extract usernames from stargazers data"""
    usernames = set()
    for edge in stargazers:
        if "node" in edge and "login" in edge["node"]:
            usernames.add(edge["node"]["login"])
    return usernames


def dump_json(data: List[Dict], filename: str, output_dir: str = "cache/raw_stargazer_data"):
    """Write JSON data to a file"""
    output_path = Path(output_dir)
    output_path.mkdir(exist_ok=True, parents=True)

    file_path = output_path / filename
    with open(file_path, 'w') as f:
        json.dump(data, f, indent=2)

    print(f"Saved {filename} to {file_path}")


def dump_usernames(usernames: Set[str], filename: str, output_dir: str = "cache/raw_stargazer_data"):
    """Write usernames to a file"""
    output_path = Path(output_dir)
    output_path.mkdir(exist_ok=True, parents=True)

    file_path = output_path / filename
    with open(file_path, 'w') as f:
        for username in sorted(usernames):
            f.write(f"{username}\n")

    print(f"Saved {filename} to {file_path}")


def cache_exists(filename: str, output_dir: str = "cache/raw_stargazer_data") -> bool:
    """Check if a cache file already exists"""
    file_path = Path(output_dir) / filename
    return file_path.exists()


def load_cached_stargazers(filename: str, output_dir: str = "cache/raw_stargazer_data") -> List[Dict]:
    """Load stargazers data from cache file"""
    file_path = Path(output_dir) / filename
    if not file_path.exists():
        return []
    with open(file_path, 'r') as f:
        return json.load(f)


def get_last_cursor(cached_data: List[Dict]) -> str:
    """Get the last cursor from cached data"""
    if not cached_data:
        return None
    return cached_data[-1].get("cursor")


def main():
    """Main function to retrieve stargazers from all repositories"""
    # Parse command-line arguments
    parser = argparse.ArgumentParser(
        description="Retrieve stargazers from GitHub repositories"
    )
    parser.add_argument(
        "--token",
        type=str,
        help="GitHub token for API authentication (default: read from GITHUB_TOKEN env var)"
    )
    parser.add_argument(
        "--use-cache",
        action="store_true",
        help="Use cached data and only fetch new data incrementally"
    )
    args = parser.parse_args()

    repositories = REPOSITORIES

    # Initialize the GitHub Stargazers client
    try:
        client = GitHubStargazersClient(token=args.token)
    except ValueError as e:
        print(f"Error: {e}")
        sys.exit(1)

    # Get stargazers from main repositories
    all_usernames = set()

    for repository in repositories:
        try:
            cache_file = repository + "_stargazers.json"
            if args.use_cache and cache_exists(cache_file):
                # Load cache and fetch new data incrementally
                cached_stargazers = load_cached_stargazers(cache_file)
                last_cursor = get_last_cursor(cached_stargazers)
                if last_cursor:
                    new_stargazers = client.get_stargazers(repository, start_cursor=last_cursor)
                    if new_stargazers:
                        # Merge cached and new data
                        merged_stargazers = cached_stargazers + new_stargazers
                        dump_json(merged_stargazers, cache_file)
                        print(f"Added {len(new_stargazers)} new stargazers to cache")
                        usernames = get_usernames(merged_stargazers)
                        dump_usernames(usernames, repository + "_usernames.txt")
                    else:
                        print(f"No new stargazers found for {repository}")
                        usernames = get_usernames(cached_stargazers)
                    all_usernames.update(usernames)
                else:
                    # Cache exists but no cursor, re-fetch all
                    stargazers = client.get_stargazers(repository)
                    usernames = get_usernames(stargazers)
                    all_usernames.update(usernames)
                    dump_json(stargazers, cache_file)
                    dump_usernames(usernames, repository + "_usernames.txt")
            else:
                stargazers = client.get_stargazers(repository)
                usernames = get_usernames(stargazers)
                all_usernames.update(usernames)
                dump_json(stargazers, cache_file)
                dump_usernames(usernames, repository + "_usernames.txt")
        except Exception as e:
            print(f"Error processing {repository}: {e}")
            continue

    # Save aggregated usernames
    dump_usernames(all_usernames, "usernames.txt")

    print("\n" + "="*60)
    print(f"Retrieved stargazers from {len(repositories)} repositories")
    print(f"Total unique stargazers: {len(all_usernames)}")
    print("="*60)

if __name__ == "__main__":
    main()