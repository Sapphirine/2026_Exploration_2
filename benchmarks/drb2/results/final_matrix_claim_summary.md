# DRB-II claim-level deltas

Noise floor: trial-level std of `evoresearcher_n3` total pass-rate = **11.88 pp** (mean 21.79%, 15 trials).

A delta exceeds the noise floor when |delta| > noise_std. Verdict = SUPPORTED if (a) sign matches expectation AND (b) delta exceeds noise; INCONCLUSIVE if sign matches but delta < noise; NOT SUPPORTED otherwise.

| Claim | Baseline | Ablation | Baseline | Ablation | Δ (pp) | Noise (pp) | Verdict |
|---|---|---|---|---|---|---|---|
| Claim 1 (Tree guidance) | `evoresearcher_n3` | `evoresearcher_blind_n3` | 21.79% | 22.97% | -1.19 | 11.88 | NOT SUPPORTED |
| Claim 2 (Elo ranking) | `evoresearcher_n3` | `evoresearcher_noelo_n3` | 21.79% | 18.81% | +2.98 | 11.88 | INCONCLUSIVE |
| Claim 4 (EMA gain) | `evoresearcher_n3` | `evoresearcher_warm_n3` | 21.79% | 22.56% | +0.77 | 11.88 | INCONCLUSIVE |

## Per-claim notes
- **Claim 1 (Tree guidance)** — Review-guided tree expansion outperforms blind expansion.  
  Default N=3 minus A_TREE blind. Positive delta means the review-guided structure earns its keep.
- **Claim 2 (Elo ranking)** — Elo tournament beats sort-by-score for top-1 selection.  
  Default N=3 minus A_ELO sort-by-score. Positive delta means Elo earns its keep.
- **Claim 4 (EMA gain)** — Warm memory pass beats cold pass.  
  Warm pass minus cold default. Positive delta means EMA adds signal.
