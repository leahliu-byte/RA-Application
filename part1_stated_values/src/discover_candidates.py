"""
discover_candidates.py
----------------------
Systematic (non-AI) discovery of candidate "About Us" URLs.

Instead of relying on someone's knowledge of each company's website, I let the
companies' own homepages tell us where their About page is:

  1. For each company homepage in data/homepages.csv, download the ARCHIVED
     homepage (Wayback Machine) as it looked in early 2016, 2020 and 2024.
     Several years are used because sites are redesigned and links move.
  2. Extract every link (<a href="...">link text</a>) on the page.
  3. Keep links whose text or address contains an About-type keyword.
  4. Score each kept link with fixed, written rules (see score_link) and drop
     links that point to excluded page types (investor, careers, news, ...).
  5. Write the surviving links, best first, to output/discovered_candidates.csv.

Everything here is deterministic keyword matching and arithmetic: no LLM or
other AI is involved, so the same inputs always produce the same output.

Usage (from the repo root, with .venv active):
    python part1_stated_values/src/discover_candidates.py
"""

import csv
import re
import time
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

# ---- Configuration ---------------------------------------------------------

PART_DIR = Path(__file__).resolve().parents[1]                 # part1_stated_values/
HOMEPAGES_CSV = PART_DIR / "data" / "homepages.csv"
CACHE_DIR = PART_DIR / "data" / "raw" / "homepages"             # downloaded HTML (git-ignored)
OUTPUT_CSV = PART_DIR / "output" / "discovered_candidates.csv"

SAMPLE_YEARS = [2016, 2020, 2024]   # start, middle and end of the study window
# Links scoring below this are discarded. 5 requires an About-type keyword in the
# visible link TEXT *and* corroboration (an About-type address, or an exact About
# label), plus being on the company's site. A first run with 4 let through
# promotional links such as "Learn about Charge & Credit Cards" (text keyword +
# same domain = 4), so the bar was raised after inspecting the results.
MIN_SCORE = 5

# Link texts starting with these words are calls-to-action inside page content
# ("Learn more about our refineries"), not navigation labels, so their text is
# not treated as an About signal. Added after the first run surfaced such links.
CALL_TO_ACTION = re.compile(r"^(learn|read|find out|discover|see|explore|watch|get)\b")
MAX_PER_COMPANY = 6                 # keep at most this many candidates per company

# Politeness settings for the Internet Archive (see probe_candidates.py for why).
REQUEST_DELAY_SEC = 4
BACKOFF_SEC = [30, 60, 120, 240, 300]
HEADERS = {"User-Agent": "RA-Application research scraper (academic project)"}

# ---- Keyword rules (the heart of the method; documented in the README) -----

# Phrases that strongly signal an About-type page.
STRONG_KEYWORDS = [
    "about", "who we are", "our company", "company overview", "company profile",
    "our story", "mission", "values", "purpose", "credo", "our culture",
]
# Words that weakly signal one (common, but also appear in unrelated links).
WEAK_KEYWORDS = ["company", "corporate", "overview"]

# Page types excluded by selection rule A (investor relations, careers, news,
# legal, ESG reports, shopping/support, etc.). A match in the link text or
# address heavily penalizes the link.
EXCLUDE_KEYWORDS = [
    "investor", "career", "job", "news", "press", "media", "blog", "event",
    "cookie", "privacy", "terms", "legal", "accessib", "sitemap",
    "esg", "sustainab", "responsib", "citizenship", "report", "impact",
    "contact", "support", "help", "store", "shop", "cart", "login", "sign",
    "advertis", "ads", "supplier", "locat", "faq",
]


def keyword_regex(words: list[str]) -> re.Pattern:
    """Match any keyword at the START of a word ("news" matches "newsroom" but
    "sign" does not match "design", "store" does not match "restore")."""
    return re.compile(r"(?<![a-z])(" + "|".join(re.escape(w) for w in words) + ")")


STRONG_RE = keyword_regex(STRONG_KEYWORDS)
WEAK_RE = keyword_regex(WEAK_KEYWORDS)
EXCLUDE_RE = keyword_regex(EXCLUDE_KEYWORDS)

# Link texts that are an exact About label: "About", "About us",
# "About <one name>" (e.g. "About Microsoft"), "Who we are", "Our company".
EXACT_ABOUT_TEXT = re.compile(
    r"^(about( us)?|about [\w&.'-]+|who we are|our company|company overview)$"
)


# ---- Helpers ---------------------------------------------------------------

def polite_get(url: str) -> requests.Response | None:
    """GET a URL from the Internet Archive with delay and progressive back-off.

    Returns the response, or None if the archive never answered successfully.
    """
    for attempt, wait in enumerate(BACKOFF_SEC, start=1):
        try:
            resp = requests.get(url, headers=HEADERS, timeout=90)
            time.sleep(REQUEST_DELAY_SEC)
            if resp.status_code == 200:
                return resp
            if resp.status_code == 404:          # nothing archived near that date
                return None
            print(f"    HTTP {resp.status_code}, retry {attempt}", flush=True)
        except requests.RequestException as exc:
            print(f"    {type(exc).__name__}, retry {attempt}", flush=True)
        time.sleep(wait)
    return None


def fetch_archived_homepage(homepage: str, year: int) -> tuple[str, str] | None:
    """Return (html, original_url) of the archived homepage nearest Jan 1 of `year`.

    The `id_` flag asks the Wayback Machine for the page exactly as originally
    captured: no Wayback toolbar, and links NOT rewritten to web.archive.org,
    so I see the company's real link addresses.
    HTML is cached on disk so re-running the script does not re-download.
    """
    cache_file = CACHE_DIR / f"{homepage.replace('/', '_')}_{year}.html"
    meta_file = cache_file.with_suffix(".url")
    failed_file = cache_file.with_suffix(".failed")
    if cache_file.exists() and meta_file.exists():
        return cache_file.read_text(encoding="utf-8"), meta_file.read_text().strip()
    # Failures are remembered too: pages the archive refuses (e.g. HTTP 403,
    # usually an owner-requested exclusion) would otherwise cost ~12 minutes of
    # retries on every re-run. Delete the .failed files to retry them.
    if failed_file.exists():
        return None

    wayback_url = f"https://web.archive.org/web/{year}0101000000id_/https://{homepage}/"
    resp = polite_get(wayback_url)
    if resp is None:
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        failed_file.write_text("archive did not return the page after all retries\n")
        return None

    # After redirects, resp.url looks like
    #   https://web.archive.org/web/20160101214549id_/https://www.microsoft.com/en-us/
    # The part after "id_/" is the original page address, needed to resolve
    # relative links such as "/en-us/about".
    match = re.search(r"/web/\d+id_/(.+)$", resp.url)
    original_url = match.group(1) if match else f"https://{homepage}/"

    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    cache_file.write_text(resp.text, encoding="utf-8")
    meta_file.write_text(original_url)
    return resp.text, original_url


def normalize_url(url: str) -> str:
    """Normalize to the same form as candidate_urls.csv: host+path, no scheme,
    no 'www.', no query string or #fragment, no trailing slash."""
    p = urlparse(url)
    host = p.netloc.lower().removeprefix("www.").split(":")[0]   # drop :80 etc.
    return (host + p.path).rstrip("/")


def registrable_domain(host: str) -> str:
    """Approximate the registrable domain: last two labels (microsoft.com)."""
    return ".".join(host.split(".")[-2:])


def score_link(text: str, url: str, homepage: str) -> float:
    """Score how likely a link is to be the company's general About page.

    Rules (higher = more likely):
      +3   link text is an exact About label ("About", "About us", "Who we are")
      +2   a strong keyword appears in the link text (not counted when the text
           is a call-to-action such as "Learn more about ...")
      +1   a strong keyword appears in the link address
      +0.5 only a weak keyword ("company", "corporate") appears
      +2   link stays on the company's own site (same domain, or a domain that
           contains the company's name, e.g. aboutamazon.com for amazon.com)
      -5   an excluded page type appears in the text or address (rule A)
    """
    text_l = text.lower()
    path_l = urlparse(url).path.lower()
    host = urlparse(url).netloc.lower().removeprefix("www.")
    score = 0.0

    # Addresses use "-" or "_" between words (/who-we-are); compare with spaces.
    # The host is included so dedicated About sites count (about.fb.com,
    # aboutamazon.com).
    path_words = re.sub(r"[-_/.]", " ", host + path_l)

    is_cta = bool(CALL_TO_ACTION.match(text_l))
    if EXACT_ABOUT_TEXT.match(text_l):
        score += 3
    if STRONG_RE.search(text_l) and not is_cta:
        score += 2
    if STRONG_RE.search(path_words):
        score += 1
    if score == 0 and (WEAK_RE.search(text_l) or WEAK_RE.search(path_words)):
        score += 0.5

    company_domain = registrable_domain(homepage)                # e.g. amazon.com
    company_name = company_domain.split(".")[0]                  # e.g. amazon
    if registrable_domain(host) == company_domain or company_name in host:
        score += 2

    if EXCLUDE_RE.search(text_l) or EXCLUDE_RE.search(path_words):
        score -= 5
    return score


def extract_links(html: str, base_url: str) -> list[tuple[str, str]]:
    """Return (link_text, absolute_url) for every http(s) link on the page."""
    soup = BeautifulSoup(html, "html.parser")
    links = []
    for a in soup.find_all("a", href=True):
        href = a["href"].strip()
        if href.startswith(("#", "mailto:", "tel:", "javascript:")):
            continue
        absolute = urljoin(base_url, href)
        if not absolute.startswith("http"):
            continue
        # Link text; fall back to aria-label/title for icon-only links.
        text = " ".join(a.get_text(" ", strip=True).split()) or a.get("aria-label", "") or a.get("title", "")
        links.append((text.strip(), absolute))
    return links


# ---- Main ------------------------------------------------------------------

def main() -> None:
    with open(HOMEPAGES_CSV, newline="") as f:
        homepages = list(csv.DictReader(f))

    # best[(ticker, normalized_url)] = info about the best-scoring sighting
    best: dict[tuple[str, str], dict] = {}
    fetch_log = []          # which homepage-years could / could not be fetched

    for i, row in enumerate(homepages, start=1):
        ticker, homepage = row["ticker"], row["homepage"]
        for year in SAMPLE_YEARS:
            print(f"[{i}/{len(homepages)}] {ticker:6s} {homepage} {year}", flush=True)
            fetched = fetch_archived_homepage(homepage, year)
            if fetched is None:
                fetch_log.append((ticker, homepage, year, "not fetched"))
                continue
            html, original_url = fetched
            links = extract_links(html, original_url)
            fetch_log.append((ticker, homepage, year, f"{len(links)} links"))

            for text, url in links:
                s = score_link(text, url, homepage)
                if s < MIN_SCORE:
                    continue
                key = (ticker, normalize_url(url))
                entry = best.setdefault(key, {"score": s, "link_text": text,
                                              "years_seen": set(), "found_on": homepage})
                entry["years_seen"].add(year)
                if s > entry["score"]:
                    entry.update(score=s, link_text=text, found_on=homepage)

    # Write results: per company, highest score first; ties broken by how many
    # sample years the link appeared in (a link present in 2016, 2020 AND 2024
    # is a more stable About page than one seen once).
    OUTPUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_CSV, "w", newline="") as out:
        writer = csv.writer(out)
        writer.writerow(["ticker", "candidate_url", "score", "years_seen",
                         "link_text", "found_on"])
        tickers = list(dict.fromkeys(r["ticker"] for r in homepages))   # keep order
        for t in tickers:
            rows = [(url, e) for (tk, url), e in best.items() if tk == t]
            rows.sort(key=lambda r: (-r[1]["score"], -len(r[1]["years_seen"])))
            for url, e in rows[:MAX_PER_COMPANY]:
                writer.writerow([t, url, e["score"],
                                 ";".join(str(y) for y in sorted(e["years_seen"])),
                                 e["link_text"][:80], e["found_on"]])

    # Fetch log, so gaps in discovery itself are documented too.
    with open(PART_DIR / "output" / "discovery_fetch_log.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["ticker", "homepage", "year", "result"])
        w.writerows(fetch_log)

    found = len({tk for tk, _ in best})
    print(f"\nDone. Candidates found for {found} of {len(tickers)} companies -> {OUTPUT_CSV}")


if __name__ == "__main__":
    main()
