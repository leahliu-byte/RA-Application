"""
analyze_snapshots.py
--------------------
Stage 6-7 of the Part 1 pipeline: LLM-assisted analysis of every downloaded
About-page snapshot, and assembly of the final company-year dataset.

The assignment asks, for each snapshot, for (a) whether the page changed from
the prior year, (b) which value/thematic categories are present, and (c) notable
linguistic shifts over time. This script does:

  1. CHANGE DETECTION, two layers
     - Non-AI: compare each snapshot with the company's previous available
       snapshot (exact match after normalisation + a word-level similarity
       ratio, 0-1). Identical texts need no LLM call.
     - LLM: when the text differs, classify the change as "cosmetic" (wording,
       numbers, layout) or "substantive" (values, mission, commitments or
       self-description changed) and summarise it in one sentence.
  2. THEME CODING (LLM) against the shared codebook (data/codebook.json):
     for each category present, a salience (1 = mentioned, 2 = emphasised) and
     a VERBATIM evidence quote. Every quote is then checked against the page
     text by code; unverifiable quotes are counted, so hallucinated evidence is
     visible rather than silent.
     The same call also records whether the page actually looks like a general
     About page (a check on the rule-based selection - it changes nothing, it
     only documents).
  3. LINGUISTIC SHIFTS (LLM): one call per company with its snapshots in
     chronological order, returning a short note per year on notable shifts in
     vocabulary, framing and tone. These become `analyst_notes`.

Reproducibility: fixed prompts (PROMPT_VERSION), a fixed model ID, structured
JSON output enforced by a schema, and every raw LLM response cached in
output/llm_cache/*.jsonl - re-running the script reuses the cache and only
calls the API for snapshots not yet analysed.

Output: output/part1_dataset.csv - one row per company-year (450 rows).

Usage (from the repo root, with .venv active and ANTHROPIC_API_KEY in .env):
    python part1_stated_values/src/analyze_snapshots.py            # everything
    python part1_stated_values/src/analyze_snapshots.py --limit 3  # test run
"""

import argparse
import csv
import json
import re
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from difflib import SequenceMatcher
from pathlib import Path

import anthropic
from dotenv import load_dotenv

PART_DIR = Path(__file__).resolve().parents[1]
REPO_DIR = PART_DIR.parent
SNAPSHOTS_CSV = PART_DIR / "output" / "snapshots.csv"
CODEBOOK_JSON = REPO_DIR / "data" / "codebook.json"
CACHE_DIR = PART_DIR / "output" / "llm_cache"
SNAP_CACHE = CACHE_DIR / "snapshot_analysis.jsonl"
SHIFT_CACHE = CACHE_DIR / "company_shifts.jsonl"
OUTPUT_CSV = PART_DIR / "output" / "part1_dataset.csv"

# Claude Haiku 5.5: chosen for budget (the project's total API budget is $5).
# Codebook coding with verbatim evidence is a structured classification task
# well within a small model's ability, and the quote-verification check below
# makes weak evidence visible. Estimated cost for all of Part 1: ~$0.50.
MODEL = "claude-haiku-5-5"
EFFORT = "medium"           # classification against a codebook; medium is ample
PROMPT_VERSION = "p1-v1"    # bump when prompts change, so cached results are not mixed
MAX_WORKERS = 4             # parallel API calls

# Spending cap: the run stops making new API calls once estimated spend
# reaches this amount (USD). Prices per million tokens for Claude Haiku 5.5
# (prompts under 100K tokens).
MAX_COST_USD = 1.50
PRICE_IN_PER_M, PRICE_OUT_PER_M = 0.10, 0.50
_spent = {"usd": 0.0}

load_dotenv(REPO_DIR / ".env")
CODEBOOK = json.loads(CODEBOOK_JSON.read_text())
CATEGORY_IDS = [c["id"] for c in CODEBOOK["categories"]]
_lock = threading.Lock()


# ---- Prompts ---------------------------------------------------------------

def codebook_text() -> str:
    """Render the codebook as plain text for the system prompt."""
    lines = []
    for c in CODEBOOK["categories"]:
        lines.append(f"- {c['id']} ({c['name']}): {c['definition']}\n"
                     f"    Include: {c['include']}\n    Exclude: {c['exclude']}")
    rules = CODEBOOK["coding_rules"]
    return ("CATEGORIES\n" + "\n".join(lines) +
            f"\n\nCODING RULES\n- Present: {rules['present']}\n- Salience: {rules['salience']}"
            f"\n- Evidence: {rules['evidence']}")


SNAPSHOT_SYSTEM = f"""You are a research assistant coding corporate "About Us" web pages for an
academic study of the values companies state publicly. You apply a fixed codebook consistently
and conservatively, and you support every judgement with verbatim text from the page.

{codebook_text()}

TASKS FOR EACH PAGE
1. themes: list every category that is present on the CURRENT page, with salience (1 or 2) and
   one short verbatim quote (copied exactly, max ~30 words) that best shows it. Omit categories
   that are absent. Do not infer values the page does not express.
2. change_from_prior: if a PRIOR page is given, classify the change from prior to current:
   "cosmetic" = wording edits, updated figures/dates, reordering or layout, but the same values,
   mission and self-description; "substantive" = values, themes, mission, commitments or
   self-description added, removed or reframed. Summarise the change in one sentence. If no
   prior page is given, use "no_prior" and an empty summary.
3. about_page_check: does the CURRENT page read like a company's general About / company
   overview page (self-description, mission, values, overview)? Answer false for e.g. a social
   media profile, a login wall, a sub-organisation's page, a product page or a news listing,
   and say briefly what it is instead."""

SNAPSHOT_SCHEMA = {
    "type": "object",
    "properties": {
        "themes": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "category": {"type": "string", "enum": CATEGORY_IDS},
                    "salience": {"type": "integer", "enum": [1, 2]},
                    "evidence": {"type": "string"},
                },
                "required": ["category", "salience", "evidence"],
                "additionalProperties": False,
            },
        },
        "change_from_prior": {
            "type": "object",
            "properties": {
                "type": {"type": "string", "enum": ["no_prior", "cosmetic", "substantive"]},
                "summary": {"type": "string"},
            },
            "required": ["type", "summary"],
            "additionalProperties": False,
        },
        "about_page_check": {
            "type": "object",
            "properties": {
                "is_about_page": {"type": "boolean"},
                "note": {"type": "string"},
            },
            "required": ["is_about_page", "note"],
            "additionalProperties": False,
        },
    },
    "required": ["themes", "change_from_prior", "about_page_check"],
    "additionalProperties": False,
}

SHIFT_SYSTEM = """You are a research assistant analysing how one company's "About Us" page
language evolved from 2016 to 2024, for an academic study of corporate stated values.
You receive the company's available snapshots in chronological order.

For EACH year provided, write one concise analyst note (1-3 sentences) on notable linguistic
shifts relative to the previous available snapshot: new or dropped vocabulary (e.g. "purpose",
"stakeholders", "net zero", "AI", "inclusion"), changes in framing (e.g. shareholder- vs
stakeholder-oriented, product vs mission), tone, length or emphasis. Quote short phrases where
useful. For the first year, describe the baseline framing briefly. If nothing notable changed,
say "No notable linguistic shift from <prior year>." Be factual and grounded in the text; do
not speculate about causes. Also give a 2-4 sentence company_summary of the overall trajectory."""

SHIFT_SCHEMA = {
    "type": "object",
    "properties": {
        "company_summary": {"type": "string"},
        "year_notes": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {"year": {"type": "integer"}, "note": {"type": "string"}},
                "required": ["year", "note"],
                "additionalProperties": False,
            },
        },
    },
    "required": ["company_summary", "year_notes"],
    "additionalProperties": False,
}


# ---- LLM call --------------------------------------------------------------

client = anthropic.Anthropic()


class BudgetExceeded(RuntimeError):
    pass


def call_llm(system: str, user: str, schema: dict) -> dict:
    """One structured-output request, with the spending cap enforced before the
    call and actual token usage added to the running total after it."""
    with _lock:
        if _spent["usd"] >= MAX_COST_USD:
            raise BudgetExceeded(f"spending cap ${MAX_COST_USD:.2f} reached")
    response = client.messages.create(
        model=MODEL,
        max_tokens=16000,
        system=system,
        output_config={"effort": EFFORT,
                       "format": {"type": "json_schema", "schema": schema}},
        messages=[{"role": "user", "content": user}],
    )
    cost = (response.usage.input_tokens * PRICE_IN_PER_M
            + response.usage.output_tokens * PRICE_OUT_PER_M) / 1e6
    with _lock:
        _spent["usd"] += cost
    if response.stop_reason == "refusal":
        raise RuntimeError(f"refused: {response.stop_details}")
    if response.stop_reason == "max_tokens":
        raise RuntimeError("output truncated (max_tokens)")
    text = next(b.text for b in response.content if b.type == "text")
    return {"result": json.loads(text), "model": response.model,
            "usage": {"input": response.usage.input_tokens, "output": response.usage.output_tokens,
                      "cost_usd": round(cost, 6)}}


# ---- Helpers ---------------------------------------------------------------

def norm(text: str) -> str:
    """Normalise for comparison: lowercase, unify quotes/dashes, collapse whitespace."""
    text = text.lower().replace("’", "'").replace("‘", "'")
    text = text.replace("“", '"').replace("”", '"').replace("–", "-").replace("—", "-")
    return re.sub(r"\s+", " ", text).strip()


def similarity(a: str, b: str) -> float:
    """Word-level similarity ratio in [0, 1] (1 = identical word sequence)."""
    return round(SequenceMatcher(None, a.split(), b.split(), autojunk=False).ratio(), 4)


def load_cache(path: Path) -> dict:
    out = {}
    if path.exists():
        for line in path.read_text().splitlines():
            rec = json.loads(line)
            if rec.get("prompt_version") == PROMPT_VERSION:
                out[rec["key"]] = rec
    return out


def append_cache(path: Path, rec: dict) -> None:
    with _lock, open(path, "a") as f:
        f.write(json.dumps(rec) + "\n")


# ---- Main ------------------------------------------------------------------

def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=None,
                    help="analyse only the first N snapshots and N companies (test run)")
    args = ap.parse_args()

    with open(SNAPSHOTS_CSV, newline="") as f:
        rows = list(csv.DictReader(f))
    CACHE_DIR.mkdir(parents=True, exist_ok=True)

    # Step 1 (non-AI): link each usable snapshot to the company's previous usable one
    ok_rows = [r for r in rows if r["status"] == "ok"]
    prev_of: dict[tuple, dict | None] = {}
    last: dict[str, dict] = {}
    for r in sorted(ok_rows, key=lambda r: (r["ticker"], int(r["year"]))):
        prev_of[(r["ticker"], r["year"])] = last.get(r["ticker"])
        last[r["ticker"]] = r

    # Step 2: per-snapshot LLM analysis (themes + change type + page check)
    snap_cache = load_cache(SNAP_CACHE)
    todo = []
    for r in ok_rows:
        key = f"{r['ticker']}|{r['year']}"
        prev = prev_of[(r["ticker"], r["year"])]
        identical = prev is not None and norm(prev["page_text_clean"]) == norm(r["page_text_clean"])
        if key not in snap_cache and not identical:
            todo.append((key, r, prev))
    if args.limit:
        todo = todo[: args.limit]

    def run_snapshot(key, r, prev):
        user = f"COMPANY: {r['company_name']} ({r['ticker']}), {r['sector']}\nYEAR: {r['year']}\n\n"
        if prev is not None:
            user += f"PRIOR PAGE ({prev['year']}):\n<<<\n{prev['page_text_clean']}\n>>>\n\n"
        user += f"CURRENT PAGE ({r['year']}):\n<<<\n{r['page_text_clean']}\n>>>"
        out = call_llm(SNAPSHOT_SYSTEM, user, SNAPSHOT_SCHEMA)
        rec = {"key": key, "prompt_version": PROMPT_VERSION, **out}
        append_cache(SNAP_CACHE, rec)
        return key, rec

    print(f"Snapshot analysis: {len(todo)} API calls needed "
          f"({len(snap_cache)} cached; identical-to-prior pages reuse the prior result)", flush=True)
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as pool:
        futures = [pool.submit(run_snapshot, *t) for t in todo]
        for i, fut in enumerate(as_completed(futures), start=1):
            try:
                key, rec = fut.result()
                snap_cache[key] = rec
                print(f"  [{i}/{len(todo)}] {key}", flush=True)
            except Exception as exc:                       # keep going; row stays un-analysed
                print(f"  [{i}/{len(todo)}] FAILED: {exc}", flush=True)

    # Step 3: per-company linguistic-shift analysis
    shift_cache = load_cache(SHIFT_CACHE)
    tickers = sorted({r["ticker"] for r in ok_rows})
    shift_todo = [t for t in tickers if t not in shift_cache]
    if args.limit:
        shift_todo = shift_todo[: args.limit]

    def run_shift(t):
        series = sorted((r for r in ok_rows if r["ticker"] == t), key=lambda r: int(r["year"]))
        user = f"COMPANY: {series[0]['company_name']} ({t}), {series[0]['sector']}\n\n"
        for r in series:
            user += f"=== {r['year']} (source: {r['selected_url']}) ===\n{r['page_text_clean']}\n\n"
        out = call_llm(SHIFT_SYSTEM, user, SHIFT_SCHEMA)
        rec = {"key": t, "prompt_version": PROMPT_VERSION, **out}
        append_cache(SHIFT_CACHE, rec)
        return t, rec

    print(f"Shift analysis: {len(shift_todo)} API calls needed ({len(shift_cache)} cached)", flush=True)
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as pool:
        futures = [pool.submit(run_shift, t) for t in shift_todo]
        for fut in as_completed(futures):
            try:
                t, rec = fut.result()
                shift_cache[t] = rec
                print(f"  shifts done: {t}", flush=True)
            except Exception as exc:
                print(f"  shift FAILED: {exc}", flush=True)

    # Step 4: assemble the dataset (one row per company-year, all 450)
    fields = ["ticker", "company_name", "sector", "year", "page_text_clean",
              "changed_from_prior", "theme_categories", "analyst_notes",
              "status", "status_reason", "selected_url", "tier", "capture_timestamp",
              "archive_url", "word_count", "prior_year_compared", "similarity_to_prior",
              "change_type", "change_summary", "about_page_check", "about_page_note",
              "theme_evidence", "n_quotes_unverified"] + [f"theme_{c}" for c in CATEGORY_IDS]
    out_rows = []
    resolved: dict[tuple, dict] = {}   # (ticker, year) -> analysis used (for identical-page reuse)
    for r in sorted(rows, key=lambda r: (r["ticker"], int(r["year"]))):
        row = {k: r.get(k, "") for k in ["ticker", "company_name", "sector", "year", "page_text_clean",
                                          "status", "status_reason", "selected_url", "tier",
                                          "capture_timestamp", "archive_url", "word_count"]}
        if r["status"] != "ok":
            out_rows.append(row)
            continue

        key = f"{r['ticker']}|{r['year']}"
        prev = prev_of[(r["ticker"], r["year"])]
        if prev is not None:
            row["prior_year_compared"] = prev["year"]
            row["similarity_to_prior"] = similarity(norm(prev["page_text_clean"]), norm(r["page_text_clean"]))
        identical = prev is not None and norm(prev["page_text_clean"]) == norm(r["page_text_clean"])

        if identical and (prev["ticker"], prev["year"]) in resolved:
            analysis = resolved[(prev["ticker"], prev["year"])]       # same text -> same coding
            change_type, change_summary = "none", "Text identical to prior snapshot."
        elif key in snap_cache:
            analysis = snap_cache[key]["result"]
            change_type = analysis["change_from_prior"]["type"]
            change_summary = analysis["change_from_prior"]["summary"]
        else:
            out_rows.append({**row, "analyst_notes": "LLM analysis not available for this snapshot"})
            continue
        resolved[(r["ticker"], r["year"])] = analysis

        row["change_type"] = change_type
        row["change_summary"] = change_summary
        row["changed_from_prior"] = ("" if prev is None else
                                     "False" if change_type == "none" else "True")

        themes = analysis["themes"]
        page_norm = norm(r["page_text_clean"])
        unverified = sum(1 for t in themes if norm(t["evidence"]) not in page_norm)
        # "none" (not blank) when the page was analysed and no value was found,
        # so it cannot be confused with a missing snapshot.
        row["theme_categories"] = ";".join(sorted({t["category"] for t in themes})) or "none"
        row["theme_evidence"] = json.dumps({t["category"]: t["evidence"] for t in themes}, ensure_ascii=False)
        row["n_quotes_unverified"] = unverified
        for c in CATEGORY_IDS:
            row[f"theme_{c}"] = max([t["salience"] for t in themes if t["category"] == c], default=0)
        row["about_page_check"] = analysis["about_page_check"]["is_about_page"]
        row["about_page_note"] = analysis["about_page_check"]["note"]

        shift = shift_cache.get(r["ticker"])
        if shift:
            notes = {n["year"]: n["note"] for n in shift["result"]["year_notes"]}
            row["analyst_notes"] = notes.get(int(r["year"]), "")
        out_rows.append(row)

    with open(OUTPUT_CSV, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows({k: v for k, v in row.items() if k in fields} for row in out_rows)

    # Company-level summaries alongside the dataset
    with open(PART_DIR / "output" / "company_shift_summaries.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["ticker", "company_summary"])
        for t in tickers:
            if t in shift_cache:
                w.writerow([t, shift_cache[t]["result"]["company_summary"]])

    n_ok = sum(1 for r in out_rows if r.get("change_type"))
    print(f"\nWrote {len(out_rows)} rows ({n_ok} analysed snapshots) -> {OUTPUT_CSV}")
    print(f"API spend this run: ${_spent['usd']:.3f} (cap ${MAX_COST_USD:.2f})")


if __name__ == "__main__":
    main()
