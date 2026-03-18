import datetime
from typing import Dict, List
from collections import defaultdict
from pathlib import Path
from repositories import REPOSITORIES
from utils import parse_github_datetime, load_json_file, write_json_output


class ActivityHistoryAnalyzer:
    """Class to analyze quarterly merged PRs and resolved issues from contributor data"""

    def __init__(self):
        self.start_date = datetime.date(2022, 1, 1)

    def _date_to_quarter(self, d: datetime.date) -> str:
        """Convert a date to quarter string like '2022-Q1'"""
        quarter = (d.month - 1) // 3 + 1
        return f"{d.year}-Q{quarter}"

    def extract_merged_pr_dates(self, pr_data: List[Dict]) -> List[datetime.date]:
        """Extract merge dates from raw PR data"""
        dates = []
        for edge in pr_data:
            try:
                node = edge.get("node", {})
                merged_at = node.get("mergedAt")
                if merged_at:
                    d = parse_github_datetime(merged_at)
                    if d:
                        day = datetime.date(d.year, d.month, d.day)
                        if day >= self.start_date:
                            dates.append(day)
            except (ValueError, KeyError):
                continue
        return dates

    def extract_resolved_issue_dates(self, issue_data: List[Dict]) -> List[datetime.date]:
        """Extract close dates from raw issue data"""
        dates = []
        for edge in issue_data:
            try:
                node = edge.get("node", {})
                closed_at = node.get("closedAt")
                if closed_at:
                    d = parse_github_datetime(closed_at)
                    if d:
                        day = datetime.date(d.year, d.month, d.day)
                        if day >= self.start_date:
                            dates.append(day)
            except (ValueError, KeyError):
                continue
        return dates

    def count_per_quarter(self, dates: List[datetime.date]) -> Dict[str, int]:
        """Count items per quarter"""
        per_quarter = defaultdict(int)
        for day in dates:
            quarter = self._date_to_quarter(day)
            per_quarter[quarter] += 1
        return dict(per_quarter)

    def generate_quarter_history(self, per_quarter: Dict[str, int], count_key: str) -> List[Dict]:
        """Generate sorted quarterly history list"""
        return [
            {"quarter": q, count_key: per_quarter[q]}
            for q in sorted(per_quarter.keys())
        ]


def main():
    """Main function to process quarterly activity history"""
    print("Processing activity history...")

    analyzer = ActivityHistoryAnalyzer()
    repositories = REPOSITORIES

    all_pr_dates = []
    all_issue_dates = []
    output_data = {}

    for repository in repositories:
        pr_path = Path("cache/raw_contributor_data") / f"{repository}_prs.json"
        issue_path = Path("cache/raw_contributor_data") / f"{repository}_issues.json"

        print(f"Processing {repository}...")

        # Merged PRs
        pr_data = load_json_file(str(pr_path))
        if pr_data:
            pr_dates = analyzer.extract_merged_pr_dates(pr_data)
            all_pr_dates.extend(pr_dates)
            per_quarter = analyzer.count_per_quarter(pr_dates)
            output_data[f"{repository}_merged_prs_history"] = analyzer.generate_quarter_history(per_quarter, "merged_pr_count")

        # Resolved issues
        issue_data = load_json_file(str(issue_path))
        if issue_data:
            issue_dates = analyzer.extract_resolved_issue_dates(issue_data)
            all_issue_dates.extend(issue_dates)
            per_quarter = analyzer.count_per_quarter(issue_dates)
            output_data[f"{repository}_resolved_issues_history"] = analyzer.generate_quarter_history(per_quarter, "resolved_issue_count")

    # Generate totals
    print("Generating total activity history...")
    total_pr_quarter = analyzer.count_per_quarter(all_pr_dates)
    output_data["total_merged_prs_history"] = analyzer.generate_quarter_history(total_pr_quarter, "merged_pr_count")

    total_issue_quarter = analyzer.count_per_quarter(all_issue_dates)
    output_data["total_resolved_issues_history"] = analyzer.generate_quarter_history(total_issue_quarter, "resolved_issue_count")

    output_file = "results/activity_history.json"
    write_json_output(output_data, output_file)

    print(f"\nDone! Generated {output_file}")
    print(f"Processed {len(repositories)} repositories")
    print(f"Total merged PRs (since 2022): {len(all_pr_dates)}")
    print(f"Total resolved issues (since 2022): {len(all_issue_dates)}")


if __name__ == "__main__":
    main()
