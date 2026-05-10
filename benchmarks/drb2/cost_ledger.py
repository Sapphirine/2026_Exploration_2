"""Token + estimated $-cost ledger across all DRB-II conditions.

Sums `usage_summary` from each results/*__deepseek.jsonl plus elapsed_s from
run_timings.jsonl (matched by label). Emits results/<out>_cost_ledger.{csv,md}.

DeepSeek pricing (as of late 2025): input $0.27/M, output $1.10/M tokens.
Override via --price-in / --price-out.
"""

from __future__ import annotations

import argparse
import csv
import json
from collections import defaultdict
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
RESULTS_DIR = REPO_ROOT / "benchmarks" / "drb2" / "results"
TIMINGS_PATH = REPO_ROOT / "benchmarks" / "drb2" / "run_timings.jsonl"


def collect_judge_usage(jsonl_path: Path) -> dict[str, int]:
    in_t = out_t = total_t = 0
    with jsonl_path.open() as fh:
        for line in fh:
            obj = json.loads(line)
            usage = (obj.get("result") or {}).get("usage_summary") or {}
            in_t += int(usage.get("input_tokens") or 0)
            out_t += int(usage.get("output_tokens") or 0)
            total_t += int(usage.get("total_tokens") or 0)
    return {"input_tokens": in_t, "output_tokens": out_t, "total_tokens": total_t}


def collect_run_seconds() -> dict[str, float]:
    """Sum elapsed_s across run_timings.jsonl, grouped by label."""
    if not TIMINGS_PATH.exists():
        return {}
    out: dict[str, float] = defaultdict(float)
    with TIMINGS_PATH.open() as fh:
        for line in fh:
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                continue
            if not obj.get("ok"):
                continue
            out[obj["label"]] += float(obj.get("elapsed_s") or 0.0)
    return dict(out)


def main() -> None:
    parser = argparse.ArgumentParser(description="Token + cost ledger for DRB-II runs.")
    parser.add_argument("--price-in", type=float, default=0.27, help="USD per 1M input tokens.")
    parser.add_argument("--price-out", type=float, default=1.10, help="USD per 1M output tokens.")
    parser.add_argument("--out-prefix", default="final")
    args = parser.parse_args()

    run_seconds = collect_run_seconds()
    rows: list[dict] = []
    for jsonl in sorted(RESULTS_DIR.glob("*__deepseek.jsonl")):
        label = jsonl.name.replace("__deepseek.jsonl", "")
        usage = collect_judge_usage(jsonl)
        cost = (
            usage["input_tokens"] / 1_000_000 * args.price_in
            + usage["output_tokens"] / 1_000_000 * args.price_out
        )
        rows.append({
            "label": label,
            "judge_input_tokens": usage["input_tokens"],
            "judge_output_tokens": usage["output_tokens"],
            "judge_total_tokens": usage["total_tokens"],
            "judge_cost_usd": round(cost, 4),
            "run_seconds": round(run_seconds.get(label, 0.0), 1),
            "run_minutes": round(run_seconds.get(label, 0.0) / 60.0, 1),
        })

    totals = {
        "label": "TOTAL",
        "judge_input_tokens": sum(r["judge_input_tokens"] for r in rows),
        "judge_output_tokens": sum(r["judge_output_tokens"] for r in rows),
        "judge_total_tokens": sum(r["judge_total_tokens"] for r in rows),
        "judge_cost_usd": round(sum(r["judge_cost_usd"] for r in rows), 4),
        "run_seconds": round(sum(r["run_seconds"] for r in rows), 1),
        "run_minutes": round(sum(r["run_minutes"] for r in rows), 1),
    }

    csv_path = RESULTS_DIR / f"{args.out_prefix}_cost_ledger.csv"
    md_path = RESULTS_DIR / f"{args.out_prefix}_cost_ledger.md"

    fields = list(totals.keys())
    with csv_path.open("w", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fields)
        writer.writeheader()
        for r in rows + [totals]:
            writer.writerow(r)

    lines = [
        "# DRB-II compute & cost ledger",
        "",
        f"DeepSeek pricing assumed: ${args.price_in:.2f}/M input, ${args.price_out:.2f}/M output. "
        "Costs cover the **judge** only — agent calls during runs are not summed here.",
        "",
        "| Label | Run min | Judge in tok | Judge out tok | Judge $ |",
        "|---|---|---|---|---|",
    ]
    for r in rows + [totals]:
        lines.append(
            f"| {r['label']} | {r['run_minutes']:.1f} | {r['judge_input_tokens']:,} | "
            f"{r['judge_output_tokens']:,} | ${r['judge_cost_usd']:.2f} |"
        )
    md_path.write_text("\n".join(lines) + "\n")

    print(f"[cost] wrote {csv_path}")
    print(f"[cost] wrote {md_path}")
    print(f"[cost] total judge tokens: {totals['judge_total_tokens']:,}, "
          f"total judge cost: ${totals['judge_cost_usd']:.2f}, "
          f"total run minutes: {totals['run_minutes']:.1f}")


if __name__ == "__main__":
    main()
