#!/usr/bin/env bash
# Chunk E: within-theme EMA pass (N=3) on 4 EN Education/GenAI tasks.
# Sequence: idx-54 -> idx-56 -> idx-58 -> idx-52 (idx-52 last, so it runs
# with the maximum accumulated within-theme memory state).
# idx-52 is the overlap anchor: it appears in the existing evoresearcher_n3
# cold-memory row, so warm-vs-cold can be compared on the same task.
# Memory is wiped at start: this is a *fresh* within-theme store, not
# building on the cross-domain memory from Chunk A/B.
set -euo pipefail
cd "$(dirname "$0")/../.."
PY=.venv/bin/python
DRB2=../DeepResearch-Bench-II
LABEL=evoresearcher_education_n3
TASKS_FILE=benchmarks/drb2/pilot_tasks_education.json
LOG_DIR=benchmarks/drb2/runs
mkdir -p "$LOG_DIR"
LOGF="$LOG_DIR/chunk_e_$(date +%Y%m%d_%H%M%S).log"

log() { echo "[chunk-E] $*" | tee -a "$LOGF"; }
T0=$(date +%s)

log "start $(date)"

# Pre-flight: backup existing memory + load env
log "pre-flight: backup + env check"
if [[ -d memory ]]; then
    cp -r memory memory.education.bak.$(date +%Y%m%d_%H%M%S) 2>/dev/null || true
fi
[[ -f .env ]] && { set -a; . .env; set +a; }
if [[ -z "${DEEPSEEK_API_KEY:-}" ]]; then
    log "ERROR: DEEPSEEK_API_KEY not set"
    exit 1
fi
[[ -f "$TASKS_FILE" ]] || { log "ERROR: tasks file missing: $TASKS_FILE"; exit 1; }
log "env ok; tasks file: $TASKS_FILE"

# Fresh within-theme memory state
log "wiping memory/ + $DRB2/report/$LABEL for fresh within-theme pass"
rm -rf memory
rm -rf "$DRB2/report/$LABEL"

# Sanity gate: idx-54 N=3 first (~8 min). If it 3/3s, the rest is safe.
log "=== SANITY: idx=54 N=3 (memory accumulates from this point) ==="
$PY benchmarks/drb2/run_evoresearcher.py \
    --trials 3 --only-idx 54 \
    --tasks-file "$TASKS_FILE" \
    --tree-depth 2 --branching-factor 2 --max-sources 6 \
    --label "$LABEL" 2>&1 | tee -a "$LOGF"

SANITY=$($PY -c "
import json
rows = [json.loads(l) for l in open('benchmarks/drb2/run_timings.jsonl')]
relevant = [r for r in rows if r['label']=='$LABEL' and r['task_idx']==54][-3:]
ok = sum(1 for r in relevant if r.get('ok'))
print(f'{ok}/{len(relevant)}')
")
log "sanity trials ok: $SANITY (expect 3/3)"
if [[ "$SANITY" != "3/3" ]]; then
    log "SANITY FAILED. Abort before remainder."
    exit 2
fi

# Remainder: idx-56, 58, 52 N=3 (in this order; memory carries over) (~25 min)
log "=== REMAINDER: idx=56,58,52 N=3 (in order; memory PRESERVED across tasks) ==="
$PY benchmarks/drb2/run_evoresearcher.py \
    --trials 3 --only-idx 56,58,52 \
    --tasks-file "$TASKS_FILE" \
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

# Memory state check
IDEATION_ENTRIES=$($PY -c "import json; d=json.load(open('memory/ideation_memory.json')); print(len(d) if isinstance(d, list) else len(d.get('entries', [])))")
PROPOSAL_ENTRIES=$($PY -c "import json; d=json.load(open('memory/proposal_memory.json')); print(len(d) if isinstance(d, list) else len(d.get('entries', [])))")
log "post-run memory state: $IDEATION_ENTRIES ideation, $PROPOSAL_ENTRIES proposal entries (expect ~12 each)"

# Judge (~5 min)
log "=== JUDGE: $LABEL ==="
$PY benchmarks/drb2/evaluate_with_deepseek.py --label "$LABEL" 2>&1 | tee -a "$LOGF"

# Aggregate this label alone
log "=== AGGREGATE: education_followup ==="
$PY benchmarks/drb2/aggregate.py \
    --inputs "benchmarks/drb2/results/${LABEL}__deepseek.jsonl" \
    --out-prefix education_followup 2>&1 | tee -a "$LOGF"

# Comparison: idx-52 cold (from evoresearcher_n3) vs idx-52 warm (from this run)
log "=== AGGREGATE: education_vs_cold (idx-52 overlap) ==="
$PY benchmarks/drb2/aggregate.py \
    --inputs "benchmarks/drb2/results/evoresearcher_n3__deepseek.jsonl" \
            "benchmarks/drb2/results/${LABEL}__deepseek.jsonl" \
    --out-prefix education_vs_cold 2>&1 | tee -a "$LOGF"

# Plot the side-by-side
log "=== PLOT: education follow-up vs cold default ==="
$PY benchmarks/drb2/plot_matrix.py \
    --labels evoresearcher_n3 "$LABEL" \
    --out-prefix education_followup_matrix \
    --title "Within-theme EMA (idx 54,56,58,52 Education) vs cross-domain cold (evoresearcher_n3)" 2>&1 | tee -a "$LOGF" || \
    log "plot failed (non-fatal)"

# Cost ledger
$PY benchmarks/drb2/cost_ledger.py --out-prefix education_followup 2>&1 | tee -a "$LOGF" || \
    log "cost ledger failed (non-fatal)"

T1=$(date +%s)
log "DONE in $((T1-T0))s ($(((T1-T0)/60)) minutes wall)"
log "key artifacts:"
log "  - $DRB2/report/$LABEL/idx-{54,56,58,52}-trial-{1,2,3}.md"
log "  - benchmarks/drb2/results/${LABEL}__deepseek.jsonl"
log "  - benchmarks/drb2/results/education_followup_summary.md"
log "  - benchmarks/drb2/results/education_vs_cold_summary.md"
log "  - benchmarks/drb2/results/education_followup_matrix.png"
