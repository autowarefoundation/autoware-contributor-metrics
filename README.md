# Autoware Contributor Metrics

## Check the metrics
Visit the following page: https://tier4.github.io/autoware-contributor-metrics/index.html

## How to run locally
```
python scripts/get_contributors.py --token <GitHubToken>
python scripts/get_stargazers.py --token <GitHubToken>
python scripts/calculate_contributor_history.py
python scripts/calculate_stargazers_history.py
```

The outputs are available under results folder:
 - `results/stars_history.json`
 - `results/contributors_history.json`  
