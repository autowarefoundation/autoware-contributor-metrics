import datetime
from typing import Dict, List
from collections import defaultdict
from pathlib import Path
from repositories import REPOSITORIES
from utils import parse_github_datetime, load_json_file, write_json_output


class CommitsHistoryAnalyzer:
    """Class to analyze and generate yearly commit history from commit data"""

    def __init__(self):
        self.start_date = datetime.date(2022, 1, 1)

    def extract_commit_dates(self, commit_data: List[Dict]) -> List[datetime.date]:
        """Extract commit dates from raw commit data"""
        dates = []

        for edge in commit_data:
            try:
                node = edge.get("node", {})
                committed_date = node.get("committedDate")
                if committed_date:
                    d = parse_github_datetime(committed_date)
                    if d:
                        day = datetime.date(d.year, d.month, d.day)
                        if day >= self.start_date:
                            dates.append(day)
            except (ValueError, KeyError):
                continue

        return dates

    def count_commits_per_year(self, dates: List[datetime.date]) -> Dict[str, int]:
        """Count commits per year"""
        per_year = defaultdict(int)

        for day in dates:
            per_year[str(day.year)] += 1

        return dict(per_year)

    def generate_year_history(self, per_year: Dict[str, int]) -> List[Dict]:
        """Generate sorted yearly history list"""
        return [
            {"year": y, "commit_count": per_year[y]}
            for y in sorted(per_year.keys())
        ]


def main():
    """Main function to process yearly commit history"""
    print("Processing commit history...")

    analyzer = CommitsHistoryAnalyzer()

    repositories = REPOSITORIES

    all_dates = []
    output_data = {}

    for repository in repositories:
        file_path = Path("cache/raw_commit_data") / f"{repository}_commits.json"

        print(f"Processing {repository}...")
        commit_data = load_json_file(str(file_path))

        if not commit_data:
            continue

        dates = analyzer.extract_commit_dates(commit_data)
        all_dates.extend(dates)

        per_year = analyzer.count_commits_per_year(dates)
        history = analyzer.generate_year_history(per_year)

        output_data[f"{repository}_commits_history"] = history

    # Generate total commits history
    print("Generating total commits history...")
    total_per_year = analyzer.count_commits_per_year(all_dates)
    total_history = analyzer.generate_year_history(total_per_year)
    output_data["total_commits_history"] = total_history

    output_file = "results/commits_history.json"
    write_json_output(output_data, output_file)

    print(f"\nDone! Generated {output_file}")
    print(f"Processed {len(repositories)} repositories")
    print(f"Total commits (since 2022): {len(all_dates)}")
    print(f"Total years: {len(total_history)}")

if __name__ == "__main__":
    main()
