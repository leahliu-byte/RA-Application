"""
probe_candidates.py
-------------------
Step 1 of the Part 1 pipeline: decide WHICH page to scrape for each company.

For every candidate "About Us" URL in data/candidate_urls.csv, ask the Wayback
Machine CDX API which years (2016-2024) have an archived capture, and what HTTP
status those captures had. I do not download any pages here; I only look at
the CDX index, which is cheap.

Output: output/candidate_coverage.csv with one row per candidate URL and, for each
year, a code describing what the archive holds:
    "200"  = at least one successful capture of the page that year (usable)
    "3xx"  = only redirect captures that year (page moved; follow or pick another URL)
    "4xx"/"5xx" = only error captures (page missing/broken)
    "rev"  = only "revisit" records (identical to an earlier capture; usable via playback)
    ""     = no capture at all that year

These codes are used to pick the best URL per company (see select_urls.py) and to
document coverage gaps in the README.

Usage (from the repo root, with .venv active):
    python part1_stated_values/src/probe_candidates.py
"""

import csv
import time
from pathlib import Path

import requests

# ---- Configuration ---------------------------------------------------------

PART_DIR = Path(__file__).resolve().parents[1]           # part1_stated_values/
CANDIDATES_CSV = PART_DIR / "data" / "candidate_urls.csv"
OUTPUT_CSV = PART_DIR / "output" / "candidate_coverage.csv"

CDX_ENDPOINT = "https://web.archive.org/cdx/search/cdx"
YEARS = list(range(2016, 2025))                           # 2016..2024 inclusive

# The Internet Archive is a free, shared service: be polite. A first run at one
# request every ~1.5 s got my IP temporarily blocked (connection refused) after
# ~20 queries, so I now pause 4 s between requests and back off for minutes
# (not seconds) when the archive refuses connections.
REQUEST_DELAY_SEC = 4
MAX_RETRIES = 5
BACKOFF_SEC = [30, 60, 120, 240, 300]   # wait before retry 1, 2, 3, ...

HEADERS = {"User-Agent": "RA-Application research scraper (academic project)"}


# ---- Helpers ---------------------------------------------------------------

def query_cdx(url: str) -> list[list[str]]:
    """Return CDX rows [timestamp, statuscode] for `url` within 2016-2024.

    `collapse=timestamp:6` keeps at most one capture per month, which is plenty
    to tell which years are covered while keeping responses small.
    Scheme (http/https) and "www." are ignored by CDX matching, so one query
    covers all of those variants.
    """
    params = {
        "url": url,
        "from": str(YEARS[0]),
        "to": str(YEARS[-1]),
        "fl": "timestamp,statuscode",
        "collapse": "timestamp:6",
        "output": "json",
    }
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            resp = requests.get(CDX_ENDPOINT, params=params, headers=HEADERS, timeout=60)
            if resp.status_code == 200:
                rows = resp.json() if resp.text.strip() else []
                return rows[1:]                              # drop the header row
            # 429 = rate limited, 5xx = archive overloaded: wait and retry
            print(f"    HTTP {resp.status_code}, retry {attempt}/{MAX_RETRIES}", flush=True)
        except (requests.RequestException, ValueError) as exc:
            print(f"    {type(exc).__name__}, retry {attempt}/{MAX_RETRIES}", flush=True)
        time.sleep(BACKOFF_SEC[attempt - 1])                 # back off progressively
    raise RuntimeError(f"CDX query failed after {MAX_RETRIES} attempts: {url}")


def summarize_year(statuses: list[str]) -> str:
    """Collapse all capture statuses within one year into a single code.

    Priority: a usable 200 beats a revisit, which beats a redirect, which beats
    an error. So a year is "200" if ANY capture that year succeeded.
    """
    if not statuses:
        return ""
    if "200" in statuses:
        return "200"
    if "-" in statuses:                  # CDX marks revisit records with "-"
        return "rev"
    if any(s.startswith("3") for s in statuses):
        return "3xx"
    if any(s.startswith("4") for s in statuses):
        return "4xx"
    return "5xx"


# ---- Main ------------------------------------------------------------------

def main() -> None:
    with open(CANDIDATES_CSV, newline="") as f:
        candidates = list(csv.DictReader(f))

    OUTPUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = ["ticker", "candidate_url", "years_200", "error"] + [str(y) for y in YEARS]

    # Resume support: keep rows that were already probed successfully in an
    # earlier (interrupted) run, so I never re-query the archive needlessly.
    done: dict[tuple[str, str], dict] = {}
    if OUTPUT_CSV.exists():
        with open(OUTPUT_CSV, newline="") as f:
            for r in csv.DictReader(f):
                if not r.get("error"):
                    done[(r["ticker"], r["candidate_url"])] = r

    with open(OUTPUT_CSV, "w", newline="") as out:
        writer = csv.DictWriter(out, fieldnames=fieldnames)
        writer.writeheader()

        for i, row in enumerate(candidates, start=1):
            ticker, url = row["ticker"], row["candidate_url"]
            if (ticker, url) in done:
                writer.writerow({k: done[(ticker, url)].get(k, "") for k in fieldnames})
                continue
            print(f"[{i}/{len(candidates)}] {ticker:6s} {url}", flush=True)

            # Query the archive; if it keeps failing, record the error and move
            # on so one bad URL cannot kill the whole run. Re-running the script
            # later retries only these failed rows.
            try:
                captures = query_cdx(url)
            except RuntimeError as exc:
                writer.writerow({"ticker": ticker, "candidate_url": url, "error": str(exc)})
                out.flush()
                continue

            # Group capture statuses by year
            by_year: dict[int, list[str]] = {y: [] for y in YEARS}
            for timestamp, status in captures:
                year = int(timestamp[:4])
                if year in by_year:
                    by_year[year].append(status)

            codes = {str(y): summarize_year(by_year[y]) for y in YEARS}
            years_200 = sum(1 for c in codes.values() if c in ("200", "rev"))
            writer.writerow({"ticker": ticker, "candidate_url": url,
                             "years_200": years_200, "error": "", **codes})
            out.flush()                  # keep partial results if interrupted

            time.sleep(REQUEST_DELAY_SEC)

    print(f"\nDone. Wrote {OUTPUT_CSV}")


if __name__ == "__main__":
    main()
