"""
build_index.py
--------------
Part 3: the Organizational Authenticity Index (OAI).

Construct. Authenticity is the alignment between the values an organisation
ESPOUSES and those it ENACTS (Schein's distinction between espoused values and
enacted culture). Its absence is what institutional theory calls DECOUPLING:
symbolic statements disconnected from practice (Meyer & Rowan 1977; Bromley &
Powell 2012). We measure decoupling at two levels, each comparing the Part 1
About page (espoused, public) with the Part 2 proxy statement (disclosed to
shareholders, and where pay is set):

  A. DISCOURSE CONSISTENCY - does the company emphasise the same values in
     both places? Spearman rank correlation, across the 11 codebook
     categories, between About-page salience (0/1/2, Part 1 LLM coding) and
     proxy emphasis relative to peers (z-score of matches per 10k words within
     category and year, Part 2 dictionaries). Standardising within category-
     year removes base rates (every proxy discusses performance) and the
     common upward trend in ESG language, so only RELATIVE emphasis counts.

  B. INCENTIVE BACKING - does the company put money behind what it says?
     For each category stated on the About page (salience > 0), its pay link
     (Part 2 CD&A extraction: 1.0 = weighted metric, 0.5 = qualitative factor,
     0 = none) minus the share of companies that year with that link (the
     base rate: some values, like respect, are rarely pay-linked anywhere).
     Averaged over the stated categories. Positive = more backing than typical.

  OAI = mean of the standardised components (z-scores pooled over all
  company-years), reported both as a z-score and a 0-100 percentile. If one
  component is unavailable (e.g. no CD&A section), the other is used and
  `n_components` records it.

Decomposition (directional decoupling):
  OVER-CLAIMING  share of stated categories with no lived evidence: below-
                 peer proxy emphasis (z < 0) AND not linked to pay.
  UNDER-CLAIMING share of visibly prioritised categories (proxy emphasis
                 z > 1, or a weighted pay metric that fewer than half of
                 companies use that year) that the About page does NOT state.

Year matching: About page of year t (early-year snapshot) with the proxy filed
in year t. Both are the company's statements at the start of year t.

Outputs (part3_authenticity_index/output/):
  authenticity_index.csv       one row per company-year
  company_summary.csv          one row per company (means, trend)
  category_contributions.csv   over-claiming by category (which values are cheap talk)
  validity_checks.txt          distribution, validity and robustness results

Usage (from the repo root, with .venv active):
    python part3_authenticity_index/src/build_index.py
"""

import json
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

REPO_DIR = Path(__file__).resolve().parents[2]
PART_DIR = REPO_DIR / "part3_authenticity_index"
P1 = REPO_DIR / "part1_stated_values" / "output" / "part1_dataset.csv"
P2_TEXT = REPO_DIR / "part2_lived_values" / "output" / "proxy_dataset.csv"
P2_PAY = REPO_DIR / "part2_lived_values" / "output" / "pay_links_wide.csv"
OUT = PART_DIR / "output"
CATS = [c["id"] for c in json.loads((REPO_DIR / "data" / "codebook.json").read_text())["categories"]]


# ---- Load and align the three layers ---------------------------------------

def load_panel() -> pd.DataFrame:
    p1 = pd.read_csv(P1)
    p1 = p1[p1["status"] == "ok"]
    p1 = p1[["ticker", "company_name", "sector", "year", "word_count", "tier",
             "about_page_check"] + [f"theme_{c}" for c in CATS]]
    p2 = pd.read_csv(P2_TEXT)[["ticker", "year"] + [f"rate_{c}" for c in CATS]]
    pay = pd.read_csv(P2_PAY)[["ticker", "year", "cda_found"] + [f"pay_{c}" for c in CATS]]
    df = p1.merge(p2, on=["ticker", "year"], how="inner").merge(pay, on=["ticker", "year"], how="left")

    # Proxy emphasis relative to peers: z-score within category and year
    for c in CATS:
        g = df.groupby("year")[f"rate_{c}"]
        df[f"z_{c}"] = (df[f"rate_{c}"] - g.transform("mean")) / g.transform("std")
    # Pay link on a 0-1 scale and its base rate per category-year
    for c in CATS:
        df[f"paylink_{c}"] = df[f"pay_{c}"] / 2.0
        df[f"paybase_{c}"] = df.groupby("year")[f"paylink_{c}"].transform("mean")
        df[f"payq_share_{c}"] = df.groupby("year")[f"pay_{c}"].transform(lambda s: (s == 2).mean())
    return df


# ---- Components --------------------------------------------------------------

def component_a(row) -> float:
    s = np.array([row[f"theme_{c}"] for c in CATS], dtype=float)
    z = np.array([row[f"z_{c}"] for c in CATS], dtype=float)
    if np.nanstd(s) == 0 or np.isnan(z).any():
        return np.nan                     # no variation in what the page states
    return stats.spearmanr(s, z).statistic


def component_b(row) -> float:
    if not row["cda_found"] or pd.isna(row["cda_found"]):
        return np.nan
    stated = [c for c in CATS if row[f"theme_{c}"] > 0]
    if not stated:
        return np.nan
    return float(np.mean([row[f"paylink_{c}"] - row[f"paybase_{c}"] for c in stated]))


def over_claiming(row) -> float:
    stated = [c for c in CATS if row[f"theme_{c}"] > 0]
    if not stated:
        return np.nan
    has_pay = bool(row["cda_found"]) and not pd.isna(row["cda_found"])
    cheap = [c for c in stated if row[f"z_{c}"] < 0 and (not has_pay or row[f"pay_{c}"] == 0)]
    return len(cheap) / len(stated)


def under_claiming(row) -> float:
    lived = [c for c in CATS
             if row[f"z_{c}"] > 1
             or (row[f"pay_{c}"] == 2 and row[f"payq_share_{c}"] < 0.5)]
    if not lived:
        return np.nan
    return sum(row[f"theme_{c}"] == 0 for c in lived) / len(lived)


def zscore(s: pd.Series) -> pd.Series:
    return (s - s.mean()) / s.std()


def build(df: pd.DataFrame) -> pd.DataFrame:
    df["A_discourse_consistency"] = df.apply(component_a, axis=1)
    df["B_incentive_backing"] = df.apply(component_b, axis=1)
    df["over_claiming"] = df.apply(over_claiming, axis=1)
    df["under_claiming"] = df.apply(under_claiming, axis=1)
    df["n_stated_values"] = sum((df[f"theme_{c}"] > 0).astype(int) for c in CATS)
    za, zb = zscore(df["A_discourse_consistency"]), zscore(df["B_incentive_backing"])
    df["n_components"] = za.notna().astype(int) + zb.notna().astype(int)
    df["OAI_z"] = pd.concat([za, zb], axis=1).mean(axis=1, skipna=True)
    df["OAI_z"] = zscore(df["OAI_z"])
    df["OAI_pct"] = (df["OAI_z"].rank(pct=True) * 100).round(1)
    return df


# ---- Validity and robustness -----------------------------------------------

def report(df: pd.DataFrame) -> str:
    lines = []
    w = lines.append
    v = df["OAI_z"].dropna()
    w("ORGANIZATIONAL AUTHENTICITY INDEX - DISTRIBUTION, VALIDITY AND ROBUSTNESS\n")
    w(f"Company-years with an index: {len(v)} (both components: {(df['n_components'] == 2).sum()}, "
      f"one component: {(df['n_components'] == 1).sum()}); companies: {df.loc[v.index, 'ticker'].nunique()}")
    w("\n1. DISTRIBUTION")
    for col in ["A_discourse_consistency", "B_incentive_backing", "OAI_z", "over_claiming", "under_claiming"]:
        s = df[col].dropna()
        w(f"  {col:26s} n={len(s):3d} mean={s.mean():6.3f} sd={s.std():5.3f} "
          f"min={s.min():6.3f} p25={s.quantile(.25):6.3f} median={s.median():6.3f} "
          f"p75={s.quantile(.75):6.3f} max={s.max():6.3f} skew={stats.skew(s):5.2f}")
    r = stats.spearmanr(df["A_discourse_consistency"], df["B_incentive_backing"], nan_policy="omit")
    w(f"  Correlation of components A and B: Spearman rho={r.statistic:.3f} (p={r.pvalue:.3f}) "
      "- low values mean the components capture different facets.")

    # Variance across companies vs over time
    d = df.dropna(subset=["OAI_z"])
    total = d["OAI_z"].var()
    between = d.groupby("ticker")["OAI_z"].transform("mean").var()
    w(f"  Share of variance BETWEEN companies: {between / total:.1%}; WITHIN companies over time: "
      f"{1 - between / total:.1%}")
    w("  Mean OAI_z by sector: " + ", ".join(
        f"{k} {x:+.2f}" for k, x in d.groupby("sector")["OAI_z"].mean().sort_values().items()))
    w("  Mean OAI_z by year:   " + ", ".join(
        f"{k} {x:+.2f}" for k, x in d.groupby("year")["OAI_z"].mean().items()))
    f = stats.f_oneway(*[g["OAI_z"].values for _, g in d.groupby("sector")])
    w(f"  Sector differences (one-way ANOVA): F={f.statistic:.2f}, p={f.pvalue:.3f}")

    w("\n2. VALIDITY CHECKS")
    # (a) Known group: Wells Fargo during the fake-accounts scandal
    banks = d[d["sector"] == "Financials"]
    wfc = banks[banks["ticker"] == "WFC"]
    others = banks[banks["ticker"] != "WFC"]
    w("  (a) Known-group check - Wells Fargo (fake-accounts scandal disclosed Sept 2016; "
      "consent orders through 2018):")
    for yrs, lab in [((2016, 2018), "2016-2018"), ((2019, 2024), "2019-2024")]:
        a = wfc[wfc["year"].between(*yrs)]["OAI_z"]
        b = others[others["year"].between(*yrs)]["OAI_z"]
        w(f"      {lab}: WFC mean {a.mean():+.2f} (n={len(a)}) vs other banks {b.mean():+.2f} (n={len(b)})")
    for col in ["over_claiming"]:
        a = wfc[wfc["year"].between(2016, 2018)][col].mean()
        b = others[others["year"].between(2016, 2018)][col].mean()
        w(f"      Over-claiming 2016-2018: WFC {a:.2f} vs other banks {b:.2f}")

    # (b) Convergent: energy companies that state safety should back it with pay
    en = d[(d["sector"] == "Energy") & (d["theme_safety"] > 0) & d["cda_found"].fillna(False).astype(bool)]
    nen = d[(d["sector"] != "Energy") & (d["theme_safety"] > 0) & d["cda_found"].fillna(False).astype(bool)]
    w("  (b) Convergent check - when SAFETY is stated, is it pay-linked? "
      f"Energy {np.mean(en['pay_safety'] > 0):.0%} (n={len(en)}) vs other sectors "
      f"{np.mean(nen['pay_safety'] > 0):.0%} (n={len(nen)}). Expected: higher in Energy, where "
      "safety is operationally material.")

    # (c) Discriminant: the index should not simply reflect page length
    rho = stats.spearmanr(d["OAI_z"], d["word_count"], nan_policy="omit")
    w(f"  (c) Discriminant check - OAI vs About-page length: rho={rho.statistic:.3f} "
      f"(p={rho.pvalue:.3f}). Near zero means the index is not an artefact of longer pages "
      "stating more values.")
    rho2 = stats.spearmanr(d["OAI_z"], d["n_stated_values"], nan_policy="omit")
    w(f"      OAI vs number of stated values: rho={rho2.statistic:.3f} (p={rho2.pvalue:.3f}).")

    # (d) Face validity: extremes
    cs = d.groupby(["ticker", "company_name"])["OAI_z"].mean().sort_values()
    w("  (d) Face validity - lowest 5 companies (mean OAI_z): " +
      "; ".join(f"{n} {x:+.2f}" for (_, n), x in cs.head(5).items()))
    w("      Highest 5 companies: " + "; ".join(f"{n} {x:+.2f}" for (_, n), x in cs.tail(5)[::-1].items()))

    w("\n3. ROBUSTNESS (rank correlation of company-year scores with the main index)")
    base = d["OAI_z"]
    alts = {
        "A only": zscore(d["A_discourse_consistency"]),
        "B only": zscore(d["B_incentive_backing"]),
    }
    for name, alt in alts.items():
        r = stats.spearmanr(base, alt, nan_policy="omit")
        w(f"  {name}: rho={r.statistic:.3f}, n={alt.notna().sum()}")
    # Do pages with selection issues (fallback tiers, or judged not a general
    # About page by the Part 1 check) score systematically differently?
    flagged = (d["tier"] >= 3) | (d["about_page_check"].astype(str) != "True")
    t = stats.ttest_ind(d.loc[flagged, "OAI_z"], d.loc[~flagged, "OAI_z"], equal_var=False)
    w(f"  Selection-issue pages (n={flagged.sum()}) vs clean pages (n={(~flagged).sum()}): "
      f"mean OAI_z {d.loc[flagged, 'OAI_z'].mean():+.2f} vs {d.loc[~flagged, 'OAI_z'].mean():+.2f} "
      f"(Welch t={t.statistic:.2f}, p={t.pvalue:.3f}). A small difference means page-selection "
      "problems add noise rather than systematic bias.")
    clean = d[~flagged]
    cs_all = d.groupby("ticker")["OAI_z"].mean()
    cs_clean = clean.groupby("ticker")["OAI_z"].mean()
    common = cs_all.index.intersection(cs_clean.index)
    r = stats.spearmanr(cs_all[common], cs_clean[common])
    w(f"  Company ranking using clean pages only vs all pages: rho={r.statistic:.3f} "
      f"({len(common)} companies)")
    # Leave-one-category-out for component A
    loo = []
    for drop in CATS:
        keep = [c for c in CATS if c != drop]
        def a_loo(row, keep=keep):
            s = np.array([row[f"theme_{c}"] for c in keep], float)
            z = np.array([row[f"z_{c}"] for c in keep], float)
            return np.nan if np.nanstd(s) == 0 or np.isnan(z).any() else stats.spearmanr(s, z).statistic
        alt = d.apply(a_loo, axis=1)
        loo.append(stats.spearmanr(d["A_discourse_consistency"], alt, nan_policy="omit").statistic)
    w(f"  Component A, leave-one-category-out: min rho={min(loo):.3f}, mean rho={np.mean(loo):.3f} "
      "(no single category drives the measure if these stay high)")
    return "\n".join(lines)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    df = build(load_panel())

    keep = (["ticker", "company_name", "sector", "year", "OAI_z", "OAI_pct",
             "A_discourse_consistency", "B_incentive_backing", "n_components",
             "over_claiming", "under_claiming", "n_stated_values", "cda_found",
             "tier", "about_page_check", "word_count"])
    df[keep].sort_values(["ticker", "year"]).round(4).to_csv(OUT / "authenticity_index.csv", index=False)

    d = df.dropna(subset=["OAI_z"])
    slope = d.groupby("ticker").apply(
        lambda g: stats.linregress(g["year"], g["OAI_z"]).slope if g["year"].nunique() > 2 else np.nan,
        include_groups=False)
    comp = d.groupby(["ticker", "company_name", "sector"]).agg(
        n_years=("year", "count"), OAI_z_mean=("OAI_z", "mean"), OAI_z_sd=("OAI_z", "std"),
        A_mean=("A_discourse_consistency", "mean"), B_mean=("B_incentive_backing", "mean"),
        over_claiming_mean=("over_claiming", "mean"), under_claiming_mean=("under_claiming", "mean"),
    ).reset_index()
    comp["OAI_trend_per_year"] = comp["ticker"].map(slope)
    comp.sort_values("OAI_z_mean").round(4).to_csv(OUT / "company_summary.csv", index=False)

    # Which stated values are most often "cheap talk"?
    rows = []
    for c in CATS:
        st = d[d[f"theme_{c}"] > 0]
        has_pay = st["cda_found"].fillna(False).astype(bool)
        cheap = (st[f"z_{c}"] < 0) & (~has_pay | (st[f"pay_{c}"] == 0))
        rows.append({"category": c, "n_stated": len(st),
                     "share_stated": round(len(st) / len(d), 3),
                     "share_stated_but_unbacked": round(cheap.mean(), 3) if len(st) else np.nan,
                     "share_stated_with_pay_link": round((st[f"pay_{c}"] > 0).mean(), 3) if len(st) else np.nan})
    pd.DataFrame(rows).sort_values("share_stated_but_unbacked", ascending=False) \
        .to_csv(OUT / "category_contributions.csv", index=False)

    text = report(df)
    (OUT / "validity_checks.txt").write_text(text)
    print(text)


if __name__ == "__main__":
    main()
