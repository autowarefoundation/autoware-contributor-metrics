import json
import datetime
from typing import Any, Dict, List, Optional
from pathlib import Path


def parse_github_datetime(date_str: str) -> Optional[datetime.datetime]:
    """Parse ISO format GitHub datetime string. Returns None on failure."""
    try:
        return datetime.datetime.strptime(date_str, '%Y-%m-%dT%H:%M:%SZ')
    except (ValueError, TypeError):
        return None


def load_json_file(file_path: str) -> Any:
    """Load JSON from file. Returns [] on missing file or decode error."""
    try:
        with open(file_path, 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        print(f"Warning: File not found: {file_path}")
        return []
    except json.JSONDecodeError:
        print(f"Warning: Invalid JSON in file: {file_path}")
        return []


def generate_cumulative_history(per_day_counts: Dict[datetime.date, int], value_key: str) -> List[Dict]:
    """Generate cumulative time-series data sorted by date.

    Args:
        per_day_counts: mapping of date -> count for that day
        value_key: key name for the cumulative value (e.g. "contributors_count", "star_count")
    """
    all_dates = sorted(per_day_counts.keys())
    cumulative_data = []
    cumulative_count = 0

    for date in all_dates:
        cumulative_count += per_day_counts[date]
        cumulative_data.append({
            "date": date.strftime('%Y-%m-%d'),
            value_key: cumulative_count,
        })

    return cumulative_data


def write_json_output(data: Any, output_path: str) -> None:
    """Write data as JSON with indent=2, creating parent dirs as needed."""
    path = Path(output_path)
    path.parent.mkdir(exist_ok=True, parents=True)
    with open(path, 'w') as f:
        json.dump(data, f, indent=2)
