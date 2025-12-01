import json
import csv
import argparse
from pathlib import Path
from typing import Dict, List, Union
from datetime import datetime


def load_json_data(json_path: str) -> Union[Dict, List]:
    """Load JSON data from file"""
    with open(json_path, 'r') as f:
        return json.load(f)


def extract_stars_history(json_data: Union[Dict, List]) -> List[Dict]:
    """Extract total_stars_history from JSON data"""
    # If it's a list, assume it's already the stars history array
    if isinstance(json_data, list):
        return json_data

    # If it's a dict, try to extract the key
    if isinstance(json_data, dict):
        # Try different possible key names
        if "total_stars_history" in json_data:
            return json_data["total_stars_history"]
        else:
            # If no matching key, return empty list
            raise ValueError("Could not find 'total_stars_history' key in JSON data")

    raise ValueError("JSON data must be either a list or a dictionary")


def convert_to_csv(stars_history: List[Dict], output_path: str) -> None:
    """Convert stars history JSON to CSV format"""
    if not stars_history:
        print("Warning: No stars history data found")
        return

    # Sort by date to ensure chronological order
    sorted_history = sorted(stars_history, key=lambda x: datetime.strptime(x["date"], '%Y-%m-%d'))

    # Write CSV file
    with open(output_path, 'w', newline='') as csvfile:
        fieldnames = ['date', 'star_count']
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)

        writer.writeheader()

        for item in sorted_history:
            writer.writerow({
                'date': item['date'],
                'star_count': item['star_count']
            })


def main():
    """Main function to convert JSON to CSV"""
    parser = argparse.ArgumentParser(
        description="Convert total_stars_history.json to CSV format"
    )
    parser.add_argument(
        "--input",
        type=str,
        default="results/stars_history.json",
        help="Path to input JSON file (default: results/stars_history.json)"
    )
    parser.add_argument(
        "--output",
        type=str,
        default="results/autoware_stars_history.csv",
        help="Path to output CSV file (default: results/total_stars_history.csv)"
    )
    parser.add_argument(
        "--key",
        type=str,
        default="total_stars_history",
        help="Key name to extract from JSON if input is a dictionary (default: total_stars_history)"
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

    # Extract stars history
    print(f"Extracting stars history data...")
    try:
        stars_history = extract_stars_history(json_data)
        print(f"Found {len(stars_history)} entries")
    except ValueError as e:
        print(f"Error: {e}")
        return
    except Exception as e:
        print(f"Error extracting stars history: {e}")
        return

    # Convert to CSV
    print(f"Converting to CSV format...")
    try:
        # Ensure output directory exists
        output_path = Path(args.output)
        output_path.parent.mkdir(exist_ok=True, parents=True)

        convert_to_csv(stars_history, args.output)
        print(f"Successfully converted to {args.output}")
    except Exception as e:
        print(f"Error converting to CSV: {e}")
        return


if __name__ == "__main__":
    main()

