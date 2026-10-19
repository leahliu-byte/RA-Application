"""
make_figures.py
---------------
Static figures (PNG) for the written summaries of Parts 1-3. Each figure is
written to that part's output/figures/ folder.

Design choices: one y-axis per chart; categorical colours assigned in a fixed
order from a colour-blind-validated reference palette (blue, orange, aqua,
yellow, magenta); every series is also named in a legend or a direct label so
identity never depends on colour alone; thin marks and a recessive grid.

Usage (from the repo root, with .venv active):
    python make_figures.py
"""

import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

REPO = Path(__file__).resolve().parent
SERIES = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4"]   # fixed categorical order
MUTED = "#a3a29b"
TEXT, TEXT2, GRID, SURFACE = "#0b0b0b", "#52514e", "#e6e5e0", "#fcfcfb"
NAMES = {c["id"]: c["name"] for c in json.loads((REPO / "data" / "codebook.json").read_text())["categories"]}

plt.rcParams.update({
    "figure.facecolor": SURFACE, "axes.facecolor": SURFACE, "savefig.facecolor": SURFACE,
    "axes.edgecolor": GRID, "axes.labelcolor": TEXT2, "xtick.color": TEXT2, "ytick.color": TEXT2,
    "text.color": TEXT, "font.size": 10, "axes.titlesize": 12, "axes.titleweight": "bold",
    "axes.titlelocation": "left", "axes.spines.top": False, "axes.spines.right": False,
    "axes.grid": True, "grid.color": GRID, "grid.linewidth": 0.8, "legend.frameon": False,
})


def end_labels(ax, items, x, min_gap):
    """Direct labels at the right end of lines, nudged apart so they never overlap.
    items: list of (y_value, text)."""
    items = sorted(items)
    placed = []
    for y, text in items:
        if placed and y - placed[-1] < min_gap:
            y = placed[-1] + min_gap
        placed.append(y)
        ax.text(x, y, text, color=TEXT2, va="center", fontsize=8)


def save(fig, part: str, name: str) -> None:
    out = REPO / part / "output" / "figures"
    out.mkdir(parents=True, exist_ok=True)
    fig.savefig(out / name, dpi=200, bbox_inches="tight")
    plt.close(fig)
    print("wrote", out / name)


def fig_part1() -> None:
    """Share of About pages stating each value, 2016 vs 2024 (dumbbell)."""
    d = pd.read_csv(REPO / "part1_stated_values" / "output" / "part1_dataset.csv")
    d = d[d["change_type"].notna()]
    cats = list(NAMES)
    share = {y: [(d[d.year == y][f"theme_{c}"] > 0).mean() * 100 for c in cats] for y in (2016, 2024)}
    order = sorted(range(len(cats)), key=lambda i: share[2024][i])
    fig, ax = plt.subplots(figsize=(7.5, 5))
    for k, i in enumerate(order):
        ax.plot([share[2016][i], share[2024][i]], [k, k], color=GRID, lw=2, zorder=1)
    ax.scatter([share[2016][i] for i in order], range(len(order)), s=60, color=MUTED,
               label="2016", zorder=2, edgecolor=SURFACE, linewidth=2)
    ax.scatter([share[2024][i] for i in order], range(len(order)), s=60, color=SERIES[0],
               label="2024", zorder=3, edgecolor=SURFACE, linewidth=2)
    for k, i in enumerate(order):
        ax.text(share[2024][i] + (2 if share[2024][i] >= share[2016][i] else -2), k,
                f"{share[2024][i]:.0f}%", va="center",
                ha="left" if share[2024][i] >= share[2016][i] else "right", color=TEXT2, fontsize=8)
    ax.set_yticks(range(len(order)), [NAMES[cats[i]] for i in order])
    ax.set_xlim(0, 100)
    ax.set_xlabel("% of companies whose About page states the value")
    ax.grid(axis="y", visible=False)
    ax.legend(loc="lower right")
    ax.set_title("Values stated on About pages, 2016 vs 2024")
    save(fig, "part1_stated_values", "fig1_values_2016_vs_2024.png")


def fig_part2() -> None:
    """Proxy language (left) and executive-pay metrics (right) for three ESG themes."""
    p = pd.read_csv(REPO / "part2_lived_values" / "output" / "proxy_dataset.csv")
    pay = pd.read_csv(REPO / "part2_lived_values" / "output" / "pay_links_wide.csv")
    pay = pay[pay["cda_found"]]
    themes = [("environment_sustainability", SERIES[0]), ("diversity_inclusion", SERIES[1]),
              ("employee_wellbeing_development", SERIES[2])]
    years = sorted(p["year"].unique())

    fig, ax = plt.subplots(figsize=(7.5, 4.2))
    labels = []
    for c, col in themes:
        y = p.groupby("year")[f"rate_{c}"].mean()
        ax.plot(years, y, color=col, lw=2, marker="o", ms=4, label=NAMES[c])
        labels.append((y.iloc[-1], NAMES[c]))
    y = p.groupby("year")["rate_esg_general"].mean()
    ax.plot(years, y, color=MUTED, lw=2, ls="--", label='The label "ESG" itself')
    labels.append((y.iloc[-1], '"ESG" label'))
    end_labels(ax, labels, years[-1] + 0.15, 1.2)
    for yr, lab in [(2021, "first proxies after\nGeorge Floyd"), (2024, "after affirmative-\naction ruling")]:
        ax.axvline(yr, color=TEXT2, lw=0.8, ls=":")
        ax.text(yr - 0.1, 0.4, lab, ha="right", va="bottom", fontsize=7, color=TEXT2)
    ax.set_xticks(years[::2])
    ax.set_xlim(years[0] - 0.3, years[-1] + 2.2)
    ax.set_ylabel("Mentions per 10,000 words (mean of 50 firms)")
    ax.legend(loc="upper left", fontsize=8)
    ax.set_title("How proxy statements talk about ESG themes, 2016-2024")
    save(fig, "part2_lived_values", "fig1_proxy_esg_language.png")

    fig, ax = plt.subplots(figsize=(7.5, 4.2))
    labels = []
    for c, col in themes + [("safety", SERIES[3])]:
        y = pay.groupby("year")[f"pay_{c}"].apply(lambda s: (s == 2).mean() * 100)
        ax.plot(years, y, color=col, lw=2, marker="o", ms=4, label=NAMES[c])
        labels.append((y.iloc[-1], NAMES[c]))
    end_labels(ax, labels, years[-1] + 0.15, 1.6)
    ax.set_xticks(years[::2])
    ax.set_xlim(years[0] - 0.3, years[-1] + 2.6)
    ax.set_ylim(0, None)
    ax.set_ylabel("% of companies with a weighted pay metric")
    ax.legend(loc="upper left", fontsize=8)
    ax.set_title("Values tied to executive pay (weighted metrics), 2016-2024")
    save(fig, "part2_lived_values", "fig2_pay_metrics.png")


def fig_part3() -> None:
    """Mean authenticity index per company, coloured by sector (dot plot)."""
    s = pd.read_csv(REPO / "part3_authenticity_index" / "output" / "company_summary.csv")
    s = s.sort_values("OAI_z_mean").reset_index(drop=True)
    sectors = ["Technology", "Financials", "Healthcare", "Consumer Discretionary", "Energy"]
    colors = dict(zip(sectors, SERIES))
    fig, ax = plt.subplots(figsize=(7.5, 9))
    ax.axvline(0, color=TEXT2, lw=0.8)
    for sec in sectors:
        sub = s[s["sector"] == sec]
        ax.scatter(sub["OAI_z_mean"], sub.index, s=46, color=colors[sec], label=sec,
                   edgecolor=SURFACE, linewidth=2, zorder=3)
    ax.set_yticks(s.index, s["company_name"], fontsize=8)
    ax.grid(axis="y", visible=False)
    ax.set_xlabel("Mean Organizational Authenticity Index (z-score; 0 = average)")
    ax.legend(loc="lower right", fontsize=8, title="Sector", title_fontsize=8)
    ax.set_title("Authenticity index by company, mean over 2016-2024")
    save(fig, "part3_authenticity_index", "fig1_oai_by_company.png")

    idx = pd.read_csv(REPO / "part3_authenticity_index" / "output" / "category_contributions.csv")
    idx = idx.sort_values("share_stated_but_unbacked")
    fig, ax = plt.subplots(figsize=(7.5, 4.6))
    ax.set_axisbelow(True)
    ax.barh([NAMES[c] for c in idx["category"]], idx["share_stated_but_unbacked"] * 100,
            color=SERIES[0], height=0.6)
    for k, v in enumerate(idx["share_stated_but_unbacked"] * 100):
        ax.text(v + 1, k, f"{v:.0f}%", va="center", fontsize=8, color=TEXT2)
    ax.grid(axis="y", visible=False)
    ax.set_xlim(0, 100)
    ax.set_xlabel("% of times a stated value has no proxy emphasis and no pay link")
    ax.set_title('Which stated values are most often "cheap talk"?')
    save(fig, "part3_authenticity_index", "fig2_cheap_talk_by_value.png")


def fig_part4() -> None:
    """COVID convergence (dumbbell) and DEI outcomes in 2024 (bars)."""
    d = pd.read_csv(REPO / "part4_proposal" / "output" / "crisis_company_panel.csv", index_col=0)
    g = d.groupby("covid_people_claimer")[["people_pay_pre", "people_pay_post"]].mean() * 100
    fig, ax = plt.subplots(figsize=(7.5, 2.8))
    labels = {True: "Claimed people values\non 2019 About page", False: "Did not claim them"}
    for k, claim in enumerate([True, False]):
        pre, post = g.loc[claim, "people_pay_pre"], g.loc[claim, "people_pay_post"]
        ax.plot([pre, post], [k, k], color=GRID, lw=2, zorder=1)
        ax.scatter([pre], [k], s=60, color=MUTED, zorder=2, edgecolor=SURFACE, linewidth=2,
                   label="2019-2020 (before COVID)" if k == 0 else None)
        ax.scatter([post], [k], s=60, color=SERIES[0], zorder=3, edgecolor=SURFACE, linewidth=2,
                   label="2021-2022 (after)" if k == 0 else None)
        ax.text(pre, k - 0.32, f"{pre:.0f}%", ha="center", fontsize=8, color=TEXT2)
        ax.text(post, k + 0.22, f"{post:.0f}%", ha="center", fontsize=8, color=TEXT2)
    ax.set_yticks([0, 1], [labels[True], labels[False]])
    ax.set_ylim(-0.6, 1.7)
    ax.set_xlim(0, 100)
    ax.grid(axis="y", visible=False)
    ax.set_xlabel("% of proxy years with an employee or safety pay link")
    ax.legend(loc="upper left", fontsize=8)
    ax.set_title("COVID-19: non-claimers caught up; claims did not predict the response")
    save(fig, "part4_proposal", "fig1_covid_convergence.png")

    c = pd.read_csv(REPO / "part4_proposal" / "output" / "dei_decoupling_2024.csv", index_col=0)
    order = ["kept both (consistent commitment)", "kept public claim, dropped pay link (decoupled)",
             "dropped both (consistent retreat)"]
    names = {"kept both (consistent commitment)": "Kept public claim and pay link",
             "kept public claim, dropped pay link (decoupled)": "Kept public claim, dropped pay link",
             "dropped both (consistent retreat)": "Dropped both"}
    counts = [int((c["outcome_2024"] == o).sum()) for o in order]
    firms = [", ".join(sorted(c.index[c["outcome_2024"] == o])) for o in order]
    fig, ax = plt.subplots(figsize=(7.5, 2.8))
    ax.set_axisbelow(True)
    ax.barh(range(3)[::-1], counts, color=[SERIES[2], SERIES[1], MUTED], height=0.6)
    for k, (n, f) in enumerate(zip(counts, firms)):
        ax.text(n + 0.1, 2 - k, f"{n}  ({f})", va="center", fontsize=8, color=TEXT2)
    ax.set_yticks(range(3)[::-1], [names[o] for o in order])
    ax.set_xlim(0, 9)
    ax.grid(axis="y", visible=False)
    ax.set_xlabel("Companies (public DEI claimers with a DEI pay link in 2022-23)")
    ax.set_title("DEI backlash, 2024: what companies kept")
    save(fig, "part4_proposal", "fig2_dei_2024_outcomes.png")


if __name__ == "__main__":
    fig_part1()
    fig_part2()
    fig_part3()
    fig_part4()
