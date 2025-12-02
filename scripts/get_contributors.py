import os
import sys
import requests
import json
import time
import argparse
from typing import List, Dict, Any
from pathlib import Path

class GitHubGraphQLClient:
    """Client for interacting with GitHub GraphQL API"""

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

    def get_first_cursor(self, contributor_type: str, repository: str) -> str:
        """Get the first cursor for a repository and contributor type"""
        query = f"""
        query($repository: String!) {{
            repository(owner:"autowarefoundation", name:$repository) {{
                {contributor_type}(first:1) {{
                    edges {{
                        cursor
                    }}
                }}
            }}
        }}
        """

        data = self.execute_query(query, {"repository": repository})

        edges = data["data"]["repository"][contributor_type]["edges"]
        if not edges:
            return None
        return edges[0]["cursor"]

    def get_contributors(self, contributor_type: str, repository: str, start_cursor: str = None) -> List[Dict]:
        """Retrieve all contributors of a specific type from a repository

        Args:
            contributor_type: Type of contributor data to fetch (issues, pullRequests, discussions)
            repository: Repository name
            start_cursor: Optional cursor to start fetching from (for incremental updates)
        """
        if start_cursor:
            print(f"Retrieving new {contributor_type} for {repository} (incremental update)...")
        else:
            print(f"Retrieving {contributor_type} for {repository}...")

        # Use provided cursor or get the first one
        if start_cursor:
            cursor = start_cursor
        else:
            cursor = self.get_first_cursor(contributor_type, repository)
            if cursor is None:
                print(f"No {contributor_type} found for {repository}")
                return []

        all_edges = []
        page_count = 0

        # Add reviews field only for pullRequests (simplified to avoid query complexity limits)
        reviews_field = ""
        if contributor_type == "pullRequests":
            reviews_field = """
                            reviews(first:100) {
                                edges {
                                    node {
                                        author {
                                            login
                                        }
                                        createdAt
                                    }
                                }
                            }"""

        query = f"""
        query($cursor: String!, $repository: String!) {{
            repository(owner:"autowarefoundation", name:$repository) {{
                {contributor_type}(first:100, after: $cursor) {{
                    totalCount
                    edges {{
                        cursor
                        node {{
                            author{{
                                login
                            }}
                            title
                            createdAt
                            comments(first:100) {{
                                edges {{
                                    node {{
                                        author{{
                                            login
                                        }}
                                        createdAt
                                    }}
                                }}
                            }}{reviews_field}
                        }}
                    }}
                }}
            }}
        }}
        """

        while cursor:
            print(f"Fetching page {page_count + 1} for {repository} {contributor_type}...")
            data = self.execute_query(query, {"cursor": cursor, "repository": repository})

            edges = data["data"]["repository"][contributor_type]["edges"]
            all_edges.extend(edges)
            page_count += 1

            if len(edges) > 0:
                cursor = edges[-1]["cursor"]
            else:
                cursor = None

        print(f"Retrieved {len(all_edges)} {contributor_type} for {repository}")
        return all_edges


def dump_json(data: Dict, filename: str, output_dir: str = "cache/raw_contributor_data"):
    """Write JSON data to a file"""
    output_path = Path(output_dir)
    output_path.mkdir(exist_ok=True, parents=True)

    file_path = output_path / filename
    with open(file_path, 'w') as f:
        json.dump(data, f, indent=2)
    print(f"Saved {filename} to {file_path}")

def cache_exists(filename: str, output_dir: str = "cache/raw_contributor_data") -> bool:
    """Check if a cache file already exists"""
    file_path = Path(output_dir) / filename
    return file_path.exists()


def load_cache(filename: str, output_dir: str = "cache/raw_contributor_data") -> List[Dict]:
    """Load cached data from a file"""
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
    """Main function to generate JSON files for all repositories"""
    # Parse command-line arguments
    parser = argparse.ArgumentParser(
        description="Generate JSON files for contributors data from GitHub repositories"
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

    # List of Autoware repositories to process
    repositories = [
        "autoware",
        "autoware_core",
        "autoware_universe",
        "autoware_common",
        "autoware_msgs",
        "autoware_adapi_msgs",
        "autoware_internal_msgs",
        "autoware_cmake",
        "autoware_utils",
        "autoware_lanelet2_extension",
        "autoware_rviz_plugins",
        "autoware_launch",
        "autoware-documentation",
        "autoware_tools",
        "autoware.privately-owned-vehicles",
        "openadkit",
        "autoware_ai",
        "autoware_ai_perception",
        "autoware_ai_planning",
        "autoware_ai_messages",
        "autoware_ai_simulation",
        "autoware_ai_visualization",
        "autoware_ai_drivers",
        "autoware_ai_utilities",
        "autoware_ai_common"
    ]

    # Initialize the GitHub GraphQL client
    try:
        client = GitHubGraphQLClient(token=args.token)
    except ValueError as e:
        print(f"Error: {e}")
        sys.exit(1)

    # Special case for autoware discussions
    try:
        discussions_file = "autoware_discussions.json"
        if args.use_cache and cache_exists(discussions_file):
            # Load cache and fetch new data incrementally
            cached_data = load_cache(discussions_file)
            last_cursor = get_last_cursor(cached_data)
            if last_cursor:
                print(f"Fetching new autoware discussions (from cached cursor)...")
                new_data = client.get_contributors("discussions", "autoware", start_cursor=last_cursor)
                if new_data:
                    # Merge cached and new data
                    merged_data = cached_data + new_data
                    dump_json(merged_data, discussions_file)
                    print(f"Added {len(new_data)} new discussions to cache")
                else:
                    print(f"No new discussions found")
            else:
                print(f"Cache exists but no cursor found, re-fetching all data...")
                discussions = client.get_contributors("discussions", "autoware")
                if discussions:
                    dump_json(discussions, discussions_file)
        else:
            print("Processing autoware discussions...")
            discussions = client.get_contributors("discussions", "autoware")
            if discussions:
                dump_json(discussions, discussions_file)
    except Exception as e:
        print(f"Error processing autoware discussions: {e}")

    # Process each repository
    for idx, repository in enumerate(repositories, 1):
        print(f"\n{'='*60}")
        print(f"Processing repository {idx}/{len(repositories)}: {repository}")
        print(f"{'='*60}\n")

        try:
            # Get issues
            issues_file = f"{repository}_issues.json"
            if args.use_cache and cache_exists(issues_file):
                # Load cache and fetch new data incrementally
                cached_issues = load_cache(issues_file)
                last_cursor = get_last_cursor(cached_issues)
                if last_cursor:
                    new_issues = client.get_contributors("issues", repository, start_cursor=last_cursor)
                    if new_issues:
                        merged_issues = cached_issues + new_issues
                        dump_json(merged_issues, issues_file)
                        print(f"Added {len(new_issues)} new issues to cache")
                    else:
                        print(f"No new issues found for {repository}")
                else:
                    issues = client.get_contributors("issues", repository)
                    if issues:
                        dump_json(issues, issues_file)
            else:
                issues = client.get_contributors("issues", repository)
                if issues:
                    dump_json(issues, issues_file)

            # Get pull requests
            prs_file = f"{repository}_prs.json"
            if args.use_cache and cache_exists(prs_file):
                # Load cache and fetch new data incrementally
                cached_prs = load_cache(prs_file)
                last_cursor = get_last_cursor(cached_prs)
                if last_cursor:
                    new_prs = client.get_contributors("pullRequests", repository, start_cursor=last_cursor)
                    if new_prs:
                        merged_prs = cached_prs + new_prs
                        dump_json(merged_prs, prs_file)
                        print(f"Added {len(new_prs)} new pull requests to cache")
                    else:
                        print(f"No new pull requests found for {repository}")
                else:
                    pull_requests = client.get_contributors("pullRequests", repository)
                    if pull_requests:
                        dump_json(pull_requests, prs_file)
            else:
                pull_requests = client.get_contributors("pullRequests", repository)
                if pull_requests:
                    dump_json(pull_requests, prs_file)

        except Exception as e:
            print(f"Error processing {repository}: {e}")
            continue

    print("\n" + "="*60)
    print("All repositories processed successfully!")
    print("="*60)

if __name__ == "__main__":
    main()
