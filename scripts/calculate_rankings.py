import json
import datetime
from typing import Dict, List
from pathlib import Path
from collections import defaultdict

# Bot users to exclude from rankings
BOT_USERS = {
    "dependabot[bot]",
    "github-actions[bot]",
    "github-actions",
    "renovate[bot]",
    "codecov[bot]",
    "codecov",
    "pre-commit-ci[bot]",
    "mergify[bot]",
    "stale",
    "awf-autoware-bot",
}


class RankingCalculator:
    """Class to calculate contributor rankings by month and year"""

    def __init__(self, start_date: datetime.datetime = None):
        self.start_date = start_date or datetime.datetime(2022, 1, 1)
        # {author: {month_key: count}}
        self.code_contributions = defaultdict(lambda: defaultdict(int))
        self.community_contributions = defaultdict(lambda: defaultdict(int))
        self.review_contributions = defaultdict(lambda: defaultdict(int))

    def _get_month_key(self, date: datetime.datetime) -> str:
        """Get month key in YYYY-MM format"""
        return date.strftime('%Y-%m')

    def _get_year_key(self, date: datetime.datetime) -> str:
        """Get year key in YYYY format"""
        return date.strftime('%Y')

    def _is_bot(self, author: str) -> bool:
        """Check if the author is a bot"""
        return author in BOT_USERS or author.endswith("[bot]")

    def _parse_date(self, date_str: str) -> datetime.datetime:
        """Parse ISO format date string"""
        try:
            return datetime.datetime.strptime(date_str, '%Y-%m-%dT%H:%M:%SZ')
        except (ValueError, TypeError):
            return None

    def process_prs(self, file_path: str) -> None:
        """Process PR file for code contributions (merged PR count per author)"""
        try:
            with open(file_path, 'r') as f:
                data = json.load(f)

            edges = data if isinstance(data, list) else data.get("data", [])

            for edge in edges:
                if not isinstance(edge, dict) or "node" not in edge:
                    continue

                node = edge["node"]
                if node.get("author") is None:
                    continue

                # Only count merged PRs
                merged_at = node.get("mergedAt")
                if not merged_at:
                    continue

                author = node["author"].get("login")

                if not author or self._is_bot(author):
                    continue

                # Use mergedAt date for ranking
                date = self._parse_date(merged_at)
                if date and date >= self.start_date:
                    month_key = self._get_month_key(date)
                    self.code_contributions[author][month_key] += 1

        except (FileNotFoundError, json.JSONDecodeError) as e:
            print(f"Warning: Could not process {file_path}: {e}")

    def process_issues_discussions(self, file_path: str) -> None:
        """Process issue/discussion file for community contributions (post + comment count)"""
        try:
            with open(file_path, 'r') as f:
                data = json.load(f)

            edges = data if isinstance(data, list) else data.get("data", [])

            for edge in edges:
                if not isinstance(edge, dict) or "node" not in edge:
                    continue

                node = edge["node"]

                # Count Issue/Discussion author (post creator)
                if node.get("author"):
                    author = node["author"].get("login")
                    created_at = node.get("createdAt")

                    if author and created_at and not self._is_bot(author):
                        date = self._parse_date(created_at)
                        if date and date >= self.start_date:
                            month_key = self._get_month_key(date)
                            self.community_contributions[author][month_key] += 1

                # Count comments
                if "comments" in node and "edges" in node["comments"]:
                    for comment_edge in node["comments"]["edges"]:
                        comment_node = comment_edge.get("node")
                        if not comment_node or not comment_node.get("author"):
                            continue

                        author = comment_node["author"].get("login")
                        created_at = comment_node.get("createdAt")

                        if not author or not created_at or self._is_bot(author):
                            continue

                        date = self._parse_date(created_at)
                        if date and date >= self.start_date:
                            month_key = self._get_month_key(date)
                            self.community_contributions[author][month_key] += 1

        except (FileNotFoundError, json.JSONDecodeError) as e:
            print(f"Warning: Could not process {file_path}: {e}")

    def process_reviews(self, file_path: str) -> None:
        """Process PR file for review contributions (PR comments + reviews, excluding self)"""
        try:
            with open(file_path, 'r') as f:
                data = json.load(f)

            edges = data if isinstance(data, list) else data.get("data", [])

            for edge in edges:
                if not isinstance(edge, dict) or "node" not in edge:
                    continue

                node = edge["node"]

                # Get PR author to exclude self-reviews/comments
                pr_author = None
                if node.get("author"):
                    pr_author = node["author"].get("login")

                # Count PR comments (Conversation tab) - exclude self-comments
                if "comments" in node and "edges" in node["comments"]:
                    for comment_edge in node["comments"]["edges"]:
                        comment_node = comment_edge.get("node")
                        if not comment_node or not comment_node.get("author"):
                            continue

                        author = comment_node["author"].get("login")
                        created_at = comment_node.get("createdAt")

                        # Exclude self-comments and bots
                        if not author or not created_at or self._is_bot(author):
                            continue
                        if author == pr_author:
                            continue

                        date = self._parse_date(created_at)
                        if date and date >= self.start_date:
                            month_key = self._get_month_key(date)
                            self.review_contributions[author][month_key] += 1

                # Count reviews - exclude self-reviews
                if "reviews" in node and "edges" in node["reviews"]:
                    for review_edge in node["reviews"]["edges"]:
                        review_node = review_edge.get("node")
                        if not review_node:
                            continue

                        if review_node.get("author"):
                            author = review_node["author"].get("login")
                            created_at = review_node.get("createdAt")

                            # Exclude self-reviews and bots
                            if not author or not created_at or self._is_bot(author):
                                continue
                            if author == pr_author:
                                continue

                            date = self._parse_date(created_at)
                            if date and date >= self.start_date:
                                month_key = self._get_month_key(date)
                                self.review_contributions[author][month_key] += 1

        except (FileNotFoundError, json.JSONDecodeError) as e:
            print(f"Warning: Could not process {file_path}: {e}")

    def _generate_ranking(self, contributions: Dict, period_key: str, limit: int = 50) -> List[Dict]:
        """Generate ranking for a specific period"""
        period_counts = []
        for author, months in contributions.items():
            count = months.get(period_key, 0)
            if count > 0:
                period_counts.append({"author": author, "count": count})

        # Sort by count descending
        period_counts.sort(key=lambda x: (-x["count"], x["author"]))

        # Add rank
        for i, item in enumerate(period_counts[:limit], 1):
            item["rank"] = i

        return period_counts[:limit]

    def _generate_yearly_ranking(self, contributions: Dict, year: str, limit: int = 50) -> List[Dict]:
        """Generate yearly ranking by aggregating all months in the year"""
        year_counts = defaultdict(int)
        for author, months in contributions.items():
            for month_key, count in months.items():
                if month_key.startswith(year):
                    year_counts[author] += count

        period_counts = [{"author": author, "count": count} for author, count in year_counts.items() if count > 0]
        period_counts.sort(key=lambda x: (-x["count"], x["author"]))

        for i, item in enumerate(period_counts[:limit], 1):
            item["rank"] = i

        return period_counts[:limit]

    def generate_rankings(self) -> Dict:
        """Generate all rankings (monthly and yearly)"""
        # Get all unique months and years
        all_months = set()
        all_years = set()

        for contributions in [self.code_contributions, self.community_contributions, self.review_contributions]:
            for author_months in contributions.values():
                all_months.update(author_months.keys())

        for month in all_months:
            all_years.add(month[:4])

        # Generate monthly rankings
        monthly = {}
        for month in sorted(all_months):
            monthly[month] = {
                "code": self._generate_ranking(self.code_contributions, month),
                "community": self._generate_ranking(self.community_contributions, month),
                "review": self._generate_ranking(self.review_contributions, month),
            }

        # Generate yearly rankings
        yearly = {}
        for year in sorted(all_years):
            yearly[year] = {
                "code": self._generate_yearly_ranking(self.code_contributions, year),
                "community": self._generate_yearly_ranking(self.community_contributions, year),
                "review": self._generate_yearly_ranking(self.review_contributions, year),
            }

        return {
            "monthly": monthly,
            "yearly": yearly,
            "last_updated": datetime.datetime.now().strftime('%Y-%m-%d'),
        }


def main():
    """Main function to calculate contributor rankings"""
    print("Calculating contributor rankings...")

    calculator = RankingCalculator()

    # Repository list
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
        "autoware_ai_common",
    ]

    cache_dir = Path("cache/raw_contributor_data")

    # Process PRs for code contributions and reviews
    print("Processing PRs for code contributions and reviews...")
    for repo in repositories:
        prs_file = cache_dir / f"{repo}_prs.json"
        if prs_file.exists():
            calculator.process_prs(str(prs_file))
            calculator.process_reviews(str(prs_file))

    # Process issues for community contributions
    print("Processing issues for community contributions...")
    for repo in repositories:
        issues_file = cache_dir / f"{repo}_issues.json"
        if issues_file.exists():
            calculator.process_issues_discussions(str(issues_file))

    # Process discussions for community contributions
    print("Processing discussions for community contributions...")
    discussions_file = cache_dir / "autoware_discussions.json"
    if discussions_file.exists():
        calculator.process_issues_discussions(str(discussions_file))

    # Generate rankings
    print("Generating rankings...")
    rankings = calculator.generate_rankings()

    # Write output
    output_path = Path("results")
    output_path.mkdir(exist_ok=True, parents=True)

    output_file = output_path / "rankings.json"
    with open(output_file, 'w') as f:
        json.dump(rankings, f, indent=2)

    print(f"\nDone! Generated {output_file}")

    # Print summary
    monthly_periods = len(rankings["monthly"])
    yearly_periods = len(rankings["yearly"])
    print(f"Monthly periods: {monthly_periods}")
    print(f"Yearly periods: {yearly_periods}")

    # Print latest month stats
    if rankings["monthly"]:
        latest_month = sorted(rankings["monthly"].keys())[-1]
        print(f"\nLatest month ({latest_month}):")
        print(f"  Code contributors: {len(rankings['monthly'][latest_month]['code'])}")
        print(f"  Community contributors: {len(rankings['monthly'][latest_month]['community'])}")
        print(f"  Review contributors: {len(rankings['monthly'][latest_month]['review'])}")


if __name__ == "__main__":
    main()
