# Part 4 — Proposal: Does a Crisis Reveal Whether Corporate Values Are Authentic?

> **Non-technical summary:** [summary.md](summary.md) · **Code:** [src/get_revenue.py](src/get_revenue.py),
> [src/crisis_tests.py](src/crisis_tests.py) · **Full output:** [output/results.txt](output/results.txt)

## What I did

I tested whether crises separate genuine values from cheap talk, using COVID-19 and the 2022–24
DEI backlash as natural tests: did companies that publicly claimed a value before each crisis back
it differently afterwards than companies that did not? I combined the Part 1–3 data with audited
2019–2020 revenue from SEC filings (to find companies for which keeping a "people first" claim was
genuinely costly), compared claimers with non-claimers using permutation tests, and examined the
Wells Fargo case in detail.

## Motivation

Part 3's most revealing result was a failure of intuition: in 2016, while Wells Fargo's
fake-accounts misconduct was under way but not yet public, the authenticity index rated it the
*most* aligned bank, and in the scandal years that followed its proxies mentioned integrity at
two to three times the rate of other banks. That raises a broader question. Folk wisdom says
"you see a company's true values in a crisis", because values that cost nothing in good times
must be paid for in bad ones. If that is right, crises are the natural validation test for any
authenticity measure. If it is wrong, and crises instead prompt everyone to say the right things,
then crisis periods are exactly when stated values are *least* informative.

## Hypotheses

- **H1, "crises reveal":** pressure separates held values from cheap talk. Firms that publicly
  claimed a value before a crisis keep or increase their backing of it when it becomes costly;
  firms that did not, do not. *Prediction:* claimers and non-claimers diverge after the crisis.
- **H2, "crises perform":** crises trigger symbolic, industry-wide responses. Firms imitate one
  another under uncertainty (institutional isomorphism; DiMaggio & Powell, 1983), so claimers and
  non-claimers move together and measured alignment rises across the board. *Prediction:* no
  claimer/non-claimer difference; a common shift.

## Design

Two crises put a *specific* value under pressure, which lets the claim made before the crisis be
compared with behaviour after it:

| Crisis | Value under pressure | "Claimers" (defined before the crisis) | Outcomes (Part 2 data) |
|---|---|---|---|
| **COVID-19** (economic shock; "people first" becomes expensive) | Employee wellbeing, safety | Last About page in 2018–2019 states either value (13 of 48 firms) | Change from 2019–2020 proxies (written before the pandemic's effects) to 2021–2022: proxy emphasis on employees and on safety; share of years with an employee or safety pay link |
| **DEI backlash** (political shock: anti-ESG campaigns from 2022; June 2023 Supreme Court ruling) | Diversity, equity & inclusion | About page states DEI in any year 2020–2022 (19 of 48 firms) | Retention of a DEI pay link in 2024 among firms that had one in 2022–23; change in proxy DEI emphasis from 2021–22 to 2024; whether the About page still states DEI in 2024 |

**Sharpening the COVID test with real cost.** A "people first" claim is only tested if keeping it
is expensive. [src/get_revenue.py](src/get_revenue.py) pulls audited revenue from the SEC's XBRL
company-facts API (calendarised annual frames CY2019 and CY2020, so Microsoft's June year-end and
others are comparable) and flags firms whose 2020 revenue fell: 19 of 49 (Broadcom does not tag
revenue in a standard concept). Tests are repeated within hit and not-hit firms.

**Inference.** With about 50 firms, differences in mean change between claimers and non-claimers
are tested by permutation (claimer labels shuffled 10,000 times, fixed seed; two-sided p), which
needs no distributional assumptions. Everything uses existing Part 1–3 outputs plus public SEC
financial data.

## Results

### COVID-19: no divergence; non-claimers converged on claimers

| Outcome (change, post − pre) | Claimers | Non-claimers | Difference | p |
|---|---|---|---|---|
| Employee emphasis in proxy (per 10k words) | +5.3 | +4.2 | +1.1 | 0.55 |
| Safety emphasis in proxy | +1.4 | +1.4 | +0.1 | 0.96 |
| Employee or safety pay link (share of years) | 62% → 58% | 39% → 54% | −0.17 | 0.34 |

Claimers did **not** respond differently. Instead, firms that had *not* claimed people values
adopted people-related pay metrics, closing most of the pre-crisis gap: a convergence, as H2
predicts. Restricting to firms whose revenue fell, the one significant difference runs **against**
H1: the four claimers hit by revenue losses *cut* safety emphasis (−2.1 vs +1.5 for hit
non-claimers, p = 0.01). All four are oil refiners or producers (Phillips 66, Occidental, Marathon
Petroleum, ExxonMobil), so this cannot be separated from what happened to Energy in 2020; excluding
Energy, no outcome differs between claimers and non-claimers (p = 0.21–0.63). Meanwhile the mean
authenticity index rose for everyone, from −0.02 (2019–2020) to +0.18 (2021–2022).

### DEI backlash: public claims survived; costly commitments did not

| | Public DEI claimers | Non-claimers | p |
|---|---|---|---|
| Kept a DEI pay link in 2024 (among firms that had one in 2022–23) | 38% (5 of 13) | 57% (8 of 14) | 0.45 |
| Change in proxy DEI emphasis, 2021–22 → 2024 (per 10k words) | −7.5 | −2.4 | 0.19 |
| About page still states DEI in 2024 | **80%** | n/a | |

Firms that had publicly championed DEI retreated from DEI *pay commitments* at least as much as
firms that had not (the differences point the wrong way for H1 but are not statistically
significant), yet **80% of them kept DEI on their public About page**. Among the 11 public
claimers that also had a DEI pay link in 2022–23
([output/dei_decoupling_2024.csv](output/dei_decoupling_2024.csv)):

- **kept both (consistent commitment):** 5 (Bank of America, BlackRock, Bristol-Myers Squibb,
  Salesforce, Johnson & Johnson);
- **kept the public claim but dropped the pay link (decoupled under pressure):** 4 (Marathon
  Petroleum, Morgan Stanley, Pfizer, Starbucks);
- **dropped both (consistent retreat):** 2 (Ford, Alphabet).

### Wells Fargo: crisis as performance

([output/wells_fargo_case.csv](output/wells_fargo_case.csv)). Integrity mentions in Wells Fargo's
proxy rose from 6.4 per 10k words in 2016 (other banks 6.8) to **22.2 in 2017** (other banks 8.9)
and stayed about twice the peer level through 2021 (19.2 vs 8.7), returning to the peer level in
2022 (9.8 vs 8.4). Its over-claiming score is zero from 2020 on: every value it states has
backing. The crisis produced intense, consistent integrity discourse rather than revealing the
values that preceded it.

## Interpretation

The evidence does **not** support H1. In neither crisis did a public claim made beforehand predict
a different response; COVID-19 produced convergence, and the DEI backlash produced retreats that
were, if anything, larger among public champions. The more precise answer the data suggest is
that **crises reveal which channel a company protects**: cheap, public statements are the
stickiest, and costly commitments (pay metrics, formal disclosure) are the first to go. Under
pressure, decoupling between saying and doing tends to *increase*.

**Implication for measuring authenticity.** Crisis periods are poor moments to read stated values
at face value. A better crisis-based signal is the *survival of costly commitments*: whether pay
links and quantified targets persist when they become expensive or politically risky. The 2×2 in
the DEI analysis (kept both / decoupled / dropped both) is a prototype of such a measure, and could
be added to the index as a "commitment durability" component.

## Assumptions

- **A claim on the About page before a crisis is a public commitment** that the company could be
  held to; its absence means the value was not publicly claimed, not that it was not held.
- **Proxy emphasis and pay links measure the response.** Changes in what a company discusses with
  shareholders and ties to pay are taken as its formal response to the crisis.
- **Pre/post windows:** 2019–2020 proxies were written before the pandemic's effects; 2021–2022
  proxies are the first written after them. For the DEI backlash, 2022–23 is the pre-period and 2024
  the post-period.
- **A revenue fall in 2020 makes keeping a people-related commitment costly.**

## Limitations

1. **Small samples and low power.** 13 COVID claimers and 11–19 DEI claimers; only large
   differences (around one standard deviation) would be detectable. Non-significant differences
   are absence of evidence, not evidence of equality; conclusions rest on direction and consistency
   across tests, plus the descriptive DEI breakdown.
2. **Claimer status is not random.** Firms that state people or DEI values differ in sector and
   size (the COVID claimers who lost revenue are all Energy firms), so claimer/non-claimer
   differences are associations, not causal effects.
3. **Simultaneous shocks.** COVID-19, the racial-justice movement and the SEC human-capital rule
   all hit 2021 proxies; the COVID outcomes cannot be attributed to the pandemic alone.
4. **Measurement inherited from Parts 1–3:** About-page coding (LLM), proxy emphasis
   (dictionaries) and pay links (LLM) all carry error, and the About-page selection issues apply
   (e.g. Meta and Apple have no stated values and cannot be claimers).
5. **Revenue is a coarse cost measure.** A revenue fall does not show that people-related spending
   was actually cut; layoffs, wage freezes or headcount would be more direct.

## What I would do next

- **Scale to all 500 S&P firms** (the pipelines are built for it), which raises power enough to
  test H1 against H2 properly, with sector fixed effects.
- **Firm-specific crises** (enforcement actions, large fines, product recalls, CEO departures) to
  move beyond two market-wide shocks, with a pre-registered event-study design.
- **Direct cost evidence:** headcount and layoffs (10-K text, WARN notices) and CEO-to-worker pay
  ratios to test whether "people first" firms protected employees when revenue fell.
- **Add commitment durability to the authenticity index** and test whether it predicts later
  outcomes (complaints, violations, employee reviews) better than the current components.

## Files

| File | Contents |
|---|---|
| [output/revenue_2019_2020.csv](output/revenue_2019_2020.csv) | Revenue 2019 and 2020, tag used, change, `revenue_hit_2020` |
| [output/crisis_company_panel.csv](output/crisis_company_panel.csv) | One row per company: claimer flags, pre/post outcomes, revenue hit, DEI retention fields |
| [output/crisis_tests.csv](output/crisis_tests.csv) | One row per test: crisis, outcome, scope, group means, difference, permutation p, group sizes |
| [output/dei_decoupling_2024.csv](output/dei_decoupling_2024.csv) | 2024 outcome for each public DEI claimer with a 2022–23 DEI pay link |
| [output/wells_fargo_case.csv](output/wells_fargo_case.csv) | Wells Fargo vs other banks by year: index, over-claiming, integrity and customer emphasis |
| [output/results.txt](output/results.txt) | All results in readable form |
| [output/figures/](output/figures/) | Charts used in the summary |
