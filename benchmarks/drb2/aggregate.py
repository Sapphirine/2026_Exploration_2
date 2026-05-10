"""Aggregate DeepSeek-judge results into report-ready CSVs.

Reads benchmarks/drb2/results/<label>__deepseek.jsonl (the output of
evaluate_with_deepseek.py) and emits:
- per_task.csv: one row per (model_label, idx) with rubric pass rates by dimension
- summary.csv: overall pass rates (mean across tasks) per model_label
- summary.md: human-readable markdown table for the report

Run:
    .venv/bin/python benchmarks/drb2/aggregate.py
"""

from __future__ import annotations

import argparse
import csv
import json
from collections import defaultdict
from pathlib import Path
from statistics import mean, stdev

REPO_ROOT = Path(__file__).resolve().parents[2]
RESULTS_DIR = REPO_ROOT / "benchmarks" / "drb2" / "results"


def pass_rate(per_item: dict[str, dict]) -> float:
    """Pass rate ignoring blocked-citation penalties; score==1 counts as pass."""
    if not per_item:
        return 0.0
    n = sum(1 for v in per_item.values() if v.get("score") == 1)
    return n / len(per_item)


def collect(jsonl_path: Path) -> list[dict]:
    rows: list[dict] = []
    with jsonl_path.open() as fh:
        for line in fh:
            obj = json.loads(line)
            res = obj.get("result") or {}
            if "error" in res:
                rows.append(
                    {
                        "label": obj["model"],
                        "idx": obj["idx"],
                        "error": res["error"],
                        "info_recall_pass": None,
                        "analysis_pass": None,
                        "presentation_pass": None,
                        "total_pass": None,
                        "n_recall": 0,
                        "n_analysis": 0,
                        "n_presentation": 0,
                    }
                )
                continue
            scores = res.get("scores", {})
            recall = scores.get("info_recall", {}) or {}
            analysis = scores.get("analysis", {}) or {}
            presentation = scores.get("presentation", {}) or {}
            all_items = {**recall, **analysis, **presentation}
            rows.append(
                {
                    "label": obj["model"],
                    "idx": obj["idx"],
                    "error": "",
                    "info_recall_pass": pass_rate(recall),
                    "analysis_pass": pass_rate(analysis),
                    "presentation_pass": pass_rate(presentation),
                    "total_pass": pass_rate(all_items),
                    "n_recall": len(recall),
                    "n_analysis": len(analysis),
                    "n_presentation": len(presentation),
                }
            )
    return rows


def write_per_task_csv(rows: list[dict], path: Path) -> None:
    fields = [
        "label",
        "idx",
        "info_recall_pass",
        "analysis_pass",
        "presentation_pass",
        "total_pass",
        "n_recall",
        "n_analysis",
        "n_presentation",
        "error",
    ]
    with path.open("w", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            writer.writerow({k: row.get(k, "") for k in fields})


def summarize(rows: list[dict]) -> list[dict]:
    by_label: dict[str, list[dict]] = defaultdict(list)
    for row in rows:
        if row.get("error"):
            continue
        by_label[row["label"]].append(row)
    out = []
    for label, items in by_label.items():
        n = len(items)

        def stat(field: str) -> tuple[float, float]:
            vals = [r[field] for r in items if r.get(field) is not None]
            if not vals:
                return 0.0, 0.0
            return mean(vals), (stdev(vals) if len(vals) > 1 else 0.0)

        rmean, rstd = stat("info_recall_pass")
        amean, astd = stat("analysis_pass")
        pmean, pstd = stat("presentation_pass")
        tmean, tstd = stat("total_pass")
        out.append(
            {
                "label": label,
                "n_tasks": n,
                "info_recall_mean": rmean,
                "info_recall_std": rstd,
                "analysis_mean": amean,
                "analysis_std": astd,
                "presentation_mean": pmean,
                "presentation_std": pstd,
                "total_mean": tmean,
                "total_std": tstd,
            }
        )
    return out


def write_summary_csv(summary: list[dict], path: Path) -> None:
    fields = [
        "label",
        "n_tasks",
        "info_recall_mean",
        "info_recall_std",
        "analysis_mean",
        "analysis_std",
        "presentation_mean",
        "presentation_std",
        "total_mean",
        "total_std",
    ]
    with path.open("w", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fields)
        writer.writeheader()
        for row in summary:
            writer.writerow({k: row[k] for k in fields})


def write_summary_md(summary: list[dict], per_task: list[dict], path: Path) -> None:
    lines = ["# DRB-II pilot results (DeepSeek-as-judge)", ""]
    lines.append("## Per-label summary (mean ± std across tasks)")
    lines.append("")
    lines.append("| Label | N | Info Recall | Analysis | Presentation | Total |")
    lines.append("|---|---|---|---|---|---|")
    for s in summary:
        lines.append(
            f"| {s['label']} | {s['n_tasks']} "
            f"| {s['info_recall_mean']*100:.1f}% ± {s['info_recall_std']*100:.1f} "
            f"| {s['analysis_mean']*100:.1f}% ± {s['analysis_std']*100:.1f} "
            f"| {s['presentation_mean']*100:.1f}% ± {s['presentation_std']*100:.1f} "
            f"| {s['total_mean']*100:.1f}% ± {s['total_std']*100:.1f} |"
        )
    lines.append("")
    lines.append("## Per-task breakdown")
    lines.append("")
    lines.append("| Label | idx | Recall | Analysis | Presentation | Total | Rubrics |")
    lines.append("|---|---|---|---|---|---|---|")
    for r in sorted(per_task, key=lambda x: (x["label"], x["idx"])):
        if r.get("error"):
            lines.append(f"| {r['label']} | {r['idx']} | ERROR | | | | {r['error']} |")
            continue
        total_n = r["n_recall"] + r["n_analysis"] + r["n_presentation"]
        lines.append(
            f"| {r['label']} | {r['idx']} "
            f"| {r['info_recall_pass']*100:.1f}% "
            f"| {r['analysis_pass']*100:.1f}% "
            f"| {r['presentation_pass']*100:.1f}% "
            f"| {r['total_pass']*100:.1f}% "
            f"| {total_n} |"
        )
    path.write_text("\n".join(lines) + "\n")


def main() -> None:
    parser = argparse.ArgumentParser(description="Aggregate DeepSeek-judge results.")
    parser.add_argument(
        "--inputs",
        nargs="+",
        default=None,
        help="Specific result jsonl files to aggregate. Default: every *.jsonl in results/.",
    )
    parser.add_argument("--out-prefix", default="pilot")
    args = parser.parse_args()

    if args.inputs:
        paths = [Path(p) for p in args.inputs]
    else:
        paths = sorted(RESULTS_DIR.glob("*.jsonl"))
    if not paths:
        raise SystemExit(f"No jsonl results found under {RESULTS_DIR}")

    all_rows: list[dict] = []
    for p in paths:
        all_rows.extend(collect(p))
    if not all_rows:
        raise SystemExit("No rows parsed.")

    per_task_csv = RESULTS_DIR / f"{args.out_prefix}_per_task.csv"
    summary_csv = RESULTS_DIR / f"{args.out_prefix}_summary.csv"
    summary_md = RESULTS_DIR / f"{args.out_prefix}_summary.md"

    write_per_task_csv(all_rows, per_task_csv)
    summary = summarize(all_rows)
    write_summary_csv(summary, summary_csv)
    write_summary_md(summary, all_rows, summary_md)

    print(f"[agg] per-task -> {per_task_csv}")
    print(f"[agg] summary  -> {summary_csv}")
    print(f"[agg] markdown -> {summary_md}")
    print()
    for s in summary:
        print(
            f"  {s['label']}: total={s['total_mean']*100:.1f}% "
            f"(recall={s['info_recall_mean']*100:.1f}%, "
            f"analysis={s['analysis_mean']*100:.1f}%, "
            f"presentation={s['presentation_mean']*100:.1f}%) "
            f"over {s['n_tasks']} tasks"
        )


if __name__ == "__main__":
    main()
