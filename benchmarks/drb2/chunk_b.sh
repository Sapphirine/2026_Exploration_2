#!/usr/bin/env bash
# Chunk B: A3 warm-memory pass (N=3) + judge + Claim 4 verdict.
# CRITICAL: do NOT wipe memory/. Reuses Chunk A's writes.
set -euo pipefail
cd "$(dirname "$0")/../.."
PY=.venv/bin/python
DRB2=../DeepResearch-Bench-II
LABEL=evoresearcher_warm_n3
LOG_DIR=benchmarks/drb2/runs
mkdir -p "$LOG_DIR"
LOGF="$LOG_DIR/chunk_b_$(date +%Y%m%d_%H%M%S).log"

log() { echo "[chunk-B] $*" | tee -a "$LOGF"; }
T0=$(date +%s)

log "start $(date)"

# Pre-flight
[[ -f .env ]] && { set -a; . .env; set +a; }
if [[ -z "${DEEPSEEK_API_KEY:-}" ]]; then
    log "ERROR: DEEPSEEK_API_KEY not set"
    exit 1
fi
log "env ok"

# Verify memory is NOT empty (the whole point of warm)
if [[ ! -f memory/ideation_memory.json ]] || [[ ! -f memory/proposal_memory.json ]]; then
    log "ERROR: memory/ missing — chunk B requires Chunk A's memory state"
    exit 1
fi
IDEATION_ENTRIES=$($PY -c "import json; d=json.load(open('memory/ideation_memory.json')); print(len(d) if isinstance(d, list) else len(d.get('entries', [])))")
PROPOSAL_ENTRIES=$($PY -c "import json; d=json.load(open('memory/proposal_memory.json')); print(len(d) if isinstance(d, list) else len(d.get('entries', [])))")
log "memory state: $IDEATION_ENTRIES ideation entries, $PROPOSAL_ENTRIES proposal entries"
if [[ "$IDEATION_ENTRIES" -lt 5 ]] || [[ "$PROPOSAL_ENTRIES" -lt 5 ]]; then
    log "WARN: memory has fewer entries than expected (expected >=15 from Chunk A's 15 trials)."
fi

# Wipe ONLY the report dir (not memory!)
log "wiping ONLY report dir for clean warm-pass output"
rm -rf "$DRB2/report/$LABEL"

# Run all 5 tasks N=3 with warm memory (~50 min)
log "=== WARM RUN: 5 tasks N=3 (memory PRESERVED) ==="
$PY benchmarks/drb2/run_evoresearcher.py \
    --trials 3 \
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

# Judge (~5 min)
log "=== JUDGE: $LABEL ==="
$PY benchmarks/drb2/evaluate_with_deepseek.py --label "$LABEL" 2>&1 | tee -a "$LOGF"

# Aggregate this label
log "=== AGGREGATE: step2_only ==="
$PY benchmarks/drb2/aggregate.py \
    --inputs "benchmarks/drb2/results/${LABEL}__deepseek.jsonl" \
    --out-prefix step2_only 2>&1 | tee -a "$LOGF"

# A→B comparison: aggregate both conditions side-by-side
log "=== AGGREGATE: A_vs_B (cold default vs warm) ==="
$PY benchmarks/drb2/aggregate.py \
    --inputs "benchmarks/drb2/results/evoresearcher_n3__deepseek.jsonl" \
            "benchmarks/drb2/results/${LABEL}__deepseek.jsonl" \
    --out-prefix step1_vs_step2 2>&1 | tee -a "$LOGF"

# Claim summary — Claim 4 (EMA gain) will now have a real verdict
log "=== CLAIM SUMMARY (Claim 4 EMA verdict ready) ==="
$PY benchmarks/drb2/claim_summary.py \
    --noise-label evoresearcher_n3 \
    --out-prefix step1_vs_step2 2>&1 | tee -a "$LOGF"

# Side-by-side plot
log "=== PLOT: A vs B ==="
$PY benchmarks/drb2/plot_matrix.py \
    --labels evoresearcher_n3 "$LABEL" \
    --out-prefix step1_vs_step2_matrix \
    --title "Chunks A and B: cold (evoresearcher_n3) vs warm (evoresearcher_warm_n3)" 2>&1 | tee -a "$LOGF"

# Cost ledger snapshot
$PY benchmarks/drb2/cost_ledger.py --out-prefix step1_vs_step2 2>&1 | tee -a "$LOGF"

T1=$(date +%s)
log "DONE in $((T1-T0))s ($((T1-T0))/60 minutes wall)"
log "key artifacts:"
log "  - $DRB2/report/$LABEL/idx-{4,16,42,52,68}-trial-{1,2,3}.md"
log "  - benchmarks/drb2/results/${LABEL}__deepseek.jsonl"
log "  - benchmarks/drb2/results/step1_vs_step2_summary.md"
log "  - benchmarks/drb2/results/step1_vs_step2_claim_summary.md"
log "  - benchmarks/drb2/results/step1_vs_step2_matrix.png"
log "  - benchmarks/drb2/results/step1_vs_step2_cost_ledger.md"
