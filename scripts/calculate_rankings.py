import datetime
from typing import Dict, List, Set
from pathlib import Path
from collections import defaultdict
from repositories import REPOSITORIES
from utils import parse_github_datetime, load_json_file, write_json_output

# Bot users to exclude from rankings
BOT_USERS = {
    "dependabot[bot]",
    "dependabot",
    "github-actions[bot]",
    "github-actions",
    "renovate[bot]",
    "codecov[bot]",
    "codecov",
    "pre-commit-ci[bot]",
    "pre-commit-ci",
    "mergify[bot]",
    "mergify",
    "stale",
    "awf-autoware-bot",
    "copilot-pull-request-reviewer",
    "claude",
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
        return date.strftime('%Y-%m')

    def _get_quarter_key(self, date: datetime.datetime) -> str:
        quarter = (date.month - 1) // 3 + 1
        return f"{date.strftime('%Y')}-Q{quarter}"

    def _is_bot(self, author: str) -> bool:
        return author in BOT_USERS or author.endswith("[bot]")

    def _load_edges(self, file_path: str) -> List[Dict]:
        """Load JSON and return the edge list."""
        data = load_json_file(file_path)
        if not data:
            return []
        return data if isinstance(data, list) else data.get("data", [])

    def _record_contribution(self, author: str, date_str: str, target: Dict) -> None:
        """Parse date, check start_date and bots, record into target contributions dict."""
        if not author or not date_str or self._is_bot(author):
            return
        date = parse_github_datetime(date_str)
        if date and date >= self.start_date:
            month_key = self._get_month_key(date)
            target[author][month_key] += 1

    def _process_comments(self, node: Dict, target: Dict, exclude_author: str = None) -> None:
        """Iterate comment edges and record each into target."""
        if "comments" not in node or "edges" not in node["comments"]:
            return
        for comment_edge in node["comments"]["edges"]:
            comment_node = comment_edge.get("node")
            if not comment_node or not comment_node.get("author"):
                continue
            author = comment_node["author"].get("login")
            if exclude_author and author == exclude_author:
                continue
            self._record_contribution(author, comment_node.get("createdAt"), target)

    def process_prs_and_reviews(self, file_path: str) -> None:
        """Process PR file for both code contributions and review contributions in one pass."""
        for edge in self._load_edges(file_path):
            if not isinstance(edge, dict) or "node" not in edge:
                continue

            node = edge["node"]
            if node.get("author") is None:
                continue

            pr_author = node["author"].get("login")

            # Code contributions: count merged PRs
            merged_at = node.get("mergedAt")
            if merged_at:
                self._record_contribution(pr_author, merged_at, self.code_contributions)

            # Review contributions: PR comments (excluding self)
            self._process_comments(node, self.review_contributions, exclude_author=pr_author)

            # Review contributions: reviews (excluding self)
            if "reviews" in node and "edges" in node["reviews"]:
                for review_edge in node["reviews"]["edges"]:
                    review_node = review_edge.get("node")
                    if not review_node or not review_node.get("author"):
                        continue
                    author = review_node["author"].get("login")
                    if author == pr_author:
                        continue
                    self._record_contribution(author, review_node.get("createdAt"), self.review_contributions)

    def process_issues_discussions(self, file_path: str) -> None:
        """Process issue/discussion file for community contributions (post + comment count)"""
        for edge in self._load_edges(file_path):
            if not isinstance(edge, dict) or "node" not in edge:
                continue

            node = edge["node"]

            # Count Issue/Discussion author (post creator)
            if node.get("author"):
                author = node["author"].get("login")
                self._record_contribution(author, node.get("createdAt"), self.community_contributions)

            # Count comments
            self._process_comments(node, self.community_contributions)

    def _get_month_keys_for_period(self, period_key: str) -> Set[str]:
        """Convert any period format to a set of month keys.

        "2024-03" -> {"2024-03"}
        "2024-Q1" -> {"2024-01", "2024-02", "2024-03"}
        "2024"    -> {"2024-01", ..., "2024-12"}
        """
        if "-Q" in period_key:
            year_str, q_str = period_key.split('-Q')
            quarter = int(q_str)
            start_month = (quarter - 1) * 3 + 1
            return {f"{year_str}-{m:02d}" for m in range(start_month, start_month + 3)}
        elif len(period_key) == 4:
            # Yearly
            return {f"{period_key}-{m:02d}" for m in range(1, 13)}
        else:
            # Monthly
            return {period_key}

    def _generate_ranking_for_period(self, contributions: Dict, period_key: str, limit: int = 50) -> List[Dict]:
        """Generate ranking for any period type (month, quarter, year)."""
        month_keys = self._get_month_keys_for_period(period_key)

        period_counts = {}
        for author, months in contributions.items():
            total = sum(months.get(mk, 0) for mk in month_keys)
            if total > 0:
                period_counts[author] = total

        ranked = [{"author": a, "count": c} for a, c in period_counts.items()]
        ranked.sort(key=lambda x: (-x["count"], x["author"]))

        for i, item in enumerate(ranked[:limit], 1):
            item["rank"] = i

        return ranked[:limit]

    def _calculate_mvp_ranking(self, code_ranking: List[Dict], community_ranking: List[Dict], review_ranking: List[Dict], limit: int = 50) -> List[Dict]:
        """Calculate MVP ranking based on combined ranks across all categories.

        Only includes authors who appear in ALL THREE categories.
        """
        code_ranks = {item["author"]: item["rank"] for item in code_ranking}
        community_ranks = {item["author"]: item["rank"] for item in community_ranking}
        review_ranks = {item["author"]: item["rank"] for item in review_ranking}

        # Build count dicts for O(1) tiebreaker lookup
        code_counts = {item["author"]: item["count"] for item in code_ranking}
        community_counts = {item["author"]: item["count"] for item in community_ranking}
        review_counts = {item["author"]: item["count"] for item in review_ranking}

        # Get authors who appear in ALL three categories
        all_authors = set(code_ranks.keys()) & set(community_ranks.keys()) & set(review_ranks.keys())

        mvp_scores = []
        for author in all_authors:
            total_rank = code_ranks[author] + community_ranks[author] + review_ranks[author]
            total_count = code_counts[author] + community_counts[author] + review_counts[author]

            mvp_scores.append({
                "author": author,
                "score": total_rank,
                "count": total_count,
            })

        # Sort by score (ascending), then by total count (descending) for tiebreaker
        mvp_scores.sort(key=lambda x: (x["score"], -x["count"], x["author"]))

        for i, item in enumerate(mvp_scores[:limit], 1):
            item["rank"] = i

        return mvp_scores[:limit]

    def generate_rankings(self) -> Dict:
        """Generate all rankings (monthly, quarterly, and yearly)"""
        # Collect all unique months
        all_months = set()
        for contributions in [self.code_contributions, self.community_contributions, self.review_contributions]:
            for author_months in contributions.values():
                all_months.update(author_months.keys())

        # Derive quarters and years from months
        all_quarters = set()
        all_years = set()
        for month in all_months:
            all_years.add(month[:4])
            date = datetime.datetime.strptime(month, '%Y-%m')
            all_quarters.add(self._get_quarter_key(date))

        # Build period_types: {type_name: sorted list of period keys}
        period_types = {
            "monthly": sorted(all_months),
            "quarterly": sorted(all_quarters),
            "yearly": sorted(all_years),
        }

        result = {}
        for period_type, period_keys in period_types.items():
            rankings = {}
            for period_key in period_keys:
                code_ranking = self._generate_ranking_for_period(self.code_contributions, period_key)
                community_ranking = self._generate_ranking_for_period(self.community_contributions, period_key)
                review_ranking = self._generate_ranking_for_period(self.review_contributions, period_key)
                mvp_ranking = self._calculate_mvp_ranking(code_ranking, community_ranking, review_ranking)

                rankings[period_key] = {
                    "code": code_ranking,
                    "community": community_ranking,
                    "review": review_ranking,
                    "mvp": mvp_ranking,
                }
            result[period_type] = rankings

        result["last_updated"] = datetime.datetime.now().strftime('%Y-%m-%d')
        return result


def main():
    """Main function to calculate contributor rankings"""
    print("Calculating contributor rankings...")

    calculator = RankingCalculator()

    repositories = REPOSITORIES
    cache_dir = Path("cache/raw_contributor_data")

    # Process PRs for code contributions and reviews (single pass per file)
    print("Processing PRs for code contributions and reviews...")
    for repo in repositories:
        prs_file = cache_dir / f"{repo}_prs.json"
        if prs_file.exists():
            calculator.process_prs_and_reviews(str(prs_file))

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

    output_file = "results/rankings.json"
    write_json_output(rankings, output_file)

    print(f"\nDone! Generated {output_file}")

    # Print summary
    monthly_periods = len(rankings["monthly"])
    quarterly_periods = len(rankings["quarterly"])
    yearly_periods = len(rankings["yearly"])
    print(f"Monthly periods: {monthly_periods}")
    print(f"Quarterly periods: {quarterly_periods}")
    print(f"Yearly periods: {yearly_periods}")

    # Print latest month stats
    if rankings["monthly"]:
        latest_month = sorted(rankings["monthly"].keys())[-1]
        print(f"\nLatest month ({latest_month}):")
        print(f"  Code contributors: {len(rankings['monthly'][latest_month]['code'])}")
        print(f"  Community contributors: {len(rankings['monthly'][latest_month]['community'])}")
        print(f"  Review contributors: {len(rankings['monthly'][latest_month]['review'])}")
        print(f"  MVP candidates: {len(rankings['monthly'][latest_month]['mvp'])}")


if __name__ == "__main__":
    main()
