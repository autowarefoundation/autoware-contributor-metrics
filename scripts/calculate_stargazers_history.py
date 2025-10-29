import json
import datetime
from typing import Dict, List, Tuple
from collections import defaultdict
from pathlib import Path


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
                    d = datetime.datetime.strptime(starred_at, '%Y-%m-%dT%H:%M:%SZ')
                    day = datetime.date(d.year, d.month, d.day)
                    stargazers_info.append((username, day))
            except (ValueError, KeyError) as e:
                continue

        return stargazers_info

    def count_stars_per_day(self, stargazers_info: List[Tuple[str, datetime.date]]) -> Dict[datetime.date, int]:
        """Count how many stars were added on each day"""
        stars_per_day = defaultdict(int)

        for _, day in stargazers_info:
            stars_per_day[day] += 1

        return dict(stars_per_day)

    def generate_cumulative_history(self, stars_per_day: Dict[datetime.date, int]) -> List[Dict]:
        """Generate cumulative star count history"""
        # Create a list of all dates
        all_dates = sorted(stars_per_day.keys())

        # Calculate cumulative counts
        cumulative_data = []
        cumulative_count = 0

        for date in all_dates:
            cumulative_count += stars_per_day[date]
            cumulative_data.append({
                "date": date.strftime('%Y-%m-%d'),
                "star_count": cumulative_count
            })

        return cumulative_data

    def load_stargazers_from_file(self, file_path: str) -> List[Dict]:
        """Load stargazers data from JSON file"""
        try:
            with open(file_path, 'r') as f:
                data = json.load(f)

            # Handle different JSON structures
            if isinstance(data, list):
                return data
            else:
                print(f"Warning: Unexpected format in {file_path}")
                return []

        except FileNotFoundError:
            print(f"Warning: File not found: {file_path}")
            return []
        except json.JSONDecodeError:
            print(f"Warning: Invalid JSON in file: {file_path}")
            return []

    def merge_star_histories(self, all_histories: List[Dict]) -> Dict[datetime.date, int]:
        """Merge multiple star histories into a total history"""
        total_stars_per_day = defaultdict(int)

        for history_data in all_histories:
            for entry in history_data:
                date_str = entry.get("date")
                star_count = entry.get("star_count", 0)

                try:
                    date = datetime.datetime.strptime(date_str, '%Y-%m-%d').date()
                    total_stars_per_day[date] += star_count
                except (ValueError, AttributeError):
                    continue

        return dict(total_stars_per_day)

    def generate_total_history(self, all_stargazers: List[List[Tuple[str, datetime.date]]]) -> List[Dict]:
        """Generate cumulative total star history from all repositories, counting unique stargazers"""
        # Collect all unique stargazers across all repositories
        # Key: username, Value: earliest star date
        unique_stargazers = {}

        for stargazers_info in all_stargazers:
            for username, day in stargazers_info:
                # Track the earliest star date for each unique username
                if username not in unique_stargazers or unique_stargazers[username] > day:
                    unique_stargazers[username] = day

        # Count unique stars per day (each stargazer only counted once at their earliest date)
        stars_per_day = defaultdict(int)
        for username, day in unique_stargazers.items():
            stars_per_day[day] += 1

        # Generate cumulative history
        all_dates = sorted(stars_per_day.keys())
        cumulative_data = []
        cumulative_count = 0

        for date in all_dates:
            new_stars = stars_per_day[date]
            cumulative_count += new_stars
            cumulative_data.append({
                "date": date.strftime('%Y-%m-%d'),
                "star_count": cumulative_count
            })

        return cumulative_data


def main():
    """Main function to process star history"""
    print("Processing star history...")

    analyzer = StarsHistoryAnalyzer()

    # List of repositories to process
    repositories = [
        "autoware",
        "autoware_core",
        "autoware_common",
        "autoware_universe",
        "autoware.privately-owned-vehicles",
        "autoware_msgs",
        "autoware_launch",
        "autoware-documentation",
        "autoware_tools",
        "autoware_cmake",
        "autoware_utils",
        "autoware_lanelet2_extension",
        "autoware_rviz_plugins",
        "autoware_adapi_msgs",
        "autoware_internal_msgs",
        "openadkit",
        "autoware_ai",
        "autoware_ai_perception",
        "autoware_ai_planning",
        "autoware_ai_messages",
        "autoware_ai_simulation",
        "autoware_ai_visualization",
        "autoware_ai_drivers",
        "autoware_ai_utilities",
        "autoware_ai_common"
    ]

    # Process each repository
    all_histories = []
    all_stargazers_info = []  # Raw stargazer data for unique counting
    output_data = {}

    for repository in repositories:
        raw_data_path = Path("cache/raw_stargazer_data")
        file_path = raw_data_path / f"{repository}_stargazers.json"

        print(f"Processing {repository}...")
        stargazers_data = analyzer.load_stargazers_from_file(str(file_path))

        if not stargazers_data:
            continue

        # Extract raw stargazer info (username, date)
        stargazers_info = analyzer.extract_stargazers_info(stargazers_data)
        all_stargazers_info.append(stargazers_info)

        # Generate per-repository history
        stars_per_day = analyzer.count_stars_per_day(stargazers_info)
        history = analyzer.generate_cumulative_history(stars_per_day)

        output_data[f"{repository}_stars_history"] = history
        all_histories.append(history)

    # Generate total stars history with unique stargazers
    print("Generating total stars history (counting unique stargazers)...")
    total_history = analyzer.generate_total_history(all_stargazers_info)
    output_data["total_stars_history"] = total_history

    # Calculate unique stargazer count
    unique_count = len(set(
        username for stargazers_info in all_stargazers_info
        for username, _ in stargazers_info
    ))

    # Write to file
    output_path = Path("results")
    output_path.mkdir(exist_ok=True, parents=True)

    output_file = output_path / "stars_history.json"
    with open(output_file, 'w') as f:
        json.dump(output_data, f, indent=2)

    print(f"\nDone! Generated {output_file}")
    print(f"Processed {len(repositories)} repositories")
    print(f"Total unique stargazers: {unique_count}")
    print(f"Total entries in history: {len(total_history)}")

if __name__ == "__main__":
    main()
