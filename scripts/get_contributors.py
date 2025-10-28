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

    def get_contributors(self, contributor_type: str, repository: str) -> List[Dict]:
        """Retrieve all contributors of a specific type from a repository"""
        print(f"Retrieving {contributor_type} for {repository}...")

        first_cursor = self.get_first_cursor(contributor_type, repository)
        if first_cursor is None:
            print(f"No {contributor_type} found for {repository}")
            return []

        all_edges = []
        cursor = first_cursor
        page_count = 0

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
                            }}
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
        print("Processing autoware discussions...")
        discussions = client.get_contributors("discussions", "autoware")
        if discussions:
            dump_json(discussions, "autoware_discussions.json")
    except Exception as e:
        print(f"Error processing autoware discussions: {e}")

    # Process each repository
    for idx, repository in enumerate(repositories, 1):
        print(f"\n{'='*60}")
        print(f"Processing repository {idx}/{len(repositories)}: {repository}")
        print(f"{'='*60}\n")

        try:
            # Get issues
            issues = client.get_contributors("issues", repository)
            if issues:
                dump_json(issues, f"{repository}_issues.json")

            # Get pull requests
            pull_requests = client.get_contributors("pullRequests", repository)
            if pull_requests:
                dump_json(pull_requests, f"{repository}_prs.json")

        except Exception as e:
            print(f"Error processing {repository}: {e}")
            continue

    print("\n" + "="*60)
    print("All repositories processed successfully!")
    print("="*60)

if __name__ == "__main__":
    main()
