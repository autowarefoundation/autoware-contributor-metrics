# Autoware Contributor Metrics

## Check the metrics
Visit the following page: https://tier4.github.io/autoware-contributor-metrics/index.html

## How to run locally

1. install dependencies
```
pip install -r requirements.txt
```

2. run the scripts
```
python scripts/get_contributors.py --token <GitHubToken>
python scripts/get_stargazers.py --token <GitHubToken>
python scripts/calculate_contributor_history.py
python scripts/calculate_stargazers_history.py
```

3. copy the results to public folder
```
cp results/stars_history.json public/
cp results/contributors_history.json public/
```

4. start the server
```
cd public
python -m http.server 8000
```

5. visit the following page: http://localhost:8000/index.html
