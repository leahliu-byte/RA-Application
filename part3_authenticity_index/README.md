# Part 3 — Measure Construction: Organizational Authenticity Index (OAI)

> **Non-technical summary:** [summary.md](summary.md) · **Code:** [src/build_index.py](src/build_index.py)
> · **Full statistical output:** [output/validity_checks.txt](output/validity_checks.txt)

## What I did

I built an index of how closely the values a company **says** it holds (its About page, Part 1)
match the values its **formal disclosures and incentives** suggest it prioritises (its proxy
statement and executive pay, Part 2), for each company and year. It is computed for **357
company-years across 47 companies**, varies both between companies and within companies over time,
and is accompanied by a decomposition into two distinct failure modes (over-claiming and
under-claiming), five validity checks (one of them inconclusive in an informative way) and
robustness tests. The script runs in seconds from the Part 1 and Part 2 outputs.

## Defining "alignment": reasoning

**Theory.** Organisational research distinguishes the values an organisation *espouses* from those
it *enacts* (Schein's model of organisational culture). Institutional theory calls the gap between
symbolic statements and actual practice **decoupling** (Meyer & Rowan, 1977); Bromley & Powell
(2012) separate *policy–practice* decoupling (saying without doing) from *means–ends* decoupling.
Authenticity is the absence of decoupling. A measure therefore needs (i) a record of what is
espoused, (ii) independent evidence of what is enacted, and (iii) a rule for comparing them.

**What is observable here.** (i) Espoused: About-page value salience per category (Part 1, 0/1/2).
(ii) Enacted evidence of two kinds, both from Part 2: what the company emphasises when reporting
formally to shareholders (proxy language), and what it **puts money behind** (values tied to
executive pay). Money is costly in a way words are not, so pay links are the stronger signal of
priority; proxy emphasis is weaker but available for every value.

**Choices made, and alternatives rejected.**

| Choice | Alternative considered | Why this one |
|---|---|---|
| Compare the **pattern across values**, not single values | One value at a time (e.g. "says safety → pays for safety") | A company's identity is a *profile*; single-value checks would give 11 noisy measures |
| Proxy emphasis **relative to peers in the same year** (z-score within category-year) | Raw mentions per 10k words | Every proxy discusses performance and all ESG language rose over the decade; without this, alignment would just track base rates and the calendar |
| Pay backing **relative to the base rate** for each value | Raw share of stated values that are pay-linked | Some values (respect) are almost never pay-linked anywhere; penalising a firm for that would measure the value's measurability, not the firm's authenticity |
| **Two components, equally weighted** | One component only | They capture different facets (correlation 0.10); equal weights are the transparent default with no external criterion to fit weights to |
| Directional **decomposition** reported alongside | A single number only | A firm can be inauthentic in two opposite ways (claiming without backing; doing without claiming); a single score hides which |
| **Outcomes** (complaints, violations) kept *out* of the index | Building them in | Using outcomes to validate a measure that already contains them would be circular; they are the natural external validation (see *What I would do differently*) |

## The measure

For company *i* in year *t* (About page snapshot of year *t*; proxy filed in year *t*):

- **A. Discourse consistency** = Spearman rank correlation, across the 11 codebook categories,
  between About-page salience and proxy emphasis z-scored within category and year. Range −1 to
  +1; +1 means the proxy emphasises, relative to peers, exactly the values the web page
  emphasises.
- **B. Incentive backing** = mean, over the categories the About page states, of
  *(pay link − share of companies with that link that year)*, where the pay link is 1 for a
  weighted metric, 0.5 for a qualitative factor, 0 for none. Positive means more money behind
  stated values than is typical for those values.
- **OAI** = mean of the z-standardised A and B, re-standardised (`OAI_z`; mean 0, SD 1) and also
  shown as a percentile (`OAI_pct`). If one component is unavailable (no CD&A section, 11 cases),
  the other is used and `n_components` records it.
- **Over-claiming** = share of stated values with *no* lived evidence: below-peer proxy emphasis
  *and* no pay link ("cheap talk").
- **Under-claiming** = share of visibly prioritised values (proxy emphasis z > 1, or a weighted pay
  metric used by fewer than half of companies) that the About page does *not* state ("quiet
  virtue", or greenhushing).

**Coverage.** 357 of the 402 usable company-years from Part 1. The index is undefined when the
About page states no value at all (component A needs variation; B needs stated values). That is
the case for every year of **Apple, Meta and Berkshire Hathaway**: for Berkshire this reflects its
famously minimal website; for Apple and Meta it reflects the page-selection limits documented in
Part 1. Conceptually, a company that states nothing has nothing to be authentic *about*; the index
measures alignment of claims, so it is silent where there are no claims.

## Distributional properties

| | n | mean | SD | min | median | max | skew |
|---|---|---|---|---|---|---|---|
| A. Discourse consistency | 357 | 0.18 | 0.31 | −0.74 | 0.20 | 0.84 | −0.27 |
| B. Incentive backing | 346 | 0.03 | 0.20 | −0.42 | 0.00 | 0.70 | 0.33 |
| **OAI (z)** | 357 | 0.00 | 1.00 | −2.78 | 0.01 | 2.93 | −0.03 |
| Over-claiming | 357 | 0.39 | 0.31 | 0 | 0.40 | 1 | 0.32 |
| Under-claiming | 325 | 0.55 | 0.43 | 0 | 0.60 | 1 | −0.21 |

- **Varies across companies and over time, as required:** 46% of the variance is between
  companies and 54% within companies across years.
- **Sector differences are significant** (ANOVA F = 7.0, p < 0.001): Energy +0.24, Healthcare
  +0.20, Financials +0.08, Technology +0.01, Consumer Discretionary −0.47.
- **Trend:** lowest in 2017 (−0.37), rising to +0.15–0.21 from 2021. Over-claiming falls from about
  0.45–0.52 (2016–2017) to 0.28–0.33 (2023–2024): stated values became more often backed.
- **Positive A on average** (mean 0.18): About pages and proxies do tend to emphasise the same
  values, but weakly.
- **Which values are most often cheap talk** ([output/category_contributions.csv](output/category_contributions.csv)):
  respect & people (68% of the times it is stated), community & social impact (55%), employee
  wellbeing (47%), versus performance & results (9%) and safety (31%).

## Validity checks

| Check | Expectation | Result | Verdict |
|---|---|---|---|
| **Convergent:** when *safety* is stated, is it pay-linked? | More in Energy, where safety is operationally material | Energy 69% (n = 42) vs other sectors 13% (n = 31) | ✅ |
| **Component structure** | A and B capture different facets | ρ = 0.10 | ✅ |
| **Discriminant:** not an artefact of page length | Near-zero association | ρ = 0.12 with word count; ρ = 0.21 with number of stated values | 🟡 Small, but stating more values raises the score slightly |
| **Face validity:** extremes | Recognisable | Highest: Eli Lilly, Phillips 66, IBM, Bristol-Myers Squibb, Marathon Petroleum. Lowest: Target, TJX, UnitedHealth, Broadcom, EOG | 🟡 Plausible (pharma and refiners with explicit safety/patient metrics high; retailers with broad community claims and few non-financial metrics low), but not a strict test |
| **Known group:** Wells Fargo should score low in the first years after its fake-accounts scandal became public (Sept 2016), i.e. 2017–2018 | Below other banks | −0.27 vs −0.13 for other banks (component A 0.11 vs 0.21), but n = 2 years. In **2016, before disclosure, while the misconduct was ongoing**, Wells Fargo scored **+1.41**, the highest bank | 🟡 **Inconclusive**, and revealing |

**What the Wells Fargo case teaches.** A first version of this check pooled 2016–2018 and found
Wells Fargo *above* other banks. That was a timing error on my part: the 2016 About page and
spring-2016 proxy were written before the scandal became public, so the correct test window is
2017–2018. With it, Wells Fargo scores slightly below its peers, in the expected direction but on
only two observations (its pay section was not detected in 2016–2018, so those scores rest on
component A alone). The more important result is 2016: while the sales-practices misconduct was
under way, but before anyone outside knew, the index rated Wells Fargo the **most aligned bank in
the sample**. Its web page then featured "Vision and Values" built on customers and integrity, and
its proxy echoed them. The index correctly saw that the firm's **statements were consistent with
each other**; it cannot see **conduct** that contradicts them. In the scandal years, the bank's
proxies mentioned integrity at 2.5 times the rate of other banks (22 vs 9 per 10,000 words in
2017) and its over-claiming score was very low (0.12 vs 0.39), consistent with crisis-driven
messaging. Conduct and risk factors entered its executive-pay assessment only later (2020–2021).
Two conclusions follow. First, the OAI measures *symbolic* alignment, consistency among a firm's
own communications and incentive design, not behavioural integrity. Second, a crisis can push
measured alignment *up*, because firms respond to scandals by saying the right things everywhere
at once. Both are threats to validity below.

## Robustness

- **Component weighting:** company-year rankings from A alone and B alone correlate 0.74 and 0.73
  with the combined index.
- **No single value drives component A:** dropping any one of the 11 categories leaves A almost
  unchanged (minimum ρ = 0.92, mean 0.95).
- **Page-selection problems:** the 109 company-years whose page came from a fallback tier or was
  judged not to be a general About page score lower on average (−0.18 vs +0.08, p = 0.03), so they
  add some downward bias. Company rankings using only clean pages correlate 0.85 with rankings using
  all pages, so conclusions about which companies are high or low are largely unaffected.

## Output schema

**[output/authenticity_index.csv](output/authenticity_index.csv)**: one row per company-year with
any data.

| Column | Meaning |
|---|---|
| `ticker`, `company_name`, `sector`, `year` | Identifiers |
| `OAI_z`, `OAI_pct` | Index as z-score and as 0–100 percentile (blank if undefined) |
| `A_discourse_consistency`, `B_incentive_backing` | The two components (raw scale) |
| `n_components` | Components available (2, or 1 when no CD&A section) |
| `over_claiming`, `under_claiming` | Directional decoupling shares (0–1) |
| `n_stated_values` | Values stated on the About page that year |
| `cda_found` | Whether the proxy's pay section was found |
| `tier`, `about_page_check`, `word_count` | Page-quality fields carried from Part 1, for robustness |

**[output/company_summary.csv](output/company_summary.csv)**: per company: years, mean and SD
of OAI, mean components, mean over/under-claiming, and the OAI trend per year (OLS slope; blank
with fewer than 3 years). **[output/category_contributions.csv](output/category_contributions.csv)**:
per value: how often stated, how often stated but unbacked, how often stated and pay-linked.
**[output/figures/](output/figures/)**: charts used in the summary.

## Limitations and threats to validity

1. **It measures consistency of claims, not conduct** (the Wells Fargo 2016 result). A firm that
   says the same things everywhere, and even designs pay around them, can still behave otherwise,
   and concealed misconduct is invisible to it. The index is a measure of *symbolic* authenticity.
2. **Crisis responses can inflate it.** Firms under scrutiny align their messages and add
   accountability metrics; a high score can mean a firm has something to prove rather than nothing
   to hide.
3. **Measurement error is inherited from both sides.** About-page coding is an LLM judgement (quotes
   verified, judgements not human-validated); proxy emphasis comes from keyword dictionaries; pay
   links from LLM reading of the pay section. Errors in any layer attenuate alignment toward zero.
4. **Not every value can be pay-linked equally.** The base-rate adjustment helps, but values like
   respect or collaboration have almost no pay evidence anywhere, so for firms that state mainly
   those values, component B is close to uninformative.
5. **Selection and missingness.** 357 of 450 company-years; three companies are excluded entirely
   and pages with selection issues score somewhat lower (see Robustness).
6. **Timing.** The About page snapshot (early year *t*) and the proxy (spring of year *t*, describing
   year *t−1*) are close but not simultaneous; a year-lag specification is a natural sensitivity
   test.
7. **Equal weighting is a choice.** With no external criterion it is the most transparent option,
   but other weights would reorder some firms (A-only and B-only rankings correlate about 0.73–0.74
   with the combined one).

## What I would do differently with more time

- **Add a third, resource-based component and external validation ("C+").** Financial data from
  SEC filings can show whether claims become spending (R&D intensity for innovation claims;
  headcount through downturns for "people first"; CEO-to-worker pay ratio for respect), and outcome
  data (CFPB complaints for banks, OSHA and EPA enforcement, recalls) can validate the index against
  behaviour, which is exactly what the Wells Fargo case shows it lacks. Validation should also use
  a larger set of scandal events than one bank.
- **Employee perception.** The most direct evidence of enacted values is employees' experience
  (e.g. culture ratings from employee reviews, as in the MIT Sloan Culture 500); access constraints
  ruled it out here.
- **Lagged and event-based specifications:** test whether stated values *precede* enacted evidence
  (commitments followed through) or *follow* it (claims catching up with practice).
- **Human validation** of the About-page coding on a stratified sample, propagated into
  uncertainty intervals for the index.
