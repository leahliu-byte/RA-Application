# Part 2 — Lived Values: Proxy Statement Analysis

> **Status:** in progress. Document collection is complete; text mining is next. Sections marked
> _TODO_ will be completed as the analysis is built.

## Document type: annual proxy statements (SEC form DEF 14A)

The assignment allows one of: ESG report, sustainability report, DEI report, or proxy statement.
I chose the **proxy statement**:

1. **Complete coverage by law.** Every U.S.-listed company must file a definitive proxy before its
   annual meeting, so all 50 companies × 9 years exist. ESG/sustainability reports are voluntary,
   many companies did not publish them in 2016–2018, and DEI reports mostly began in 2020–2021;
   either would build large, non-random gaps into the panel (the companies that started reporting
   early are systematically different).
2. **One official, machine-readable source.** SEC EDGAR is free and versioned; collection is fully
   rule-based and runs unchanged for all 500 S&P companies, matching the brief's "designed to
   scale". ESG reports would have to be found by hand on company websites.
3. **A behavioural signal, not just talk.** Proxies disclose what executives are **paid** to
   achieve (incentive metrics such as safety, emissions or diversity targets), board composition
   and oversight of ESG topics, and shareholder proposals the board opposes or supports. That is
   closer to "what the company actually prioritises" than a promotional sustainability report.
4. **Comparable across companies.** The SEC prescribes the content, so differences between firms
   reflect choices rather than document format.

**Trade-off:** proxies are governance documents, so environmental and community topics get less
space than in a sustainability report; their emphasis is board, pay and shareholder matters. This
is noted under Limitations and is taken into account when comparing with Part 1 in Part 3.

## Collection procedure

[src/collect_proxies.py](src/collect_proxies.py) → [output/proxy_manifest.csv](output/proxy_manifest.csv).
All rules are applied by code; no AI is involved.

1. **Company identity.** Each ticker is mapped to its SEC Central Index Key (CIK) using the SEC's
   own `company_tickers.json` (BRK.B appears there as BRK-B).
2. **Predecessor entities.** Three companies reorganised under a new legal entity during or after
   the window, so the current CIK has no filings for earlier years. Their predecessor CIKs
   ([data/predecessor_ciks.csv](data/predecessor_ciks.csv)) were found with EDGAR's company search
   and verified by the former names EDGAR records for each entity:
   ExxonMobil (Exxon Mobil Corp → ExxonMobil Holdings Corp, 2026), BlackRock (BlackRock, Inc. →
   new holding company in 2024; old entity renamed BlackRock Finance, Inc.), Broadcom (Broadcom
   Limited, Singapore → Broadcom Inc., 2018).
3. **Form types.** `DEF 14A` (definitive proxy) and `DEFC14A` (definitive proxy in a contested
   election). The latter is the company's annual proxy in a proxy-fight year: McDonald's 2022
   (Carl Icahn), ExxonMobil 2021 (Engine No. 1) and Starbucks 2024. Excluded: `DEFA14A`
   (supplementary soliciting material), `DEFM14A` (merger proxies), `PRE 14A`/`PREC14A`
   (preliminary drafts) and `DFAN14A` (filed by dissident shareholders, not the company).
4. **Proxy year.** The calendar year of the filing date, except that **December filings count
   toward the next year**, because they solicit votes for the next year's annual meeting (Apple
   filed its 2018 proxy on 27 December 2017). Note that a proxy filed in spring of year *t*
   largely describes fiscal year *t−1*; Microsoft, with a June fiscal year end, files in October.
5. **One proxy per year.** If a year has several (special meetings for mergers or pay awards),
   the one whose cover pages announce an **annual meeting** is kept, with document size as the
   tie-break. Nine company-years had multiple candidates. A first version that used size alone
   picked Tesla's February 2018 special-meeting proxy (on Elon Musk's pay award); the
   annual-meeting rule correctly selects Tesla's April 2018 annual proxy and changes no other pick.
6. **Text extraction.** The primary document's HTML is converted to text with scripts, styles
   and the hidden inline-XBRL header removed. Table text is kept, because proxies put much of their
   substance (pay metrics, board skills matrices) in tables.

The SEC's fair-access policy requires automated clients to identify themselves with a contact
email and stay under 10 requests per second; the email is read from `.env` (not committed) and
requests are spaced 0.15 s apart.

## Coverage

**450 of 450 company-years (100%).** Median length 50,000 words (range ≈10,000 for Berkshire
Hathaway to ≈257,000). Raw HTML and extracted text are kept in `data/raw/proxies/`
(git-ignored because of size; fully re-creatable by re-running the script).

## Text mining

_TODO_

## Assumptions

- The annual proxy is treated as the company's most authoritative yearly statement of governance
  and pay priorities.
- Code was written with AI coding assistance (Claude); document selection is entirely rule-based.

## What I would do differently with more time

_TODO_

## Known limitations

- **Governance focus.** Proxies under-represent environmental and community topics relative to
  sustainability reports (see trade-off above).
- **Boilerplate.** Large parts of every proxy are legally required, near-identical text (cover
  page, voting procedures), which dampens year-to-year change measures; the analysis must
  normalise for this.

_TODO: more as the analysis is built._
