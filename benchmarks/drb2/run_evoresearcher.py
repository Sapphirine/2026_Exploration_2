"""Drive EvoResearcher across DRB-II pilot tasks.

Reads benchmarks/drb2/pilot_tasks.json, loads the matching prompt from the cloned
DeepResearch-Bench-II/tasks_and_rubrics.jsonl, and runs the EvoResearcher pipeline
(in-process, not via CLI) for N trials per task. Each trial's research_report.md is
copied into report/evoresearcher/idx-{idx}.md (or idx-{idx}-trial-{trial}.md when N>1).

Run from repo root:
    .venv/bin/python benchmarks/drb2/run_evoresearcher.py \
        --trials 1 \
        --tree-depth 2 \
        --branching-factor 2 \
        --max-sources 6
"""

from __future__ import annotations

import argparse
import json
import shutil
import time
import traceback
from pathlib import Path

from evoresearcher.agents.evolution_memory_agent import EvolutionMemoryAgent
from evoresearcher.agents.intake_agent import IntakeAgent
from evoresearcher.agents.proposal_agent import ProposalAgent
from evoresearcher.agents.research_agent import ResearchAgent
from evoresearcher.config import load_config
from evoresearcher.llm import LLMClient
from evoresearcher.memory.store import JSONMemoryStore
from evoresearcher.orchestration.graph import build_graph

REPO_ROOT = Path(__file__).resolve().parents[2]
BENCH_DIR = REPO_ROOT / "benchmarks" / "drb2"
DRB2_REPO = REPO_ROOT.parent / "DeepResearch-Bench-II"
TASKS_JSONL = DRB2_REPO / "tasks_and_rubrics.jsonl"
PILOT_JSON = BENCH_DIR / "pilot_tasks.json"
REPORT_DIR = DRB2_REPO / "report" / "evoresearcher"
RUNS_DIR = BENCH_DIR / "runs"
TIMINGS_PATH = BENCH_DIR / "run_timings.jsonl"


def load_pilot_prompts() -> list[dict]:
    pilot = json.loads(PILOT_JSON.read_text())
    pilot_idx_set = {entry["idx"] for entry in pilot}
    prompts: dict[int, dict] = {}
    with TASKS_JSONL.open() as fh:
        for line in fh:
            obj = json.loads(line)
            if obj["idx"] in pilot_idx_set:
                prompts[obj["idx"]] = obj
    out: list[dict] = []
    for entry in pilot:
        task = prompts[entry["idx"]]
        out.append(
            {
                "idx": entry["idx"],
                "id": entry["id"],
                "theme": entry["theme"],
                "description": entry["description"],
                "prompt": task["prompt"],
            }
        )
    return out


def main() -> None:
    parser = argparse.ArgumentParser(description="Run EvoResearcher across DRB-II pilot tasks.")
    parser.add_argument("--trials", type=int, default=1, help="Trials per task.")
    parser.add_argument("--tree-depth", type=int, default=2)
    parser.add_argument("--branching-factor", type=int, default=2)
    parser.add_argument("--max-sources", type=int, default=6)
    parser.add_argument("--no-search", action="store_true")
    parser.add_argument("--mode", default="general", choices=("general", "ml"))
    parser.add_argument(
        "--label",
        default="evoresearcher",
        help="Subdir under report/. Use different labels for different conditions.",
    )
    parser.add_argument(
        "--only-idx",
        default=None,
        help="Comma-separated task indices to run (subset of pilot_tasks.json). Default: all.",
    )
    args = parser.parse_args()

    if not DRB2_REPO.exists():
        raise SystemExit(f"DRB-II repo not found at {DRB2_REPO}. Clone it first.")

    pilot_tasks = load_pilot_prompts()
    if args.only_idx:
        wanted = {int(x) for x in args.only_idx.split(",") if x.strip()}
        pilot_tasks = [t for t in pilot_tasks if t["idx"] in wanted]
        if not pilot_tasks:
            raise SystemExit(f"No pilot tasks match --only-idx {args.only_idx}")
    print(f"[run] {len(pilot_tasks)} pilot tasks × {args.trials} trial(s) = {len(pilot_tasks)*args.trials} runs")
    print(
        f"[run] settings: mode={args.mode}, tree_depth={args.tree_depth}, branching={args.branching_factor}, "
        f"max_sources={args.max_sources}, search={'off' if args.no_search else 'on'}"
    )
    report_root = DRB2_REPO / "report" / args.label
    report_root.mkdir(parents=True, exist_ok=True)
    RUNS_DIR.mkdir(parents=True, exist_ok=True)

    config = load_config(
        workspace_dir=str(REPO_ROOT),
        search_enabled=not args.no_search,
        tree_depth=args.tree_depth,
        branching_factor=args.branching_factor,
        max_sources=args.max_sources,
    )
    llm = LLMClient(config)
    ideation_memory = JSONMemoryStore(config.memory_dir / "ideation_memory.json")
    proposal_memory = JSONMemoryStore(config.memory_dir / "proposal_memory.json")
    intake_agent = IntakeAgent(llm)
    research_agent = ResearchAgent(config, llm, ideation_memory, proposal_memory)
    proposal_agent = ProposalAgent(llm)
    ema_agent = EvolutionMemoryAgent(
        ideation_memory=ideation_memory,
        proposal_memory=proposal_memory,
    )
    graph = build_graph(
        config=config,
        intake_agent=intake_agent,
        research_agent=research_agent,
        proposal_agent=proposal_agent,
        ema_agent=ema_agent,
    )

    timings_fh = TIMINGS_PATH.open("a")

    for task in pilot_tasks:
        for trial in range(1, args.trials + 1):
            label = f"idx-{task['idx']}" if args.trials == 1 else f"idx-{task['idx']}-trial-{trial}"
            print(f"\n[run] === {label} | theme={task['theme']} ===")
            run_id = f"drb2-{label}-{int(time.time())}"
            run_dir = RUNS_DIR / run_id
            run_dir.mkdir(parents=True, exist_ok=True)
            t0 = time.time()
            error = None
            try:
                state = graph.invoke(
                    {
                        "run_id": run_id,
                        "run_dir": str(run_dir),
                        "mode": args.mode,
                        "goal": task["prompt"],
                    }
                )
            except Exception as exc:
                error = f"{type(exc).__name__}: {exc}"
                traceback.print_exc()
                state = None
            elapsed = time.time() - t0

            md_src = run_dir / "research_report.md"
            md_dst = report_root / f"{label}.md"
            if md_src.exists():
                shutil.copyfile(md_src, md_dst)
                print(f"[run] copied -> {md_dst.relative_to(REPO_ROOT.parent)}")
            else:
                print(f"[run] WARNING: no markdown produced at {md_src}")

            timings_fh.write(
                json.dumps(
                    {
                        "label": args.label,
                        "task_idx": task["idx"],
                        "task_theme": task["theme"],
                        "trial": trial,
                        "run_id": run_id,
                        "elapsed_s": round(elapsed, 1),
                        "ok": state is not None,
                        "error": error,
                        "report_path": str(md_dst.relative_to(REPO_ROOT.parent)) if md_src.exists() else None,
                    }
                )
                + "\n"
            )
            timings_fh.flush()
            print(f"[run] elapsed={elapsed:.1f}s | ok={state is not None}")

    timings_fh.close()
    print(f"\n[run] done. Timings -> {TIMINGS_PATH}")


if __name__ == "__main__":
    main()
