import json
import datetime
from typing import Dict, List, Tuple
from pathlib import Path
from collections import defaultdict
from repositories import REPOSITORIES

class ContributorHistory:
    """Class to track contributor history and generate cumulative statistics"""

    def __init__(self, start_date: datetime.datetime = None):
        self.start_date = start_date or datetime.datetime(2022, 1, 1)
        self.code_contributors = {}  # {author: first_contribution_date}
        self.community_contributors = {}
        self.autoware_contributors = {}

    def load_contributors_from_file(self, file_path: str, contributor_dict: Dict) -> None:
        """Load contributors from a JSON file and track their first contribution date"""
        try:
            with open(file_path, 'r') as f:
                data = json.load(f)

            if isinstance(data, list):
                edges = data
            elif isinstance(data, dict) and "data" in data:
                edges = data["data"]
            else:
                print(f"Warning: Unexpected format in {file_path}")
                return

            for edge in edges:
                if not isinstance(edge, dict) or "node" not in edge:
                    continue

                node = edge["node"]

                # Process main contribution
                if node.get("author") is not None:
                    author = node["author"].get("login")
                    created_at = node.get("createdAt")

                    if author and created_at:
                        try:
                            d = datetime.datetime.strptime(created_at, '%Y-%m-%dT%H:%M:%SZ')
                            if d >= self.start_date:
                                if author not in contributor_dict or contributor_dict[author] > d:
                                    contributor_dict[author] = d
                        except ValueError:
                            pass

                # Process comments
                if "comments" in node and "edges" in node["comments"]:
                    for comment_edge in node["comments"]["edges"]:
                        if comment_edge.get("node") and comment_edge["node"].get("author"):
                            author = comment_edge["node"]["author"].get("login")
                            created_at = comment_edge["node"].get("createdAt")

                            if author and created_at:
                                try:
                                    d = datetime.datetime.strptime(created_at, '%Y-%m-%dT%H:%M:%SZ')
                                    if d >= self.start_date:
                                        if author not in contributor_dict or contributor_dict[author] > d:
                                            contributor_dict[author] = d
                                except ValueError:
                                    pass

        except FileNotFoundError:
            print(f"Warning: File not found: {file_path}")
        except json.JSONDecodeError:
            print(f"Warning: Invalid JSON in file: {file_path}")

    def merge_contributors(self) -> None:
        """Merge code and community contributors into autoware_contributors"""
        self.autoware_contributors = self.community_contributors.copy()

        for author, date in self.code_contributors.items():
            if author not in self.autoware_contributors:
                self.autoware_contributors[author] = date
            elif self.autoware_contributors[author] > date:
                self.autoware_contributors[author] = date

    def count_per_day(self, contributors: Dict) -> Dict[datetime.date, int]:
        """Count how many contributors first contributed on each day"""
        contributors_per_day = defaultdict(int)

        for author in contributors.keys():
            date = contributors[author]
            day = datetime.date(date.year, date.month, date.day)
            contributors_per_day[day] += 1

        return dict(contributors_per_day)

    def generate_cumulative_data(self, contributors_per_day: Dict[datetime.date, int]) -> List[Dict]:
        """Generate cumulative contributor data sorted by date"""
        # Create a list of all dates
        all_dates = sorted(contributors_per_day.keys())

        # Calculate cumulative counts
        cumulative_data = []
        cumulative_count = 0

        for date in all_dates:
            cumulative_count += contributors_per_day[date]
            cumulative_data.append({
                "date": date.strftime('%Y-%m-%d'),
                "contributors_count": cumulative_count
            })

        return cumulative_data

    def to_json(self) -> Dict:
        """Convert all contributor history to JSON format"""
        # Count contributors per day
        code_per_day = self.count_per_day(self.code_contributors)
        community_per_day = self.count_per_day(self.community_contributors)
        autoware_per_day = self.count_per_day(self.autoware_contributors)

        # Generate cumulative data
        return {
            "autoware_code_contributors": self.generate_cumulative_data(code_per_day),
            "autoware_community_contributors": self.generate_cumulative_data(community_per_day),
            "autoware_contributors": self.generate_cumulative_data(autoware_per_day)
        }


def main():
    """Main function to process contributor history"""
    print("Processing contributor history...")

    history = ContributorHistory()

    repositories = REPOSITORIES
    cache_dir = Path("cache/raw_contributor_data")

    # Load community contributors (issues and discussions)
    print("Loading community contributors...")
    for repo in repositories:
        issues_file = cache_dir / f"{repo}_issues.json"
        if issues_file.exists():
            history.load_contributors_from_file(str(issues_file), history.community_contributors)

    # Special case: autoware discussions
    discussions_file = cache_dir / "autoware_discussions.json"
    if discussions_file.exists():
        history.load_contributors_from_file(str(discussions_file), history.community_contributors)

    # Load code contributors (pull requests)
    print("Loading code contributors...")
    for repo in repositories:
        prs_file = cache_dir / f"{repo}_prs.json"
        if prs_file.exists():
            history.load_contributors_from_file(str(prs_file), history.code_contributors)

    # Merge contributors
    print("Merging contributors...")
    history.merge_contributors()

    # Generate JSON output
    print("Generating JSON output...")
    output_data = history.to_json()

    # Write to file
    output_path = Path("results")
    output_path.mkdir(exist_ok=True, parents=True)

    output_file = output_path / "contributors_history.json"
    with open(output_file, 'w') as f:
        json.dump(output_data, f, indent=2)

    print(f"\nDone! Generated {output_file}")
    print(f"Code contributors: {len(history.code_contributors)}")
    print(f"Community contributors: {len(history.community_contributors)}")
    print(f"Total contributors: {len(history.autoware_contributors)}")


if __name__ == "__main__":
    main()
