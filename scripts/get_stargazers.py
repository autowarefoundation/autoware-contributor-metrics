import sys
import argparse
from typing import List, Dict, Set
from pathlib import Path
from repositories import REPOSITORIES
from github_client import GitHubGraphQLClient, fetch_with_cache, dump_json, load_cache

CACHE_DIR = "cache/raw_stargazer_data"
COUNTS_FILE = "current_counts.json"
ACCESS_FILE = "access_status.json"

# Permission levels whose holders GitHub still lets list stargazers. Measured
# across all tracked repositories with no exceptions: WRITE and above works,
# READ/TRIAGE/NONE does not. See ACCESS_RESTRICTION_URL.
LISTING_PERMISSIONS = {"ADMIN", "MAINTAIN", "WRITE"}
RESTRICTED_PERMISSIONS = {"TRIAGE", "READ", "NONE"}
ACCESS_RESTRICTION_URL = (
    "https://github.blog/changelog/2026-06-30-upcoming-access-restrictions-"
    "to-public-api-endpoints-and-ui-views/"
)


def can_list_stargazers(viewer_permission: str) -> bool:
    """Whether the authenticated token may list this repository's stargazers.

    GitHub restricted stargazer listing to admins and collaborators. The
    refusal arrives as a generic "Something went wrong" message with HTTP 200
    and no error type, so it cannot be recognised after the fact — checking the
    permission up front is what keeps us from burning a full retry/backoff
    cycle on a request that can never succeed.

    Unknown levels are treated as allowed so that a future permission name does
    not silently drop a repository we can actually read.
    """
    if not viewer_permission:
        return False
    return viewer_permission.upper() not in RESTRICTED_PERMISSIONS


def get_repository_star_info(client: GitHubGraphQLClient, repository: str) -> Dict:
    """Current star count and the token's permission on a repository.

    Deliberately uses the scalar `stargazerCount`, never the `stargazers`
    connection: the scalar still works for repositories whose stargazer list
    the token may not read, so every repository keeps an accurate current
    number even when its per-date history cannot be built.
    """
    query = """
    query($repository: String!) {
        repository(owner:"autowarefoundation", name:$repository) {
            stargazerCount
            viewerPermission
        }
    }
    """
    data = client.execute_query(query, {"repository": repository})
    repo = data["data"]["repository"]
    return {
        "stargazerCount": repo["stargazerCount"],
        "viewerPermission": repo.get("viewerPermission"),
    }


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


def dump_usernames(usernames: Set[str], filename: str, output_dir: str = None):
    """Write usernames to a file"""
    # Resolved at call time, not bound as a default: a default argument would
    # capture CACHE_DIR at import and ignore any later override.
    output_path = Path(output_dir if output_dir is not None else CACHE_DIR)
    output_path.mkdir(exist_ok=True, parents=True)
    file_path = output_path / filename
    with open(file_path, 'w') as f:
        for username in sorted(usernames):
            f.write(f"{username}\n")
    print(f"Saved {filename} to {file_path}")


def process_repository(client: GitHubGraphQLClient, repository: str,
                       use_cache: bool, status: Dict) -> Set[str]:
    """Fetch one repository's stargazers, recording what was possible.

    Returns the usernames collected (empty when the listing is restricted or
    fails). Never raises: one repository must not end the run.
    """
    try:
        info = get_repository_star_info(client, repository)
    except Exception as e:
        print(f"Could not read star info for {repository}: {e}")
        return set()

    permission = info["viewerPermission"]
    allowed = can_list_stargazers(permission)
    status[repository] = {
        "stars": info["stargazerCount"],
        "viewer_permission": permission,
        "can_list_stargazers": allowed,
        "listing_failed": False,
    }

    if not allowed:
        # Skipping rather than trying: the request is guaranteed to fail, and
        # attempting it would cost a full retry/backoff cycle per repository.
        print(f"Skipping stargazer listing for {repository}: "
              f"not permitted with {permission} permission")
        return set()

    try:
        data = fetch_with_cache(
            repository + "_stargazers.json",
            CACHE_DIR,
            lambda start_cursor=None, r=repository: get_stargazers(client, r, start_cursor=start_cursor),
            use_cache=use_cache,
        )
    except Exception as e:
        print(f"Error processing {repository}: {e}")
        status[repository]["listing_failed"] = True
        return set()

    if not data:
        return set()
    usernames = get_usernames(data)
    dump_usernames(usernames, repository + "_usernames.txt")
    return usernames


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

    # Keep previously recorded values so a transient failure does not erase one.
    cached_counts = load_cache(COUNTS_FILE, CACHE_DIR)
    current_counts = cached_counts if isinstance(cached_counts, dict) else {}
    cached_status = load_cache(ACCESS_FILE, CACHE_DIR)
    access_status = cached_status if isinstance(cached_status, dict) else {}

    for repository in repositories:
        status = {}
        all_usernames.update(
            process_repository(client, repository, args.use_cache, status)
        )
        if repository in status:
            access_status[repository] = status[repository]
            current_counts[repository] = status[repository]["stars"]

    # Save aggregated usernames
    dump_usernames(all_usernames, "usernames.txt")
    dump_json(current_counts, COUNTS_FILE, CACHE_DIR)
    dump_json(access_status, ACCESS_FILE, CACHE_DIR)

    restricted = sorted(
        r for r, s in access_status.items() if not s.get("can_list_stargazers", True)
    )

    print("\n" + "="*60)
    print(f"Retrieved stargazers from {len(repositories)} repositories")
    print(f"Total unique stargazers: {len(all_usernames)}")
    print(f"Current star counts recorded: {len(current_counts)} repositories "
          f"({sum(current_counts.values())} stars total)")
    if restricted:
        print(f"\nStargazer listing not permitted for {len(restricted)} repositories "
              f"(no per-date history can be built for them):")
        for repository in restricted:
            print(f"  - {repository} ({access_status[repository].get('viewer_permission')})")
        print(f"See {ACCESS_RESTRICTION_URL}")
    print("="*60)

if __name__ == "__main__":
    main()
