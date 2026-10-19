"""
build_candidates.py
-------------------
Assemble the final list of candidate "About Us" URLs from two rule-based,
non-AI sources, and write it to data/candidate_urls.csv (the input of
probe_candidates.py).

Source 1 - "discovered": links found on each company's archived homepage by
           discover_candidates.py (output/discovered_candidates.csv).
Source 2 - "pattern":    a FIXED list of common About-page paths, tried on every
           company homepage in data/homepages.csv. The same paths are used for
           every company, so no company-specific knowledge enters the list.
           This is the fallback for sites whose menus are built by JavaScript
           (links invisible to discovery).

Source 3 - "homepage":   the company homepage itself, as the last-resort
           fallback of selection rule B.3.

A URL found by several sources is kept once, e.g. source = "discovered+pattern".
Any URL added by hand later (rule: only after inspecting the archived homepage
by eye) should go in data/manual_additions.csv with a note explaining why;
those rows are appended with source = "manual (human-inspected)".

Usage (from the repo root, with .venv active):
    python part1_stated_values/src/build_candidates.py
"""

import csv
from pathlib import Path

PART_DIR = Path(__file__).resolve().parents[1]
HOMEPAGES_CSV = PART_DIR / "data" / "homepages.csv"
DISCOVERED_CSV = PART_DIR / "output" / "discovered_candidates.csv"
MANUAL_CSV = PART_DIR / "data" / "manual_additions.csv"      # optional
COVERAGE_CSV = PART_DIR / "output" / "candidate_coverage.csv"
OUTPUT_CSV = PART_DIR / "data" / "candidate_urls.csv"

# Generic About-page paths, applied identically to every homepage.
# Chosen as the most common conventions on corporate websites; documented in
# the README so the list itself can be critiqued or extended.
COMMON_ABOUT_PATHS = [
    "about",
    "about-us",
    "aboutus",
    "who-we-are",
    "our-company",
    "company",
    "en-us/about",
    "us/en/about",
]


def main() -> None:
    # candidates[(ticker, url)] = set of sources that produced it
    candidates: dict[tuple[str, str], set[str]] = {}

    # Source 1: homepage discovery
    if DISCOVERED_CSV.exists():
        with open(DISCOVERED_CSV, newline="") as f:
            for r in csv.DictReader(f):
                candidates.setdefault((r["ticker"], r["candidate_url"]), set()).add("discovered")
    else:
        print(f"Warning: {DISCOVERED_CSV.name} not found; run discover_candidates.py first.")

    # Source 2: fixed common paths on every homepage
    with open(HOMEPAGES_CSV, newline="") as f:
        for r in csv.DictReader(f):
            for path in COMMON_ABOUT_PATHS:
                url = f"{r['homepage']}/{path}"
                candidates.setdefault((r["ticker"], url), set()).add("pattern")

    # Last-resort source (selection rule B.3): the homepage itself, added ONLY
    # for companies where no About-type candidate has any archived capture.
    # (Homepages have enormous capture histories, so CDX queries on them are
    # slow and often time out; checking them for every company would waste
    # hours on a fallback that is not needed.)
    has_usable = set()
    if COVERAGE_CSV.exists():
        with open(COVERAGE_CSV, newline="") as f:
            for r in csv.DictReader(f):
                if r.get("years_200") and int(r["years_200"]) > 0:
                    has_usable.add(r["ticker"])
    with open(HOMEPAGES_CSV, newline="") as f:
        for r in csv.DictReader(f):
            if r["ticker"] not in has_usable:
                candidates.setdefault((r["ticker"], r["homepage"]), set()).add("homepage")

    # Optional source 3: human-inspected additions
    if MANUAL_CSV.exists():
        with open(MANUAL_CSV, newline="") as f:
            for r in csv.DictReader(f):
                candidates.setdefault((r["ticker"], r["candidate_url"]), set()).add(
                    "manual (human-inspected)")

    # Write, grouped by ticker in homepages.csv order
    order = {}
    with open(HOMEPAGES_CSV, newline="") as f:
        for r in csv.DictReader(f):
            order.setdefault(r["ticker"], len(order))

    rows = sorted(candidates.items(), key=lambda kv: (order.get(kv[0][0], 999), kv[0][1]))
    with open(OUTPUT_CSV, "w", newline="") as out:
        w = csv.writer(out)
        w.writerow(["ticker", "candidate_url", "source"])
        for (ticker, url), sources in rows:
            w.writerow([ticker, url, "+".join(sorted(sources))])

    print(f"Wrote {len(rows)} candidates for {len(order)} companies -> {OUTPUT_CSV}")


if __name__ == "__main__":
    main()
