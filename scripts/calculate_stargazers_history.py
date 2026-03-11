import datetime
from typing import Dict, List, Tuple
from collections import defaultdict
from pathlib import Path
from repositories import REPOSITORIES
from utils import parse_github_datetime, load_json_file, generate_cumulative_history, write_json_output


class StarsHistoryAnalyzer:
    """Class to analyze and generate star history from stargazer data"""

    def extract_stargazers_info(self, stargazers_data: List[Dict]) -> List[Tuple[str, datetime.date]]:
        """Extract (username, date) tuples from stargazer data"""
        stargazers_info = []

        for edge in stargazers_data:
            try:
                starred_at = edge.get("starredAt")
                username = edge.get("node", {}).get("login") if edge.get("node") else None

                if starred_at and username:
                    d = parse_github_datetime(starred_at)
                    if d:
                        day = datetime.date(d.year, d.month, d.day)
                        stargazers_info.append((username, day))
            except (ValueError, KeyError):
                continue

        return stargazers_info

    def count_stars_per_day(self, stargazers_info: List[Tuple[str, datetime.date]]) -> Dict[datetime.date, int]:
        """Count how many stars were added on each day"""
        stars_per_day = defaultdict(int)

        for _, day in stargazers_info:
            stars_per_day[day] += 1

        return dict(stars_per_day)

    def generate_total_history(self, all_stargazers: List[List[Tuple[str, datetime.date]]]) -> List[Dict]:
        """Generate cumulative total star history from all repositories, counting unique stargazers"""
        # Collect all unique stargazers across all repositories
        # Key: username, Value: earliest star date
        unique_stargazers = {}

        for stargazers_info in all_stargazers:
            for username, day in stargazers_info:
                if username not in unique_stargazers or unique_stargazers[username] > day:
                    unique_stargazers[username] = day

        # Count unique stars per day (each stargazer only counted once at their earliest date)
        stars_per_day = defaultdict(int)
        for username, day in unique_stargazers.items():
            stars_per_day[day] += 1

        return generate_cumulative_history(dict(stars_per_day), "star_count")


def main():
    """Main function to process star history"""
    print("Processing star history...")

    analyzer = StarsHistoryAnalyzer()

    repositories = REPOSITORIES

    # Process each repository
    all_stargazers_info = []  # Raw stargazer data for unique counting
    output_data = {}

    for repository in repositories:
        file_path = Path("cache/raw_stargazer_data") / f"{repository}_stargazers.json"

        print(f"Processing {repository}...")
        stargazers_data = load_json_file(str(file_path))

        if not stargazers_data:
            continue

        # Extract raw stargazer info (username, date)
        stargazers_info = analyzer.extract_stargazers_info(stargazers_data)
        all_stargazers_info.append(stargazers_info)

        # Generate per-repository history
        stars_per_day = analyzer.count_stars_per_day(stargazers_info)
        history = generate_cumulative_history(stars_per_day, "star_count")

        output_data[f"{repository}_stars_history"] = history

    # Generate total stars history with unique stargazers
    print("Generating total stars history (counting unique stargazers)...")
    total_history = analyzer.generate_total_history(all_stargazers_info)
    output_data["total_stars_history"] = total_history

    # Calculate unique stargazer count
    unique_count = len(set(
        username for stargazers_info in all_stargazers_info
        for username, _ in stargazers_info
    ))

    output_file = "results/stars_history.json"
    write_json_output(output_data, output_file)

    print(f"\nDone! Generated {output_file}")
    print(f"Processed {len(repositories)} repositories")
    print(f"Total unique stargazers: {unique_count}")
    print(f"Total entries in history: {len(total_history)}")

if __name__ == "__main__":
    main()
