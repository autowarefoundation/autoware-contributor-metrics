import sys
import argparse
from typing import List, Dict, Set
from pathlib import Path
from repositories import REPOSITORIES
from github_client import GitHubGraphQLClient, fetch_with_cache, dump_json, load_cache

CACHE_DIR = "cache/raw_stargazer_data"
COUNTS_FILE = "current_counts.json"


def get_stargazer_count(client: GitHubGraphQLClient, repository: str) -> int:
    """Current star count for a repository.

    Uses the scalar `stargazerCount` rather than the `stargazers` connection.
    GitHub fails every `stargazers(...)` query for some repositories (see
    "Non-obvious Behaviors" in CLAUDE.md) but still reports this scalar
    correctly, so those repositories at least keep an accurate current number
    even though their per-date history cannot be rebuilt.
    """
    query = """
    query($repository: String!) {
        repository(owner:"autowarefoundation", name:$repository) {
            stargazerCount
        }
    }
    """
    data = client.execute_query(query, {"repository": repository})
    return data["data"]["repository"]["stargazerCount"]


def get_stargazers(client: GitHubGraphQLClient, repository: str, start_cursor: str = None) -> List[Dict]:
    """Retrieve all stargazers from a repository

    Args:
        client: GitHubGraphQLClient instance
        repository: Repository name
        start_cursor: Optional cursor to resume from (for incremental updates).
                      None starts at the very first stargazer.
    """
    if start_cursor:
        print(f"Retrieving new stargazers for {repository} (incremental update)...")
    else:
        print(f"Retrieving stargazers for {repository}...")

    # `after: null` starts at the very first stargazer. Seeding this with the
    # first stargazer's own cursor would silently skip that stargazer, because
    # `after` is exclusive.
    cursor = start_cursor
    all_edges = []
    page_count = 0

    query = """
    query($cursor: String, $repository: String!) {
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

    while True:
        print(f"Fetching page {page_count + 1} for {repository}...")
        data = client.execute_query(query, {"cursor": cursor, "repository": repository})

        edges = data["data"]["repository"]["stargazers"]["edges"]
        if not edges:
            break
        all_edges.extend(edges)
        page_count += 1
        cursor = edges[-1]["cursor"]

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

    # Keep previously recorded counts so a transient failure does not erase one.
    cached_counts = load_cache(COUNTS_FILE, CACHE_DIR)
    current_counts = cached_counts if isinstance(cached_counts, dict) else {}

    for repository in repositories:
        # Recorded before the edge fetch, and separately from it: this scalar
        # still works for repositories whose stargazers connection is broken,
        # which are exactly the ones the fetch below will fail on.
        try:
            current_counts[repository] = get_stargazer_count(client, repository)
        except Exception as e:
            print(f"Could not read stargazerCount for {repository}: {e}")

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
    dump_json(current_counts, COUNTS_FILE, CACHE_DIR)

    print("\n" + "="*60)
    print(f"Retrieved stargazers from {len(repositories)} repositories")
    print(f"Total unique stargazers: {len(all_usernames)}")
    print(f"Current star counts recorded: {len(current_counts)} repositories "
          f"({sum(current_counts.values())} stars total)")
    print("="*60)

if __name__ == "__main__":
    main()
