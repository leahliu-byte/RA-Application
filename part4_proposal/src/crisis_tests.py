"""
crisis_tests.py
---------------
Part 4: Does a crisis reveal whether corporate values are authentic?

Two competing hypotheses:
  H1 "Crises reveal": pressure separates held values from cheap talk. Firms
     that publicly claimed a value before a crisis keep or increase their
     backing of it when it becomes costly; firms that did not claim it do not.
     Prediction: claimers diverge from non-claimers after the crisis.
  H2 "Crises perform": crises trigger symbolic, industry-wide alignment.
     Everyone says the right things at once, so claimers and non-claimers move
     together and measured alignment rises for all.
     Prediction: no claimer/non-claimer difference; common shift.

Two crises, each putting a specific value under pressure:

  1. COVID-19 (economic shock; "people first" becomes expensive).
     Value: PEOPLE = employee wellbeing & development, or safety.
     Claimers: the company's last About page before the crisis (2019, else
     2018) states either value.
     Outcomes, pre = mean of 2019-2020 proxies (both written before the
     pandemic's effects), post = mean of 2021-2022 proxies:
       - proxy emphasis on employee wellbeing and on safety (per 10k words)
       - share of years with an employee or safety pay link
     Sharpened by the revenue test: firms whose 2020 revenue fell
     (get_revenue.py) are the ones whose claim was truly costly to keep.

  2. DEI BACKLASH (political shock: anti-ESG campaigns from 2022, the June 2023
     Supreme Court ruling on race-conscious admissions).
     Value: diversity, equity & inclusion.
     Claimers: the About page states DEI in any of 2020-2022 (before the
     backlash peaked).
     Outcomes: (a) among firms that had a DEI pay link in 2022 or 2023, the
     share still having one in 2024 (retention); (b) change in proxy DEI
     emphasis from 2021-2022 to 2024; (c) for claimers, whether the About page
     still states DEI in 2024 (public retention vs pay retention).

Inference: with ~50 firms, differences in mean change between claimers and
non-claimers are tested by PERMUTATION (claimer labels shuffled 10,000 times;
two-sided p = share of shuffles with an absolute difference at least as large
as observed). This makes no distributional assumptions.

Plus the Wells Fargo case (the Part 3 finding behind H2): yearly index,
components and integrity emphasis versus other banks.

Outputs (part4_proposal/output/):
  crisis_company_panel.csv   one row per company: claimer flags, pre/post values
  crisis_tests.csv           one row per test: groups, means, difference, p-value
  wells_fargo_case.csv       Wells Fargo vs other banks by year
  results.txt                readable summary of all tests

Usage (from the repo root, with .venv active):
    python part4_proposal/src/crisis_tests.py
"""

from pathlib import Path

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parents[2]
OUT = REPO / "part4_proposal" / "output"
RNG = np.random.default_rng(20240101)        # fixed seed: results are reproducible
N_PERM = 10_000


def load():
    p1 = pd.read_csv(REPO / "part1_stated_values" / "output" / "part1_dataset.csv")
    p1 = p1[p1["status"] == "ok"]
    p2 = pd.read_csv(REPO / "part2_lived_values" / "output" / "proxy_dataset.csv")
    oai = pd.read_csv(REPO / "part3_authenticity_index" / "output" / "authenticity_index.csv")
    rev = pd.read_csv(OUT / "revenue_2019_2020.csv")
    return p1, p2, oai, rev


def permutation_test(values: pd.Series, groups: pd.Series) -> tuple[float, float, int, int]:
    """Difference in means (group True minus False) and two-sided permutation p."""
    v = values.to_numpy(float)
    g = groups.to_numpy(bool)
    keep = ~np.isnan(v)
    v, g = v[keep], g[keep]
    n1, n0 = g.sum(), (~g).sum()
    if n1 < 3 or n0 < 3:
        return np.nan, np.nan, int(n1), int(n0)
    obs = v[g].mean() - v[~g].mean()
    perm = np.empty(N_PERM)
    for i in range(N_PERM):
        s = RNG.permutation(g)
        perm[i] = v[s].mean() - v[~s].mean()
    p = (np.abs(perm) >= abs(obs) - 1e-12).mean()
    return obs, p, int(n1), int(n0)


def last_page_before(p1: pd.DataFrame, years: list[int]) -> pd.DataFrame:
    """Each company's latest usable About page among `years`."""
    sub = p1[p1["year"].isin(years)].sort_values("year")
    return sub.groupby("ticker").tail(1).set_index("ticker")


def window_mean(p2, col, years):
    return p2[p2["year"].isin(years)].groupby("ticker")[col].mean()


def covid(p1, p2, rev, tests, panel):
    pre_page = last_page_before(p1, [2018, 2019])
    claim = ((pre_page["theme_employee_wellbeing_development"] > 0) |
             (pre_page["theme_safety"] > 0)).rename("covid_people_claimer")
    df = pd.DataFrame(claim)
    for col, lab in [("rate_employee_wellbeing_development", "employee_emphasis"),
                     ("rate_safety", "safety_emphasis")]:
        df[f"{lab}_pre"] = window_mean(p2, col, [2019, 2020])
        df[f"{lab}_post"] = window_mean(p2, col, [2021, 2022])
        df[f"{lab}_change"] = df[f"{lab}_post"] - df[f"{lab}_pre"]
    p2 = p2.assign(people_pay=((p2["pay_employee_wellbeing_development"] > 0) |
                               (p2["pay_safety"] > 0)).astype(float)
                   .where(p2["pay_safety"].notna()))
    df["people_pay_pre"] = window_mean(p2, "people_pay", [2019, 2020])
    df["people_pay_post"] = window_mean(p2, "people_pay", [2021, 2022])
    df["people_pay_change"] = df["people_pay_post"] - df["people_pay_pre"]
    df = df.join(rev.set_index("ticker")[["revenue_change_pct", "revenue_hit_2020"]])
    df["revenue_hit_2020"] = df["revenue_hit_2020"].astype("boolean")

    for outcome in ["employee_emphasis_change", "safety_emphasis_change", "people_pay_change"]:
        for scope, mask in [("all firms", pd.Series(True, index=df.index)),
                            ("revenue-hit firms", df["revenue_hit_2020"].fillna(False).astype(bool)),
                            ("not-hit firms", ~df["revenue_hit_2020"].fillna(True).astype(bool))]:
            d = df[mask]
            diff, p, n1, n0 = permutation_test(d[outcome], d["covid_people_claimer"])
            tests.append({"crisis": "COVID-19", "value": "people (employee wellbeing or safety)",
                          "outcome": outcome, "scope": scope,
                          "claimers_mean_change": d[d["covid_people_claimer"]][outcome].mean(),
                          "nonclaimers_mean_change": d[~d["covid_people_claimer"]][outcome].mean(),
                          "difference": diff, "p_value": p, "n_claimers": n1, "n_nonclaimers": n0})
    # Sector confound: revenue hits are concentrated in Energy. Re-test excluding Energy.
    sec = p1.drop_duplicates("ticker").set_index("ticker")["sector"]
    df = df.join(sec)
    d = df[df["sector"] != "Energy"]
    for outcome in ["employee_emphasis_change", "safety_emphasis_change", "people_pay_change"]:
        diff, p, n1, n0 = permutation_test(d[outcome], d["covid_people_claimer"])
        tests.append({"crisis": "COVID-19", "value": "people (employee wellbeing or safety)",
                      "outcome": outcome, "scope": "all firms excl. Energy",
                      "claimers_mean_change": d[d["covid_people_claimer"]][outcome].mean(),
                      "nonclaimers_mean_change": d[~d["covid_people_claimer"]][outcome].mean(),
                      "difference": diff, "p_value": p, "n_claimers": n1, "n_nonclaimers": n0})
    panel.append(df.drop(columns="sector"))


def dei_backlash(p1, p2, tests, panel):
    pre = p1[p1["year"].between(2020, 2022)]
    claim = pre.groupby("ticker")["theme_diversity_inclusion"].max().gt(0).rename("dei_public_claimer")
    df = pd.DataFrame(claim)
    pay = p2.pivot(index="ticker", columns="year", values="pay_diversity_inclusion")
    had = (pay[[2022, 2023]] > 0).any(axis=1)
    df["dei_pay_2022_23"] = had
    df["dei_pay_2024"] = (pay[2024] > 0).where(pay[2024].notna())
    df["dei_pay_retained_2024"] = df["dei_pay_2024"].where(df["dei_pay_2022_23"])
    df["dei_emphasis_pre"] = window_mean(p2, "rate_diversity_inclusion", [2021, 2022])
    df["dei_emphasis_2024"] = window_mean(p2, "rate_diversity_inclusion", [2024])
    df["dei_emphasis_change"] = df["dei_emphasis_2024"] - df["dei_emphasis_pre"]
    about24 = p1[p1["year"] == 2024].set_index("ticker")["theme_diversity_inclusion"]
    df["dei_about_page_2024"] = (about24 > 0).reindex(df.index)

    for outcome in ["dei_pay_retained_2024", "dei_emphasis_change"]:
        d = df.dropna(subset=[outcome])
        diff, p, n1, n0 = permutation_test(d[outcome].astype(float), d["dei_public_claimer"])
        tests.append({"crisis": "DEI backlash 2022-2024", "value": "diversity, equity & inclusion",
                      "outcome": outcome, "scope": "firms with the outcome defined",
                      "claimers_mean_change": d[d["dei_public_claimer"]][outcome].astype(float).mean(),
                      "nonclaimers_mean_change": d[~d["dei_public_claimer"]][outcome].astype(float).mean(),
                      "difference": diff, "p_value": p, "n_claimers": n1, "n_nonclaimers": n0})
    panel.append(df)
    return df


def wells_fargo(oai, p2):
    banks = oai[oai["sector"] == "Financials"]
    rows = []
    for y in range(2016, 2025):
        w = banks[(banks["ticker"] == "WFC") & (banks["year"] == y)]
        o = banks[(banks["ticker"] != "WFC") & (banks["year"] == y)]
        pw = p2[(p2["ticker"] == "WFC") & (p2["year"] == y)]
        po = p2[(p2["sector"] == "Financials") & (p2["ticker"] != "WFC") & (p2["year"] == y)]
        rows.append({"year": y,
                     "wfc_OAI_z": w["OAI_z"].mean(), "other_banks_OAI_z": o["OAI_z"].mean(),
                     "wfc_over_claiming": w["over_claiming"].mean(),
                     "other_banks_over_claiming": o["over_claiming"].mean(),
                     "wfc_integrity_per10k": pw["rate_integrity_ethics"].mean(),
                     "other_banks_integrity_per10k": po["rate_integrity_ethics"].mean(),
                     "wfc_customer_per10k": pw["rate_customer_focus"].mean(),
                     "other_banks_customer_per10k": po["rate_customer_focus"].mean()})
    return pd.DataFrame(rows).round(3)


def main():
    p1, p2, oai, rev = load()
    tests, panel = [], []
    covid(p1, p2, rev, tests, panel)
    dei = dei_backlash(p1, p2, tests, panel)

    t = pd.DataFrame(tests).round(4)
    t.to_csv(OUT / "crisis_tests.csv", index=False)
    pd.concat(panel, axis=1).round(4).to_csv(OUT / "crisis_company_panel.csv")
    wf = wells_fargo(oai, p2)
    wf.to_csv(OUT / "wells_fargo_case.csv", index=False)

    # H2 check: did measured alignment rise for everyone after COVID?
    o = oai.dropna(subset=["OAI_z"])
    pre, post = o[o["year"].isin([2019, 2020])], o[o["year"].isin([2021, 2022])]
    lines = ["PART 4 - DOES A CRISIS REVEAL AUTHENTIC VALUES?\n"]
    lines.append(f"Mean OAI_z 2019-2020: {pre['OAI_z'].mean():+.3f}; 2021-2022: {post['OAI_z'].mean():+.3f} "
                 f"(common shift after COVID-19)")
    lines.append("\nTESTS (difference = claimers minus non-claimers; permutation p, 10,000 shuffles)")
    lines.append(t.to_string(index=False))
    claim_pay = dei[dei["dei_public_claimer"] & dei["dei_pay_2022_23"]]
    lines.append(f"\nDEI public retention among claimers: About page still states DEI in 2024 for "
                 f"{dei[dei['dei_public_claimer']]['dei_about_page_2024'].mean():.0%} of claimers "
                 f"with a 2024 page; DEI pay link retained in 2024 for "
                 f"{claim_pay['dei_pay_retained_2024'].mean():.0%} of claimers that had one in 2022-23.")
    # Decoupling under pressure: among public DEI claimers that also had a DEI
    # pay link in 2022-23 (and a usable 2024 About page), what happened in 2024
    # to the public claim versus the pay commitment?
    c = claim_pay.dropna(subset=["dei_about_page_2024", "dei_pay_2024"]).copy()
    c["outcome_2024"] = np.select(
        [c["dei_about_page_2024"].astype(bool) & c["dei_pay_2024"].astype(bool),
         c["dei_about_page_2024"].astype(bool) & ~c["dei_pay_2024"].astype(bool),
         ~c["dei_about_page_2024"].astype(bool) & ~c["dei_pay_2024"].astype(bool)],
        ["kept both (consistent commitment)", "kept public claim, dropped pay link (decoupled)",
         "dropped both (consistent retreat)"], default="dropped public claim, kept pay link")
    c[["outcome_2024"]].to_csv(OUT / "dei_decoupling_2024.csv")
    lines.append(f"\nDEI DECOUPLING IN 2024 (public claimers with a 2022-23 DEI pay link, n={len(c)}):")
    for k, g in c.groupby("outcome_2024"):
        lines.append(f"  {k}: {len(g)} ({', '.join(g.index)})")
    lines.append("\nWELLS FARGO VS OTHER BANKS")
    lines.append(wf.to_string(index=False))
    text = "\n".join(lines)
    (OUT / "results.txt").write_text(text)
    print(text)


if __name__ == "__main__":
    main()
