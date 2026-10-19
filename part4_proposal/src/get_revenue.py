"""
get_revenue.py
--------------
Part 4, step 1: identify which companies were financially hit by COVID-19,
i.e. whose revenue fell in calendar 2020 versus 2019. These are the firms whose
"people first" claims were tested when budgets got tight.

Source: SEC XBRL "company facts" API (data.sec.gov/api/xbrl/companyfacts),
free and official; values are the audited figures tagged in 10-K filings.

Rules (no AI, applied identically to every company):
  - Revenue concept: the first of these US-GAAP tags that has values for both
    years, in this order (companies and industries tag revenue differently):
      Revenues
      RevenueFromContractWithCustomerExcludingAssessedTax
      RevenueFromContractWithCustomerIncludingAssessedTax
      SalesRevenueNet
      RevenuesNetOfInterestExpense   (banks report net revenue this way)
  - Period: the SEC's calendarised annual frames "CY2019" and "CY2020", which
    align different fiscal year-ends (e.g. Microsoft's June year-end) to
    calendar years, so all companies are compared over the same period.
  - Companies that later reorganised under a new legal entity use their
    predecessor's CIK (part2_lived_values/data/predecessor_ciks.csv), because
    the 2019-2020 filings were made by the predecessor.
  - revenue_hit_2020 = revenue change < 0.

Output: part4_proposal/output/revenue_2019_2020.csv

Usage (from the repo root, with .venv active):
    python part4_proposal/src/get_revenue.py
"""

import csv
import os
import time
from pathlib import Path

import requests
from dotenv import load_dotenv

REPO = Path(__file__).resolve().parents[2]
OUT = REPO / "part4_proposal" / "output" / "revenue_2019_2020.csv"
TAGS = ["Revenues", "RevenueFromContractWithCustomerExcludingAssessedTax",
        "RevenueFromContractWithCustomerIncludingAssessedTax", "SalesRevenueNet",
        "RevenuesNetOfInterestExpense"]

load_dotenv(REPO / ".env")
HEADERS = {"User-Agent": os.environ["SEC_USER_AGENT"]}


def get(url: str) -> dict | None:
    for attempt in range(3):
        r = requests.get(url, headers=HEADERS, timeout=60)
        time.sleep(0.15)                                   # SEC fair-access limit
        if r.status_code == 200:
            return r.json()
        if r.status_code == 404:
            return None
        time.sleep(5 * (attempt + 1))
    return None


def frame_value(facts: dict, tag: str, frame: str) -> float | None:
    """Value of a US-GAAP tag for a calendarised annual frame, if reported."""
    units = facts.get("facts", {}).get("us-gaap", {}).get(tag, {}).get("units", {}).get("USD", [])
    vals = [u["val"] for u in units if u.get("frame") == frame]
    return float(vals[-1]) if vals else None


def main() -> None:
    companies = list(csv.DictReader(open(REPO / "data" / "companies.csv")))
    preds = {r["ticker"]: int(r["cik"]) for r in
             csv.DictReader(open(REPO / "part2_lived_values" / "data" / "predecessor_ciks.csv"))}
    # CIKs used for the proxies (Part 2 manifest), year 2020
    man = list(csv.DictReader(open(REPO / "part2_lived_values" / "output" / "proxy_manifest.csv")))
    cik_2020 = {r["ticker"]: int(r["cik"]) for r in man if r["year"] == "2020"}

    rows = []
    for co in companies:
        t = co["ticker"]
        cik = preds.get(t, cik_2020.get(t))
        facts = get(f"https://data.sec.gov/api/xbrl/companyfacts/CIK{cik:010d}.json")
        row = {"ticker": t, "company_name": co["company_name"], "sector": co["sector"], "cik": cik}
        for tag in TAGS:
            r19 = frame_value(facts or {}, tag, "CY2019")
            r20 = frame_value(facts or {}, tag, "CY2020")
            if r19 and r20:
                row.update(revenue_tag=tag, revenue_2019=r19, revenue_2020=r20,
                           revenue_change_pct=round(100 * (r20 - r19) / r19, 2),
                           revenue_hit_2020=r20 < r19)
                break
        else:
            row.update(revenue_tag="", note="no revenue tag with both CY2019 and CY2020 values")
        rows.append(row)
        print(t, row.get("revenue_change_pct", "n/a"), flush=True)

    fields = ["ticker", "company_name", "sector", "cik", "revenue_tag", "revenue_2019",
              "revenue_2020", "revenue_change_pct", "revenue_hit_2020", "note"]
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows({k: r.get(k, "") for k in fields} for r in rows)
    print(f"{sum(1 for r in rows if r.get('revenue_tag'))} of {len(rows)} companies with revenue -> {OUT}")


if __name__ == "__main__":
    main()
