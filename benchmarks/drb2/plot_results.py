"""Render the DRB-II pilot results as a labeled bar chart.

Reads benchmarks/drb2/results/<label>__deepseek.jsonl and benchmarks/drb2/pilot_tasks.json,
emits a grouped bar chart at benchmarks/drb2/results/<label>_chart.png.

Run from repo root:
    .venv/bin/python benchmarks/drb2/plot_results.py
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np

REPO_ROOT = Path(__file__).resolve().parents[2]
BENCH_DIR = REPO_ROOT / "benchmarks" / "drb2"
RESULTS_DIR = BENCH_DIR / "results"
PILOT_TASKS_PATH = BENCH_DIR / "pilot_tasks.json"

# A short label for each pilot task — keeps the x-axis legible.
SHORT_LABELS: dict[int, str] = {
    4:  "Retirement\nSavings",
    16: "Materials\nInverse Design",
    42: "Low-Code\nPlatforms",
    52: "GenAI in\nEducation",
    68: "AI Shared\nDecision-Making",
}


def pass_rate(per_item: dict) -> float:
    if not per_item:
        return 0.0
    return sum(1 for v in per_item.values() if v.get("score") == 1) / len(per_item)


def load_results(jsonl_path: Path) -> dict[int, dict]:
    out: dict[int, dict] = {}
    with jsonl_path.open() as fh:
        for line in fh:
            obj = json.loads(line)
            res = obj.get("result") or {}
            scores = res.get("scores", {})
            recall = scores.get("info_recall", {}) or {}
            analysis = scores.get("analysis", {}) or {}
            presentation = scores.get("presentation", {}) or {}
            all_items = {**recall, **analysis, **presentation}
            out[int(obj["idx"])] = {
                "recall": pass_rate(recall),
                "analysis": pass_rate(analysis),
                "presentation": pass_rate(presentation),
                "total": pass_rate(all_items),
                "n_recall": len(recall),
                "n_analysis": len(analysis),
                "n_presentation": len(presentation),
            }
    return out


def render(label: str, jsonl_path: Path, out_path: Path) -> None:
    pilot = json.loads(PILOT_TASKS_PATH.read_text())
    pilot.sort(key=lambda e: e["idx"])
    results = load_results(jsonl_path)

    task_idxs = [e["idx"] for e in pilot]
    themes = {e["idx"]: e["theme"] for e in pilot}

    dims = ["recall", "analysis", "presentation", "total"]
    dim_labels = ["Info Recall", "Analysis", "Presentation", "Total"]
    colors = ["#4C72B0", "#55A868", "#C44E52", "#8172B2"]

    fig, ax = plt.subplots(figsize=(11, 6.2))
    n_groups = len(task_idxs)
    n_dims = len(dims)
    bar_w = 0.18
    x = np.arange(n_groups)

    for i, (dim, dim_label, color) in enumerate(zip(dims, dim_labels, colors)):
        vals = [results[idx][dim] * 100 for idx in task_idxs]
        offset = (i - (n_dims - 1) / 2) * bar_w
        bars = ax.bar(x + offset, vals, bar_w, label=dim_label, color=color, edgecolor="white", linewidth=0.6)
        for bar, v in zip(bars, vals):
            ax.text(
                bar.get_x() + bar.get_width() / 2,
                bar.get_height() + 1.2,
                f"{v:.0f}",
                ha="center",
                va="bottom",
                fontsize=8,
                color="#333",
            )

    # Per-task mean as a faint horizontal marker line
    means = [results[idx]["total"] * 100 for idx in task_idxs]
    overall_total = float(np.mean(means))
    ax.axhline(overall_total, color="#8172B2", linestyle=":", linewidth=1.0, alpha=0.7,
               label=f"Mean Total ({overall_total:.1f}%)")

    # X-axis: idx + short label + theme
    xticklabels = []
    for idx in task_idxs:
        short = SHORT_LABELS.get(idx, f"idx-{idx}")
        theme = themes.get(idx, "")
        xticklabels.append(f"idx-{idx}\n{short}\n[{theme}]")
    ax.set_xticks(x)
    ax.set_xticklabels(xticklabels, fontsize=9)

    ax.set_ylabel("Rubric pass rate (%)")
    ax.set_ylim(0, 110)
    ax.set_yticks([0, 20, 40, 60, 80, 100])
    ax.set_axisbelow(True)
    ax.yaxis.grid(True, linestyle=":", alpha=0.5)
    for spine in ("top", "right"):
        ax.spines[spine].set_visible(False)

    ax.set_title(
        f"EvoResearcher on DeepResearch-Bench-II (pilot: {n_groups} EN tasks, N=1)\n"
        f"Judge: DeepSeek (text-only) substituting for Gemini. Search ON, depth=2, branching=2.",
        fontsize=11,
        loc="left",
        pad=12,
    )
    ax.legend(loc="upper right", frameon=False, fontsize=9, ncol=5)

    fig.tight_layout()
    fig.savefig(out_path, dpi=160, bbox_inches="tight")
    print(f"[plot] wrote {out_path}")
    plt.close(fig)


def main() -> None:
    parser = argparse.ArgumentParser(description="Render DRB-II pilot results.")
    parser.add_argument("--label", default="evoresearcher", help="Subdir label that grade JSONL is keyed by.")
    parser.add_argument("--input", default=None, help="Override input JSONL path.")
    args = parser.parse_args()

    jsonl_path = Path(args.input) if args.input else RESULTS_DIR / f"{args.label}__deepseek.jsonl"
    if not jsonl_path.exists():
        raise SystemExit(f"Input not found: {jsonl_path}")
    out_path = RESULTS_DIR / f"{args.label}_chart.png"
    render(args.label, jsonl_path, out_path)


if __name__ == "__main__":
    main()
