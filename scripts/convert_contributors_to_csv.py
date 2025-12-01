import json
import csv
import argparse
from pathlib import Path
from typing import Dict, List
from datetime import datetime


def load_json_data(json_path: str) -> Dict:
    """Load JSON data from file"""
    with open(json_path, 'r') as f:
        return json.load(f)


def convert_to_csv(json_data: Dict, output_path: str) -> None:
    """Convert contributors history JSON to CSV format"""
    # Extract the three contributor arrays
    code_contributors = json_data.get("autoware_code_contributors", [])
    community_contributors = json_data.get("autoware_community_contributors", [])
    autoware_contributors = json_data.get("autoware_contributors", [])

    # Create dictionaries for quick lookup: {date: count}
    code_dict = {item["date"]: item["contributors_count"] for item in code_contributors}
    community_dict = {item["date"]: item["contributors_count"] for item in community_contributors}
    autoware_dict = {item["date"]: item["contributors_count"] for item in autoware_contributors}

    # Collect all unique dates and sort them
    all_dates = set(code_dict.keys()) | set(community_dict.keys()) | set(autoware_dict.keys())
    sorted_dates = sorted(all_dates, key=lambda x: datetime.strptime(x, '%Y-%m-%d'))

    # Write CSV file
    with open(output_path, 'w', newline='') as csvfile:
        fieldnames = ['date', 'autoware_code_contributors', 'autoware_community_contributors', 'autoware_contributors']
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)

        writer.writeheader()

        # Track last known values for cumulative data
        last_code = 0
        last_community = 0
        last_autoware = 0

        for date in sorted_dates:
            # Get values for this date, or use last known value if date doesn't exist
            code_count = code_dict.get(date, last_code)
            community_count = community_dict.get(date, last_community)
            autoware_count = autoware_dict.get(date, last_autoware)

            # Update last known values
            last_code = code_count
            last_community = community_count
            last_autoware = autoware_count

            writer.writerow({
                'date': date,
                'autoware_code_contributors': code_count,
                'autoware_community_contributors': community_count,
                'autoware_contributors': autoware_count
            })


def main():
    """Main function to convert JSON to CSV"""
    parser = argparse.ArgumentParser(
        description="Convert contributors_history.json to CSV format"
    )
    parser.add_argument(
        "--input",
        type=str,
        default="results/contributors_history.json",
        help="Path to input JSON file (default: results/contributors_history.json)"
    )
    parser.add_argument(
        "--output",
        type=str,
        default="results/contributors_history.csv",
        help="Path to output CSV file (default: results/contributors_history.csv)"
    )
    args = parser.parse_args()

    # Load JSON data
    print(f"Loading JSON data from {args.input}...")
    try:
        json_data = load_json_data(args.input)
    except FileNotFoundError:
        print(f"Error: File not found: {args.input}")
        return
    except json.JSONDecodeError as e:
        print(f"Error: Invalid JSON in file {args.input}: {e}")
        return

    # Convert to CSV
    print(f"Converting to CSV format...")
    try:
        # Ensure output directory exists
        output_path = Path(args.output)
        output_path.parent.mkdir(exist_ok=True, parents=True)

        convert_to_csv(json_data, args.output)
        print(f"Successfully converted to {args.output}")
    except Exception as e:
        print(f"Error converting to CSV: {e}")
        return


if __name__ == "__main__":
    main()

