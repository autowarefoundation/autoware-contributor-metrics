import sys
import argparse
from typing import List, Dict, Optional
from repositories import REPOSITORIES
from github_client import GitHubGraphQLClient, fetch_with_cache

CACHE_DIR = "cache/raw_commit_data"


def get_first_cursor(client: GitHubGraphQLClient, repository: str) -> Optional[str]:
    """Get the first cursor for a repository's commit history"""
    query = """
    query($repository: String!) {
        repository(owner:"autowarefoundation", name:$repository) {
            defaultBranchRef {
                target {
                    ... on Commit {
                        history(first:1) {
                            edges {
                                cursor
                                node {
                                    oid
                                    committedDate
                                }
                            }
                        }
                    }
                }
            }
        }
    }
    """

    data = client.execute_query(query, {"repository": repository})
    default_branch = data["data"]["repository"].get("defaultBranchRef")
    if not default_branch:
        return None
    edges = default_branch["target"]["history"]["edges"]
    if not edges:
        return None
    return edges[0]["cursor"]


def get_commits(client: GitHubGraphQLClient, repository: str, start_cursor: str = None) -> List[Dict]:
    """Retrieve all commits from a repository's default branch

    Args:
        client: GitHubGraphQLClient instance
        repository: Repository name
        start_cursor: Optional cursor to start fetching from (for incremental updates)
    """
    if start_cursor:
        print(f"Retrieving new commits for {repository} (incremental update)...")
    else:
        print(f"Retrieving commits for {repository}...")

    # Use provided cursor or get the first one
    if start_cursor:
        cursor = start_cursor
    else:
        cursor = get_first_cursor(client, repository)
        if cursor is None:
            print(f"No commits found for {repository}")
            return []

    all_edges = []
    page_count = 0

    query = """
    query($cursor: String!, $repository: String!) {
        repository(owner:"autowarefoundation", name:$repository) {
            defaultBranchRef {
                target {
                    ... on Commit {
                        history(first:100, after: $cursor) {
                            edges {
                                cursor
                                node {
                                    oid
                                    committedDate
                                    author {
                                        user {
                                            login
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
            }
        }
    }
    """

    while cursor:
        print(f"Fetching page {page_count + 1} for {repository}...")
        data = client.execute_query(query, {"cursor": cursor, "repository": repository})

        default_branch = data["data"]["repository"].get("defaultBranchRef")
        if not default_branch:
            break

        edges = default_branch["target"]["history"]["edges"]
        all_edges.extend(edges)
        page_count += 1

        if len(edges) > 0:
            cursor = edges[-1]["cursor"]
        else:
            cursor = None

    print(f"Retrieved {len(all_edges)} commits for {repository}")
    return all_edges


def main():
    """Main function to retrieve commits from all repositories"""
    parser = argparse.ArgumentParser(
        description="Retrieve commits from GitHub repositories"
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

    total_commits = 0

    for repository in repositories:
        try:
            cache_file = repository + "_commits.json"
            data = fetch_with_cache(
                cache_file,
                CACHE_DIR,
                lambda start_cursor=None, r=repository: get_commits(client, r, start_cursor=start_cursor),
                use_cache=args.use_cache,
            )
            if data:
                total_commits += len(data)
        except Exception as e:
            print(f"Error processing {repository}: {e}")
            continue

    print("\n" + "=" * 60)
    print(f"Retrieved commits from {len(repositories)} repositories")
    print(f"Total commits: {total_commits}")
    print("=" * 60)

if __name__ == "__main__":
    main()
