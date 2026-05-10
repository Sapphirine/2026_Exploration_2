# EvoResearcher

EvoResearcher is an interactive deep-research proposal system with:

- Rich TUI with animated live phases
- LangGraph orchestration
- DeepSeek API as the model backend
- Dual memory plus an Evolution Memory Agent (EMA)
- Tree-search based ideation
- LaTeX report generation and direct PDF rendering (markdown is always
  emitted; PDF compilation is best-effort and non-fatal)

## Quick start

```bash
python -m evoresearcher.main --mode general
python -m evoresearcher.main --mode ml
python -m evoresearcher.main --mode general --goal "Investigate why social protection programs in South Asia often fail the ultra-poor as of September 2023."
```

Outputs are written under `outputs/<run-id>/`.

### Ablation flags

Two opt-in flags isolate specific architectural contributions for
benchmarking. Both default off; the existing pipeline behavior is
bit-identical when neither is set.

- `--blind-expansion` — drops the review-guided refine-vs-alternative
  structure from tree expansion (A_TREE).
- `--no-elo` — skips the Elo tournament and ranks leaf proposals by
  `total_score` directly (A_ELO).

The flags are independent and can be combined.

## Environment

Create `.env` with:

```bash
DEEPSEEK_API_KEY=...
DEEPSEEK_MODEL=deepseek-chat
DEEPSEEK_BASE_URL=https://api.deepseek.com/chat/completions
```

## Benchmarks

The `benchmarks/drb2/` directory contains a self-contained harness for
DeepResearch-Bench-II evaluation under a DeepSeek judge, including the
full N=3 ablation matrix (default / warm memory / blind expansion /
no-elo) and a Qwen-3-Max-DeepResearch external anchor extracted from
the HF dataset. See [`benchmarks/drb2/results/FINDINGS.md`](benchmarks/drb2/results/FINDINGS.md)
for the interpretive writeup and [`benchmarks/drb2/TODO.md`](benchmarks/drb2/TODO.md)
for reproduction commands.

## Tests

```bash
.venv/bin/python -m pytest tests/ --ignore=tests/test_memory_and_graph.py -q
```

17 unit tests cover the LLM JSON-retry path, the ablation flags, the
proposal/PDF resilience layer, the memory store, and the review-guided
tree expansion logic. `tests/test_memory_and_graph.py` is a live
integration test that requires a real `DEEPSEEK_API_KEY` and is
excluded from the default offline run above.
