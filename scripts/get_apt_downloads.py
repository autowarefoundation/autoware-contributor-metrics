#!/usr/bin/env python3
"""Fetch APT download counts from AWStats for Autoware ROS packages.

Fetches monthly download statistics from packages.ros.org AWStats reports
and generates cumulative download history for all autoware-related packages.
"""

import re
import argparse
import datetime
import time
from collections import defaultdict
from pathlib import Path

import requests

from utils import write_json_output

CACHE_DIR = "cache/raw_apt_download_data"
OUTPUT_FILE = "results/apt_downloads.json"

AWSTATS_URL_TEMPLATE = (
    "https://awstats.osuosl.org/reports/packages.ros.org/"
    "{year}/{month:02d}/awstats.packages.ros.org.downloads.html"
)

# Package name regex: extract directory name from AWStats href URL
# e.g. ".../r/ros-humble-autoware-core/ros-humble-autoware-core_1.7.0..." -> "ros-humble-autoware-core"
PKG_NAME_RE = re.compile(
    r'<a\s+href="[^"]*/(ros-(humble|jazzy|rolling)-autoware[^/]*)/[^"]*"'
)
# Hit count: first <td>DIGITS</td> after closing </a></td>
HIT_COUNT_RE = re.compile(r'</a></td>\s*<td>([\d,]+)</td>')

START_YEAR = 2022
START_MONTH = 1


def get_months_range():
    """Generate (year, month) tuples from start to current month (inclusive)."""
    now = datetime.date.today()
    year, month = START_YEAR, START_MONTH
    months = []
    while (year, month) <= (now.year, now.month):
        months.append((year, month))
        month += 1
        if month > 12:
            month = 1
            year += 1
    return months


def get_cache_path(year, month):
    return Path(CACHE_DIR) / f"{year}-{month:02d}.html"


def fetch_awstats_page(year, month):
    """Fetch AWStats HTML page for a given month. Returns text or None."""
    url = AWSTATS_URL_TEMPLATE.format(year=year, month=month)
    print(f"Fetching {url}...")
    try:
        resp = requests.get(url, timeout=120)
        if resp.status_code == 404:
            print(f"  No data for {year}-{month:02d} (404)")
            return None
        resp.raise_for_status()
        print(f"  Downloaded {len(resp.text):,} bytes")
        return resp.text
    except requests.exceptions.RequestException as e:
        print(f"  Error fetching {year}-{month:02d}: {e}")
        return None


def extract_downloads(html_text):
    """Extract autoware package download counts from AWStats HTML.

    Returns dict: {package_name: total_hits} (excludes -dbgsym packages).
    """
    counts = defaultdict(int)

    for line in html_text.split('\n'):
        if 'autoware' not in line:
            continue

        pkg_match = PKG_NAME_RE.search(line)
        if not pkg_match:
            continue

        pkg_name = pkg_match.group(1)

        # Skip debug symbol packages
        if pkg_name.endswith('-dbgsym'):
            continue

        hit_match = HIT_COUNT_RE.search(line)
        if not hit_match:
            continue

        hits = int(hit_match.group(1).replace(',', ''))
        counts[pkg_name] += hits

    return dict(counts)


def distro_from_pkg(pkg_name):
    """Extract ROS distro from package name."""
    m = re.match(r'ros-(humble|jazzy|rolling)-', pkg_name)
    return m.group(1) if m else 'unknown'


def main():
    parser = argparse.ArgumentParser(
        description="Fetch APT download counts from AWStats"
    )
    parser.add_argument(
        "--use-cache", action="store_true",
        help="Use cached HTML files for past months",
    )
    args = parser.parse_args()

    cache_dir = Path(CACHE_DIR)
    cache_dir.mkdir(parents=True, exist_ok=True)

    now = datetime.date.today()
    current_month = (now.year, now.month)
    months = get_months_range()

    monthly_data = {}

    for year, month in months:
        month_key = f"{year}-{month:02d}"
        cache_path = get_cache_path(year, month)
        is_current = (year, month) == current_month

        html_text = None

        if args.use_cache and not is_current and cache_path.exists():
            print(f"Using cached data for {month_key}")
            html_text = cache_path.read_text()
        else:
            html_text = fetch_awstats_page(year, month)
            if html_text is not None:
                cache_path.write_text(html_text)
            time.sleep(1)

        if html_text is None:
            continue

        pkg_counts = extract_downloads(html_text)
        if not pkg_counts:
            print(f"  {month_key}: no autoware packages found")
            continue

        # Aggregate by distro
        by_distro = defaultdict(int)
        for pkg, hits in pkg_counts.items():
            by_distro[distro_from_pkg(pkg)] += hits

        total = sum(pkg_counts.values())
        monthly_data[month_key] = {
            "by_distro": dict(by_distro),
            "by_package": pkg_counts,
            "total": total,
        }
        print(f"  {month_key}: {dict(by_distro)} total={total}")

    # Build cumulative data
    cumulative = []
    running_distro = defaultdict(int)
    running_total = 0

    for month_key in sorted(monthly_data.keys()):
        m = monthly_data[month_key]
        for distro, count in m["by_distro"].items():
            running_distro[distro] += count
        running_total += m["total"]

        entry = {"date": month_key}
        for distro in ["humble", "jazzy", "rolling"]:
            entry[distro] = running_distro.get(distro, 0)
        entry["total"] = running_total
        cumulative.append(entry)

    # Build package totals (all-time)
    package_totals = defaultdict(int)
    for m in monthly_data.values():
        for pkg, hits in m["by_package"].items():
            package_totals[pkg] += hits

    # Sort by total downloads descending
    package_totals = dict(
        sorted(package_totals.items(), key=lambda x: x[1], reverse=True)
    )

    output = {
        "monthly": monthly_data,
        "cumulative": cumulative,
        "package_totals": package_totals,
        "last_updated": now.strftime('%Y-%m-%d'),
    }

    write_json_output(output, OUTPUT_FILE)
    print(f"\nDone! Generated {OUTPUT_FILE}")

    if cumulative:
        latest = cumulative[-1]
        print(f"Total downloads (all time): {latest['total']:,}")
        for distro in ["humble", "jazzy", "rolling"]:
            print(f"  {distro}: {latest.get(distro, 0):,}")
        print(f"\nTop 10 packages:")
        for pkg, count in list(package_totals.items())[:10]:
            print(f"  {pkg}: {count:,}")


if __name__ == "__main__":
    main()
