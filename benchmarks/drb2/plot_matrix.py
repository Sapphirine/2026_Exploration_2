"""Multi-condition matrix plot for the DRB-II ablation results.

For each `*__deepseek.jsonl` file in results/, computes per-task pass rate by
dimension (info_recall, analysis, presentation, total). When a condition has
multiple trials per idx (N>1), error bars show the std across trials.

Outputs benchmarks/drb2/results/<out>_matrix.png plus a per-condition strip
chart at <out>_per_condition.png.
"""

from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path
from statistics import mean, stdev

import matplotlib.pyplot as plt
import numpy as np

REPO_ROOT = Path(__file__).resolve().parents[2]
RESULTS_DIR = REPO_ROOT / "benchmarks" / "drb2" / "results"
PILOT_TASKS_PATH = REPO_ROOT / "benchmarks" / "drb2" / "pilot_tasks.json"

DIMS = ["info_recall", "analysis", "presentation", "total"]
DIM_LABELS = {"info_recall": "Recall", "analysis": "Analysis", "presentation": "Presentation", "total": "Total"}
DIM_COLORS = {"info_recall": "#4C72B0", "analysis": "#55A868", "presentation": "#C44E52", "total": "#8172B2"}


def _pass_rate(per_item: dict | None) -> float:
    if not per_item:
        return 0.0
    return sum(1 for v in per_item.values() if v.get("score") == 1) / len(per_item)


def load_label_trials(jsonl_path: Path) -> dict[int, list[dict]]:
    """Return {idx: [{dim: rate} per trial]} from a single label's jsonl."""
    by_idx: dict[int, list[dict]] = defaultdict(list)
    with jsonl_path.open() as fh:
        for line in fh:
            obj = json.loads(line)
            res = obj.get("result") or {}
            if "error" in res:
                continue
            scores = res.get("scores", {})
            recall = scores.get("info_recall", {}) or {}
            analysis = scores.get("analysis", {}) or {}
            presentation = scores.get("presentation", {}) or {}
            allof = {**recall, **analysis, **presentation}
            by_idx[int(obj["idx"])].append(
                {
                    "info_recall": _pass_rate(recall),
                    "analysis": _pass_rate(analysis),
                    "presentation": _pass_rate(presentation),
                    "total": _pass_rate(allof),
                }
            )
    return by_idx


def _agg(values: list[float]) -> tuple[float, float]:
    if not values:
        return 0.0, 0.0
    if len(values) == 1:
        return values[0], 0.0
    return mean(values), stdev(values)


def per_condition_stats(by_idx: dict[int, list[dict]]) -> dict[str, tuple[float, float]]:
    """Mean ± std across (idx, trial) per dimension. Std reflects the full sample."""
    out: dict[str, tuple[float, float]] = {}
    for dim in DIMS:
        vals = [trial[dim] for trials in by_idx.values() for trial in trials]
        out[dim] = _agg(vals)
    return out


def plot_matrix(label_to_path: dict[str, Path], out_path: Path, title: str) -> None:
    labels = list(label_to_path.keys())
    stats: dict[str, dict[str, tuple[float, float]]] = {}
    for label, path in label_to_path.items():
        stats[label] = per_condition_stats(load_label_trials(path))

    n_labels = len(labels)
    n_dims = len(DIMS)
    bar_w = 0.18
    x = np.arange(n_labels)

    fig, ax = plt.subplots(figsize=(max(8, 1.5 * n_labels + 4), 6))
    for i, dim in enumerate(DIMS):
        means_pct = [stats[lbl][dim][0] * 100 for lbl in labels]
        stds_pct = [stats[lbl][dim][1] * 100 for lbl in labels]
        offset = (i - (n_dims - 1) / 2) * bar_w
        bars = ax.bar(
            x + offset,
            means_pct,
            bar_w,
            yerr=stds_pct,
            label=DIM_LABELS[dim],
            color=DIM_COLORS[dim],
            edgecolor="white",
            linewidth=0.6,
            capsize=3,
        )
        for bar, m in zip(bars, means_pct):
            ax.text(
                bar.get_x() + bar.get_width() / 2,
                bar.get_height() + 1.5,
                f"{m:.0f}",
                ha="center",
                va="bottom",
                fontsize=8,
                color="#333",
            )

    ax.set_xticks(x)
    ax.set_xticklabels(labels, fontsize=9, rotation=20, ha="right")
    ax.set_ylabel("Rubric pass rate (%)")
    ax.set_ylim(0, 110)
    ax.set_yticks([0, 20, 40, 60, 80, 100])
    ax.set_axisbelow(True)
    ax.yaxis.grid(True, linestyle=":", alpha=0.5)
    for spine in ("top", "right"):
        ax.spines[spine].set_visible(False)
    ax.set_title(title, fontsize=11, loc="left", pad=12)
    ax.legend(loc="upper right", frameon=False, fontsize=9, ncol=4)

    fig.tight_layout()
    fig.savefig(out_path, dpi=160, bbox_inches="tight")
    print(f"[plot] wrote {out_path}")
    plt.close(fig)


def main() -> None:
    parser = argparse.ArgumentParser(description="Multi-condition matrix plot for DRB-II.")
    parser.add_argument(
        "--labels",
        nargs="+",
        default=None,
        help="Specific labels to include (default: every label with a *__deepseek.jsonl).",
    )
    parser.add_argument("--out-prefix", default="final_matrix")
    parser.add_argument(
        "--title",
        default="EvoResearcher DRB-II ablation matrix (DeepSeek-as-judge)",
    )
    args = parser.parse_args()

    if args.labels:
        wanted = list(args.labels)
    else:
        wanted = [p.name.replace("__deepseek.jsonl", "") for p in sorted(RESULTS_DIR.glob("*__deepseek.jsonl"))]
    label_to_path = {l: RESULTS_DIR / f"{l}__deepseek.jsonl" for l in wanted}
    missing = [l for l, p in label_to_path.items() if not p.exists()]
    if missing:
        raise SystemExit(f"Missing input(s): {missing}")
    out_path = RESULTS_DIR / f"{args.out_prefix}.png"
    plot_matrix(label_to_path, out_path, args.title)


if __name__ == "__main__":
    main()
