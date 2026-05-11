#!/usr/bin/env bash
# Chunk E resume: backfill idx-52 N=3 after the original chunk_e.sh wedge
# (httpx connection-pool deadlock during the original run). Memory state
# is preserved from the wedged run (has 8 within-theme entries from
# idx-54 x3, idx-56 x2, idx-58 x2). idx-52 starts with this warmed state,
# matching the experiment design intent (memory primed by within-theme
# content before idx-52 runs).
set -euo pipefail
cd "$(dirname "$0")/../.."
PY=.venv/bin/python
DRB2=../DeepResearch-Bench-II
LABEL=evoresearcher_education_n3
TASKS_FILE=benchmarks/drb2/pilot_tasks_education.json
LOG_DIR=benchmarks/drb2/runs
mkdir -p "$LOG_DIR"
LOGF="$LOG_DIR/chunk_e_resume_$(date +%Y%m%d_%H%M%S).log"

log() { echo "[chunk-E-resume] $*" | tee -a "$LOGF"; }
T0=$(date +%s)

log "start $(date)"
[[ -f .env ]] && { set -a; . .env; set +a; }
if [[ -z "${DEEPSEEK_API_KEY:-}" ]]; then
    log "ERROR: DEEPSEEK_API_KEY not set"
    exit 1
fi
log "env ok"

# Confirm preserved state before resuming
IDEATION_ENTRIES=$($PY -c "import json; d=json.load(open('memory/ideation_memory.json')); print(len(d) if isinstance(d, list) else len(d.get('entries', [])))")
PROPOSAL_ENTRIES=$($PY -c "import json; d=json.load(open('memory/proposal_memory.json')); print(len(d) if isinstance(d, list) else len(d.get('entries', [])))")
log "memory state at resume: $IDEATION_ENTRIES ideation, $PROPOSAL_ENTRIES proposal"
EXISTING_REPORTS=$(ls "$DRB2/report/$LABEL/" 2>/dev/null | wc -l | tr -d ' ')
log "existing successful reports: $EXISTING_REPORTS (should be 7: idx-54 x3, idx-56 x2, idx-58 x2)"

# Resume: idx-52 N=3 (overlap anchor) (~9 min)
log "=== RESUME: idx=52 N=3 (memory PRESERVED from wedged run) ==="
$PY benchmarks/drb2/run_evoresearcher.py \
    --trials 3 --only-idx 52 \
    --tasks-file "$TASKS_FILE" \
    --tree-depth 2 --branching-factor 2 --max-sources 6 \
    --label "$LABEL" 2>&1 | tee -a "$LOGF"

# Validate
RUN_SUMMARY=$($PY -c "
import json
rows = [json.loads(l) for l in open('benchmarks/drb2/run_timings.jsonl')]
relevant = [r for r in rows if r['label']=='$LABEL' and r['task_idx']==52][-3:]
ok = sum(1 for r in relevant if r.get('ok'))
print(f'idx-52 resume: {ok}/{len(relevant)} trials ok')
for r in relevant:
    print(f'  trial={r[\"trial\"]} ok={r.get(\"ok\")} elapsed={r.get(\"elapsed_s\")}s error={r.get(\"error\")}')
")
log "resume summary:"
echo "$RUN_SUMMARY" | tee -a "$LOGF"

log "post-resume reports staged:"
ls "$DRB2/report/$LABEL/" | sort | tee -a "$LOGF"

# Judge
log "=== JUDGE: $LABEL ==="
$PY benchmarks/drb2/evaluate_with_deepseek.py --label "$LABEL" 2>&1 | tee -a "$LOGF"

# Aggregate
log "=== AGGREGATE: education_followup ==="
$PY benchmarks/drb2/aggregate.py \
    --inputs "benchmarks/drb2/results/${LABEL}__deepseek.jsonl" \
    --out-prefix education_followup 2>&1 | tee -a "$LOGF"

log "=== AGGREGATE: education_vs_cold (idx-52 overlap with evoresearcher_n3) ==="
$PY benchmarks/drb2/aggregate.py \
    --inputs "benchmarks/drb2/results/evoresearcher_n3__deepseek.jsonl" \
            "benchmarks/drb2/results/${LABEL}__deepseek.jsonl" \
    --out-prefix education_vs_cold 2>&1 | tee -a "$LOGF"

$PY benchmarks/drb2/plot_matrix.py \
    --labels evoresearcher_n3 "$LABEL" \
    --out-prefix education_followup_matrix \
    --title "Within-theme EMA (Education, partial) vs cross-domain cold (evoresearcher_n3)" 2>&1 | tee -a "$LOGF" || log "plot failed (non-fatal)"

$PY benchmarks/drb2/cost_ledger.py --out-prefix education_followup 2>&1 | tee -a "$LOGF" || log "cost ledger failed (non-fatal)"

T1=$(date +%s)
log "DONE in $((T1-T0))s ($(((T1-T0)/60)) minutes wall)"
