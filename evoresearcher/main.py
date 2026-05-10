"""CLI entrypoint."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from evoresearcher.agents.evolution_memory_agent import EvolutionMemoryAgent
from evoresearcher.agents.intake_agent import IntakeAgent
from evoresearcher.agents.proposal_agent import ProposalAgent
from evoresearcher.agents.research_agent import ResearchAgent
from evoresearcher.config import load_config
from evoresearcher.llm import LLMClient
from evoresearcher.memory.store import JSONMemoryStore
from evoresearcher.orchestration.graph import build_graph
from evoresearcher.tui.observer import RichObserver


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run EvoResearcher.")
    parser.add_argument("--goal", default=None, help="Research goal or benchmark-style query.")
    parser.add_argument("--mode", choices=("general", "ml"), default="general")
    parser.add_argument("--workspace-dir", default=None)
    parser.add_argument("--tree-depth", type=int, default=2, help="Idea tree search depth.")
    parser.add_argument("--branching-factor", type=int, default=2, help="Number of children kept per expansion step.")
    parser.add_argument("--max-sources", type=int, default=6, help="Maximum number of retrieved web sources.")
    parser.add_argument("--no-search", action="store_true")
    parser.add_argument(
        "--blind-expansion",
        action="store_true",
        help="A_TREE ablation: drop review feedback / refine-vs-alternative structure from tree expansion.",
    )
    parser.add_argument(
        "--no-elo",
        action="store_true",
        help="A_ELO ablation: skip Elo tournament and rank leaves by total_score.",
    )
    parser.add_argument("--print-json", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> None:
    args = build_parser().parse_args(argv)
    goal = args.goal or input("Enter your research question: ").strip()
    if not goal:
        raise SystemExit("A non-empty goal is required.")
    config = load_config(
        workspace_dir=args.workspace_dir,
        search_enabled=not args.no_search,
        tree_depth=args.tree_depth,
        branching_factor=args.branching_factor,
        max_sources=args.max_sources,
    )
    run_id = config.make_run_id(goal)
    run_dir = config.outputs_dir / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    llm = LLMClient(config)
    ideation_memory = JSONMemoryStore(config.memory_dir / "ideation_memory.json")
    proposal_memory = JSONMemoryStore(config.memory_dir / "proposal_memory.json")
    intake_agent = IntakeAgent(llm)
    research_agent = ResearchAgent(
        config,
        llm,
        ideation_memory,
        proposal_memory,
        expansion_blind=args.blind_expansion,
        skip_elo=args.no_elo,
    )
    proposal_agent = ProposalAgent(llm)
    ema_agent = EvolutionMemoryAgent(
        ideation_memory=ideation_memory,
        proposal_memory=proposal_memory,
    )
    with RichObserver() as observer:
        observer.start_run(
            run_id=run_id,
            mode=args.mode,
            goal=goal,
            model_name=config.deepseek_model,
            provider="deepseek",
            workspace_dir=config.workspace_dir,
        )
        app = build_graph(
            config=config,
            intake_agent=intake_agent,
            research_agent=research_agent,
            proposal_agent=proposal_agent,
            ema_agent=ema_agent,
            observer=observer,
        )
        state = app.invoke(
            {
                "run_id": run_id,
                "run_dir": str(run_dir),
                "mode": args.mode,
                "goal": goal,
            }
        )
        (run_dir / "run_summary.json").write_text(json.dumps(state, indent=2))
        observer.artifact("run_summary", run_dir / "run_summary.json")
        observer.finish("run completed")
    if args.print_json:
        print(json.dumps(state, indent=2))
    else:
        print(f"Run completed: {run_dir}")


if __name__ == "__main__":
    main()
