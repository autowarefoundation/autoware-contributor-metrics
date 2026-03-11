import sys
import argparse
from typing import List, Dict, Optional
from repositories import REPOSITORIES
from github_client import GitHubGraphQLClient, fetch_with_cache

CACHE_DIR = "cache/raw_contributor_data"


def get_first_cursor(client: GitHubGraphQLClient, contributor_type: str, repository: str) -> Optional[str]:
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

    data = client.execute_query(query, {"repository": repository})
    edges = data["data"]["repository"][contributor_type]["edges"]
    if not edges:
        return None
    return edges[0]["cursor"]


def get_contributors(client: GitHubGraphQLClient, contributor_type: str, repository: str, start_cursor: str = None) -> List[Dict]:
    """Retrieve all contributors of a specific type from a repository

    Args:
        client: GitHubGraphQLClient instance
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
        cursor = get_first_cursor(client, contributor_type, repository)
        if cursor is None:
            print(f"No {contributor_type} found for {repository}")
            return []

    all_edges = []
    page_count = 0

    # Add mergedAt and reviews field only for pullRequests
    pr_extra_fields = ""
    if contributor_type == "pullRequests":
        pr_extra_fields = """
                        mergedAt
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
                        }}{pr_extra_fields}
                    }}
                }}
            }}
        }}
    }}
    """

    while cursor:
        print(f"Fetching page {page_count + 1} for {repository} {contributor_type}...")
        data = client.execute_query(query, {"cursor": cursor, "repository": repository})

        edges = data["data"]["repository"][contributor_type]["edges"]
        all_edges.extend(edges)
        page_count += 1

        if len(edges) > 0:
            cursor = edges[-1]["cursor"]
        else:
            cursor = None

    print(f"Retrieved {len(all_edges)} {contributor_type} for {repository}")
    return all_edges


def main():
    """Main function to generate JSON files for all repositories"""
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

    repositories = REPOSITORIES

    try:
        client = GitHubGraphQLClient(token=args.token)
    except ValueError as e:
        print(f"Error: {e}")
        sys.exit(1)

    # Special case for autoware discussions
    try:
        fetch_with_cache(
            "autoware_discussions.json",
            CACHE_DIR,
            lambda start_cursor=None: get_contributors(client, "discussions", "autoware", start_cursor=start_cursor),
            use_cache=args.use_cache,
        )
    except Exception as e:
        print(f"Error processing autoware discussions: {e}")

    # Process each repository
    for idx, repository in enumerate(repositories, 1):
        print(f"\n{'='*60}")
        print(f"Processing repository {idx}/{len(repositories)}: {repository}")
        print(f"{'='*60}\n")

        try:
            # Get issues
            fetch_with_cache(
                f"{repository}_issues.json",
                CACHE_DIR,
                lambda start_cursor=None, r=repository: get_contributors(client, "issues", r, start_cursor=start_cursor),
                use_cache=args.use_cache,
            )

            # Get pull requests
            fetch_with_cache(
                f"{repository}_prs.json",
                CACHE_DIR,
                lambda start_cursor=None, r=repository: get_contributors(client, "pullRequests", r, start_cursor=start_cursor),
                use_cache=args.use_cache,
            )

        except Exception as e:
            print(f"Error processing {repository}: {e}")
            continue

    print("\n" + "="*60)
    print("All repositories processed successfully!")
    print("="*60)

if __name__ == "__main__":
    main()
