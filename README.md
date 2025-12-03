# Autoware Contributor Metrics

## Check the metrics
Visit the following page: https://tier4.github.io/autoware-contributor-metrics/index.html

## Metrics Overview

### GitHub Stars History

Tracks the cumulative number of unique stargazers across Autoware Foundation repositories over time.

**Total Unique Stars Calculation:**
- Collects all stargazers from 25+ Autoware repositories via GitHub GraphQL API
- If the same user starred multiple repositories, only the **earliest star date** is counted
- Result: One star per unique GitHub user across all repositories

**Example:** If user A starred `autoware` on Jan 1 and `autoware_universe` on Feb 1, they are counted once on Jan 1.

### GitHub Contributors History

Tracks the cumulative number of unique contributors over time.

**Total Unique Contributors Calculation:**
- **Code Contributors**: Users who created at least one Pull Request
- **Community Contributors**: Users who created Issues, Discussions, or commented on them
- **Total Contributors**: Union of Code + Community contributors
  - If a user contributed to both, only the **earliest contribution date** is counted
  - Each user is counted exactly once across all repositories

**Example:** If user B created a PR on Mar 1 and commented on an Issue on Feb 1, they appear in Total Contributors on Feb 1.

**Target Repositories:**
- Dynamically fetched from autowarefoundation organization via GitHub API
- Top 25 by composite score (stars + forks)
- Legacy autoware_ai repositories included for historical tracking

**Note:** Archived repositories and repositories not updated within 2 years are excluded, except for legacy autoware_ai repositories.

### Contributor Rankings
Monthly and yearly rankings for four categories:

| Category | Metric | Description |
|----------|--------|-------------|
| **MVP** | Combined Rank | Sum of ranks across all three categories (lower is better) |
| **Best Committer** | Merged PR count | Number of Pull Requests merged |
| **Best Evangelist** | Posts + Comments | Issue/Discussion posts created + comments made |
| **Best Reviewer** | Reviews + Comments | PR reviews + PR comments (excluding self-reviews) |

**MVP Calculation:**
- Only contributors who appear in ALL THREE categories are eligible
- Each contributor's rank in the three categories is summed
- Ties are broken by total contribution count across all categories

**Note**: Bot accounts (dependabot, github-actions, codecov, etc.) are excluded from rankings.

## How to run locally

1. Install dependencies
```bash
pip install -r requirements.txt
```

2. Run the scripts
```bash
# First, fetch and generate repository list
python scripts/fetch_repositories.py --token <GitHubToken>

# Then fetch contributor and stargazer data
python scripts/get_contributors.py --token <GitHubToken>
python scripts/get_stargazers.py --token <GitHubToken>

# Process the data
python scripts/calculate_contributor_history.py
python scripts/calculate_stargazers_history.py
python scripts/calculate_rankings.py
```

3. Copy the results to public folder
```bash
cp results/stars_history.json public/
cp results/contributors_history.json public/
cp results/rankings.json public/
```

4. Start the server
```bash
cd public
python -m http.server 8000
```

5. Visit the following page: http://localhost:8000/index.html
