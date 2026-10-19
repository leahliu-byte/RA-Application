"""
mine_proxies.py
---------------
Part 2, step 2: classical (non-LLM) text mining of the 450 proxy statements.

Why classical methods: proxies are long (median ~50,000 words), so an LLM pass
over all of them would cost far more than this project's API budget, and
dictionary measures are transparent, reproducible and standard in accounting
and finance text analysis. The dictionaries operationalise the SAME codebook
used in Part 1 (data/codebook.json -> data/theme_dictionaries.json), which is
what makes the Part 3 comparison possible.

For each company-year it computes:
  1. THEME EMPHASIS: matches per 10,000 words for each codebook category, in
     (a) the whole proxy and (b) the Compensation Discussion & Analysis
     (CD&A) - the section explaining what executives are paid for. Emphasis
     inside the pay section is the closest text proxy for "lived" priorities.
  2. SPECIFICITY: share of a category's sentences that contain a quantified
     commitment (a percentage, or a target year such as "by 2030"). Concrete
     targets are costlier to state than aspirations.
  3. LANGUAGE CHANGE: TF-IDF cosine similarity with the company's previous
     proxy (1 = same wording). TF-IDF down-weights words common to all proxies,
     so shared legal boilerplate influences this less than raw overlap would.

It then produces the cross-sectional and event analyses:
  - sector-by-year means;
  - variance decomposition: how much of each category's variation is
    explained by sector, by company, and by year;
  - event tests: for each external event (data/external_events.csv), the
    within-company change in the expected category from the two proxy years
    before the first affected year to the two years from it, against the
    average change over all other comparable two-year windows (a simple
    placebo baseline, so a steady trend is not mistaken for an event effect).

Outputs (part2_lived_values/output/):
  proxy_dataset.csv            one row per company-year (schema in README)
  sector_year_means.csv        category emphasis by sector and year
  variance_decomposition.csv   R^2 of sector / company / year, per category
  event_tests.csv              one row per event x expected category

Usage (from the repo root, with .venv active):
    python part2_lived_values/src/mine_proxies.py
"""

import csv
import json
import re
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

PART_DIR = Path(__file__).resolve().parents[1]
REPO_DIR = PART_DIR.parent
MANIFEST_CSV = PART_DIR / "output" / "proxy_manifest.csv"
RAW_DIR = PART_DIR / "data" / "raw" / "proxies"
DICT_JSON = REPO_DIR / "data" / "theme_dictionaries.json"
EVENTS_CSV = REPO_DIR / "data" / "external_events.csv"
OUT_DIR = PART_DIR / "output"

DICTS = json.loads(DICT_JSON.read_text())
CATEGORIES = list(DICTS["categories"])
MIN_CDA_WORDS = 2000          # a shorter "CD&A" span is a mis-detection

# ---- Pattern compilation ---------------------------------------------------

def compile_terms(terms: list[str]) -> re.Pattern:
    """Match any term at the start of a word, case-insensitively."""
    return re.compile(r"(?<![a-z])(" + "|".join(re.escape(t) for t in terms) + ")")


CAT_RE = {c: compile_terms(t) for c, t in DICTS["categories"].items()}
SUPP_RE = {c: compile_terms(t) for c, t in DICTS["supplementary"].items()}
EXCLUDE_RE = re.compile("|".join(re.escape(p) for p in DICTS["exclude_phrases"]))
# Quantified commitment: a percentage, or a target year (2020-2059) after by/until/before/through
QUANT_RE = re.compile(r"\d+(\.\d+)?\s?(%|percent)|\b(by|until|before|through)\s+20[2-5]\d\b")
SENT_SPLIT = re.compile(r"(?<=[.!?;])\s+|\n{2,}")


def prepare(text: str) -> str:
    """Lowercase, unify apostrophes, drop excluded legal/financial phrases."""
    text = text.lower().replace("’", "'")
    return EXCLUDE_RE.sub(" ", text)


def rate(pattern: re.Pattern, text: str, n_words: int) -> float:
    """Matches per 10,000 words."""
    return round(len(pattern.findall(text)) / n_words * 10_000, 3) if n_words else np.nan


def find_cda(text: str) -> str:
    """Extract the Compensation Discussion & Analysis section.

    The heading also appears in the table of contents, so: take every
    occurrence of "compensation discussion and analysis" and pair it with the
    next occurrence of "summary compensation table" (the table that follows
    the CD&A); keep the longest span. Returns "" if none is long enough."""
    starts = [m.start() for m in re.finditer(r"compensation discussion (and|&) analysis", text)]
    ends = [m.start() for m in re.finditer(r"summary compensation table", text)]
    best = ""
    for s in starts:
        e = next((e for e in ends if e > s), None)
        if e is not None and e - s > len(best):
            best = text[s:e]
    return best if len(best.split()) >= MIN_CDA_WORDS else ""


def specificity(pattern: re.Pattern, sentences: list[str]) -> tuple[float, int]:
    """Share of sentences mentioning the category that contain a quantified
    commitment, and the number of such sentences."""
    hits = [s for s in sentences if pattern.search(s)]
    if not hits:
        return np.nan, 0
    return round(sum(bool(QUANT_RE.search(s)) for s in hits) / len(hits), 4), len(hits)


# ---- Per-document measures -------------------------------------------------

def measure_documents(manifest: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    rows, texts = [], {}
    for _, m in manifest.iterrows():
        raw = (RAW_DIR / m["text_file"]).read_text(encoding="utf-8")
        text = prepare(raw)
        n = len(text.split())
        cda = find_cda(text)
        n_cda = len(cda.split())
        sentences = [s for s in SENT_SPLIT.split(text) if len(s.split()) >= 5]
        row = {"ticker": m["ticker"], "company_name": m["company_name"], "sector": m["sector"],
               "year": int(m["year"]), "form": m["form"], "filing_date": m["filing_date"],
               "accession": m["accession"], "url": m["url"], "n_words": n,
               "cda_found": bool(cda), "n_words_cda": n_cda}
        for c in CATEGORIES:
            row[f"rate_{c}"] = rate(CAT_RE[c], text, n)
            row[f"cda_rate_{c}"] = rate(CAT_RE[c], cda, n_cda) if cda else np.nan
            spec, n_sent = specificity(CAT_RE[c], sentences)
            row[f"spec_{c}"] = spec
            row[f"nsent_{c}"] = n_sent
        for c, pat in SUPP_RE.items():
            row[f"rate_{c}"] = rate(pat, text, n)
        rows.append(row)
        texts[(m["ticker"], int(m["year"]))] = text
    return pd.DataFrame(rows), texts


def add_language_change(df: pd.DataFrame, texts: dict) -> pd.DataFrame:
    """TF-IDF cosine similarity with the company's previous available proxy."""
    keys = list(texts)
    vec = TfidfVectorizer(min_df=2, max_df=0.95, stop_words="english",
                          token_pattern=r"(?u)\b[a-z][a-z]+\b", sublinear_tf=True)
    X = vec.fit_transform([texts[k] for k in keys])
    index = {k: i for i, k in enumerate(keys)}
    sims = []
    for _, r in df.iterrows():
        prev = (r["ticker"], r["year"] - 1)
        if prev in index:
            sims.append(round(float(cosine_similarity(X[index[prev]], X[index[(r["ticker"], r["year"])]])[0, 0]), 4))
        else:
            sims.append(np.nan)
    df["tfidf_similarity_to_prior"] = sims
    return df


# ---- Cross-sectional analyses ----------------------------------------------

def r2(y: pd.Series, groups: pd.Series) -> float:
    """Share of variance in y explained by group means (eta-squared)."""
    total = ((y - y.mean()) ** 2).sum()
    fitted = y.groupby(groups).transform("mean")
    return round(1 - ((y - fitted) ** 2).sum() / total, 4) if total > 0 else np.nan


def variance_decomposition(df: pd.DataFrame) -> pd.DataFrame:
    out = []
    for c in CATEGORIES:
        y = df[f"rate_{c}"]
        out.append({"category": c, "mean_rate": round(y.mean(), 3), "sd_rate": round(y.std(), 3),
                    "r2_sector": r2(y, df["sector"]), "r2_company": r2(y, df["ticker"]),
                    "r2_year": r2(y, df["year"])})
    return pd.DataFrame(out)


def event_tests(df: pd.DataFrame, events: pd.DataFrame) -> pd.DataFrame:
    """Within-company pre/post comparison for each event and expected category.

    pre  = mean of the two proxy years before the first affected year Y
    post = mean of Y and Y+1
    Change for the event window is compared with the same two-year-vs-two-year
    change computed at every OTHER feasible split year (placebo windows).
    The test statistic is the paired difference across companies; the
    "excess" is event change minus the average placebo change.
    """
    years = sorted(df["year"].unique())
    out = []
    for _, ev in events.iterrows():
        Y = int(ev["first_proxy_year_affected"])
        for c in ev["expected_categories"].split(";"):
            col = f"rate_{c}"
            wide = df.pivot(index="ticker", columns="year", values=col)

            def window_change(split):
                pre = wide[[split - 2, split - 1]].mean(axis=1)
                post_years = [y for y in (split, split + 1) if y in years]
                post = wide[post_years].mean(axis=1)
                return post - pre, pre, post

            # A split needs two pre years; the post window uses one year when
            # the panel ends (the 2024 split has no 2025).
            feasible = [s for s in years if s - 2 in years]
            if Y not in feasible:
                out.append({"event_id": ev["event_id"], "category": c, "first_year": Y,
                            "note": "no pre-period inside 2016-2024; descriptive only"})
                continue
            short_post = Y + 1 not in years
            diff, pre, post = window_change(Y)
            diff = diff.dropna()
            t, p = stats.ttest_1samp(diff, 0.0)
            placebo = [window_change(s)[0].mean() for s in feasible if s != Y]
            out.append({
                "event_id": ev["event_id"], "category": c, "first_year": Y,
                "expected_direction": ev["expected_direction"], "n_companies": len(diff),
                "pre_mean": round(pre.mean(), 3), "post_mean": round(post.mean(), 3),
                "change": round(diff.mean(), 3),
                "pct_change": round(100 * diff.mean() / pre.mean(), 1) if pre.mean() else np.nan,
                "share_companies_moving_expected_way": round(
                    ((diff > 0) if ev["expected_direction"] == "up" else (diff < 0)).mean(), 3),
                "t_stat": round(t, 2), "p_value": round(p, 4),
                "placebo_mean_change": round(float(np.mean(placebo)), 3),
                "placebo_max_abs_change": round(float(np.max(np.abs(placebo))), 3),
                "excess_change_vs_placebo": round(diff.mean() - float(np.mean(placebo)), 3),
                "note": "post window is one year only (panel ends 2024)" if short_post else "",
            })
    return pd.DataFrame(out)


# ---- Main ------------------------------------------------------------------

def main() -> None:
    manifest = pd.read_csv(MANIFEST_CSV)
    manifest = manifest[manifest["status"] == "ok"]
    events = pd.read_csv(EVENTS_CSV)

    df, texts = measure_documents(manifest)
    df = add_language_change(df, texts)
    df = df.sort_values(["ticker", "year"]).reset_index(drop=True)
    for c in CATEGORIES:                                    # year-on-year change in emphasis
        df[f"yoy_change_{c}"] = df.groupby("ticker")[f"rate_{c}"].diff().round(3)

    df.to_csv(OUT_DIR / "proxy_dataset.csv", index=False, quoting=csv.QUOTE_MINIMAL)
    rate_cols = [f"rate_{c}" for c in CATEGORIES]
    df.groupby(["sector", "year"])[rate_cols].mean().round(3).reset_index() \
      .to_csv(OUT_DIR / "sector_year_means.csv", index=False)
    variance_decomposition(df).to_csv(OUT_DIR / "variance_decomposition.csv", index=False)
    event_tests(df, events).to_csv(OUT_DIR / "event_tests.csv", index=False)

    print(f"{len(df)} documents measured; CD&A found in {df['cda_found'].sum()}.")
    print("Outputs written to", OUT_DIR)


if __name__ == "__main__":
    main()
