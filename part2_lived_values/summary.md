# Part 2 Summary: What Companies Tell Shareholders, and What They Pay Executives For

## What we did

Every U.S.-listed company must publish a **proxy statement** each year before its shareholder
meeting. It describes the board, governance, and above all **what executives are paid for**. We
collected the official proxy statement for all 50 sample companies for every year from 2016 to
2024 from the SEC's public database: **450 of 450 documents, about 24 million words, with no
gaps**. We chose proxies over sustainability or diversity reports because every company must file
one, every year, in a comparable format, whereas voluntary reports have large gaps before 2019 and
can be written as marketing.

We then measured, for each document, how much it discusses each of the same eleven values used in
Part 1, using transparent word lists applied identically to every document. Separately, an AI model
read the executive-pay section of each proxy to identify which values are **actually built into
executive pay** (for example, "10% of the annual bonus depends on safety targets") as opposed to
merely mentioned. We tested every shift against eleven external events, such as the 2019 Business
Roundtable statement on corporate purpose and the murder of George Floyd in 2020.

![How proxy statements talk about ESG themes](output/figures/fig1_proxy_esg_language.png)

## What we found

**1. Environmental, diversity and workforce language exploded, then split.** Between 2016 and
2022, mentions of environment and sustainability rose roughly fivefold, diversity about 2.6-fold
and employee wellbeing about 2.7-fold. After 2022 the paths diverge: environmental language holds
steady, but **diversity language falls every year from its 2021 peak (−20% by 2024)**. The generic
label "ESG" fell even faster in 2024 (−30%) while the substance it labels did not. Companies are
keeping the content and dropping the politically charged word, a pattern known as "greenhushing".

**2. Some events clearly moved language beyond the background trend; others did not.**

| Event | Value it should move | Change in the next proxies | Beyond normal trend? |
|---|---|---|---|
| George Floyd's murder (May 2020) | Diversity | +48%; 88% of companies rose | Yes, strongly |
| Business Roundtable purpose statement (2019) | Community; employees | +53%; +59% | Yes |
| COVID-19 (2020) | Employee wellbeing; safety | +47%; +61% | Yes |
| ChatGPT launch (2022) | Innovation | +43% | Yes, modestly |
| BlackRock's climate letter (2020) | Environment | +102% | **No**: environment was already rising this fast every year |
| Supreme Court affirmative-action ruling (2023) | Diversity | −14%; 62% of companies cut | Yes, a reversal |

Several 2020 events reach the 2021 proxies at the same time, so their individual effects cannot
be separated.

![Values tied to executive pay](output/figures/fig2_pay_metrics.png)

**3. Money followed words, with a lag, and retreated faster.** The share of companies tying
executive pay to an **environmental** target rose from 2% (2016) to 27% (2023–2024); to a
**diversity** target from 0% to 25% in 2023, then **dropped to 15% in 2024**, a 40% retreat in a
single year. Values such as respect, collaboration and community are almost never tied to pay.
Financial results remain the dominant pay metric (around 60–75% of companies use them in a formula;
the rest, such as Amazon, ExxonMobil and the large banks, deliberately pay on board judgement).

**4. Who a company is matters more than what industry it is in.** For every value, the individual
company explains far more of the variation (40–79%) than its sector (3–42%). Sector matters most
where the business demands it: Energy proxies discuss environment and safety most (about twice the
average), Financials discuss customers and diversity most, Healthcare discusses innovation most.

## What this means for a reader acting on it

- **Look at pay, not prose.** The pay section separates commitments with consequences from
  commitments in name only; ESG pay metrics are now common enough to compare across companies.
- **Expect retreats to start where accountability is weakest to defend.** In the backlash,
  diversity pay targets were cut faster than diversity language, and the "ESG" label faster than
  environmental substance.
- **Judge companies individually.** Sector averages hide most of the variation.

## Caveats

Word counts measure attention, not quality: discussing a lawsuit and announcing a target both
count. The event analysis is descriptive, not proof of cause. Proxies are governance documents, so
they understate environmental and community topics relative to sustainability reports. The pay
reading was done by a small AI model, with 93% of its supporting quotes verified against the
documents.
