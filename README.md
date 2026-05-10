# EvoResearcher

EvoResearcher is a deep-research agent that takes a single research question and
produces a fully cited research-proposal report. The system runs a five-stage
LangGraph pipeline with live web retrieval, tree-structured idea expansion, a
pairwise Elo ranker over competing proposals, a dual long-term memory backed by
an Evolution Memory Agent (EMA), and markdown/LaTeX/PDF output. It is the
EECS 6895 final project — the empirical contribution is a controlled ablation
of three of its architectural choices on the
[DeepResearch-Bench-II](https://huggingface.co/datasets/muset-ai/DeepResearch-Bench-II-Dataset)
benchmark.

The DRB-II ablation matrix (N=3 per condition × 4 conditions × 5 tasks + an
external Qwen-3-Max-DeepResearch anchor) is fully reproducible from this
repository; headline numbers and the interpretive writeup live in
[`benchmarks/drb2/results/FINDINGS.md`](benchmarks/drb2/results/FINDINGS.md).

---

## 1. Project description

A research user types a question; EvoResearcher returns a structured proposal
report (`research_report.md` + `.tex` + `.pdf`) backed by quoted web sources,
plus the full reasoning trace (idea tree, Elo match history, evidence
synthesis, memory updates) as separate JSON artifacts.

Internally the system runs a fixed graph of agent nodes:

```
                    +---------+    +-----------+    +-----------+    +---------+    +-----+
  research goal --> | intake  | -> | research  | -> | proposal  | -> | publish | -> | EMA |
                    +---------+    +-----------+    +-----------+    +---------+    +-----+
                         |              |                 |                |           |
                    normalised      idea tree         report sections   md/tex/pdf  long-term
                      brief        + Elo ranking     + evidence          on disk    memory
                                   + sources                                       update
```

- **IntakeAgent** (`evoresearcher/agents/intake_agent.py`) — normalises the raw
  user goal into a `ResearchBrief` (reframed goal, scope, success criteria,
  out-of-scope, mode-specific structure for `general` vs `ml`).
- **ResearchAgent** (`evoresearcher/agents/research_agent.py`) — pulls top-k
  memory hits, retrieves up to N web sources via the
  `evoresearcher/retrieval/search.py` DDG client, then grows an idea tree of
  configurable depth/branching using either *review-guided* expansion
  (one refinement child of the parent's weakest dimension + one alternative
  child) or *blind* expansion (two arbitrary children) when `--blind-expansion`
  is set. Leaves are ranked by an Elo tournament
  (`evoresearcher/research/elo_tournament.py`) using pairwise LLM judgements,
  or by `total_score` directly when `--no-elo` is set.
- **ProposalAgent** (`evoresearcher/agents/proposal_agent.py`) — turns the top
  three unique ranked ideas plus evidence into eight structured report
  sections (abstract / problem / evidence / proposed direction / plan /
  risks / conclusion / references). The LaTeX-fragment validator warns rather
  than aborts so the markdown path always reaches `publish`.
- **publish** (`evoresearcher/orchestration/graph.py:publish_node`) — writes
  `research_report.md`, attempts `research_report.tex` + `.pdf` (PDF
  compilation via `tectonic` is best-effort; markdown is always emitted), and
  dumps `idea_tree.json`, `elo_matches.json`, `evidence.json`,
  `memory_context.json`, `sources.json`, `top_ideas.json`.
- **EvolutionMemoryAgent** (`evoresearcher/agents/evolution_memory_agent.py`)
  — writes a distilled entry back into ideation_memory + proposal_memory so
  future runs can retrieve it via the JSONMemoryStore.

The orchestrator is a `langgraph.graph.StateGraph` defined in
`evoresearcher/orchestration/graph.py`; the LLM client (`evoresearcher/llm.py`)
talks to DeepSeek and implements a structured-output retry path
(`MAX_STRUCTURED_RETRIES=3`, stricter system prompt + temp=0 on retry).

---

## 2. Repository layout

```
EvoResearcher_EECS6895/
├── README.md                       this file
├── pyproject.toml                  installable package (`evoresearcher` console script)
├── .env.example                    template for DEEPSEEK_API_KEY etc.
│
├── evoresearcher/                  the system package (~2,300 LOC)
│   ├── main.py                     CLI entrypoint (argparse, wires the graph)
│   ├── config.py                   AppConfig + load_config (.env, paths, run-id)
│   ├── schemas.py                  pydantic models: ResearchBrief, ResearchIdea,
│   │                               EvidenceSynthesis, ReportSections, GraphState…
│   ├── llm.py                      DeepSeek client + structured()-with-retry
│   ├── agents/
│   │   ├── intake_agent.py         goal -> ResearchBrief
│   │   ├── research_agent.py       tree expansion + Elo ranking + ablation flags
│   │   ├── proposal_agent.py       top ideas -> ReportSections
│   │   └── evolution_memory_agent.py  writes back distilled memory entries
│   ├── research/
│   │   ├── tree_search.py          depth-bounded idea-tree expansion driver
│   │   └── elo_tournament.py       pairwise LLM-judge Elo ranker
│   ├── memory/
│   │   ├── store.py                JSONMemoryStore (ideation + proposal)
│   │   └── mcp_server.py           MCP-style read/write surface
│   ├── orchestration/graph.py      LangGraph nodes + edges
│   ├── retrieval/search.py         DDG web search (BeautifulSoup parser)
│   ├── report/pdf.py               markdown + LaTeX + tectonic invocation
│   └── tui/observer.py             Rich live-progress observer (phases, metrics)
│
├── benchmarks/drb2/                DeepResearch-Bench-II evaluation harness
│   ├── run_evoresearcher.py        runs the pipeline per task/trial
│   ├── evaluate_with_deepseek.py   batched 3-way (1/0/-1) rubric judge (DeepSeek)
│   ├── aggregate.py                per-task + per-label CSV/MD aggregation
│   ├── plot_matrix.py              grouped bar chart across all conditions
│   ├── claim_summary.py            sign+noise-floor verdicts per registered claim
│   ├── cost_ledger.py              token + $ accounting per condition
│   ├── hf_baselines.py             extract Qwen-3-Max reports from HF dataset
│   ├── chunk_{a..d}.sh + run_all.sh  full N=3 ablation sweep with sanity-gate retry
│   ├── pilot_tasks.json            5 EN tasks: idx={4,16,42,52,68}
│   ├── TODO.md                     status + per-condition reproduction commands
│   ├── results/
│   │   ├── FINDINGS.md             ← read this for the interpretive writeup
│   │   ├── final_matrix.png        headline grouped bar chart
│   │   ├── final_matrix_summary.{md,csv}      per-condition mean ± std
│   │   ├── final_matrix_per_task.csv          one row per (condition, idx, trial)
│   │   ├── final_matrix_claim_summary.{md,csv}   per-claim verdicts
│   │   ├── final_matrix_cost_ledger.{md,csv}     judge token + $ accounting
│   │   ├── evoresearcher_n3__deepseek.jsonl      default-condition raw judge
│   │   ├── evoresearcher_warm_n3__deepseek.jsonl warm-memory raw judge
│   │   ├── evoresearcher_blind_n3__deepseek.jsonl  A_TREE raw judge
│   │   ├── evoresearcher_noelo_n3__deepseek.jsonl  A_ELO raw judge
│   │   ├── evoresearcher__deepseek.jsonl       pre-fix N=1 pilot (historical)
│   │   ├── qwen3_max__deepseek.jsonl           external anchor raw judge
│   │   └── step1_only_*, through_step{3,4}_*   per-chunk historical snapshots
│   └── run_timings.jsonl           per-trial timing + ablation-flag provenance
│
├── tests/                          17 offline unit tests (+ 2 live-only)
│   ├── test_llm_retry_unit.py            JSON-retry path (6 tests)
│   ├── test_ablation_flags_unit.py       --blind-expansion / --no-elo (4 tests)
│   ├── test_proposal_resilience_unit.py  validator-warn + PDF-non-fatal (4 tests)
│   ├── test_memory_store_unit.py         JSONMemoryStore (2 tests)
│   ├── test_review_guided_tree_unit.py   tree expansion logic (1 test)
│   ├── test_memory_and_graph.py          live integration (requires API key)
│   └── conftest.py
│
└── outputs/                        run artifacts (timestamped runs are gitignored)
    ├── general_task_example1/      committed example of a "general" run
    └── ML_task_example1/           committed example of an "ml"-mode run
```

---

## 3. Setup

Requires Python ≥ 3.11. `tectonic` (for the PDF step) is optional — markdown
is always emitted; the LaTeX/PDF path logs a warning and is skipped when
`tectonic` is missing.

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e .            # installs the evoresearcher package + console script
pip install -e '.[dev]'     # also installs pytest for the test suite
```

Create a `.env` in the repo root:

```bash
cp .env.example .env
# then edit .env to set:
DEEPSEEK_API_KEY=sk-...
DEEPSEEK_MODEL=deepseek-chat
DEEPSEEK_BASE_URL=https://api.deepseek.com/chat/completions
```

`.env` is gitignored. Only `.env.example` (with a `replace_me` placeholder) is
committed.

---

## 4. Usage

### 4.1 Single goal (interactive)

```bash
python -m evoresearcher.main --mode general
# prompts: Enter your research question:
```

### 4.2 Single goal (non-interactive)

```bash
python -m evoresearcher.main \
    --mode general \
    --goal "Investigate why social protection programs in South Asia often fail the ultra-poor as of September 2023."
```

Modes:
- `--mode general` — generic research-proposal structure.
- `--mode ml` — ML-specific structure (methods, datasets, baselines, eval).

Knobs:
- `--tree-depth INT` (default 2) — idea-tree search depth.
- `--branching-factor INT` (default 2) — children kept per expansion step.
- `--max-sources INT` (default 6) — web retrieval budget.
- `--no-search` — disable web retrieval (uses memory + LLM priors only).
- `--workspace-dir PATH` — override the outputs/memory root.
- `--print-json` — also dump the final graph state to stdout.

Ablation flags (default off; the pipeline is bit-identical when both are
unset):

- `--blind-expansion` — A_TREE: drops the review-guided
  refine-vs-alternative structure from tree expansion. Both children are
  arbitrary directions.
- `--no-elo` — A_ELO: skips `run_elo_tournament` and ranks leaves by
  `total_score` (ties broken by `idea_id`).

The flags are independent and can be combined.

### 4.3 Output layout

Each run creates `outputs/<timestamped-run-id>/` containing:

| File                       | What it is                                              |
| -------------------------- | ------------------------------------------------------- |
| `research_report.md`       | canonical proposal report (always emitted)              |
| `research_report.tex`      | LaTeX source (best-effort)                              |
| `research_report.pdf`      | PDF render (only when tectonic + LaTeX succeed)         |
| `run_summary.json`         | final LangGraph state (brief, sources, ideas, evidence) |
| `idea_tree.json`           | full expanded tree with parent/child relations          |
| `elo_matches.json`         | pairwise Elo match history with judge rationales        |
| `evidence.json`            | evidence synthesis: claims, quotes, source mapping      |
| `sources.json`             | retrieved sources with URL + extracted text snippets    |
| `top_ideas.json`           | top-3 unique-by-title ranked ideas                      |
| `memory_context.json`      | memory hits surfaced into this run                      |
| `memory_updates.json`      | what EMA wrote back at the end of this run              |

Two example runs are committed for inspection:
[`outputs/general_task_example1/`](outputs/general_task_example1/) and
[`outputs/ML_task_example1/`](outputs/ML_task_example1/).

---

## 5. Reproducing the DRB-II benchmark results

The headline matrix in
[`benchmarks/drb2/results/FINDINGS.md`](benchmarks/drb2/results/FINDINGS.md) is
reproducible from the harness in `benchmarks/drb2/`. There are four
EvoResearcher conditions plus one external anchor.

### 5.1 One-shot: full sweep

```bash
.venv/bin/python -m pip install datasets reportlab matplotlib   # if you also
                                                                 # want plots + HF
bash benchmarks/drb2/run_all.sh                                  # full N=3 matrix
```

`run_all.sh` orchestrates the four `chunk_{a,b,c,d}.sh` scripts (default /
warm / blind / no-elo) with sanity-gate retry, then runs aggregation, claim
verdicts, cost ledger, and plotting. Expect ~3.5 hours wall-clock and ~$0.70
in DeepSeek judge tokens.

### 5.2 Per-condition (matches what `run_all.sh` calls)

Default (noise-floor + baseline; A3 cold pass):

```bash
rm -rf memory DeepResearch-Bench-II/report/evoresearcher_n3
.venv/bin/python benchmarks/drb2/run_evoresearcher.py \
    --trials 3 --tree-depth 2 --branching-factor 2 --max-sources 6 \
    --label evoresearcher_n3
.venv/bin/python benchmarks/drb2/evaluate_with_deepseek.py \
    --label evoresearcher_n3
```

Warm memory (A3 — do **not** wipe `memory/` after the default pass):

```bash
rm -rf DeepResearch-Bench-II/report/evoresearcher_warm_n3
.venv/bin/python benchmarks/drb2/run_evoresearcher.py \
    --trials 3 --tree-depth 2 --branching-factor 2 --max-sources 6 \
    --label evoresearcher_warm_n3
.venv/bin/python benchmarks/drb2/evaluate_with_deepseek.py \
    --label evoresearcher_warm_n3
```

A_TREE — blind expansion:

```bash
rm -rf memory DeepResearch-Bench-II/report/evoresearcher_blind_n3
.venv/bin/python benchmarks/drb2/run_evoresearcher.py \
    --trials 3 --blind-expansion \
    --tree-depth 2 --branching-factor 2 --max-sources 6 \
    --label evoresearcher_blind_n3
.venv/bin/python benchmarks/drb2/evaluate_with_deepseek.py \
    --label evoresearcher_blind_n3
```

A_ELO — sort-by-score:

```bash
rm -rf memory DeepResearch-Bench-II/report/evoresearcher_noelo_n3
.venv/bin/python benchmarks/drb2/run_evoresearcher.py \
    --trials 3 --no-elo \
    --tree-depth 2 --branching-factor 2 --max-sources 6 \
    --label evoresearcher_noelo_n3
.venv/bin/python benchmarks/drb2/evaluate_with_deepseek.py \
    --label evoresearcher_noelo_n3
```

Qwen-3-Max external anchor (extracts reports from the HF dataset, stages
them as markdown, then re-grades with the same DeepSeek judge for a
like-for-like comparison):

```bash
.venv/bin/python benchmarks/drb2/hf_baselines.py extract \
    --id-field <FIELD> --pdf-field <PDF_FIELD>
.venv/bin/python benchmarks/drb2/evaluate_with_deepseek.py --label qwen3_max
```

Aggregate across all conditions:

```bash
.venv/bin/python benchmarks/drb2/aggregate.py     --out-prefix final_matrix
.venv/bin/python benchmarks/drb2/plot_matrix.py   --out-prefix final_matrix
.venv/bin/python benchmarks/drb2/claim_summary.py --out-prefix final_matrix
.venv/bin/python benchmarks/drb2/cost_ledger.py   --out-prefix final_matrix
```

### 5.3 Headline numbers (from `final_matrix_summary.md`)

| Condition                                 | Total pass-rate | N  | Δ vs default |
| ----------------------------------------- | --------------- | -- | ------------ |
| Qwen-3-Max-DeepResearch (external anchor) | 60.6% ± 32.7    | 5  | +38.8 pp     |
| EvoResearcher blind expansion             | 23.0% ± 15.9    | 15 | +1.2 pp      |
| EvoResearcher warm memory                 | 22.6% ± 14.2    | 15 | +0.8 pp      |
| **EvoResearcher default (N=3)**           | **21.8% ± 11.9**| 15 | —            |
| EvoResearcher no-elo (sort-by-score)      | 18.8% ± 14.0    | 15 | −3.0 pp      |
| EvoResearcher N=1 pilot (pre-fix)         | 15.7% ± 11.5    | 5  | (different code) |

Trial-level noise floor on the default condition: **11.88 pp**. All three
architectural claim deltas fall inside the noise floor. Per-task analysis in
FINDINGS.md localizes each component's real contribution; the executive
summary, methodology, claim verdicts, and the Qwen anchor discussion are
all there.

---

## 6. Tests

```bash
.venv/bin/python -m pytest tests/ --ignore=tests/test_memory_and_graph.py -q
# 17 passed
```

Coverage:
- **LLM JSON retry** (6 tests, `test_llm_retry_unit.py`) — retry on bad JSON,
  retry on `pydantic.ValidationError`, exhaustion re-raises, temp=0 on retry,
  schema-suffix appended on retry, and a replay of the pilot's exact failure
  shape (escaped backslash + LaTeX `$` artifact).
- **Ablation flags** (4 tests, `test_ablation_flags_unit.py`) — defaults are
  `False`; `--blind-expansion` routes through `BlindIdeaExpansion`; `--no-elo`
  bypasses `run_elo_tournament`; flags compose.
- **Proposal/PDF resilience** (4 tests, `test_proposal_resilience_unit.py`) —
  validator warns rather than raises on each forbidden pattern; PDF renderer's
  tectonic-missing and compile-fail paths return a markdown-only artifact dict
  without raising.
- **Memory store** (2 tests) — JSONMemoryStore round-trip and persistence.
- **Review-guided tree expansion** (1 test) — review feedback shape and
  refine-vs-alternative selection.

`test_memory_and_graph.py` is a live integration test that requires a real
`DEEPSEEK_API_KEY` and is excluded from the default offline run above.

---

## 7. Configuration reference

`evoresearcher/config.py` reads:

| Env var               | Default                                          | What it controls                  |
| --------------------- | ------------------------------------------------ | --------------------------------- |
| `DEEPSEEK_API_KEY`    | *(required)*                                     | DeepSeek API auth                 |
| `DEEPSEEK_MODEL`      | `deepseek-chat`                                  | LLM model name                    |
| `DEEPSEEK_BASE_URL`   | `https://api.deepseek.com/chat/completions`      | API endpoint                      |
| `EVORESEARCHER_AUTHOR`| `EvoResearcher`                                  | Author line on the LaTeX report   |

The workspace dir (where `outputs/` and `memory/` are created) is set by
`--workspace-dir`; it defaults to the current working directory. The
ablation flags are CLI-only.

---

## 8. Pointers

- **Empirical writeup with claim verdicts:** [`benchmarks/drb2/results/FINDINGS.md`](benchmarks/drb2/results/FINDINGS.md)
- **DRB-II reproduction commands + status:** [`benchmarks/drb2/TODO.md`](benchmarks/drb2/TODO.md)
- **Example runs:** [`outputs/general_task_example1/`](outputs/general_task_example1/), [`outputs/ML_task_example1/`](outputs/ML_task_example1/)
- **Branch policy:** ongoing work is pushed to `adam-updates` and merged into
  `main` once verified.
