# DRB-II Benchmark — Deferred Work

The pilot run covers the **default condition** at **N=1** (5 tasks: idx={4, 16, 42, 52, 68}).
This file tracks the remaining ablation matrix agreed with the user.

## Status legend

- [ ] not started
- [x] done
- ~~strikethrough~~ = declined (with reason)

---

## Ablation matrix (agreed)

| # | Ablation                        | Status | N | Code change?     | Tests                                |
| - | ------------------------------- | ------ | - | ---------------- | ------------------------------------ |
| 1 | Default rerun (variance)        | [ ]    | 3 | no               | Noise floor / methodology            |
| 2 | A3 — warm memory pass           | [ ]    | 3 | no               | Claim 4 (EMA earns its keep)         |
| 3 | A_TREE — blind expansion        | [ ]    | 3 | yes (~10 LoC)    | Claim 1 (review-guided expansion)    |
| 4 | A_ELO — sort-by-score           | [ ]    | 3 | yes (~5 LoC)     | Claim 2 (Elo ranking)                |
| 5 | HF baselines (Perplexity, Qwen) | [ ]    | — | no (judge only)  | External comparison anchor           |

**Total compute estimate: ~3.5–4 hours wall-clock, ~$5 in DeepSeek.**

Declined items are at the bottom with reasons.

## Code-change contract (applies to A_TREE and A_ELO)

Both ablations require code changes in `evoresearcher/`. To keep the existing
agent's behavior unaffected:

- **Opt-in only.** Add a boolean flag to `ResearchAgent.__init__` defaulting to
  `False`. When the flag is `False`, the code path is bit-identical to today's.
- **Single branching point.** The flag gates exactly one `if`/`else` inside the
  affected method (`_expand_from_review` for A_TREE, the ranking call site for
  A_ELO). No other functions or modules touched in `evoresearcher/`.
- **Plumb-through, don't refactor.** Add the matching CLI flag in `main.py` and
  `benchmarks/drb2/run_evoresearcher.py`; pass it straight to `ResearchAgent`.
  Don't rename existing parameters, don't restructure call sites, don't add
  abstractions for "future ablations".
- **Tests stay green.** The existing tests in `tests/` (especially
  `test_review_guided_tree_unit.py`) must continue to pass without modification.
- **No interaction effects.** A_TREE and A_ELO flags are independent — setting
  both does the union, neither implies the other. They live as separate
  arguments, not a single "mode" enum.
- **Reversible.** Changes can be reverted by deleting the new arguments. No
  schema migrations, no memory file changes, no output format changes.

These are documentation contracts — verify them when reviewing the diff before
running anything.

---

## P0 — Run order

Execute in this order. Each step's outputs feed into later analysis.

### [ ] Step 1: Default rerun at N=3 — noise floor

Establishes the variance band. Every other ablation's "did it help?" claim is
gated on whether the delta exceeds this noise band.

```bash
# Wipe memory + report dir for a clean start
rm -rf memory DeepResearch-Bench-II/report/evoresearcher_n3
cd EvoResearcher_EECS6895
.venv/bin/python benchmarks/drb2/run_evoresearcher.py \
    --trials 3 \
    --tree-depth 2 --branching-factor 2 --max-sources 6 \
    --label evoresearcher_n3
.venv/bin/python benchmarks/drb2/evaluate_with_deepseek.py --label evoresearcher_n3
.venv/bin/python benchmarks/drb2/aggregate.py --out-prefix pilot_n3
```

Expected: ~70 min. This is also the **cold pass** of A3 (memory is empty for the
whole run because we wiped it at the start). We re-use these results for A3.

### [ ] Step 2: A3 — warm memory pass at N=3

Run the same 5 prompts at N=3 again on the SAME memory dir (do NOT wipe). The
ideation_memory and proposal_memory now contain entries from Step 1, so each
new run starts with `top_k=3` retrieved hits surfaced in the research/proposal
prompts. Compare scores against Step 1 to measure EMA gain.

```bash
# CRITICAL: do NOT wipe memory/ between Step 1 and Step 2.
# Only wipe the report dir so files don't collide.
rm -rf DeepResearch-Bench-II/report/evoresearcher_warm_n3
.venv/bin/python benchmarks/drb2/run_evoresearcher.py \
    --trials 3 \
    --tree-depth 2 --branching-factor 2 --max-sources 6 \
    --label evoresearcher_warm_n3
.venv/bin/python benchmarks/drb2/evaluate_with_deepseek.py --label evoresearcher_warm_n3
.venv/bin/python benchmarks/drb2/aggregate.py --out-prefix pilot_warm_n3
```

Expected: ~70 min.

**Caveat to note in the report:** the 5 pilot tasks span 5 different themes
(Finance / Sci&Tech / Software / Education / Health), so memory hit semantic
similarity will be low. Even if EMA "works", the warm-vs-cold delta could be
small. A more favorable test would be 5 tasks in the same theme.

### [ ] Step 3: A_TREE — blind expansion at N=3

**Requires code change** in `evoresearcher/agents/research_agent.py`:

- Add a constructor flag `expansion_blind: bool = False` to `ResearchAgent`.
- When `expansion_blind=True`, `_expand_from_review` builds a prompt that
  *omits* `Parent weakest dimension` and `Parent review feedback`, and asks
  for two arbitrary children (system prompt rewritten to drop the
  refine-vs-alternative structure).
- Plumb the flag through `main.py` (new CLI flag) and add a matching
  `--blind-expansion` to the driver `run_evoresearcher.py`.

Then:

```bash
rm -rf memory DeepResearch-Bench-II/report/evoresearcher_blind_n3
.venv/bin/python benchmarks/drb2/run_evoresearcher.py \
    --trials 3 --blind-expansion \
    --tree-depth 2 --branching-factor 2 --max-sources 6 \
    --label evoresearcher_blind_n3
.venv/bin/python benchmarks/drb2/evaluate_with_deepseek.py --label evoresearcher_blind_n3
.venv/bin/python benchmarks/drb2/aggregate.py --out-prefix pilot_blind_n3
```

Expected: ~70 min run + ~30 min code+test = ~100 min total.

### [ ] Step 4: A_ELO — sort-by-score at N=3

**Requires code change** in `evoresearcher/agents/research_agent.py`:

- Add a constructor flag `skip_elo: bool = False`.
- When `skip_elo=True`, replace the `run_elo_tournament(...)` call with
  `ranked = sorted(leaf_ideas, key=lambda i: -i.total_score)` and return an
  empty `elo_matches` list.
- Plumb a `--no-elo` flag through `main.py` and the driver.

Then:

```bash
rm -rf memory DeepResearch-Bench-II/report/evoresearcher_noelo_n3
.venv/bin/python benchmarks/drb2/run_evoresearcher.py \
    --trials 3 --no-elo \
    --tree-depth 2 --branching-factor 2 --max-sources 6 \
    --label evoresearcher_noelo_n3
.venv/bin/python benchmarks/drb2/evaluate_with_deepseek.py --label evoresearcher_noelo_n3
.venv/bin/python benchmarks/drb2/aggregate.py --out-prefix pilot_noelo_n3
```

Expected: ~60 min (saves the ~6 Elo LLM calls per task) + ~20 min code+test ≈ ~80 min.

### [ ] Step 5: HF baselines — re-grade Perplexity + Qwen-3-Max under DeepSeek judge

**Conditional on PDF→idx mapping working.** The HF dataset
`muset-ai/DeepResearch-Bench-II-Dataset` has 135 PDFs across two `label`
classes (Perplexity-Research, Qwen-3-Max-DeepResearch) but an empty README.
First step is a 30-min feasibility check to confirm we can identify which PDFs
correspond to our pilot indices {4, 16, 42, 52, 68}.

```bash
# Feasibility: download a few rows, inspect filenames / PDF metadata
python3 -c "from datasets import load_dataset; ds = load_dataset('muset-ai/DeepResearch-Bench-II-Dataset', split='train[:5]'); print(ds.info, ds[0].keys())"

# If mapping works:
# 1. Extract text from each baseline PDF -> .md
# 2. Drop them at DeepResearch-Bench-II/report/perplexity_research/idx-N.md
#    and .../report/qwen3_max/idx-N.md
# 3. Grade with the same judge:
.venv/bin/python benchmarks/drb2/evaluate_with_deepseek.py --label perplexity_research
.venv/bin/python benchmarks/drb2/evaluate_with_deepseek.py --label qwen3_max
.venv/bin/python benchmarks/drb2/aggregate.py --out-prefix with_baselines
```

Expected: ~30 min feasibility + ~15 min download/extract + ~15 min judge ≈ ~60 min.

**Why we re-grade and don't use published numbers:** DRB-II's leaderboard scores
are graded by Gemini 2.5 Pro. EvoResearcher's pilot score is graded by DeepSeek.
Cross-judge numbers aren't comparable. Re-grading both baselines under the
DeepSeek judge gives a like-for-like comparison.

### [ ] Step 6: Final aggregation across all conditions

```bash
.venv/bin/python benchmarks/drb2/aggregate.py --out-prefix final_matrix
```

The aggregator already groups by `label` and reports mean ± std per condition.
The output `final_matrix_summary.md` will have one row per condition for the
report.

---

## Declined items

### ~~A1 — search OFF baseline~~

Just measures "without grounding, Recall tanks" — obvious from the architecture
and doesn't validate any specific design claim.

### ~~A2 — depth=1 ablation~~

Signal overlaps significantly with A_TREE. With A_TREE on the matrix, the depth
sweep is mostly redundant — a depth=2 → depth=1 drop conflates "less search"
with "less guidance", whereas A_TREE isolates the guidance contribution
directly.

### ~~A_DUAL — single combined memory~~

The dual-vs-single split-store distinction is too subtle to detect at our 5-task
cross-domain pilot scale. Most likely outcome is a clean null. Low information
value relative to cost. (If we ever scale up to many same-theme tasks, revisit.)

### ~~Cross-judge sanity check~~

Would require Gemini API access (or another judge) we don't have. Methodology
footnote, not a contribution. Acceptable to acknowledge in the report as
"DeepSeek-as-judge is a proxy; cross-judge agreement was not measured."

### ~~Scale to all 66 EN tasks (or +66 ZH)~~

Out of scope for this pilot. The 5-task matrix at N=3 already gives statistically
useful comparisons for the report.

---

## Robustness improvements (P3 — engineering, not benchmarking)

### [ ] Make `proposal_agent`/`pdf.py` graceful on LaTeX failure

The DRB-II driver uses markdown so this doesn't block the pilot, but in the
default `python -m evoresearcher.main` flow, a malformed math fragment from the
LLM (e.g. `+$L\_0$$`) raises `RuntimeError` and aborts the run. Cleaner would
be to log + skip PDF instead of raising, since markdown is always usable.

### [ ] DDG search resilience

DuckDuckGo HTML scraping gets rate-limited on long sequences of runs. Before
ever scaling beyond the 5-task pilot, swap for a proper search API
(Tavily / Serper / Brave) and set retry+backoff.

### [ ] LLM JSON-parse retry in `llm.py`

`LLMClient._extract_json` raises on the first malformed response. We saw 3
failures during the pilot from this (idx-16 once, idx-62 twice). A simple
"retry with stricter system prompt + temperature=0" path on JSON failure would
have caught all three. Worth doing before any large-scale run.
