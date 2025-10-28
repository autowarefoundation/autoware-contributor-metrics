import os
import sys
import argparse
import requests
import json
import time
from typing import List, Dict, Any, Set
from pathlib import Path


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

        try:
            resp = requests.post(
                self.base_url,
                json=payload,
                headers=self.headers,
                timeout=60
            )
            resp.raise_for_status()
            data = resp.json()

            # Check for GraphQL errors
            if "errors" in data:
                raise Exception(f"GraphQL errors: {data['errors']}")

            # Rate limiting
            time.sleep(self.rate_limit_wait)
            return data

        except requests.exceptions.RequestException as e:
            print(f"Request failed: {e}")
            sys.exit(1)

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

    def get_stargazers(self, repository: str) -> List[Dict]:
        """Retrieve all stargazers from a repository"""
        print(f"Retrieving stargazers for {repository}...")

        first_cursor = self.get_first_cursor(repository)
        if first_cursor is None:
            print(f"No stargazers found for {repository}")
            return []

        all_edges = []
        cursor = first_cursor
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
    args = parser.parse_args()

    # List of Autoware repositories
    repositories = [
        "autoware",
        "autoware_core",
        "autoware_common",
        "autoware_universe",
        "autoware.privately-owned-vehicles",
        "autoware_msgs",
        "autoware_launch",
        "autoware-documentation",
        "autoware_tools",
        "autoware_cmake",
        "autoware_utils",
        "autoware_lanelet2_extension",
        "autoware_rviz_plugins",
        "autoware_adapi_msgs",
        "autoware_internal_msgs",
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
            stargazers = client.get_stargazers(repository)
            usernames = get_usernames(stargazers)
            all_usernames.update(usernames)
            dump_json(stargazers, repository + "_stargazers.json")
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