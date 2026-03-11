import sys
import argparse
from typing import List, Dict, Optional, Set
from pathlib import Path
from repositories import REPOSITORIES
from github_client import GitHubGraphQLClient, fetch_with_cache

CACHE_DIR = "cache/raw_stargazer_data"


def get_first_cursor(client: GitHubGraphQLClient, repository: str) -> Optional[str]:
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

    data = client.execute_query(query, {"repository": repository})
    edges = data["data"]["repository"]["stargazers"]["edges"]
    if not edges:
        return None
    return edges[0]["cursor"]


def get_stargazers(client: GitHubGraphQLClient, repository: str, start_cursor: str = None) -> List[Dict]:
    """Retrieve all stargazers from a repository

    Args:
        client: GitHubGraphQLClient instance
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
        cursor = get_first_cursor(client, repository)
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
        data = client.execute_query(query, {"cursor": cursor, "repository": repository})

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


def dump_usernames(usernames: Set[str], filename: str, output_dir: str = CACHE_DIR):
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

    try:
        client = GitHubGraphQLClient(token=args.token)
    except ValueError as e:
        print(f"Error: {e}")
        sys.exit(1)

    all_usernames = set()

    for repository in repositories:
        try:
            cache_file = repository + "_stargazers.json"
            data = fetch_with_cache(
                cache_file,
                CACHE_DIR,
                lambda start_cursor=None, r=repository: get_stargazers(client, r, start_cursor=start_cursor),
                use_cache=args.use_cache,
            )
            if data:
                usernames = get_usernames(data)
                dump_usernames(usernames, repository + "_usernames.txt")
                all_usernames.update(usernames)
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
