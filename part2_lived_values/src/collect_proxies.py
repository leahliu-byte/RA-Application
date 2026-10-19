"""
collect_proxies.py
------------------
Part 2, step 1: collect the annual proxy statement (SEC form DEF 14A) for each
of the 50 sample companies, for every calendar year 2016-2024, from SEC EDGAR.

Why proxy statements, and why EDGAR (see README for the full reasoning):
  - Every U.S.-listed company must file one each year, so coverage is complete
    by law, and EDGAR is the single official, free, machine-readable source.
  - The same code works unchanged for all 500 S&P companies (no manual search).

Procedure (rule-based, no AI):
  1. Map each ticker to its SEC Central Index Key (CIK) using the SEC's own
     ticker file (company_tickers.json). BRK.B is listed there as BRK-B.
  2. Read the company's full filing history from the EDGAR submissions API
     (data.sec.gov), including the older-filings pages for heavy filers.
     Companies that reorganised under a new legal entity (new CIK) also get
     their predecessor entity's history (data/predecessor_ciks.csv: found via
     EDGAR's company search and verified by the former names EDGAR lists).
  3. Keep definitive proxy statements: form "DEF 14A", and "DEFC14A", the
     definitive proxy filed in a contested election (proxy fight), which is
     the company's annual proxy in that year (e.g. McDonald's 2022,
     ExxonMobil 2021, Starbucks 2024). Excluded: DEFA14A (additional
     soliciting material), DEFM14A (merger proxies), PRE 14A / PREC14A
     (preliminary drafts), DFAN14A (filed by dissident shareholders).
  4. Assign each filing to a PROXY YEAR: the calendar year of its filing date,
     except that December filings count toward the next year, because they
     solicit votes for the next year's annual meeting (e.g. Apple filed its
     2018 proxy on 27 Dec 2017). If a proxy year has more than one filing
     (e.g. a special meeting), keep the LARGEST one: the annual-meeting proxy
     (board, pay, governance) is far longer than a special-meeting proxy.
     The number of candidates is recorded.
  5. Download the primary document and extract its text (scripts, styles and
     hidden XBRL header removed; whitespace normalised).

Outputs:
  output/proxy_manifest.csv       one row per company-year, incl. gaps + reasons
  data/raw/proxies/*.htm, *.txt   raw HTML and extracted text (git-ignored; re-creatable)

The SEC requires automated clients to identify themselves with a contact email
(fair-access policy, max 10 requests/second). It is read from SEC_USER_AGENT
in the repo's .env file so it is not committed.

Usage (from the repo root, with .venv active):
    python part2_lived_values/src/collect_proxies.py
"""

import csv
import json
import os
import re
import time
from pathlib import Path

import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv

PART_DIR = Path(__file__).resolve().parents[1]
REPO_DIR = PART_DIR.parent
COMPANIES_CSV = REPO_DIR / "data" / "companies.csv"
RAW_DIR = PART_DIR / "data" / "raw" / "proxies"
MANIFEST_CSV = PART_DIR / "output" / "proxy_manifest.csv"
PREDECESSORS_CSV = PART_DIR / "data" / "predecessor_ciks.csv"

YEARS = list(range(2016, 2025))
FORMS = {"DEF 14A", "DEFC14A"}
REQUEST_DELAY_SEC = 0.15          # stays well under the SEC's 10 requests/second

load_dotenv(REPO_DIR / ".env")
HEADERS = {"User-Agent": os.environ["SEC_USER_AGENT"]}


def sec_get(url: str) -> requests.Response:
    """GET from SEC with the required User-Agent, a polite delay and retries."""
    for attempt in range(4):
        resp = requests.get(url, headers=HEADERS, timeout=60)
        time.sleep(REQUEST_DELAY_SEC)
        if resp.status_code == 200:
            return resp
        time.sleep(5 * (attempt + 1))          # 403/429/5xx: back off and retry
    resp.raise_for_status()
    return resp


def ticker_to_cik() -> dict[str, int]:
    """SEC's official ticker -> CIK map. SEC writes class shares with '-'."""
    data = sec_get("https://www.sec.gov/files/company_tickers.json").json()
    return {row["ticker"].upper(): int(row["cik_str"]) for row in data.values()}


def proxy_filings(cik: int) -> list[dict]:
    """All definitive proxy filings for a company, from recent + older submission pages."""
    sub = sec_get(f"https://data.sec.gov/submissions/CIK{cik:010d}.json").json()
    pages = [sub["filings"]["recent"]]
    for older in sub["filings"].get("files", []):
        pages.append(sec_get(f"https://data.sec.gov/submissions/{older['name']}").json())
    out = []
    for p in pages:
        for form, date, acc, doc, size in zip(p["form"], p["filingDate"], p["accessionNumber"],
                                              p["primaryDocument"], p["size"]):
            if form in FORMS:
                out.append({"form": form, "filing_date": date, "accession": acc, "cik": cik,
                            "primary_document": doc, "size": size})
    return out


def proxy_year(filing_date: str) -> int:
    """Calendar year of filing, with December filings moved to the next year."""
    year, month = int(filing_date[:4]), int(filing_date[5:7])
    return year + 1 if month == 12 else year


def html_to_text(html: str) -> str:
    """Visible text of a proxy statement. EDGAR documents carry an inline-XBRL
    header (ix:header) that is hidden in browsers; it is removed with scripts
    and styles. Table text is kept, because proxies put much of their
    substance (pay metrics, board skills matrices) in tables."""
    soup = BeautifulSoup(html, "lxml")
    for tag in soup(["script", "style", "ix:header", "head"]):
        tag.decompose()
    text = soup.get_text("\n")
    text = re.sub(r"[ \t ]+", " ", text)
    text = re.sub(r"\n\s*\n+", "\n\n", text)
    return text.strip()


def fetch_text(filing: dict) -> tuple[Path, str]:
    """Download a filing's primary document (once) and return (text file, URL).
    The cache is keyed by the SEC accession number, which is unique per filing,
    so a change in selection rules can never reuse the wrong document."""
    acc_nodash = filing["accession"].replace("-", "")
    url = (f"https://www.sec.gov/Archives/edgar/data/{filing['cik']}/{acc_nodash}/"
           f"{filing['primary_document']}")
    txt_file = RAW_DIR / f"{filing['accession']}.txt"
    if not txt_file.exists():
        html = sec_get(url).content.decode("utf-8", errors="replace")
        (RAW_DIR / f"{filing['accession']}.htm").write_text(html, encoding="utf-8")
        txt_file.write_text(html_to_text(html), encoding="utf-8")
    return txt_file, url


def main() -> None:
    with open(COMPANIES_CSV, newline="") as f:
        companies = list(csv.DictReader(f))
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    MANIFEST_CSV.parent.mkdir(parents=True, exist_ok=True)
    ciks = ticker_to_cik()
    predecessors: dict[str, list[int]] = {}
    with open(PREDECESSORS_CSV, newline="") as f:
        for r in csv.DictReader(f):
            predecessors.setdefault(r["ticker"], []).append(int(r["cik"]))

    rows = []
    for co in companies:
        sec_ticker = co["ticker"].replace(".", "-")             # BRK.B -> BRK-B
        cik = ciks.get(sec_ticker)
        base = {**co, "cik": cik or ""}
        if cik is None:
            rows += [{**base, "year": y, "status": "missing",
                      "status_reason": "ticker not in SEC ticker file"} for y in YEARS]
            continue

        filings = proxy_filings(cik)
        for pred in predecessors.get(co["ticker"], []):
            filings += proxy_filings(pred)
        print(f"{co['ticker']:6s} CIK {cik}: {len(filings)} definitive proxies in history", flush=True)
        for y in YEARS:
            in_year = [f for f in filings if proxy_year(f["filing_date"]) == y]
            if not in_year:
                rows.append({**base, "year": y, "status": "missing",
                             "status_reason": f"no definitive proxy filed for {y}"})
                continue
            if len(in_year) == 1:
                chosen = in_year[0]
            else:
                # Several proxies in one year (special meetings for mergers or
                # pay packages). Prefer one whose cover pages announce an
                # ANNUAL meeting; size breaks ties. (Size alone failed for
                # Tesla 2018, whose special-meeting proxy on Elon Musk's pay
                # award was longer than its annual proxy.)
                def is_annual(f):
                    head = " ".join(fetch_text(f)[0].read_text(encoding="utf-8").split()[:3000]).lower()
                    return "annual meeting" in head
                chosen = max(in_year, key=lambda f: (is_annual(f), f["size"]))
            txt_file, url = fetch_text(chosen)
            n_words = len(txt_file.read_text(encoding="utf-8").split())
            rows.append({**base, "cik": chosen["cik"], "year": y, "form": chosen["form"],
                         "filing_date": chosen["filing_date"],
                         "accession": chosen["accession"], "text_file": txt_file.name,
                         "primary_document": chosen["primary_document"], "url": url,
                         "n_def14a_in_year": len(in_year), "n_words": n_words,
                         "status": "ok", "status_reason": ""})

    fields = ["ticker", "company_name", "sector", "year", "cik", "form", "filing_date",
              "accession", "primary_document", "url", "text_file", "n_def14a_in_year", "n_words",
              "status", "status_reason"]
    with open(MANIFEST_CSV, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows({k: r.get(k, "") for k in fields} for r in rows)
    ok = sum(r["status"] == "ok" for r in rows)
    print(f"\nDone. {ok} of {len(rows)} company-years collected -> {MANIFEST_CSV}")


if __name__ == "__main__":
    main()
