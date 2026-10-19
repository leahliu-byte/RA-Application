"""
download_pages.py
-----------------
Stage 5 of the Part 1 pipeline: download the selected page for every
company-year from the Wayback Machine and extract its clean body text.

For each row of output/selected_pages.csv with status "selected":
  1. Rule E - find the FIRST usable capture of that URL in that calendar year
     (CDX query restricted to the year, excluding 3xx/4xx/5xx captures).
  2. Download that capture in `id_` mode (the original HTML, without the
     Wayback toolbar or rewritten links). Raw HTML is cached on disk.
  3. Extract visible body text, stripping navigation, header, footer, cookie
     banners and other boilerplate (trafilatura; BeautifulSoup fallback).
  4. Rule F - quality check: text under MIN_WORDS words, or text that matches
     a known error/"page not found" pattern, is marked as missing.

Output: output/snapshots.csv - one row per company-year (all 450, including
missing ones, so every gap carries its reason).

The script is resumable: rows already finished in a previous run are kept and
not re-downloaded; rows that failed to download are retried.

Usage (from the repo root, with .venv active):
    python part1_stated_values/src/download_pages.py
"""

import csv
import re
import time
from pathlib import Path

import requests
import trafilatura
from bs4 import BeautifulSoup

from discover_candidates import HEADERS, polite_get     # same polite request policy

PART_DIR = Path(__file__).resolve().parents[1]
SELECTED_CSV = PART_DIR / "output" / "selected_pages.csv"
OUTPUT_CSV = PART_DIR / "output" / "snapshots.csv"
RAW_DIR = PART_DIR / "data" / "raw" / "pages"           # cached HTML (git-ignored)

CDX_ENDPOINT = "https://web.archive.org/cdx/search/cdx"
MIN_WORDS = 50                                          # rule F threshold

# Rule F: phrases that identify an error page or a non-content placeholder
# served with HTTP 200 (a "soft 404"). Matched case-insensitively against the
# first part of the extracted text.
ERROR_PATTERNS = re.compile(
    r"(page (you requested )?(was )?not (be )?found|404 error|error 404|"
    r"page (is )?(no longer )?(available|unavailable)|this page isn.t available|"
    r"sorry, (we|the page)|we can.t find (the|that) page|access denied|"
    r"enable javascript|javascript is (disabled|required))",
    re.IGNORECASE,
)

FIELDS = ["ticker", "company_name", "sector", "year", "selected_url", "tier", "tier_label",
          "selection_note", "capture_timestamp", "archive_url", "status", "status_reason",
          "word_count", "page_text_clean"]


# ---- Step 1: find the first usable capture in the year (rule E) -----------

_first_by_year: dict[str, dict[int, tuple[str, str]]] = {}   # url -> {year: (ts, original)}


def first_capture_in_year(url: str, year: int) -> tuple[str, str] | None:
    """Return (timestamp, original_url) of the first non-3xx/4xx/5xx capture of
    `url` in `year`, or None. Revisit records (status "-") are allowed: they
    point to identical, earlier-stored content and play back normally.

    One CDX query per URL covers all years (`collapse=timestamp:4` keeps the
    first matching capture of each year); results are memoised, so a page used
    for 9 years costs one index lookup instead of nine."""
    if url not in _first_by_year:
        params = {
            "url": url, "from": "2016", "to": "2024",
            "fl": "timestamp,original,statuscode",
            "filter": "!statuscode:[345]..",      # drop redirects and errors
            "collapse": "timestamp:4",            # first capture per year
            "output": "json",
        }
        for wait in (30, 60, 120, 240, None):
            try:
                r = requests.get(CDX_ENDPOINT, params=params, headers=HEADERS, timeout=90)
                time.sleep(4)
                if r.status_code == 200:
                    rows = r.json() if r.text.strip() else []
                    _first_by_year[url] = {int(ts[:4]): (ts, orig) for ts, orig, _ in rows[1:]}
                    break
                print(f"    CDX HTTP {r.status_code}", flush=True)
            except (requests.RequestException, ValueError) as exc:
                print(f"    CDX {type(exc).__name__}", flush=True)
            if wait is None:
                raise RuntimeError("CDX unavailable")
            time.sleep(wait)
    return _first_by_year[url].get(year)


# ---- Steps 2-3: download and extract ---------------------------------------

def decode_html(raw: bytes) -> str:
    """Decode page bytes. Archived pages are overwhelmingly UTF-8, but the
    archive's HTTP header often omits the charset, in which case `requests`
    falls back to ISO-8859-1 and turns every curly apostrophe or dash into
    a run of garbage characters ("mojibake"). So: try UTF-8 first, then the
    encoding detected from the bytes."""
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError:
        import charset_normalizer
        best = charset_normalizer.from_bytes(raw).best()
        return str(best) if best else raw.decode("latin-1")


def repair_mojibake(text: str) -> str:
    """Repair HTML cached by an earlier run that was decoded as ISO-8859-1
    although it was UTF-8. Reversible exactly: re-encode as ISO-8859-1 and
    decode as UTF-8. Text that was decoded correctly fails this round trip
    and is returned unchanged."""
    try:
        return text.encode("latin-1").decode("utf-8")
    except (UnicodeEncodeError, UnicodeDecodeError):
        return text

def normalize_text(text: str) -> str:
    """Collapse runs of spaces/tabs inside lines and blank-line runs, so the
    text is clean for analysis while keeping paragraph boundaries."""
    lines = [re.sub(r"[ \t ]+", " ", ln).strip() for ln in text.splitlines()]
    text = "\n".join(lines)
    # Line breaks copied from the HTML source can split a sentence
    # ("Build\nbest-in-class platforms"). A break followed by a lowercase
    # letter is a continuation, so it becomes a space; breaks before capitals
    # (new headings/sentences) are kept.
    text = re.sub(r"(?<=\S)\n(?=[a-z])", " ", text)
    return re.sub(r"\n{3,}", "\n\n", text).strip()


def extract_text(html: str) -> str:
    """Main-content extraction. trafilatura removes navigation, header,
    footer and boilerplate; `favor_recall` keeps short About-page sections
    (mission statements, value lists) that stricter settings drop. If it
    returns nothing, fall back to BeautifulSoup with structural tags removed."""
    text = trafilatura.extract(html, include_comments=False, include_tables=False,
                               favor_recall=True) or ""
    if len(text.split()) < MIN_WORDS:
        soup = BeautifulSoup(html, "html.parser")
        for tag in soup(["script", "style", "noscript", "nav", "header", "footer",
                         "form", "svg", "iframe", "aside"]):
            tag.decompose()
        fallback = soup.get_text("\n", strip=True)
        if len(fallback.split()) > len(text.split()):
            text = fallback
    return normalize_text(text)


# ---- Main ------------------------------------------------------------------

def main() -> None:
    with open(SELECTED_CSV, newline="") as f:
        selected = list(csv.DictReader(f))

    # Resume: keep finished rows; retry only those whose download failed
    done = {}
    if OUTPUT_CSV.exists():
        with open(OUTPUT_CSV, newline="") as f:
            for r in csv.DictReader(f):
                if r["status"] != "fetch_failed":
                    done[(r["ticker"], r["year"], r["selected_url"])] = r

    RAW_DIR.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_CSV, "w", newline="") as out:
        w = csv.DictWriter(out, fieldnames=FIELDS)
        w.writeheader()

        for i, s in enumerate(selected, start=1):
            key = (s["ticker"], s["year"], s["selected_url"])
            base = {"ticker": s["ticker"], "company_name": s["company_name"],
                    "sector": s["sector"], "year": s["year"],
                    "selected_url": s["selected_url"], "tier": s["tier"],
                    "tier_label": s["tier_label"], "selection_note": s["note"]}

            if key in done:
                w.writerow({k: done[key].get(k, "") for k in FIELDS})
                continue
            if s["status"] != "selected":
                w.writerow({**base, "status": "missing", "status_reason": s["note"]})
                continue

            print(f"[{i}/{len(selected)}] {s['ticker']:6s} {s['year']} {s['selected_url']}", flush=True)
            year = int(s["year"])
            raw_file = RAW_DIR / f"{s['ticker']}_{year}.html"
            row = dict(base)

            try:
                cap = first_capture_in_year(s["selected_url"], year)
            except RuntimeError:
                w.writerow({**row, "status": "fetch_failed", "status_reason": "CDX unavailable"})
                out.flush()
                continue
            if cap is None:
                # The coverage check (monthly sampling) saw a capture, but none
                # is usable on closer inspection.
                w.writerow({**row, "status": "missing",
                            "status_reason": "no usable capture found in this year at download time"})
                out.flush()
                continue

            ts, original = cap
            archive_url = f"https://web.archive.org/web/{ts}id_/{original}"
            row.update(capture_timestamp=ts, archive_url=archive_url)

            if raw_file.exists():
                html = repair_mojibake(raw_file.read_text(encoding="utf-8", errors="ignore"))
            else:
                resp = polite_get(archive_url)
                if resp is None:
                    w.writerow({**row, "status": "fetch_failed",
                                "status_reason": "archive did not return the capture"})
                    out.flush()
                    continue
                html = decode_html(resp.content)
                raw_file.write_text(html, encoding="utf-8")

            text = extract_text(html)
            n_words = len(text.split())
            row.update(word_count=n_words, page_text_clean=text)

            # Rule F quality check
            if n_words < MIN_WORDS:
                row.update(status="too_short", status_reason=f"only {n_words} words after cleaning")
            elif ERROR_PATTERNS.search(text[:600]):
                m = ERROR_PATTERNS.search(text[:600]).group(0)
                row.update(status="error_page", status_reason=f'error/placeholder text: "{m}"')
            else:
                row.update(status="ok", status_reason="")
            w.writerow(row)
            out.flush()

    with open(OUTPUT_CSV, newline="") as f:
        rows = list(csv.DictReader(f))
    counts = {}
    for r in rows:
        counts[r["status"]] = counts.get(r["status"], 0) + 1
    print(f"\nDone. {counts} -> {OUTPUT_CSV}")


if __name__ == "__main__":
    main()
