#!/usr/bin/env bash
# Chunk D: A_ELO sort-by-score (N=3) + judge + Claim 2 verdict.
# Cold start (memory wiped) for a clean ablation. Skips the Elo tournament,
# selects top-1 by total_score directly.
set -euo pipefail
cd "$(dirname "$0")/../.."
PY=.venv/bin/python
DRB2=../DeepResearch-Bench-II
LABEL=evoresearcher_noelo_n3
LOG_DIR=benchmarks/drb2/runs
mkdir -p "$LOG_DIR"
LOGF="$LOG_DIR/chunk_d_$(date +%Y%m%d_%H%M%S).log"

log() { echo "[chunk-D] $*" | tee -a "$LOGF"; }
T0=$(date +%s)

log "start $(date)"

# Pre-flight
[[ -f .env ]] && { set -a; . .env; set +a; }
if [[ -z "${DEEPSEEK_API_KEY:-}" ]]; then
    log "ERROR: DEEPSEEK_API_KEY not set"
    exit 1
fi
log "env ok"

# Cold start: wipe memory + report dir
log "wiping memory (cold start) + report dir for ablation purity"
rm -rf memory
rm -rf "$DRB2/report/$LABEL"

# Run all 5 tasks N=3 with --no-elo (~45 min — faster than default since no Elo calls)
log "=== A_ELO SORT-BY-SCORE: 5 tasks N=3 (memory cold, --no-elo) ==="
$PY benchmarks/drb2/run_evoresearcher.py \
    --trials 3 --no-elo \
    --tree-depth 2 --branching-factor 2 --max-sources 6 \
    --label "$LABEL" 2>&1 | tee -a "$LOGF"

# Run validation
RUN_SUMMARY=$($PY -c "
import json
rows = [json.loads(l) for l in open('benchmarks/drb2/run_timings.jsonl')]
relevant = [r for r in rows if r['label']=='$LABEL']
ok = sum(1 for r in relevant if r.get('ok'))
fails = [(r['task_idx'], r['trial'], r['error']) for r in relevant if not r.get('ok')]
print(f'{ok} ok of {len(relevant)} trials')
for f in fails:
    print(f'FAIL: idx={f[0]} trial={f[1]}: {f[2]}')
")
log "run summary:"
echo "$RUN_SUMMARY" | tee -a "$LOGF"

# Provenance check: verify --no-elo flag recorded on every trial
NOELO_FLAG_OK=$($PY -c "
import json
rows = [json.loads(l) for l in open('benchmarks/drb2/run_timings.jsonl')]
relevant = [r for r in rows if r['label']=='$LABEL']
if not relevant:
    print('NONE')
else:
    flags = {r['settings'].get('skip_elo') for r in relevant}
    print('OK' if flags == {True} else f'BAD: {flags}')
")
log "settings.skip_elo across all trials: $NOELO_FLAG_OK"

# Judge (~5 min)
log "=== JUDGE: $LABEL ==="
$PY benchmarks/drb2/evaluate_with_deepseek.py --label "$LABEL" 2>&1 | tee -a "$LOGF"

# Aggregate this label
log "=== AGGREGATE: step4_only ==="
$PY benchmarks/drb2/aggregate.py \
    --inputs "benchmarks/drb2/results/${LABEL}__deepseek.jsonl" \
    --out-prefix step4_only 2>&1 | tee -a "$LOGF"

# Cumulative aggregate through chunk D — all four N=3 conditions
log "=== AGGREGATE: through_step4 (A + B + C + D, all N=3 conditions) ==="
$PY benchmarks/drb2/aggregate.py \
    --inputs \
        "benchmarks/drb2/results/evoresearcher_n3__deepseek.jsonl" \
        "benchmarks/drb2/results/evoresearcher_warm_n3__deepseek.jsonl" \
        "benchmarks/drb2/results/evoresearcher_blind_n3__deepseek.jsonl" \
        "benchmarks/drb2/results/${LABEL}__deepseek.jsonl" \
    --out-prefix through_step4 2>&1 | tee -a "$LOGF"

# Claim summary — all three claims now have verdicts
log "=== CLAIM SUMMARY (all three claims have verdicts) ==="
$PY benchmarks/drb2/claim_summary.py \
    --noise-label evoresearcher_n3 \
    --out-prefix through_step4 2>&1 | tee -a "$LOGF"

# Plot all four conditions side-by-side
log "=== PLOT: A vs B vs C vs D ==="
$PY benchmarks/drb2/plot_matrix.py \
    --labels evoresearcher_n3 evoresearcher_warm_n3 evoresearcher_blind_n3 "$LABEL" \
    --out-prefix through_step4_matrix \
    --title "Through Chunk D: cold default vs warm vs blind vs no-elo (N=3 each)" 2>&1 | tee -a "$LOGF"

# Cost ledger snapshot
$PY benchmarks/drb2/cost_ledger.py --out-prefix through_step4 2>&1 | tee -a "$LOGF"

T1=$(date +%s)
log "DONE in $((T1-T0))s ($((T1-T0))/60 minutes wall)"
log "key artifacts:"
log "  - $DRB2/report/$LABEL/idx-{4,16,42,52,68}-trial-{1,2,3}.md"
log "  - benchmarks/drb2/results/${LABEL}__deepseek.jsonl"
log "  - benchmarks/drb2/results/through_step4_summary.md"
log "  - benchmarks/drb2/results/through_step4_claim_summary.md"
log "  - benchmarks/drb2/results/through_step4_matrix.png"
log "  - benchmarks/drb2/results/through_step4_cost_ledger.md"
