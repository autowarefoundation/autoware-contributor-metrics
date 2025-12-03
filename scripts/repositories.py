# Repository loader utility
# Loads repository list from public/repositories.json
# Run fetch_repositories.py first to generate the JSON file

import json
from pathlib import Path


def load_repositories() -> list:
    """Load repository list from JSON file"""
    # Try multiple paths to find the JSON file
    possible_paths = [
        Path(__file__).parent.parent / "public" / "repositories.json",
        Path("public/repositories.json"),
        Path("../public/repositories.json"),
    ]

    for path in possible_paths:
        if path.exists():
            with open(path, 'r') as f:
                data = json.load(f)
            return data.get("repositories", [])

    raise FileNotFoundError(
        "repositories.json not found. Run 'python scripts/fetch_repositories.py' first."
    )


# For backward compatibility - load repositories on import
try:
    REPOSITORIES = load_repositories()
except FileNotFoundError:
    # Fallback to empty list if JSON doesn't exist yet
    print("Warning: repositories.json not found. Using empty list.")
    print("Run 'python scripts/fetch_repositories.py' to generate the repository list.")
    REPOSITORIES = []
