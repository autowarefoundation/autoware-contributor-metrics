"""Stargazer records preserved for repositories GitHub will not let us list.

GitHub restricted stargazer listing to a repository's collaborators, and the
GitHub Actions cache holding these repositories' records was evicted before
anyone noticed. Neither half is recoverable on its own: the API cannot return
the records again, and `actions/cache` guarantees nothing about keeping them.
So the records recovered from a 2025-12-04 snapshot are committed to the
repository, which is the only store here that nothing evicts.

See data/README.md for provenance and the rules for touching that file.
"""
import datetime
import json
from pathlib import Path
from typing import Dict, Iterable, List, NamedTuple, Tuple

# Relative to the repository root, like every other path in this pipeline.
ARCHIVE_PATH = "data/frozen_star_history.json"

_REPO_ROOT = Path(__file__).resolve().parent.parent


class FrozenStarHistory(NamedTuple):
    """One capture of stargazer records, frozen at ``captured_at``."""

    captured_at: str
    repositories: Dict[str, List[Tuple[str, str]]]

    def unknown_repositories(self, tracked: Iterable[str]) -> List[str]:
        """Archived repositories that are no longer tracked, e.g. after a rename.

        Their records are simply never read. Worth surfacing so a rename is
        noticed rather than quietly costing a repository its history.
        """
        tracked = set(tracked)
        return sorted(repo for repo in self.repositories if repo not in tracked)


def _require_date(value: object, where: str) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{where}: expected a YYYY-MM-DD string, got {value!r}")
    try:
        datetime.date.fromisoformat(value)
    except ValueError:
        raise ValueError(f"{where}: expected a YYYY-MM-DD date, got {value!r}") from None
    return value


def _parse_records(repository: str, records: object) -> List[Tuple[str, str]]:
    if not isinstance(records, list):
        raise ValueError(f"{repository}: expected a list of records, got {type(records).__name__}")

    parsed = []
    for index, record in enumerate(records):
        where = f"{repository}[{index}]"
        if not isinstance(record, list) or len(record) != 2:
            raise ValueError(f"{where}: expected a [login, date] pair, got {record!r}")
        login, date = record
        if not isinstance(login, str) or not login:
            raise ValueError(f"{where}: expected a non-empty login, got {login!r}")
        parsed.append((login, _require_date(date, where)))
    return parsed


def load_frozen_star_history(path: str = ARCHIVE_PATH) -> FrozenStarHistory:
    """Read the committed archive, or raise.

    Strict on purpose, unlike ``repositories.py`` and ``utils.load_json_file``,
    which return empty on a missing or broken file. Those defaults are wrong
    here: a caller that receives "no frozen history" cannot tell it apart from
    an archive that legitimately holds nothing, and would re-drop eleven
    repositories with no signal at all. That is precisely how this data was
    lost the first time. A red build is the cheaper outcome.

    Raises:
        FileNotFoundError: the archive is missing.
        json.JSONDecodeError: the archive is not valid JSON.
        ValueError: the archive is valid JSON of the wrong shape.
    """
    resolved = Path(path)
    if not resolved.is_absolute() and not resolved.exists():
        resolved = _REPO_ROOT / path

    with open(resolved, "r") as f:
        payload = json.load(f)

    if not isinstance(payload, dict):
        raise ValueError(f"{resolved}: expected a JSON object at the top level")

    captured_at = _require_date(payload.get("captured_at"), f"{resolved}: captured_at")

    repositories = payload.get("repositories")
    if not isinstance(repositories, dict):
        raise ValueError(f"{resolved}: expected 'repositories' to be an object")

    return FrozenStarHistory(
        captured_at=captured_at,
        repositories={
            repository: _parse_records(repository, records)
            for repository, records in repositories.items()
        },
    )
