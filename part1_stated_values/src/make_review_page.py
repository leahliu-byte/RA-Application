"""
make_review_page.py
-------------------
Build a self-contained HTML page for the human audit of the automatic page
selection (see select_pages.py, "Audit").

For each company it shows:
  - the automatically selected page for every year, each linked to the
    archived copy on the Wayback Machine so it can be opened and checked;
  - automatic flags that point the reviewer at likely problems;
  - the other usable candidates (with their years), in case one is better;
  - a link to the archived homepage, for the human-inspection fallback.

The reviewer records decisions in data/manual_overrides.csv (format described
on the page itself) and re-runs select_pages.py.

Usage (from the repo root, with .venv active):
    python part1_stated_values/src/make_review_page.py
    open part1_stated_values/review/selection_review.html
"""

import csv
import html
import re
from pathlib import Path

from select_pages import assign_tier          # same tier rule as the selection itself

PART_DIR = Path(__file__).resolve().parents[1]
YEARS = list(range(2016, 2025))
OUT_HTML = PART_DIR / "review" / "selection_review.html"


def read_csv(path: Path) -> list[dict]:
    with open(path, newline="") as f:
        return list(csv.DictReader(f))


def wayback(url: str, year: int) -> str:
    """Wayback link that opens the capture nearest mid-January of `year`."""
    return f"https://web.archive.org/web/{year}0115000000/https://{url}"


def same_page_key(url: str) -> str:
    """Collapse trivial variants of one address so they are not reported as a
    tie: case, trailing index/default/home files and .html/.aspx/.htm endings
    (e.g. 'x.com/about-us' == 'x.com/about-us.html' == 'x.com/about-us/index.html')."""
    u = url.lower().rstrip("/")
    u = re.sub(r"/(index|default|home)\.(html?|aspx|page)$", "", u)
    u = re.sub(r"\.(html?|aspx|page)$", "", u)
    return u


def flags_for(summary: dict, cands: list[dict]) -> list[str]:
    """Simple, rule-based warnings to focus the reviewer's attention."""
    flags = []
    tier = summary["primary_tier"]
    if tier == "3":
        flags.append("Found only by the standard-address fallback (not linked from homepage): check it is a real About page")
    if tier == "4":
        flags.append("Homepage used as last resort: inspect the archived homepage for an About link")
    if int(summary["years_selected"]) < 8:
        flags.append(f"Only {summary['years_selected']} of 9 years covered: look for an older/newer About page")
    if int(summary["n_urls_used"]) >= 3:
        flags.append(f"{summary['n_urls_used']} different pages stitched together: check they are the same kind of page")
    # A tie: another candidate in the same tier with the same number of years
    prim = next((c for c in cands if c["url"] == summary["primary_url"]), None)
    if prim:
        ties = [c for c in cands if c is not prim and c["tier"] == prim["tier"]
                and c["n_years"] == prim["n_years"]
                and same_page_key(c["url"]) != same_page_key(prim["url"])]
        if ties:
            flags.append("Tie with another candidate of the same tier and coverage (picked by tie-break): check the right one won")
    return flags


def main() -> None:
    summary = read_csv(PART_DIR / "output" / "selection_summary.csv")
    pages = read_csv(PART_DIR / "output" / "selected_pages.csv")
    coverage = read_csv(PART_DIR / "output" / "candidate_coverage.csv")
    candidates = {(r["ticker"], r["candidate_url"]): r["source"]
                  for r in read_csv(PART_DIR / "data" / "candidate_urls.csv")}
    discovered = {(r["ticker"], r["candidate_url"]): r
                  for r in read_csv(PART_DIR / "output" / "discovered_candidates.csv")}
    homepages: dict[str, list[str]] = {}
    for r in read_csv(PART_DIR / "data" / "homepages.csv"):
        homepages.setdefault(r["ticker"], []).append(r["homepage"])

    # Usable candidates per company, with a rough tier for display
    cands_by_ticker: dict[str, list[dict]] = {}
    for r in coverage:
        if not r["years_200"] or int(r["years_200"]) == 0:
            continue
        key = (r["ticker"], r["candidate_url"])
        src = candidates.get(key, "")
        d = discovered.get(key, {})
        tier = str(assign_tier(src, d.get("link_text")))
        cands_by_ticker.setdefault(r["ticker"], []).append({
            "url": r["candidate_url"], "source": src, "tier": tier,
            "link_text": d.get("link_text", ""), "n_years": int(r["years_200"]),
            "codes": {y: r[str(y)] for y in YEARS},
        })
    for lst in cands_by_ticker.values():
        lst.sort(key=lambda c: (c["tier"], -c["n_years"], c["url"]))

    esc = html.escape
    cards = []
    for s in summary:
        t = s["ticker"]
        cands = cands_by_ticker.get(t, [])
        flags = flags_for(s, cands)

        year_cells = []
        for p in (p for p in pages if p["ticker"] == t):
            y = int(p["year"])
            if p["status"] == "selected":
                year_cells.append(
                    f'<tr><td>{y}</td><td><a href="{esc(wayback(p["selected_url"], y))}" target="_blank">'
                    f'{esc(p["selected_url"])}</a></td><td>{esc(p["note"])}</td></tr>')
            else:
                year_cells.append(f'<tr class="missing"><td>{y}</td><td>missing</td><td>{esc(p["note"])}</td></tr>')

        alt_rows = []
        for c in cands[:8]:
            grid = "".join(
                f'<span class="cell {"ok" if c["codes"][y] in ("200", "rev") else "redir" if c["codes"][y] == "3xx" else "none"}" '
                f'title="{y}: {c["codes"][y] or "no capture"}">{str(y)[2:]}</span>' for y in YEARS)
            mark = " ★" if c["url"] == s["primary_url"] else ""
            alt_rows.append(
                f'<tr><td><a href="{esc(wayback(c["url"], 2020))}" target="_blank">{esc(c["url"])}</a>{mark}</td>'
                f'<td>{esc(c["link_text"])}</td><td>{esc(c["source"])}</td><td class="grid">{grid}</td></tr>')

        hp_links = " · ".join(
            f'<a href="{esc(wayback(h, y))}" target="_blank">{esc(h)} {y}</a>'
            for h in homepages.get(t, []) for y in (2016, 2020, 2024))

        flag_html = ("".join(f"<li>{esc(f)}</li>" for f in flags)) or "<li class='okflag'>No automatic flags</li>"
        cards.append(f"""
<section class="card {'flagged' if flags else ''}" id="{esc(t)}">
  <h2>{esc(t)} · {esc(s['company_name'])} <small>{esc(s['sector'])}</small></h2>
  <p><b>Primary page:</b> {esc(s['primary_url']) or '—'}
     &nbsp;<b>Link text on homepage:</b> {esc(s['primary_link_text']) or '—'}
     &nbsp;<b>Years covered:</b> {esc(s['years_selected'])}/9</p>
  <ul class="flags">{flag_html}</ul>
  <details {'open' if flags else ''}><summary>Selected page per year (click to open archived copy)</summary>
    <table class="years"><tr><th>Year</th><th>Selected URL</th><th>Why</th></tr>{''.join(year_cells)}</table>
  </details>
  <details><summary>All usable candidates ({len(cands)}) — ★ = primary</summary>
    <table class="alts"><tr><th>URL (opens 2020 copy)</th><th>Homepage link text</th><th>Source</th><th>Years 2016–2024</th></tr>{''.join(alt_rows)}</table>
  </details>
  <p class="hp"><b>Archived homepage:</b> {hp_links}</p>
</section>""")

    n_flagged = sum('class="card flagged"' in c for c in cards)
    page = f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Page Selection Review</title>
<style>
:root {{ --bg:#fff; --fg:#1d1d1f; --muted:#666; --card:#f6f6f8; --line:#ddd; --accent:#0b62d6;
        --warn:#fff4e5; --warnline:#f0a030; --ok:#2e9e5b; --redir:#e0a020; --none:#ccc; }}
@media (prefers-color-scheme: dark) {{ :root {{ --bg:#141416; --fg:#eee; --muted:#aaa; --card:#1f1f23;
        --line:#333; --accent:#6aa8ff; --warn:#2c2416; --warnline:#c88a20; --none:#444; }} }}
body {{ background:var(--bg); color:var(--fg); font:15px/1.5 -apple-system, system-ui, sans-serif;
        max-width:1100px; margin:0 auto; padding:16px; }}
a {{ color:var(--accent); word-break:break-all; }}
.card {{ background:var(--card); border:1px solid var(--line); border-radius:10px; padding:12px 16px; margin:14px 0; }}
.card.flagged {{ border-left:5px solid var(--warnline); }}
h2 {{ margin:0 0 6px; font-size:18px; }} h2 small {{ color:var(--muted); font-weight:normal; }}
.flags li {{ background:var(--warn); margin:3px 0; padding:2px 6px; border-radius:4px; list-style:none; }}
.flags {{ padding:0; }} .okflag {{ background:transparent !important; color:var(--ok); }}
table {{ border-collapse:collapse; width:100%; font-size:13px; margin:6px 0; }}
td, th {{ border-bottom:1px solid var(--line); padding:3px 6px; text-align:left; vertical-align:top; }}
tr.missing td {{ color:var(--muted); font-style:italic; }}
.cell {{ display:inline-block; width:22px; text-align:center; font-size:11px; border-radius:3px; margin:1px; color:#fff; }}
.cell.ok {{ background:var(--ok); }} .cell.redir {{ background:var(--redir); }} .cell.none {{ background:var(--none); color:var(--muted); }}
.grid {{ white-space:nowrap; }}
.howto {{ background:var(--card); border:1px solid var(--line); border-radius:10px; padding:12px 16px; }}
code {{ background:var(--line); padding:1px 4px; border-radius:3px; }}
nav a {{ margin-right:6px; }}
</style></head><body>
<h1>Page selection review</h1>
<div class="howto">
<p><b>{n_flagged} of {len(summary)}</b> companies have automatic flags (orange bar). For each company, open a few years'
archived copies and ask: <i>is this the company's general About page (rule A/B)?</i></p>
<p>To change a pick, add a row to <code>part1_stated_values/data/manual_overrides.csv</code>:</p>
<pre>ticker,years,url,reason
JPM,2016-2023,jpmorganchase.com/corporate/About-JPMC/about-us.htm,Auto pick was the JPMorgan Chase Institute (research arm) About page, not the company's
META,2016-2021,,facebook.com/facebook is the company's social-media profile, not an About page</pre>
<p><code>years</code> = <code>all</code>, <code>2024</code> or <code>2016-2023</code>. <code>url</code> must be one of the candidates listed
below; leave it empty to mark those years missing. If the right page is not listed at all, find it on the archived
homepage and add it to <code>data/manual_additions.csv</code> (<code>ticker,candidate_url,note</code>) first.</p>
<p>Coverage squares: <span class="cell ok">16</span> captured &nbsp;<span class="cell redir">16</span> redirect only
&nbsp;<span class="cell none">16</span> nothing.</p>
</div>
<nav>{' '.join(f'<a href="#{esc(s["ticker"])}">{esc(s["ticker"])}</a>' for s in summary)}</nav>
{''.join(cards)}
</body></html>"""
    OUT_HTML.parent.mkdir(parents=True, exist_ok=True)
    OUT_HTML.write_text(page, encoding="utf-8")
    print(f"{n_flagged} of {len(summary)} companies flagged -> {OUT_HTML}")


if __name__ == "__main__":
    main()
