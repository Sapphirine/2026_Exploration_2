"""Claim-level deltas vs the noise floor for DRB-II ablations.

Reads benchmarks/drb2/results/*__deepseek.jsonl. For each registered claim,
computes the delta between the ablation condition and its baseline, and
compares it to the noise floor (std of the default N=3 condition across
trials). Emits results/<out>_claim_summary.md and .csv.

The claim registry is intentionally explicit so reviewers can audit which
comparison maps to which Claim in the writeup.
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

# Each claim: (claim id, label, baseline label, ablation label, expected sign)
# expected_sign = "+": ablation should improve over baseline (warm > cold)
# expected_sign = "-": ablation should drop vs baseline (blind < default; noelo < default)
CLAIMS: list[dict] = [
    {
        "claim_id": "Claim 1 (Tree guidance)",
        "summary": "Review-guided tree expansion outperforms blind expansion.",
        "baseline": "evoresearcher_n3",
        "ablation": "evoresearcher_blind_n3",
        "expected_sign": "-",
        "description": "Default N=3 minus A_TREE blind. Positive delta means the review-guided structure earns its keep.",
    },
    {
        "claim_id": "Claim 2 (Elo ranking)",
        "summary": "Elo tournament beats sort-by-score for top-1 selection.",
        "baseline": "evoresearcher_n3",
        "ablation": "evoresearcher_noelo_n3",
        "expected_sign": "-",
        "description": "Default N=3 minus A_ELO sort-by-score. Positive delta means Elo earns its keep.",
    },
    {
        "claim_id": "Claim 4 (EMA gain)",
        "summary": "Warm memory pass beats cold pass.",
        "baseline": "evoresearcher_n3",
        "ablation": "evoresearcher_warm_n3",
        "expected_sign": "+",
        "description": "Warm pass minus cold default. Positive delta means EMA adds signal.",
    },
]


def _pass_rate(per_item: dict | None) -> float:
    if not per_item:
        return 0.0
    return sum(1 for v in per_item.values() if v.get("score") == 1) / len(per_item)


def per_trial_totals(jsonl_path: Path) -> list[float]:
    """Return one total pass-rate per (idx, trial) row."""
    out: list[float] = []
    with jsonl_path.open() as fh:
        for line in fh:
            obj = json.loads(line)
            res = obj.get("result") or {}
            if "error" in res:
                continue
            scores = res.get("scores", {})
            allof = {
                **(scores.get("info_recall", {}) or {}),
                **(scores.get("analysis", {}) or {}),
                **(scores.get("presentation", {}) or {}),
            }
            out.append(_pass_rate(allof))
    return out


def per_task_means(jsonl_path: Path) -> dict[int, float]:
    """Return idx -> mean total pass-rate across that idx's trials."""
    by_idx: dict[int, list[float]] = defaultdict(list)
    with jsonl_path.open() as fh:
        for line in fh:
            obj = json.loads(line)
            res = obj.get("result") or {}
            if "error" in res:
                continue
            scores = res.get("scores", {})
            allof = {
                **(scores.get("info_recall", {}) or {}),
                **(scores.get("analysis", {}) or {}),
                **(scores.get("presentation", {}) or {}),
            }
            by_idx[int(obj["idx"])].append(_pass_rate(allof))
    return {idx: mean(v) for idx, v in by_idx.items() if v}


def _agg(vals: list[float]) -> tuple[float, float]:
    if not vals:
        return 0.0, 0.0
    if len(vals) == 1:
        return vals[0], 0.0
    return mean(vals), stdev(vals)


def main() -> None:
    parser = argparse.ArgumentParser(description="Compute claim-level deltas vs noise floor.")
    parser.add_argument("--noise-label", default="evoresearcher_n3", help="Condition whose trial-level std defines the noise floor.")
    parser.add_argument("--out-prefix", default="final")
    args = parser.parse_args()

    noise_path = RESULTS_DIR / f"{args.noise_label}__deepseek.jsonl"
    if not noise_path.exists():
        raise SystemExit(f"Noise label not graded yet: {noise_path}")
    noise_trials = per_trial_totals(noise_path)
    noise_mean, noise_std = _agg(noise_trials)
    print(f"[claim] noise floor ({args.noise_label}, N={len(noise_trials)} trials): mean={noise_mean:.3f} std={noise_std:.3f}")

    rows: list[dict] = []
    for claim in CLAIMS:
        base_path = RESULTS_DIR / f"{claim['baseline']}__deepseek.jsonl"
        abl_path = RESULTS_DIR / f"{claim['ablation']}__deepseek.jsonl"
        if not base_path.exists() or not abl_path.exists():
            rows.append({
                **claim,
                "baseline_mean": None,
                "ablation_mean": None,
                "delta": None,
                "noise_std": noise_std,
                "exceeds_noise": None,
                "expected_sign_match": None,
                "verdict": "PENDING (missing run)",
            })
            continue
        base_mean, _ = _agg(per_trial_totals(base_path))
        abl_mean, _ = _agg(per_trial_totals(abl_path))
        # For "+" expected sign, delta = ablation - baseline (we want positive).
        # For "-" expected sign, delta = baseline - ablation (we want positive: how much we'd lose).
        if claim["expected_sign"] == "+":
            delta = abl_mean - base_mean
        else:
            delta = base_mean - abl_mean
        exceeds = abs(delta) > noise_std
        sign_match = delta > 0
        verdict = "SUPPORTED" if (sign_match and exceeds) else ("INCONCLUSIVE" if sign_match else "NOT SUPPORTED")
        rows.append({
            **claim,
            "baseline_mean": base_mean,
            "ablation_mean": abl_mean,
            "delta": delta,
            "noise_std": noise_std,
            "exceeds_noise": exceeds,
            "expected_sign_match": sign_match,
            "verdict": verdict,
        })

    csv_path = RESULTS_DIR / f"{args.out_prefix}_claim_summary.csv"
    md_path = RESULTS_DIR / f"{args.out_prefix}_claim_summary.md"

    with csv_path.open("w", newline="") as fh:
        writer = csv.DictWriter(
            fh,
            fieldnames=[
                "claim_id", "summary", "baseline", "ablation", "expected_sign",
                "baseline_mean", "ablation_mean", "delta", "noise_std",
                "exceeds_noise", "expected_sign_match", "verdict", "description",
            ],
        )
        writer.writeheader()
        for r in rows:
            writer.writerow(r)

    lines = [
        "# DRB-II claim-level deltas",
        "",
        f"Noise floor: trial-level std of `{args.noise_label}` total pass-rate "
        f"= **{noise_std*100:.2f} pp** (mean {noise_mean*100:.2f}%, "
        f"{len(noise_trials)} trials).",
        "",
        "A delta exceeds the noise floor when |delta| > noise_std. "
        "Verdict = SUPPORTED if (a) sign matches expectation AND (b) delta exceeds noise; "
        "INCONCLUSIVE if sign matches but delta < noise; NOT SUPPORTED otherwise.",
        "",
        "| Claim | Baseline | Ablation | Baseline | Ablation | Δ (pp) | Noise (pp) | Verdict |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for r in rows:
        bm = "—" if r["baseline_mean"] is None else f"{r['baseline_mean']*100:.2f}%"
        am = "—" if r["ablation_mean"] is None else f"{r['ablation_mean']*100:.2f}%"
        d = "—" if r["delta"] is None else f"{r['delta']*100:+.2f}"
        n = f"{r['noise_std']*100:.2f}"
        lines.append(
            f"| {r['claim_id']} | `{r['baseline']}` | `{r['ablation']}` | {bm} | {am} | {d} | {n} | {r['verdict']} |"
        )
    lines.append("")
    lines.append("## Per-claim notes")
    for r in rows:
        lines.append(f"- **{r['claim_id']}** — {r['summary']}  ")
        lines.append(f"  {r['description']}")
    md_path.write_text("\n".join(lines) + "\n")

    print(f"[claim] wrote {csv_path}")
    print(f"[claim] wrote {md_path}")
    for r in rows:
        if r["delta"] is None:
            print(f"  {r['claim_id']}: PENDING")
        else:
            print(f"  {r['claim_id']}: Δ={r['delta']*100:+.2f}pp  noise={r['noise_std']*100:.2f}pp  -> {r['verdict']}")


if __name__ == "__main__":
    main()
