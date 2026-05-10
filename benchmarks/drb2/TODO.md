# DRB-II Benchmark — Status

The ablation matrix agreed during the N=1 pilot is **complete**. Headline
results, methodology, and per-claim verdicts live in
[`results/FINDINGS.md`](results/FINDINGS.md). This file now serves as an
index of what ran and how to reproduce a single condition.

## Status legend

- [x] done
- ~~strikethrough~~ = declined (with reason)

---

## Completed ablation matrix

| # | Ablation                        | Status | N  | Code change?     | Where the result lives                  |
| - | ------------------------------- | ------ | -- | ---------------- | --------------------------------------- |
| 1 | Default rerun (noise floor)     | [x]    | 15 | no               | `results/evoresearcher_n3__deepseek.jsonl` |
| 2 | A3 — warm memory pass           | [x]    | 15 | no               | `results/evoresearcher_warm_n3__deepseek.jsonl` |
| 3 | A_TREE — blind expansion        | [x]    | 15 | `--blind-expansion` | `results/evoresearcher_blind_n3__deepseek.jsonl` |
| 4 | A_ELO — sort-by-score           | [x]    | 15 | `--no-elo`       | `results/evoresearcher_noelo_n3__deepseek.jsonl` |
| 5 | HF baselines (Qwen-3-Max anchor)| [x]    | 5  | no (judge only)  | `results/qwen3_max__deepseek.jsonl`     |

Headline numbers (post-rejudge, 2026-05-07):
default 21.8% ± 11.9 (noise floor), warm 22.6%, blind 23.0%, no-elo 18.8%;
Qwen-3-Max external anchor 60.6%. All three architectural claim deltas
fall within the 11.88 pp trial-level noise floor — see FINDINGS.md for
the per-task interpretive layer.

Total compute used: ~192 minutes wall-clock, ~$0.68 in DeepSeek judge tokens.

---

## Reproducing a single condition

The four EvoResearcher conditions are driven by the same harness with
different flags. `run_all.sh` orchestrates the full N=3 sweep across all
four conditions; the per-condition `chunk_{a,b,c,d}.sh` scripts wrap the
individual runs with sanity-gate retry logic.

Default / noise-floor condition:

```bash
rm -rf memory DeepResearch-Bench-II/report/evoresearcher_n3
.venv/bin/python benchmarks/drb2/run_evoresearcher.py \
    --trials 3 \
    --tree-depth 2 --branching-factor 2 --max-sources 6 \
    --label evoresearcher_n3
.venv/bin/python benchmarks/drb2/evaluate_with_deepseek.py --label evoresearcher_n3
```

Warm-memory pass (do NOT wipe `memory/` between default and warm — the
warm pass reuses the cold pass's stored entries):

```bash
rm -rf DeepResearch-Bench-II/report/evoresearcher_warm_n3
.venv/bin/python benchmarks/drb2/run_evoresearcher.py \
    --trials 3 \
    --tree-depth 2 --branching-factor 2 --max-sources 6 \
    --label evoresearcher_warm_n3
.venv/bin/python benchmarks/drb2/evaluate_with_deepseek.py --label evoresearcher_warm_n3
```

A_TREE — drops the review-guided refine-vs-alternative structure:

```bash
rm -rf memory DeepResearch-Bench-II/report/evoresearcher_blind_n3
.venv/bin/python benchmarks/drb2/run_evoresearcher.py \
    --trials 3 --blind-expansion \
    --tree-depth 2 --branching-factor 2 --max-sources 6 \
    --label evoresearcher_blind_n3
.venv/bin/python benchmarks/drb2/evaluate_with_deepseek.py --label evoresearcher_blind_n3
```

A_ELO — skips the Elo tournament, sorts leaves by `total_score`:

```bash
rm -rf memory DeepResearch-Bench-II/report/evoresearcher_noelo_n3
.venv/bin/python benchmarks/drb2/run_evoresearcher.py \
    --trials 3 --no-elo \
    --tree-depth 2 --branching-factor 2 --max-sources 6 \
    --label evoresearcher_noelo_n3
.venv/bin/python benchmarks/drb2/evaluate_with_deepseek.py --label evoresearcher_noelo_n3
```

After all four conditions are graded:

```bash
.venv/bin/python benchmarks/drb2/aggregate.py --out-prefix final_matrix
.venv/bin/python benchmarks/drb2/plot_matrix.py --out-prefix final_matrix
.venv/bin/python benchmarks/drb2/claim_summary.py --out-prefix final_matrix
.venv/bin/python benchmarks/drb2/cost_ledger.py   --out-prefix final_matrix
```

---

## Robustness fixes (applied before the N=3 run)

The N=1 pilot exposed two fragile failure modes that were fixed before the
ablation matrix ran. Both fixes are minimal-additive; the existing
successful-path behavior is bit-identical.

- `evoresearcher/llm.py` — `structured()` retries up to
  `MAX_STRUCTURED_RETRIES=3` on `json.JSONDecodeError` and
  `pydantic.ValidationError`, appending a stricter schema-only suffix and
  forcing `temperature=0` on retry.
- `evoresearcher/agents/proposal_agent.py` — `_validate_latex_fragments`
  logs warnings rather than raising; markdown always reaches the publish
  step.
- `evoresearcher/report/pdf.py` — `render_outputs` writes markdown first;
  LaTeX normalization + tectonic invocation are wrapped in try/except and
  no longer abort the run.

Coverage: 17 unit tests in `tests/test_llm_retry_unit.py`,
`tests/test_ablation_flags_unit.py`, and `tests/test_proposal_resilience_unit.py`,
including one that explicitly replays the pilot's failure shape
(escaped backslash + LaTeX `$` artifact).

Trial success rate after the fixes: **60/61 attempts (98.4%)** across
all four N=3 conditions; the one transient `Connection reset by peer`
was retried successfully, so the final state is 60/60 reports graded.

---

## Declined items (kept for institutional memory)

### ~~A1 — search OFF baseline~~

Just measures "without grounding, Recall tanks" — obvious from the
architecture and doesn't validate any specific design claim.

### ~~A2 — depth=1 ablation~~

Signal overlaps significantly with A_TREE. With A_TREE on the matrix,
the depth sweep is mostly redundant — a depth=2 → depth=1 drop
conflates "less search" with "less guidance", whereas A_TREE isolates
the guidance contribution directly.

### ~~A_DUAL — single combined memory~~

The dual-vs-single split-store distinction is too subtle to detect at
our 5-task cross-domain pilot scale. Most likely outcome is a clean
null. (If we ever scale up to many same-theme tasks, revisit.)

### ~~Perplexity-Research external anchor~~

Attempted; declined per the original contingency. The HF dataset
contains only 5 Perplexity entries total and none correspond to our
pilot's English tasks (4 are Chinese on unrelated topics, 1 is on
obesity guidelines). Qwen-3-Max-DeepResearch covered all 5 pilot
indices and serves as the external anchor instead.

### ~~Cross-judge sanity check~~

Would require Gemini API access we don't have. Acknowledged in
FINDINGS.md §1.6 as "DeepSeek-as-judge is a proxy; cross-judge
agreement was not measured."

### ~~Scale to all 66 EN tasks~~

Out of scope for this pilot. The 5-task matrix at N=3 already gives
statistically useful comparisons; see FINDINGS.md for what the noise
floor allows and doesn't allow concluding.

---

## Open follow-ups

### [ ] DDG search resilience

DuckDuckGo HTML scraping gets rate-limited on long sequences of runs.
Before ever scaling beyond the 5-task pilot, swap for a proper search
API (Tavily / Serper / Brave) and set retry+backoff.

### [ ] Within-theme evaluation for EMA

The current cross-domain pilot is a structurally weak test of EMA
(low semantic similarity between pilot tasks). A 5-task within-theme
evaluation would isolate the warm-memory contribution from the
domain-mismatch confound. See FINDINGS.md §2.2.
