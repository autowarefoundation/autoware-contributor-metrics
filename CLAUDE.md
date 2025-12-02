# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This repository tracks and visualizes contributor and stargazer metrics for Autoware Foundation repositories. It generates JSON data files from GitHub's GraphQL API and displays interactive charts on a GitHub Pages site showing:
- GitHub star growth over time across repositories
- Contributor growth (code contributors, community contributors, and total)

Live site: https://tier4.github.io/autoware-contributor-metrics/index.html

## Development Workflow

### Running locally

The data collection and processing pipeline consists of four scripts that must be run in order:

```bash
# 1. Fetch contributor data (issues, PRs, discussions) from GitHub GraphQL API
python scripts/get_contributors.py --token <GitHubToken>

# 2. Fetch stargazer data from GitHub GraphQL API
python scripts/get_stargazers.py --token <GitHubToken>

# 3. Process contributor data into cumulative history
python scripts/calculate_contributor_history.py

# 4. Process stargazer data into cumulative history
python scripts/calculate_stargazers_history.py
```

Alternatively, use the `GITHUB_TOKEN` environment variable instead of `--token`:
```bash
export GITHUB_TOKEN=<your_token>
python scripts/get_contributors.py
```

### Installing dependencies

```bash
pip install -r requirements.txt
```

The only external dependency is `requests>=2.31.0`.

### Viewing the dashboard locally

Open `public/index.html` in a browser. The page expects `contributors_history.json` and `stars_history.json` to be in the `public/` directory.

## Architecture

### Data Pipeline Flow

```
GitHub GraphQL API
    ↓
1. get_contributors.py → cache/raw_contributor_data/*.json
2. get_stargazers.py → cache/raw_stargazer_data/*.json
    ↓
3. calculate_contributor_history.py → results/contributors_history.json
4. calculate_stargazers_history.py → results/stars_history.json
    ↓
Copy to public/ → Visualized in index.html
```

### Key Components

**Data Fetchers** (`scripts/get_contributors.py` and `scripts/get_stargazers.py`):
- Use GitHub GraphQL API to fetch raw data from 24+ Autoware repositories
- Implement rate limiting, retry logic, and error handling
- Pagination: fetch 100 items per page, tracking cursors
- Store raw JSON in `cache/` directories

**Data Processors** (`scripts/calculate_contributor_history.py` and `scripts/calculate_stargazers_history.py`):
- Parse cached JSON files
- Track first contribution/star date per user
- Generate cumulative daily counts
- Output time-series data to `results/`

**Visualization** (`public/main.js` and `public/index.html`):
- Uses ApexCharts to render interactive line charts
- Fetches JSON from `stars_history.json` and `contributors_history.json`
- Displays total metrics plus breakdown by repository/contributor type

### Contributor Types

The repository distinguishes between:
- **Code contributors**: Users who created PRs
- **Community contributors**: Users who created issues/discussions or commented
- **Total contributors**: Union of both types (earliest contribution date tracked)

### Repository List

The scripts process these Autoware Foundation repositories (defined in both `get_contributors.py` and `get_stargazers.py`):
- autoware, autoware_core, autoware_universe, autoware_common
- autoware_msgs, autoware_adapi_msgs, autoware_internal_msgs
- autoware_cmake, autoware_utils, autoware_lanelet2_extension
- autoware_rviz_plugins, autoware_launch, autoware-documentation
- autoware_tools, autoware.privately-owned-vehicles, openadkit
- autoware_ai and related (ai_perception, ai_planning, ai_messages, etc.)

## GitHub Actions

The workflow `.github/workflows/measure-contributors.yml`:
- Runs daily via cron (`0 0 * * *`) and on push to main
- Uses a secret `ACCESS_TOKEN` for GitHub API access
- Runs all four scripts in sequence
- Copies results to `public/` and deploys to GitHub Pages
- Archives raw cache and results as workflow artifacts

## Important Implementation Details

### Rate Limiting Strategy

Both fetcher scripts implement sophisticated rate limiting:
- Check `X-RateLimit-Remaining` header before each request
- Wait until rate limit reset if < 10 requests remaining
- Exponential backoff on 403 errors (up to 5 retries)
- 1 second delay between successful requests

### Data Deduplication

- **Contributors**: Track earliest contribution date per username across all repos
- **Stargazers**: `calculate_stargazers_history.py` counts unique stargazers across repos (same user starring multiple repos counts once)

### Date Filtering

Contributor history starts from January 1, 2022 (`ContributorHistory.start_date`). Earlier contributions are ignored.

## File Structure

```
.
├── scripts/
│   ├── get_contributors.py              # Fetch issues/PRs/discussions
│   ├── get_stargazers.py                # Fetch stargazers
│   ├── calculate_contributor_history.py # Process contributors
│   └── calculate_stargazers_history.py  # Process stargazers
├── public/
│   ├── index.html                       # Dashboard HTML
│   └── main.js                          # Visualization logic
├── cache/                               # Raw API responses (gitignored)
│   ├── raw_contributor_data/
│   └── raw_stargazer_data/
├── results/                             # Processed JSON (gitignored)
│   ├── contributors_history.json
│   └── stars_history.json
├── requirements.txt
└── README.md
```
