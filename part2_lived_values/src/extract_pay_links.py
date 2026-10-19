"""
extract_pay_links.py
--------------------
Part 2, step 3 (LLM-assisted): which codebook values are actually TIED TO
EXECUTIVE PAY in each proxy's Compensation Discussion & Analysis (CD&A)?

Why an LLM here, when the rest of Part 2 is classical: a dictionary can count
how often "safety" appears in the pay section, but cannot tell "safety is 20%
of the annual bonus scorecard" from "the committee also considered safety" or
"no safety metric is used". That distinction - money behind a value versus
words about it - is exactly the "lived values" signal Part 3 needs, and it is
a reading-comprehension task. To stay within budget, only the CD&A section
(median ~12,000 words, not the whole ~50,000-word proxy) is sent, to Claude
Haiku 5.5, with a hard spending cap.

For each proxy the model lists every codebook category linked to executive
pay, with:
  - mechanism: "quantitative_metric" (an explicit, weighted or formulaic
    metric/goal in an incentive plan or scorecard) or "qualitative_factor"
    (considered in a discretionary or individual-performance assessment);
  - weight_percent: the stated weight in the plan, or -1 if not stated;
  - a verbatim evidence quote, verified against the text by code.

Output: output/pay_links.csv (one row per company-year x linked category) and
        output/pay_links_wide.csv (one row per company-year; 2 = quantitative
        metric, 1 = qualitative factor, 0 = not linked, blank = no CD&A).

Usage (from the repo root, with .venv active):
    python part2_lived_values/src/extract_pay_links.py [--limit N]
"""

import argparse
import json
import re
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import anthropic
import pandas as pd
from dotenv import load_dotenv

PART_DIR = Path(__file__).resolve().parents[1]
REPO_DIR = PART_DIR.parent
MANIFEST_CSV = PART_DIR / "output" / "proxy_manifest.csv"
RAW_DIR = PART_DIR / "data" / "raw" / "proxies"
CODEBOOK = json.loads((REPO_DIR / "data" / "codebook.json").read_text())
CACHE = PART_DIR / "output" / "llm_cache" / "pay_links.jsonl"
CATEGORY_IDS = [c["id"] for c in CODEBOOK["categories"]]

MODEL = "claude-haiku-5-5"       # budget choice; see Part 1 README
EFFORT = "low"                   # extraction from a supplied passage
PROMPT_VERSION = "pay-v2"
MAX_WORKERS = 4
MAX_COST_USD = 1.10              # hard cap (agreed budget ~$1)
PRICE_IN_PER_M, PRICE_OUT_PER_M = 0.10, 0.50
MIN_CDA_WORDS = 2000

load_dotenv(REPO_DIR / ".env")
client = anthropic.Anthropic()
_lock = threading.Lock()
_spent = {"usd": 0.0}

SYSTEM = """You read the Compensation Discussion & Analysis (CD&A) section of a U.S. company's
proxy statement and identify which of the following value categories are LINKED TO EXECUTIVE
PAY - i.e. used as a goal, metric, modifier or assessment factor that affects how much the
executives are paid. Mentions that do not affect pay (e.g. general descriptions of the
business, or of committee processes) do not count.

CATEGORIES
""" + "\n".join(f"- {c['id']}: {c['definition']}" for c in CODEBOOK["categories"]) + """

For each linked category report:
- mechanism: "quantitative_metric" if it is an explicit metric or goal with a weight, target or
  formula in an incentive plan or scorecard; "qualitative_factor" if it is considered in a
  discretionary, strategic or individual-performance assessment without a formula.
- weight_percent: the stated weight of that metric in the plan as a number (e.g. 10), or -1 if
  no weight is stated.
- evidence: one short quote (max ~30 words) copied exactly from ONE contiguous passage of the
  text. Do not join separate passages, do not use "..." and do not paraphrase.
Financial metrics (revenue, earnings, TSR, cash flow, returns) belong to performance_results.
List each category at most once (choose its strongest link). Return an empty list if none."""

SCHEMA = {
    "type": "object",
    "properties": {
        "links": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "category": {"type": "string", "enum": CATEGORY_IDS},
                    "mechanism": {"type": "string", "enum": ["quantitative_metric", "qualitative_factor"]},
                    "weight_percent": {"type": "number"},
                    "evidence": {"type": "string"},
                },
                "required": ["category", "mechanism", "weight_percent", "evidence"],
                "additionalProperties": False,
            },
        }
    },
    "required": ["links"],
    "additionalProperties": False,
}


def extract_cda(raw: str) -> str:
    """Same rule as mine_proxies.find_cda, but returns the original-case text:
    the longest span from a 'Compensation Discussion and Analysis' heading to
    the next 'Summary Compensation Table'."""
    low = raw.lower()
    starts = [m.start() for m in re.finditer(r"compensation discussion (and|&) analysis", low)]
    ends = [m.start() for m in re.finditer(r"summary compensation table", low)]
    best = ""
    for s in starts:
        e = next((e for e in ends if e > s), None)
        if e is not None and e - s > len(best):
            best = raw[s:e]
    return best if len(best.split()) >= MIN_CDA_WORDS else ""


def quote_support(quote: str, text_norm: str) -> float:
    """Share of the quote's 3-word phrases found in the text (1.0 = verbatim).
    Tolerant of whitespace/line breaks between table cells, but a paraphrased
    or invented quote scores low."""
    words = norm(quote).split()
    if len(words) < 3:
        return float(norm(quote) in text_norm)
    grams = [" ".join(words[i:i + 3]) for i in range(len(words) - 2)]
    return sum(g in text_norm for g in grams) / len(grams)


def norm(t: str) -> str:
    t = t.lower().replace("’", "'").replace("“", '"').replace("”", '"')
    return re.sub(r"\s+", " ", t).strip()


def call(cda: str, company: str, year: int) -> dict:
    with _lock:
        if _spent["usd"] >= MAX_COST_USD:
            raise RuntimeError(f"spending cap ${MAX_COST_USD:.2f} reached")
    resp = client.messages.create(
        model=MODEL, max_tokens=8000, system=SYSTEM,
        output_config={"effort": EFFORT, "format": {"type": "json_schema", "schema": SCHEMA}},
        messages=[{"role": "user", "content": f"COMPANY: {company}\nPROXY YEAR: {year}\n\nCD&A TEXT:\n<<<\n{cda}\n>>>"}],
    )
    cost = (resp.usage.input_tokens * PRICE_IN_PER_M + resp.usage.output_tokens * PRICE_OUT_PER_M) / 1e6
    with _lock:
        _spent["usd"] += cost
    if resp.stop_reason in ("refusal", "max_tokens"):
        raise RuntimeError(f"stop_reason={resp.stop_reason}")
    text = next(b.text for b in resp.content if b.type == "text")
    return {"result": json.loads(text), "model": resp.model, "cost_usd": round(cost, 6)}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=None)
    args = ap.parse_args()

    man = pd.read_csv(MANIFEST_CSV)
    man = man[man["status"] == "ok"]
    CACHE.parent.mkdir(parents=True, exist_ok=True)
    cache = {}
    if CACHE.exists():
        for line in CACHE.read_text().splitlines():
            r = json.loads(line)
            if r["prompt_version"] == PROMPT_VERSION:
                cache[r["key"]] = r

    docs = {}
    for _, m in man.iterrows():
        raw = (RAW_DIR / m["text_file"]).read_text(encoding="utf-8")
        docs[(m["ticker"], int(m["year"]))] = (m, extract_cda(raw))
    todo = [k for k, (_, cda) in docs.items() if cda and f"{k[0]}|{k[1]}" not in cache]
    if args.limit:
        todo = todo[: args.limit]
    print(f"{len(todo)} CD&A sections to process ({len(cache)} cached)", flush=True)

    def work(k):
        m, cda = docs[k]
        out = call(cda, m["company_name"], k[1])
        rec = {"key": f"{k[0]}|{k[1]}", "prompt_version": PROMPT_VERSION, **out}
        with _lock, open(CACHE, "a") as f:
            f.write(json.dumps(rec) + "\n")
        return rec

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as pool:
        futs = {pool.submit(work, k): k for k in todo}
        for i, fut in enumerate(as_completed(futs), 1):
            try:
                rec = fut.result()
                cache[rec["key"]] = rec
                if i % 25 == 0:
                    print(f"  {i}/{len(todo)}  spent ${_spent['usd']:.3f}", flush=True)
            except Exception as exc:
                print(f"  {futs[fut]} FAILED: {exc}", flush=True)

    # Assemble long and wide outputs, verifying every quote against the CD&A text
    long_rows, wide_rows = [], []
    for (t, y), (m, cda) in sorted(docs.items()):
        wide = {"ticker": t, "company_name": m["company_name"], "sector": m["sector"], "year": y,
                "cda_found": bool(cda)}
        rec = cache.get(f"{t}|{y}")
        if cda and rec:
            cda_norm = norm(cda)
            for c in CATEGORY_IDS:
                wide[f"pay_{c}"] = 0
            for l in rec["result"]["links"]:
                support = quote_support(l["evidence"], cda_norm)
                long_rows.append({"ticker": t, "year": y, "sector": m["sector"], **l,
                                  "quote_support": round(support, 3),
                                  "quote_verified": support >= 0.8})
                wide[f"pay_{l['category']}"] = 2 if l["mechanism"] == "quantitative_metric" else 1
        wide_rows.append(wide)
    pd.DataFrame(long_rows).to_csv(PART_DIR / "output" / "pay_links.csv", index=False)
    wide_df = pd.DataFrame(wide_rows)
    wide_df.to_csv(PART_DIR / "output" / "pay_links_wide.csv", index=False)

    # Merge the pay columns into the main Part 2 dataset (proxy_dataset.csv,
    # written by mine_proxies.py) so Part 2 has a single analysis-ready table.
    main_csv = PART_DIR / "output" / "proxy_dataset.csv"
    if main_csv.exists():
        main = pd.read_csv(main_csv)
        pay_cols = [f"pay_{c}" for c in CATEGORY_IDS]
        main = main.drop(columns=[c for c in pay_cols if c in main.columns])
        main = main.merge(wide_df[["ticker", "year"] + pay_cols], on=["ticker", "year"], how="left")
        main.to_csv(main_csv, index=False)
        print(f"Merged {len(pay_cols)} pay columns into {main_csv.name}")
    total = sum(r.get("cost_usd", 0) for r in cache.values())
    ver = pd.DataFrame(long_rows)["quote_verified"].mean() if long_rows else float("nan")
    print(f"\nDone. Spend this run ${_spent['usd']:.3f}; all cached results ${total:.3f}. "
          f"Quotes verified: {ver:.1%}")


if __name__ == "__main__":
    main()
