# Organizational Authenticity & Corporate Value Alignment

Research assistant assignment (Wharton–TAU lab): a scoped proof of concept, for 50 S&P 500
companies over 2016–2024, of measuring the alignment between what companies **say** they value and
what their disclosures and incentives suggest they **prioritise**. Every method is rule-based or
documented, and designed to run unchanged on all 500 firms.

| Part | Question | Data | Write-ups |
|---|---|---|---|
| [1. Stated values](part1_stated_values/) | What do companies say they value, and how has it changed? | 402 archived "About Us" snapshots (Wayback Machine), coded by LLM against a research-based codebook | [README](part1_stated_values/README.md) · [Summary](part1_stated_values/summary.md) |
| [2. Lived values](part2_lived_values/) | What do they emphasise to shareholders, and what do they pay executives for? | 450/450 annual proxy statements (SEC EDGAR); classical text mining + LLM reading of the pay section | [README](part2_lived_values/README.md) · [Summary](part2_lived_values/summary.md) |
| [3. Authenticity index](part3_authenticity_index/) | How aligned are the two, by company and year? | Index of discourse consistency + incentive backing, with over-/under-claiming | [README](part3_authenticity_index/README.md) · [Summary](part3_authenticity_index/summary.md) |
| [4. Proposal](part4_proposal/) | Does a crisis reveal whether corporate values are authentic? | COVID-19 and the 2022–24 DEI backlash as tests: do pre-crisis public claims predict post-crisis behaviour? Permutation tests; SEC revenue data | [README](part4_proposal/README.md) · [Summary](part4_proposal/summary.md) |

## Shared design decisions

- **One codebook for every part** ([data/codebook.json](data/codebook.json)): 11 value categories,
  a hybrid of the MIT Sloan "Big Nine" corporate values and stakeholder/ESG themes plus safety.
  Using identical categories for stated (Part 1) and lived (Part 2) values is what makes Part 3's
  comparison possible.
- **Sample** ([data/companies.csv](data/companies.csv)): the 50 companies specified in the
  assignment, 10 per sector (Technology, Financials, Healthcare, Consumer Discretionary, Energy).
- **External events** ([data/external_events.csv](data/external_events.csv)) and **keyword
  dictionaries** ([data/theme_dictionaries.json](data/theme_dictionaries.json)) are shared data
  files, so every analytic choice can be inspected and changed in one place.
- **Every gap is documented** at the row level (`status`, `status_reason` columns) and summarised
  in each part's README.

## Repository layout

```
data/                         shared inputs: companies, codebook, dictionaries, events
partN_*/src/                  code for that part (each script documents its rules at the top)
partN_*/data/                 part-specific inputs (raw downloads in data/raw/ are git-ignored)
partN_*/output/               datasets, logs of LLM responses (llm_cache/), figures
partN_*/README.md             what / why / assumptions / limitations / what next
partN_*/summary.md            1–2 page non-technical summary
make_figures.py               figures used in the summaries
requirements.txt              pinned Python dependencies
```

## Reproducing

```bash
python3.12 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
# .env (not committed) needs:
#   ANTHROPIC_API_KEY=...                      (Parts 1 and 2 LLM steps)
#   SEC_USER_AGENT=<project name> <email>      (SEC fair-access policy)
```

Then run each part's scripts in the order listed in its README. Downloads are polite (the
Internet Archive and SEC are rate-limited) and resumable; LLM steps reuse cached responses in
`output/llm_cache/`, so re-running reproduces the same results without new API calls.

## LLM use

Claude Haiku 5.5 is used for the reading tasks the assignment calls for (Part 1 coding; Part 2
pay-section reading): a small, fast model suited to structured classification at the scale this
pipeline is designed for (all 500 S&P firms). Every LLM judgement must cite a quote, and quotes are
verified against the source text by code (Part 1: 98.3%; Part 2: 92.7%).
