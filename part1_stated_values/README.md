# Part 1 — Stated Values: "About Us" Pages via the Wayback Machine

> **Non-technical summary:** [summary.md](summary.md)

## What I did

I collected one archived snapshot per year (2016–2024) of each sample company's "About Us" page
from the Wayback Machine, extracted the clean body text, and used an LLM to code each snapshot for
(a) change from the prior year, (b) value themes from a research-based codebook, and (c) linguistic
shifts.

| Stage | Script | Output |
|---|---|---|
| 1. Discover candidate About pages from archived homepages | [src/discover_candidates.py](src/discover_candidates.py), [src/build_candidates.py](src/build_candidates.py) | [output/discovered_candidates.csv](output/discovered_candidates.csv), [data/candidate_urls.csv](data/candidate_urls.csv) |
| 2. Check each candidate's archive coverage per year (CDX API) | [src/probe_candidates.py](src/probe_candidates.py) | [output/candidate_coverage.csv](output/candidate_coverage.csv) |
| 3. Select one page per company-year by the rules below | [src/select_pages.py](src/select_pages.py) | [output/selected_pages.csv](output/selected_pages.csv), [output/selection_summary.csv](output/selection_summary.csv) |
| 4. Download first capture of each year, extract text, quality check | [src/download_pages.py](src/download_pages.py) | [output/snapshots.csv](output/snapshots.csv) |
| 5. LLM coding: change, themes (with verified quotes), shifts | [src/analyze_snapshots.py](src/analyze_snapshots.py) | **[output/part1_dataset.csv](output/part1_dataset.csv)**, [output/company_shift_summaries.csv](output/company_shift_summaries.csv) |

**Result:** usable text for **402 of 450 company-years (89%)**, covering all 50 companies;
1,690 theme codes, 98.3% backed by an evidence quote verified verbatim against the page.

**Reproduce:** from the repo root with the virtual environment active, run the five scripts in
the order above (stage 5 needs `ANTHROPIC_API_KEY` in `.env`; it cost $0.33 and reuses
cached responses on re-runs, so re-running is free). [src/make_review_page.py](src/make_review_page.py) builds an
optional human-audit page.

## Key decisions at a glance

| Decision | Choice | Why | Details |
|---|---|---|---|
| Which page counts | The general **About / company overview** page; a mission/values page only if none exists; homepage as last resort | Nearly every company has one, so companies are comparable; it is the company's main public self-description | Rules A–B |
| How candidate pages are found | **Rules only:** About-type links on each archived homepage, plus a fixed list of standard addresses tried for every company | Repeatable and scalable to all 500 firms; no company-specific guessing | Rule C |
| Which candidate wins | Best tier, then most years archived; one page for all years where possible | Holding the page constant makes year-to-year change about wording, not page switches | Rule C |
| Moved pages and redirects | Redirects are **not** followed in the archive; a moved page is "stitched" (old address before the move, new one after) | Redirect hops can be archived on different dates and silently mix years | Rule D |
| Which snapshot per year | First working capture of the calendar year; a missing year stays missing | Evenly spaced time points; never borrow from another year | Rule E |
| Quality bar | Under 50 words or an error page counts as missing | Empty JavaScript shells and error pages are not the company's words | Rule F |
| Value categories | 11-category hybrid codebook (MIT "Big Nine" values + stakeholder/ESG themes + safety), shared with Part 2 | Research-grounded, and identical categories make the Part 3 comparison possible | *Codebook* |
| LLM | Claude Haiku 5.5, every theme backed by a quote verified by code | Fits a $5 budget; verification makes errors visible | *LLM analysis* |

## Page selection criteria

The assignment asks for "the corporate 'About Us' (or equivalent mission/values) page." Because
companies do not share a standard URL, page type, or site structure, I defined the following
rules and applied them identically to all 50 companies. The definition of the correct page
(A, B) and the snapshot rules (E, F) were set before collecting data; the keyword rules used to
*discover* candidate pages were revised once after inspecting their first output (see C).

### A. What counts as an "About Us" page

A page qualifies if it is:

- hosted on the company's **official corporate website**, in the **US English** version;
- a page where the company **describes itself** — who it is, its mission, purpose, vision, or values;
- **evergreen** (not a dated news post or press release).

Excluded: investor-relations pages, careers/recruiting pages, newsroom articles, product pages,
and ESG/sustainability reports (the latter are the subject of Part 2, and keeping them out of
Part 1 keeps the "stated" and "lived" values sources distinct for Part 3).

### B. Which page, when several qualify (priority order)

1. The **general About / Company overview page** (typically linked as "About" from the homepage).
2. If none exists, a dedicated **Mission / Values / Purpose page** (e.g., Johnson & Johnson's Credo).
3. If neither exists, the **homepage** — used as a last resort and flagged in the data.

**Why the general About page rather than a dedicated values page?** Comparability. Nearly every
company has a general About page, whereas dedicated values pages are inconsistent in existence,
naming, and location, which would produce more gaps and an apples-to-oranges comparison. The
About page is also the company's primary public self-presentation — what a visitor sees when
they ask "who is this company?" — which is exactly the "stated values" construct this part
measures. The trade-off is that About pages can be thinner on explicit values language than a
dedicated values page; this is noted under Limitations.

### C. Choosing among valid candidates

- Candidate URLs are generated by **rules only, with no AI and no company-specific guessing**
  ([src/build_candidates.py](src/build_candidates.py)):
  1. **Homepage discovery** ([src/discover_candidates.py](src/discover_candidates.py)): links on
     each company's archived homepage (early 2016, 2020, 2024) whose text or address matches a
     fixed About-type keyword list, scored by written rules that also exclude rule-A page types.
  2. **Common-path fallback:** the same fixed list of standard paths (`/about`, `/about-us`,
     `/who-we-are`, `/our-company`, …) tried on every company's homepage, for sites whose menus
     are rendered by JavaScript and so are invisible to discovery.
  3. **Human inspection (last resort, available but not used):** the code accepts URLs found by
     inspecting an archived homepage by eye (`data/manual_additions.csv`, with a note). It was not
     used in this run, to keep selection fully rule-based; Intel is the company that would most
     benefit (see *Known selection issues*).
- **Rule revision after inspection.** The first discovery run (kept for the record as
  [output/discovered_candidates_v1_loose_rules.csv](output/discovered_candidates_v1_loose_rules.csv))
  accepted any on-site link whose text contained "about", which let through promotional links
  such as "Learn about Charge & Credit Cards" (American Express) and "Learn more about our
  refineries" (Marathon Petroleum). Two fixes were made: link texts that begin with a
  call-to-action verb ("Learn", "Read", "Discover", …) no longer count as About signals, and a
  link now needs an About-type word in its text **plus** corroboration (an About-type address or
  an exact label like "About Us") to qualify. Re-running on the same cached homepages removed the
  false positives.
- **Discovery results** ([output/discovered_candidates.csv](output/discovered_candidates.csv)):
  a genuine About link (e.g. "About Us", "Who We Are", "Our Company", "About Microsoft") was found
  on the archived homepage for **44 of 50** companies. For Apple, IBM, Tesla and EOG, only the
  common-path fallback produced a usable candidate; for Intel and Berkshire Hathaway, neither
  source did (see rule B.3 and the human-inspection step). In total there are 603 candidates
  ([data/candidate_urls.csv](data/candidate_urls.csv)), each labelled with the source that produced it.
- Each candidate's year-by-year archive coverage is then checked against the Wayback Machine CDX
  index ([src/probe_candidates.py](src/probe_candidates.py)), producing
  [output/candidate_coverage.csv](output/candidate_coverage.csv).
- **Selection** ([src/select_pages.py](src/select_pages.py)) ranks every usable candidate by:
  1. **tier** (rule B): 1 = linked from the homepage under an exact About label ("About",
     "About Us", "About &lt;Company&gt;", "Who We Are", "Our Company", "Company Overview");
     2 = other About-type homepage link (e.g. "Our Values", "Our Credo"); 3 = standard-address
     fallback not linked from the homepage; 4 = the homepage itself;
  2. then **most years with a successful capture** in 2016–2024;
  3. then discovery score, then shortest URL (a neutral final tie-break).
- The top-ranked candidate is the company's **primary page**, used in every year it was captured.
  **One URL for all years is preferred**, because holding the page constant makes year-over-year
  change attributable to the company's wording rather than to a switch between pages.
- **No manual audit or overrides were applied.** Selection is entirely rule-based; known
  imperfections are documented under *Coverage gaps and known selection issues* below rather
  than corrected by hand. (A review page, [src/make_review_page.py](src/make_review_page.py), and
  an override mechanism exist in the code for future use, but were not used.)

### D. Redirects and moved pages

- **Redirects are not followed through the archive.** Only captures where the URL itself returned
  HTTP 200 (or an identical "revisit") are used. Each hop of a redirect chain may have been
  archived on a different date, so following redirects inside the Wayback Machine can silently
  mix content from different years, violating rule E.
- **Moved pages are handled by stitching instead.** A move shows up in the coverage table as a
  `3xx` on the old URL and `200`s on the new one. In any year the primary page has no usable
  capture, the next-best candidate captured that year is used (same tier first, lower tiers only
  if none). Every switch is recorded in `note` in
  [output/selected_pages.csv](output/selected_pages.csv) (e.g. `switched (primary page 3xx this year)`).
- An old URL that redirects to the **homepage** or an unrelated page is therefore never used
  for that year; if no other candidate was captured, the year is **missing**.

### E. Which snapshot within a year

- The **first successful (HTTP 200) capture in each calendar year**, so time points are roughly
  evenly spaced (early in each year) and comparable across companies.
- If a year has no successful capture, it is recorded as **missing** with the reason. I do
  **not** borrow a capture from an adjacent year, since that would fabricate stability.

### F. Post-download quality check

- A snapshot whose cleaned text is under 50 words, or that opens with a known error/placeholder
  phrase ("page not found", "enable JavaScript", …), is treated as missing, with the reason
  recorded.
- No manual spot-check of extracted text against the archived pages was carried out; the
  automated quote verification in the analysis step (98.3% of quotes found verbatim) is the main
  check on extraction quality. A manual check is listed under *What I would do differently*.

## Download and text extraction

[src/download_pages.py](src/download_pages.py) → [output/snapshots.csv](output/snapshots.csv) (one row per company-year).

- **Snapshot choice (rule E):** one CDX query per selected URL returns the first capture of each
  year that is not a redirect or error; that capture is downloaded in the Wayback Machine's `id_`
  mode (original HTML, no toolbar, links not rewritten).
- **Text extraction:** `trafilatura` (a main-content extractor) strips navigation, headers,
  footers, cookie banners and other boilerplate; `favor_recall` is on so short About-page sections
  (mission lines, value lists) are kept. If it yields under 50 words, a BeautifulSoup fallback
  removes `nav`/`header`/`footer`/`script`/`style`/`form`/`aside` elements and keeps the remaining
  text. Line breaks inherited from the HTML source are rejoined when a line continues a sentence.
- **Quality check (rule F):** under 50 words → `too_short`; an error/placeholder phrase in the
  first 600 characters ("page not found", "enable JavaScript", …) → `error_page`. Both count as
  missing, with the reason in `status_reason`.
- **Encoding fix.** The archive often omits the charset header, so the HTTP library decoded UTF-8
  pages as ISO-8859-1, turning curly apostrophes into garbage ("mojibake"). This was caught by the
  quote-verification check in the analysis step (a verbatim quote could not be found in the page
  text). Pages are now decoded as UTF-8 first, and HTML cached before the fix is repaired by the
  exact inverse transformation.

## Analytical categories (codebook)

Defined in [../data/codebook.json](../data/codebook.json), shared with Part 2 so that Part 3 can
compare stated and disclosed values **on identical categories**. It is a hybrid of two research
traditions:

| Group | Category | Origin |
|---|---|---|
| Culture values | Innovation · Integrity & ethics · Customer focus · Collaboration & teamwork · Performance & results · Respect & people | MIT Sloan "Big Nine" corporate values (Sull, Turconi & Sull, 2020), the values most often stated by large U.S. firms; agility folded into innovation, execution into performance |
| Stakeholder / ESG themes | Diversity, equity & inclusion · Environment & sustainability · Community & social impact · Employee wellbeing & development | Stakeholder theory (Freeman, 1984; Business Roundtable, 2019) and the ESG pillars that Part 2's disclosures address |
| Sector-salient | Safety | Central to Energy and Healthcare, two of the five sample sectors |

**Why a hybrid?** The Big Nine alone describe *what kind of company* a firm claims to be but say
nothing about environment or community, which is what ESG disclosures (Part 2) are about;
stakeholder categories alone capture *whom* a firm claims to serve but miss cultural identity
(innovative, ethical, results-driven). Eleven categories is few enough for consistent coding and
for a human validation check. Each category has a definition plus explicit include/exclude rules
(e.g. "sustainable growth" in a purely financial sense is *not* environment), and a category counts
as present only if the page expresses it as something the company values or commits to, not
merely if a keyword appears. Guiso, Sapienza & Zingales (2015) provide the precedent for coding
values stated on S&P 500 websites.

## LLM analysis

[src/analyze_snapshots.py](src/analyze_snapshots.py) → [output/part1_dataset.csv](output/part1_dataset.csv).
Model: Claude Haiku 5.5 (`claude-haiku-5-5`), structured JSON output enforced by a schema, fixed
prompts (`PROMPT_VERSION`), and every raw response cached in `output/llm_cache/` for
reproducibility and resumability. **Model choice was budget-driven:** the project's total API
budget is $5; the largest model would have cost roughly $14 for Part 1 alone; Haiku cost $0.33. Codebook classification with verbatim evidence is well within a small model's
ability, and the quote-verification check makes weak evidence visible. The script enforces a
hard spending cap (`MAX_COST_USD`) and logs the cost of every call.

- **(a) Changed from prior year.** Two layers. *Non-AI:* each snapshot is compared with the
  company's previous available snapshot (exact match after normalisation, plus a word-level
  similarity ratio, `similarity_to_prior`). Identical text → `change_type = none`, no LLM call,
  and the prior coding is reused (guaranteeing identical pages get identical codes). *LLM:* when
  the text differs, it is classified `cosmetic` (wording, figures, layout) or `substantive`
  (values, mission, commitments or self-description changed), with a one-sentence summary. The
  similarity score alone cannot tell a reworded sentence from a new value, which is why the LLM
  layer is used.
- **(b) Theme categories.** The LLM codes each page against the codebook: presence, salience
  (1 = mentioned, 2 = emphasised) and one **verbatim evidence quote** per category. Code then
  verifies every quote against the page text (`n_quotes_unverified`), so fabricated evidence is
  counted rather than hidden.
- **(c) Linguistic shifts.** One LLM call per company reads all its snapshots in chronological
  order and writes a per-year note on shifts in vocabulary, framing and tone (`analyst_notes`),
  plus a company-level summary ([output/company_shift_summaries.csv](output/company_shift_summaries.csv)).
- **Selection check.** The same call records whether each page reads like a general About page
  (`about_page_check`). This documents the known selection issues (e.g. Meta, JPMorgan) without
  changing the rule-based selection.

## Coverage gaps and known selection issues

**Coverage funnel (450 company-years):**

| Step | Remaining | Lost | Reason |
|---|---|---|---|
| Page selection | 424 | 26 | No candidate page archived that year (table below) |
| Download | 423 | 1 | IBM 2016: listed in the archive's index, but the archive returns "not found" for the capture on every attempt |
| Quality check (rule F) | **402** | 21 | Under 50 words of text after cleaning: Broadcom 2020–24 (2 words each), Intel 2019 & 2021 (0), Lilly 2021–23 (7), ExxonMobil 2016–18 (45), Nike 2023–24, Meta 2016 & 2023, NVIDIA 2016, JPMorgan 2020, Target 2023, TJX 2018. Almost all are **JavaScript-rendered pages**: the archive stored an empty HTML shell whose content only appears when a browser runs the site's code |

Every row of [output/part1_dataset.csv](output/part1_dataset.csv) carries `status` and
`status_reason`, so each gap is documented at the company-year level.

**Missing at selection (26).** In every case the reason is the same: *no candidate page for
that company had a usable archived capture in that year* (`note` column in
[output/selected_pages.csv](output/selected_pages.csv)). Per rule E, no year was filled from an
adjacent year.

| Company | Missing years | Likely cause |
|---|---|---|
| Citigroup (C) | 2016–2022 | Archived 2016 homepage exposed 0 links and 2020 only 8 (JavaScript-rendered navigation), so discovery found only the 2023+ About page |
| American Express (AXP) | 2021–2024 | The only About-type candidate with captures was archived 2016–2020; no successor page was found by discovery or the standard addresses |
| EOG Resources (EOG) | 2016–2018 | Only the standard-address fallback `/company` was found, and it was not archived before 2019 |
| IBM | 2017–2019 | Only the standard-address fallback `/about` was found; not archived in those years |
| Broadcom (AVGO) | 2017–2018 | Primary page not archived in those years; no alternative captured |
| Apple, BofA, Goldman Sachs, ExxonMobil, Oracle, Lilly, Halliburton | 1 year each (2019, 2022, 2020, 2022, 2024, 2024, 2024) | Single-year gaps in the archive's captures |

**Known selection issues (pages present but not ideal).** These follow mechanically from the
rules and were left uncorrected to keep selection fully rule-based:

- **JPMorgan Chase (2016–2023):** two tier-1 candidates tied on coverage (8 years each); the
  shortest-URL tie-break chose the About page of the *JPMorgan Chase Institute* (the firm's
  research arm), not the corporate "About Us" page. 2024 uses the corporate `/about` page.
- **Meta (all years):** the 2016 Facebook homepage's "About" footer link pointed to
  `facebook.com/facebook`, Facebook's own social-media profile, which has 9 years of captures
  and so outranks `about.meta.com` (2022–2024 only). Its content is a profile/login page: the
  quality check rejected 2016 and 2023, and the remaining years state no values, so Meta has no
  authenticity score in Part 3.
- **Intel (all years) and Berkshire Hathaway (all years):** no About-type candidate was found,
  so the homepage is used (tier 4, rule B.3). For Berkshire this matches reality (its website
  has no About page). For Intel it is a limitation: an About page exists, but the archived
  homepage's navigation is JavaScript-rendered and invisible to discovery.
- **Apple, IBM, Tesla, EOG:** selected via the standard-address fallback (tier 3); these pages
  were not linked from the sampled homepages, so their content has not been confirmed to be a
  general About page.

## Data collection notes

- **Rate limiting.** A first run querying the CDX API every ~1.5 s was blocked by the Internet
  Archive (connection refused) after ~20 requests. The probe script now waits 4 s between
  requests, backs off 30 s – 5 min on refusals, logs persistent failures instead of crashing,
  and resumes from where it stopped. These choices are what make the pipeline scale to the full
  S&P 500 (slower, but unattended and restartable).
- **Archive refusals.** The Wayback Machine returned HTTP 403 (refused) for 5 of the 180
  homepage snapshots used in discovery: Nike 2020, Lowe's corporate site 2016 and 2020, Chevron
  2024, Valero 2016 ([output/discovery_fetch_log.csv](output/discovery_fetch_log.csv)). A 403 from
  the archive usually reflects an exclusion requested by the site owner. Discovery for these
  companies relied on their other sample years. Failed fetches are cached so re-runs skip them.

## Dataset schema — [output/part1_dataset.csv](output/part1_dataset.csv)

One row per company-year (450 rows; analysis fields are blank where `status` is not `ok`).

| Column | Meaning |
|---|---|
| `ticker`, `company_name`, `sector`, `year` | Identifiers (required) |
| `page_text_clean` | Extracted visible body text (required) |
| `changed_from_prior` | `True` if the text differs from the previous available snapshot, `False` if identical, blank for the first snapshot (required) |
| `theme_categories` | Semicolon-separated codebook categories present; `none` if the page was analysed and states no value (required) |
| `analyst_notes` | LLM note on linguistic shifts versus the prior snapshot (required) |
| `status`, `status_reason` | `ok`, `missing`, `too_short`, `fetch_failed`, with the reason |
| `selected_url`, `tier` | Page used and its selection tier (1 = homepage "About" link … 4 = homepage) |
| `capture_timestamp`, `archive_url` | Exact Wayback capture used (re-openable) |
| `word_count` | Words of cleaned text |
| `prior_year_compared`, `similarity_to_prior` | Year compared with, and word-level similarity (0–1, non-AI) |
| `change_type`, `change_summary` | `none` / `cosmetic` / `substantive`, and a one-sentence description |
| `about_page_check`, `about_page_note` | LLM judgement of whether the page reads like a general About page (documents selection issues; not used to filter) |
| `theme_evidence` | JSON: category → verbatim evidence quote |
| `n_quotes_unverified` | Evidence quotes not found verbatim in the page text |
| `theme_<category>` (11 columns) | Salience per category: 0 absent, 1 mentioned, 2 emphasised |

## Findings in brief

See [summary.md](summary.md). In short: About pages change often (about half of year-on-year
changes are substantive), and the mix of stated values shifted toward integrity, respect,
diversity and safety, while the sharp post-2021 retreat seen in formal disclosures (Part 2) does
**not** appear on About pages.

## Assumptions

- `data/homepages.csv` lists each company's main corporate web address (for retailers and some
  others, the corporate site, e.g. `corporate.target.com`, since the shopping site is not where the
  company describes itself). Every entry was verified by hand as the company's official site
  on 2026-10-19.
- **Use of AI.** Code was written with AI coding assistance (Claude). Candidate pages are
  **not** AI-generated: an early draft list of candidate URLs written by the AI assistant was
  discarded and is not used anywhere in the pipeline. All candidates now come from the
  rule-based sources in C, and the final choice follows the written rules. (An LLM *is* used
  later, by design, for the content analysis the assignment asks for.)

## What I would do differently with more time

- **Render JavaScript during discovery** (e.g. a headless browser) so sites like Citigroup and
  Intel expose their navigation links.
- **Manually audit all 50 selections** against the archived pages and record corrections with
  reasons (the tooling exists: `make_review_page.py` and `data/manual_overrides.csv`).
- **Use a content-based tie-break** (e.g. prefer the candidate whose text best matches the
  company's name and self-description) instead of shortest URL, which would have avoided the
  JPMorgan Chase Institute pick.
- **Render archived pages in a headless browser before extraction**, recovering the 21
  JavaScript-rendered snapshots lost at the quality check.
- **Validate the LLM coding against human labels** on a stratified sample (e.g. 20–30 pages across
  sectors and years) and report agreement per category; and re-code a sample with a larger model
  to measure model sensitivity.
- **Manually spot-check text extraction** on a random sample of snapshots against the rendered
  archived page.
- **Archive-timing robustness:** use several captures per year (e.g. January and July) to check
  that the first capture of a year is representative.

## Known limitations

- **About pages may under-represent values language** relative to dedicated values pages (see B).
- **Candidate generation is not exhaustive.** Discovery only sees links present in the archived
  HTML (JavaScript-built menus are invisible), and the common-path list covers only standard
  conventions; an About page at an unusual address on a JavaScript-heavy site could be missed.
- **Selection is imperfect for a few companies** (Meta's social-media profile, JPMorgan's research
  institute, Intel's homepage); see *Known selection issues*. The LLM's `about_page_check` flags
  some snapshots as not reading like a general About page; Part 3 tests whether these bias the
  results.
- **LLM coding is unvalidated against humans.** Theme presence is a judgement; quotes are verified
  but whether a quote really expresses a *value* is not. A small model (Claude Haiku 5.5) was used
  for budget reasons.
- **Missingness is not random.** JavaScript-heavy sites lose snapshots at the quality check, so
  coverage is lower for modern, script-built sites.
- **"Changed from prior" depends on extraction.** A redesign can change what the extractor keeps
  even if the company's wording did not change; `change_type` (cosmetic vs substantive) mitigates
  but does not eliminate this.
