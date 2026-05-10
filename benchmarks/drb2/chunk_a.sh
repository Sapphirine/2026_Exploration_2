#!/usr/bin/env bash
# Chunk A: step 1 default rerun N=3, judge, noise-floor artifact.
set -euo pipefail
cd "$(dirname "$0")/../.."
PY=.venv/bin/python
DRB2=../DeepResearch-Bench-II
LABEL=evoresearcher_n3
LOG_DIR=benchmarks/drb2/runs
mkdir -p "$LOG_DIR"
LOGF="$LOG_DIR/chunk_a_$(date +%Y%m%d_%H%M%S).log"

log() { echo "[chunk-A] $*" | tee -a "$LOGF"; }
T0=$(date +%s)

log "start $(date)"

# Pre-flight
log "pre-flight: backup + env check"
if [[ -d memory ]]; then
    cp -r memory memory.pilot.bak.$(date +%Y%m%d_%H%M%S) 2>/dev/null || true
fi
[[ -f .env ]] && { set -a; . .env; set +a; }
if [[ -z "${DEEPSEEK_API_KEY:-}" ]]; then
    log "ERROR: DEEPSEEK_API_KEY not set"
    exit 1
fi
log "env ok"

# Cold start
log "wiping memory + report dir for clean N=3 cold pass"
rm -rf memory
rm -rf "$DRB2/report/$LABEL"

# Sanity: idx=4 N=3 (~10 min)
log "=== SANITY: idx=4 N=3 ==="
$PY benchmarks/drb2/run_evoresearcher.py \
    --trials 3 --only-idx 4 \
    --tree-depth 2 --branching-factor 2 --max-sources 6 \
    --label "$LABEL" 2>&1 | tee -a "$LOGF"

# Validate sanity
SANITY=$($PY -c "
import json
rows = [json.loads(l) for l in open('benchmarks/drb2/run_timings.jsonl')]
relevant = [r for r in rows if r['label']=='$LABEL' and r['task_idx']==4][-3:]
ok = sum(1 for r in relevant if r.get('ok'))
print(f'{ok}/{len(relevant)}')
")
log "sanity trials ok: $SANITY (expect 3/3)"
if [[ "$SANITY" != "3/3" ]]; then
    log "SANITY FAILED. Abort before remainder."
    exit 2
fi

# Remainder: idx=16,42,52,68 N=3 (~40 min)
log "=== REMAINDER: idx=16,42,52,68 N=3 ==="
$PY benchmarks/drb2/run_evoresearcher.py \
    --trials 3 --only-idx 16,42,52,68 \
    --tree-depth 2 --branching-factor 2 --max-sources 6 \
    --label "$LABEL" 2>&1 | tee -a "$LOGF"

# Final run validation
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

# Judge (~5 min)
log "=== JUDGE: $LABEL ==="
$PY benchmarks/drb2/evaluate_with_deepseek.py --label "$LABEL" 2>&1 | tee -a "$LOGF"

# Per-condition aggregate
log "=== AGGREGATE: step1_only ==="
$PY benchmarks/drb2/aggregate.py \
    --inputs "benchmarks/drb2/results/${LABEL}__deepseek.jsonl" \
    --out-prefix step1_only 2>&1 | tee -a "$LOGF"

# Noise-floor artifact
log "=== NOISE FLOOR: claim_summary (Claims 1/2/4 will show PENDING) ==="
$PY benchmarks/drb2/claim_summary.py --noise-label "$LABEL" --out-prefix step1_only 2>&1 | tee -a "$LOGF"

# Plot for this condition
log "=== PLOT: step1_only ==="
$PY benchmarks/drb2/plot_matrix.py \
    --labels "$LABEL" \
    --out-prefix step1_only_matrix \
    --title "Chunk A noise floor: $LABEL (N=3, 5 EN tasks)" 2>&1 | tee -a "$LOGF"

# Cost ledger snapshot
$PY benchmarks/drb2/cost_ledger.py --out-prefix step1_only 2>&1 | tee -a "$LOGF"

T1=$(date +%s)
log "DONE in $((T1-T0))s ($((T1-T0))/60 minutes wall)"
log "artifacts:"
log "  - $DRB2/report/$LABEL/idx-{4,16,42,52,68}-trial-{1,2,3}.md"
log "  - benchmarks/drb2/results/${LABEL}__deepseek.jsonl"
log "  - benchmarks/drb2/results/step1_only_summary.md"
log "  - benchmarks/drb2/results/step1_only_per_task.csv"
log "  - benchmarks/drb2/results/step1_only_claim_summary.md"
log "  - benchmarks/drb2/results/step1_only_matrix.png"
log "  - benchmarks/drb2/results/step1_only_cost_ledger.md"
