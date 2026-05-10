#!/usr/bin/env bash
# Chunk C: A_TREE blind expansion (N=3) + judge + Claim 1 verdict.
# Cold start (memory wiped) for a clean ablation.
set -euo pipefail
cd "$(dirname "$0")/../.."
PY=.venv/bin/python
DRB2=../DeepResearch-Bench-II
LABEL=evoresearcher_blind_n3
LOG_DIR=benchmarks/drb2/runs
mkdir -p "$LOG_DIR"
LOGF="$LOG_DIR/chunk_c_$(date +%Y%m%d_%H%M%S).log"

log() { echo "[chunk-C] $*" | tee -a "$LOGF"; }
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

# Run all 5 tasks N=3 with --blind-expansion (~50 min)
log "=== A_TREE BLIND: 5 tasks N=3 (memory cold, --blind-expansion) ==="
$PY benchmarks/drb2/run_evoresearcher.py \
    --trials 3 --blind-expansion \
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

# Sanity check: the timings rows must record blind_expansion=True
BLIND_FLAG_OK=$($PY -c "
import json
rows = [json.loads(l) for l in open('benchmarks/drb2/run_timings.jsonl')]
relevant = [r for r in rows if r['label']=='$LABEL']
if not relevant:
    print('NONE')
else:
    flags = {r['settings'].get('blind_expansion') for r in relevant}
    print('OK' if flags == {True} else f'BAD: {flags}')
")
log "settings.blind_expansion across all trials: $BLIND_FLAG_OK"
if [[ "$BLIND_FLAG_OK" != "OK" ]]; then
    log "WARN: blind_expansion flag not set on every trial — provenance broken"
fi

# Judge (~5 min)
log "=== JUDGE: $LABEL ==="
$PY benchmarks/drb2/evaluate_with_deepseek.py --label "$LABEL" 2>&1 | tee -a "$LOGF"

# Aggregate this label
log "=== AGGREGATE: step3_only ==="
$PY benchmarks/drb2/aggregate.py \
    --inputs "benchmarks/drb2/results/${LABEL}__deepseek.jsonl" \
    --out-prefix step3_only 2>&1 | tee -a "$LOGF"

# Cumulative aggregate through chunk C
log "=== AGGREGATE: through_step3 (A + B + C) ==="
$PY benchmarks/drb2/aggregate.py \
    --inputs \
        "benchmarks/drb2/results/evoresearcher_n3__deepseek.jsonl" \
        "benchmarks/drb2/results/evoresearcher_warm_n3__deepseek.jsonl" \
        "benchmarks/drb2/results/${LABEL}__deepseek.jsonl" \
    --out-prefix through_step3 2>&1 | tee -a "$LOGF"

# Claim summary — Claim 1 (Tree guidance) verdict ready; Claim 4 (EMA) re-stated
log "=== CLAIM SUMMARY (Claim 1 verdict ready) ==="
$PY benchmarks/drb2/claim_summary.py \
    --noise-label evoresearcher_n3 \
    --out-prefix through_step3 2>&1 | tee -a "$LOGF"

# Plot all three conditions side-by-side
log "=== PLOT: A vs B vs C ==="
$PY benchmarks/drb2/plot_matrix.py \
    --labels evoresearcher_n3 evoresearcher_warm_n3 "$LABEL" \
    --out-prefix through_step3_matrix \
    --title "Through Chunk C: cold (default) vs warm (EMA) vs blind (no review-guided expansion)" 2>&1 | tee -a "$LOGF"

# Cost ledger snapshot
$PY benchmarks/drb2/cost_ledger.py --out-prefix through_step3 2>&1 | tee -a "$LOGF"

T1=$(date +%s)
log "DONE in $((T1-T0))s ($((T1-T0))/60 minutes wall)"
log "key artifacts:"
log "  - $DRB2/report/$LABEL/idx-{4,16,42,52,68}-trial-{1,2,3}.md"
log "  - benchmarks/drb2/results/${LABEL}__deepseek.jsonl"
log "  - benchmarks/drb2/results/through_step3_summary.md"
log "  - benchmarks/drb2/results/through_step3_claim_summary.md"
log "  - benchmarks/drb2/results/through_step3_matrix.png"
log "  - benchmarks/drb2/results/through_step3_cost_ledger.md"
