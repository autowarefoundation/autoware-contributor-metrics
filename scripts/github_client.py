import os
import sys
import json
import time
import requests
from typing import Any, Callable, Dict, List, Optional
from pathlib import Path


class GitHubGraphQLClient:
    """Shared client for interacting with GitHub GraphQL API"""

    def __init__(self, token: str = None):
        self.token = token or os.getenv("GITHUB_TOKEN")
        if not self.token:
            raise ValueError(
                "GITHUB_TOKEN is required. Provide it as an argument or set it as an environment variable."
            )
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
                    timeout=60,
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


# ---------------------------------------------------------------------------
# Cache I/O helpers
# ---------------------------------------------------------------------------

def dump_json(data: Any, filename: str, output_dir: str) -> None:
    """Write JSON data to a file inside output_dir."""
    output_path = Path(output_dir)
    output_path.mkdir(exist_ok=True, parents=True)
    file_path = output_path / filename
    with open(file_path, 'w') as f:
        json.dump(data, f, indent=2)
    print(f"Saved {filename} to {file_path}")


def load_cache(filename: str, output_dir: str) -> List[Dict]:
    """Load JSON list from cache file. Returns [] if missing."""
    file_path = Path(output_dir) / filename
    try:
        with open(file_path, 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        return []


def get_last_cursor(cached_data: List[Dict]) -> Optional[str]:
    """Return the last cursor from cached edge data, or None."""
    if not cached_data:
        return None
    return cached_data[-1].get("cursor")


# ---------------------------------------------------------------------------
# Incremental fetch helper
# ---------------------------------------------------------------------------

def fetch_with_cache(
    filename: str,
    cache_dir: str,
    fetch_fn: Callable[..., List[Dict]],
    use_cache: bool = False,
) -> List[Dict]:
    """Unify the cache-or-fetch pattern.

    Args:
        filename: cache filename (e.g. "autoware_issues.json")
        cache_dir: directory for cache files
        fetch_fn: callable accepting optional ``start_cursor`` kwarg,
                  returns list of edge dicts
        use_cache: when True, load existing cache and fetch only new data

    Returns:
        The full data list (cached + new, or fresh).
    """
    cached_data = load_cache(filename, cache_dir) if use_cache else []
    last_cursor = get_last_cursor(cached_data)

    if last_cursor:
        print(f"Fetching new data for {filename} (from cached cursor)...")
        new_data = fetch_fn(start_cursor=last_cursor)
        if new_data:
            merged = cached_data + new_data
            dump_json(merged, filename, cache_dir)
            print(f"Added {len(new_data)} new entries to cache")
            return merged
        else:
            print(f"No new data found for {filename}")
            return cached_data
    else:
        if cached_data:
            print(f"Cache exists but no cursor found, re-fetching all data...")
        data = fetch_fn()
        if data:
            dump_json(data, filename, cache_dir)
        return data
