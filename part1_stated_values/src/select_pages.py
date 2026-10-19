"""
select_pages.py
---------------
Stage 4 of the Part 1 pipeline: apply the written selection rules to choose,
for every company and every year 2016-2024, exactly one URL to download (or to
record the year as missing, with the reason).

Inputs (all produced by earlier, rule-based steps; no AI involved):
    data/candidate_urls.csv            every candidate and the source that produced it
    output/discovered_candidates.csv   homepage-discovery score and link text
    output/candidate_coverage.csv      per-year archive status of every candidate

Rules implemented here (numbering matches the README):

  B  Page-type priority. Every candidate gets a tier:
       tier 1  general About page: found on the homepage under an exact About
               label ("About", "About Us", "About <Company>", "Who We Are",
               "Our Company", "Company Overview")
       tier 2  other About-type page found on the homepage (e.g. "Our Values",
               "Mission", "Our Credo")
       tier 3  standard-address fallback (/about, /about-us, ...), not linked
               from any sampled homepage
       tier 4  the homepage itself (last resort, flagged)
  C  Among usable candidates, order by tier, then by number of years with a
     successful capture, then by discovery score. The first one is the
     company's PRIMARY page; it is used in every year it was captured.
  D  Moved pages (stitching). In a year the primary page has no successful
     capture, use the next candidate in the same ordering that does - i.e. the
     best same-tier page first, lower tiers only if no same-tier page exists
     that year. Every such switch is recorded.
     Only captures where the URL itself returned HTTP 200 (or an identical
     "revisit") are used. Redirect captures (3xx) are NOT followed through the
     archive: each hop of a redirect may have been archived on a different
     date, so following them would mix years. A page move instead shows up as
     a 3xx on the old URL and 200s on the new one, and stitching picks the new
     one for those years.
  E  One snapshot per year. The exact capture (first 200 of the year) is
     resolved at download time; here I only decide the URL. A year with no
     usable capture on any candidate is MISSING, never filled from another year.

  Audit  After the automatic pick, every company's selection is reviewed by
     hand (make_review_page.py). Corrections go in data/manual_overrides.csv,
     one row per decision, with a written reason:
         ticker, years, url, reason
     `years` is "all", a single year "2024", or a range "2016-2023".
     `url` must be a rule-generated candidate (data/candidate_urls.csv);
     leave it EMPTY to mark those years missing (e.g. page is not a real
     About page). Overrides are applied last and flagged in the output.

Outputs:
    output/selected_pages.csv     one row per company-year (450 rows)
    output/selection_summary.csv  one row per company: primary page, coverage, switches

Usage (from the repo root, with .venv active):
    python part1_stated_values/src/select_pages.py
"""

import csv
from pathlib import Path

from discover_candidates import EXACT_ABOUT_TEXT     # same label rule as discovery

PART_DIR = Path(__file__).resolve().parents[1]
REPO_DIR = PART_DIR.parent
COMPANIES_CSV = REPO_DIR / "data" / "companies.csv"
CANDIDATES_CSV = PART_DIR / "data" / "candidate_urls.csv"
DISCOVERED_CSV = PART_DIR / "output" / "discovered_candidates.csv"
COVERAGE_CSV = PART_DIR / "output" / "candidate_coverage.csv"
OVERRIDES_CSV = PART_DIR / "data" / "manual_overrides.csv"
OUT_PAGES = PART_DIR / "output" / "selected_pages.csv"
OUT_SUMMARY = PART_DIR / "output" / "selection_summary.csv"

YEARS = list(range(2016, 2025))
USABLE = {"200", "rev"}            # coverage codes that mean "a usable capture exists"
TIER_LABELS = {1: "about page", 2: "other About-type page",
               3: "standard address (fallback)", 4: "homepage (last resort)"}


def read_csv(path: Path) -> list[dict]:
    with open(path, newline="") as f:
        return list(csv.DictReader(f))


def assign_tier(sources: str, link_text: str | None) -> int:
    """Rule B: map a candidate's source and homepage link text to a tier."""
    if "discovered" in sources:
        if link_text and EXACT_ABOUT_TEXT.match(link_text.strip().lower()):
            return 1
        return 2
    if "pattern" in sources or "manual" in sources:
        return 3
    return 4                                          # homepage only


def parse_years(spec: str) -> list[int]:
    """'all' -> 2016..2024; '2019' -> [2019]; '2016-2023' -> 2016..2023."""
    spec = spec.strip().lower()
    if spec == "all":
        return YEARS
    if "-" in spec:
        a, b = (int(x) for x in spec.split("-"))
        return list(range(a, b + 1))
    return [int(spec)]


def load_overrides(known_urls: set[tuple[str, str]]) -> dict[tuple[str, int], dict]:
    """Read human audit decisions; refuse URLs the rules never produced."""
    if not OVERRIDES_CSV.exists():
        return {}
    out = {}
    for r in read_csv(OVERRIDES_CSV):
        url = r["url"].strip()
        if url and (r["ticker"], url) not in known_urls:
            raise ValueError(f"Override URL is not a rule-generated candidate: {r['ticker']} {url}. "
                             "Add it via data/manual_additions.csv (human-inspected) first.")
        if not r["reason"].strip():
            raise ValueError(f"Override for {r['ticker']} {r['years']} has no reason.")
        for y in parse_years(r["years"]):
            out[(r["ticker"], y)] = {"url": url, "reason": r["reason"].strip()}
    return out


def main() -> None:
    companies = read_csv(COMPANIES_CSV)
    discovered = {(r["ticker"], r["candidate_url"]): r for r in read_csv(DISCOVERED_CSV)}
    coverage = {(r["ticker"], r["candidate_url"]): r for r in read_csv(COVERAGE_CSV)}

    # Assemble candidate records with tier, coverage and score
    by_ticker: dict[str, list[dict]] = {}
    for r in read_csv(CANDIDATES_CSV):
        key = (r["ticker"], r["candidate_url"])
        cov = coverage.get(key)
        if cov is None or cov.get("error"):
            continue                                   # never checked: cannot be used
        disc = discovered.get(key, {})
        usable_years = {y for y in YEARS if cov.get(str(y)) in USABLE}
        if not usable_years:
            continue
        by_ticker.setdefault(r["ticker"], []).append({
            "url": r["candidate_url"],
            "source": r["source"],
            "tier": assign_tier(r["source"], disc.get("link_text")),
            "link_text": disc.get("link_text", ""),
            "score": float(disc.get("score") or 0),
            "years": usable_years,
            "codes": {y: cov.get(str(y), "") for y in YEARS},
        })

    all_candidates = {(r["ticker"], r["candidate_url"]): r for r in read_csv(CANDIDATES_CSV)}
    overrides = load_overrides(set(all_candidates))

    page_rows, summary_rows = [], []
    for co in companies:
        t = co["ticker"]
        # Rule C ordering: tier, then most years, then discovery score, then
        # shortest URL (a stable, neutral tie-break favouring top-level pages).
        cands = sorted(by_ticker.get(t, []),
                       key=lambda c: (c["tier"], -len(c["years"]), -c["score"], len(c["url"])))
        primary = cands[0] if cands else None

        used_urls = []
        cand_by_url = {c["url"]: c for c in cands}
        for y in YEARS:
            chosen, note = None, ""
            ov = overrides.get((t, y))
            if ov is not None:
                # Human audit decision (applied before the automatic rules)
                if not ov["url"]:
                    page_rows.append({**co, "year": y, "selected_url": "", "tier": "",
                                      "tier_label": "", "source": "", "link_text": "",
                                      "status": "missing", "note": f"override: {ov['reason']}"})
                    continue
                c = cand_by_url.get(ov["url"])
                if c is None or y not in c["years"]:
                    page_rows.append({**co, "year": y, "selected_url": "", "tier": "",
                                      "tier_label": "", "source": "", "link_text": "",
                                      "status": "missing",
                                      "note": f"override: {ov['reason']} (no capture of {ov['url']} this year)"})
                    continue
                chosen, note = c, f"override: {ov['reason']}"
            elif primary and y in primary["years"]:
                chosen, note = primary, "primary page"
            else:
                # Rule D: best other candidate captured this year (same ordering)
                for c in cands[1:]:
                    if y in c["years"]:
                        chosen = c
                        why = ("primary page not captured" if primary["codes"][y] == ""
                               else f"primary page {primary['codes'][y]} this year")
                        note = f"switched ({why})"
                        break
            if chosen is None:
                why = "no candidates with any capture" if not cands else "no candidate captured this year"
                page_rows.append({**co, "year": y, "selected_url": "", "tier": "",
                                  "tier_label": "", "source": "", "link_text": "",
                                  "status": "missing", "note": why})
                continue
            if chosen["url"] not in used_urls:
                used_urls.append(chosen["url"])
            page_rows.append({**co, "year": y, "selected_url": chosen["url"],
                              "tier": chosen["tier"], "tier_label": TIER_LABELS[chosen["tier"]],
                              "source": chosen["source"], "link_text": chosen["link_text"],
                              "status": "selected", "note": note})

        n_years = sum(1 for r in page_rows if r["ticker"] == t and r["status"] == "selected")
        n_overridden = sum(1 for y in YEARS if (t, y) in overrides)
        summary_rows.append({
            **co,
            "primary_url": primary["url"] if primary else "",
            "primary_tier": primary["tier"] if primary else "",
            "primary_link_text": primary["link_text"] if primary else "",
            "years_primary": len(primary["years"]) if primary else 0,
            "years_selected": n_years,
            "years_missing": len(YEARS) - n_years,
            "n_urls_used": len(used_urls),
            "urls_used": " | ".join(used_urls),
            "years_overridden": n_overridden,
        })

    for path, rows in [(OUT_PAGES, page_rows), (OUT_SUMMARY, summary_rows)]:
        with open(path, "w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
            w.writeheader()
            w.writerows(rows)

    sel = sum(r["status"] == "selected" for r in page_rows)
    print(f"Selected {sel} of {len(page_rows)} company-years "
          f"({len(page_rows) - sel} missing). -> {OUT_PAGES.name}, {OUT_SUMMARY.name}")


if __name__ == "__main__":
    main()
