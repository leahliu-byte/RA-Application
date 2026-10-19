# Part 2 — Lived Values: Proxy Statement Analysis

> **Non-technical summary:** [summary.md](summary.md)

**Pipeline:** [src/collect_proxies.py](src/collect_proxies.py) (collect, 450/450) →
[src/mine_proxies.py](src/mine_proxies.py) (classical text mining) →
[src/extract_pay_links.py](src/extract_pay_links.py) (LLM reading of the executive-pay section).
Run them in that order from the repo root; the last needs `ANTHROPIC_API_KEY` and reuses
its cache on re-runs.

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

## Text mining: methods and why

**Classical methods for the whole corpus; an LLM only where reading comprehension is essential.**
Proxies are long (median ~50,000 words; 23.7 million words in total). Sending them all to an LLM
would be slow and impractical at the scale of 500 firms, and dictionary measures are transparent,
reproducible and standard in accounting and finance text analysis. The one question a dictionary
cannot answer, whether a value is actually *tied to pay* rather than merely mentioned near pay, is
given to an LLM, on the pay section only.

1. **Theme emphasis (dictionaries).** The 11 codebook categories from Part 1
   ([../data/codebook.json](../data/codebook.json)) are operationalised as keyword dictionaries
   ([../data/theme_dictionaries.json](../data/theme_dictionaries.json)), drafted from each category's
   definition and include-list. Because proxies are legal documents, phrases whose dominant meaning
   there is legal or financial are deleted before counting: "equity" (stock) except in "racial/pay
   equity", "with respect to", "safe harbor", "shareholder engagement", "performance share/period".
   Emphasis = matches per 10,000 words, computed for the whole proxy and separately for the
   **Compensation Discussion & Analysis (CD&A)**, the section explaining what executives are paid
   for. Using the *same* categories as Part 1 is what makes the Part 3 comparison possible.
2. **Specificity.** Among sentences mentioning a category, the share containing a quantified
   commitment (a percentage, or a target year such as "by 2030"). Concrete targets are costlier
   to state than aspirations.
3. **Language change.** TF-IDF cosine similarity with the company's previous proxy. TF-IDF
   down-weights words shared by all proxies, so legal boilerplate influences it less than raw
   overlap would.
4. **Cross-company and cross-sector variation.** Sector-by-year means, and a variance
   decomposition: the share of each category's variation explained by sector, by company, and by
   year (eta-squared).
5. **External events** ([../data/external_events.csv](../data/external_events.csv)): 11 dated
   events, each with the categories it should move, the expected direction, and the first proxy
   year it could affect (spring proxies largely describe the previous year, so mid-year events
   appear a year later). Test: within each company, mean emphasis in the two proxy years from the
   first affected year minus the two years before (one year after for the 2024 split, where the
   panel ends); a paired t-test across companies; and, crucially, the same pre/post change computed
   at every *other* possible split year (placebo windows). An event "effect" is only credible if it
   exceeds the placebo average, because most ESG language rose steadily all decade.
6. **Values tied to executive pay (LLM).** Claude Haiku 5.5 reads each CD&A (median 12,000 words)
   and lists every codebook category linked to pay, as a `quantitative_metric` (weighted or
   formulaic goal) or `qualitative_factor` (discretionary assessment), with the stated weight and
   a quote. Quotes are verified by code: a quote counts as supported if at least 80% of its
   three-word phrases appear in the CD&A (tolerant of table spacing, but a paraphrase scores low).
   A first prompt let the model stitch table cells with "..."; requiring one contiguous passage
   raised verification from 44% to 93%.

**CD&A detection.** The heading also appears in the table of contents, so the section is taken as
the longest span from a "Compensation Discussion and Analysis" heading to the next "Summary
Compensation Table". It was found in 424 of 450 proxies. Not found: Berkshire Hathaway (all
years; its proxy has no standard CD&A), Meta 2016–2020 and Target 2017–2018 and 2022–2024
(non-standard headings), Wells Fargo 2016–2018, Marathon Petroleum 2021–2022, Microsoft 2018, Nike
2022. For these, CD&A-based columns are blank.

**Validity checks on the pay extraction.** (a) 92.7% of 1,691 evidence quotes are supported by
the text. (b) Companies coded as having *no* formulaic financial metric are the ones known for
discretionary pay: Amazon (whose proxy states that performance goals "would undermine our focus
on innovation"), ExxonMobil (board judgement without formulas), the large banks (holistic
assessments) and Alphabet/Oracle/Broadcom (mostly time-vested stock). The extraction distinguishes
formula-driven from discretionary plans rather than assuming every plan has metrics.

## Dataset schema

### [output/proxy_dataset.csv](output/proxy_dataset.csv): **the main Part 2 dataset**, one row per company-year (450 rows, 79 columns)

Built by `mine_proxies.py`; the 11 `pay_` columns are merged in by `extract_pay_links.py`, so run
the scripts in pipeline order.

| Column | Meaning | Why included |
|---|---|---|
| `ticker`, `company_name`, `sector`, `year` | Identifiers; `year` is the proxy year (see collection rule 4) | Join key with Parts 1 and 3 |
| `form`, `filing_date`, `accession`, `url` | SEC form (`DEF 14A`/`DEFC14A`), filing date, SEC accession number, document URL | Provenance: every row can be re-opened at the source |
| `n_words` | Words in the proxy after removing excluded phrases | Denominator for rates; length itself is a disclosure choice |
| `cda_found`, `n_words_cda` | Whether the CD&A section was detected, and its length | Documents where pay-section measures are missing |
| `rate_<category>` (11) | Dictionary matches per 10,000 words, whole proxy | Main measure of how much a value is discussed |
| `cda_rate_<category>` (11) | Same, inside the CD&A only | Emphasis where pay is justified: closer to lived priorities |
| `spec_<category>` (11) | Share of the category's sentences with a quantified commitment | Concrete versus aspirational language |
| `nsent_<category>` (11) | Number of sentences mentioning the category | Reliability weight for `spec_` (small counts are noisy) |
| `rate_esg_general` | Matches for the generic ESG label ("ESG", "environmental, social…") | Separates use of the *label* from substance (greenhushing) |
| `tfidf_similarity_to_prior` | TF-IDF cosine similarity with the previous proxy (1 = same wording) | Within-company language change |
| `yoy_change_<category>` (11) | Change in `rate_` from the previous year | Within-company change in emphasis |
| `pay_<category>` (11) | Tied to executive pay: 2 = weighted metric, 1 = qualitative factor, 0 = not linked; blank where no CD&A was found | The strongest "lived" signal: values with money behind them (LLM reading of the CD&A; evidence in `pay_links.csv`) |

### [output/pay_links.csv](output/pay_links.csv): one row per company-year × pay-linked category

`ticker`, `year`, `sector`; `category`; `mechanism` (`quantitative_metric` or
`qualitative_factor`); `weight_percent` (stated weight, −1 if none stated); `evidence` (quote);
`quote_support` (share of the quote's 3-word phrases found in the CD&A); `quote_verified`
(`quote_support` ≥ 0.8). Kept in long form so every coded link can be audited against its quote.

### [output/pay_links_wide.csv](output/pay_links_wide.csv): one row per company-year

The same `pay_<category>` columns as in the main dataset, with `cda_found`, kept as a standalone
file because Part 3 reads it directly.

### Aggregate outputs

- [output/sector_year_means.csv](output/sector_year_means.csv): mean `rate_` by sector and year.
- [output/variance_decomposition.csv](output/variance_decomposition.csv): per category, mean,
  standard deviation, and R² explained by sector, company and year.
- [output/event_tests.csv](output/event_tests.csv): per event × category: pre and post means,
  change and % change, share of companies moving in the expected direction, t and p, placebo mean
  and maximum change, and the excess over placebo.
- [output/proxy_manifest.csv](output/proxy_manifest.csv): collection record (see above).
- Figures: [output/figures/](output/figures/).

## Findings in brief

See [summary.md](summary.md). ESG and people-related language roughly tripled in proxies between
2016 and 2022; company identity explains far more of the variation than sector; the clearest
event effects beyond trend are George Floyd → diversity (+48%), the Business Roundtable statement
→ community and employees, COVID-19 → employee wellbeing and safety, and ChatGPT → innovation;
after 2022, diversity language and diversity pay metrics retreat, and the generic "ESG" label falls
while environmental substance does not.

## Assumptions

- The annual proxy is treated as the company's most authoritative yearly statement of governance
  and pay priorities.
- Dictionary matches measure *attention*, not sentiment or quality: a firm discussing a diversity
  lawsuit and one announcing a diversity target both score.

## What I would do differently with more time

- **Section-aware analysis throughout:** split every proxy into its standard sections (board,
  pay, shareholder proposals) and measure each separately, rather than the whole document plus
  CD&A only.
- **Shareholder proposals as a second behavioural signal:** extract ESG proposals and the board's
  recommendation (support/oppose), a direct revealed-preference measure.
- **Validate the dictionaries** against human-coded sentences, and extend them with embedding-based
  nearest-neighbour terms to improve recall.
- **Stronger event designs:** a difference-in-differences using companies or sectors the event
  should not affect (e.g. Nasdaq- vs NYSE-listed firms for the Nasdaq board-diversity rule).
- **Add a sustainability-report corpus** for 2019–2024 (when coverage is good) to test whether the
  proxy's governance focus understates environmental commitments.

## Known limitations

- **Governance focus.** Proxies under-represent environmental and community topics relative to
  sustainability reports (see trade-off above).
- **Boilerplate.** Large parts of every proxy are legally required, near-identical text (cover
  page, voting procedures), which dampens year-to-year change measures. Rates per 10,000 words
  and TF-IDF weighting mitigate but do not remove this.
- **Dictionary error.** Keyword matching misses paraphrases and can count off-topic uses; the
  exclusion list removes the largest known false positives, but precision and recall were not
  measured against human coding.
- **Event tests are descriptive, not causal.** Events cluster in 2020–2021 (COVID-19, George
  Floyd, the SEC human-capital rule all first affect 2021 proxies), so their effects cannot be
  separated; the placebo comparison guards against mistaking trend for effect, not against
  simultaneous events.
- **LLM pay coding.** A small model was used; the quantitative/qualitative
  boundary is a judgement, and some evidence quotes are only a scorecard label.
- **Disclosure, not behaviour.** A pay metric shows what the board says it rewards; whether
  targets were hard or payouts actually depended on them is not measured.
