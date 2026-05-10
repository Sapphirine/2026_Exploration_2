#!/usr/bin/env bash
# Run the full DRB-II ablation matrix per benchmarks/drb2/TODO.md.
#
# Steps (executed in order, each one is independently --skip-able):
#   1. evoresearcher_n3       - default rerun, N=3 (also = A3 cold pass)
#   2. evoresearcher_warm_n3  - A3 warm pass; reuses memory from step 1
#   3. evoresearcher_blind_n3 - A_TREE ablation
#   4. evoresearcher_noelo_n3 - A_ELO ablation
#   5. hf_baselines           - Perplexity-Research + Qwen-3-Max-DeepResearch (re-graded)
#   6. aggregate              - final matrix
#
# Usage:
#   bash benchmarks/drb2/run_all.sh                # run all
#   bash benchmarks/drb2/run_all.sh --dry-run      # echo commands
#   bash benchmarks/drb2/run_all.sh --steps 1,3,4  # run subset (must be ordered)
#   bash benchmarks/drb2/run_all.sh --resume       # don't wipe, don't re-run already-graded labels

set -euo pipefail

cd "$(dirname "$0")/../.."
REPO_ROOT="$(pwd)"
PY=.venv/bin/python
DRB2="$REPO_ROOT/../DeepResearch-Bench-II"
LOG_DIR="$REPO_ROOT/benchmarks/drb2/runs"
mkdir -p "$LOG_DIR"

DRY_RUN=0
RESUME=0
STEPS="1,2,3,4,5,6"

while [[ $# -gt 0 ]]; do
    case "$1" in
        --dry-run) DRY_RUN=1; shift ;;
        --resume)  RESUME=1; shift ;;
        --steps)   STEPS="$2"; shift 2 ;;
        -h|--help)
            sed -n '2,30p' "$0"
            exit 0
            ;;
        *) echo "unknown arg: $1" >&2; exit 2 ;;
    esac
done

step_enabled() {
    local s=$1
    [[ ",$STEPS," == *",$s,"* ]]
}

run() {
    local label=$1; shift
    local logf="$LOG_DIR/run_all_${label}.log"
    echo
    echo "=== [$label] $(date) ==="
    echo "$ $*"
    echo "  log: $logf"
    if [[ $DRY_RUN -eq 1 ]]; then return 0; fi
    # tee preserves human-readable output; pipefail ensures we still abort on error.
    "$@" 2>&1 | tee "$logf"
}

wipe_memory() {
    echo "  wiping memory/"
    if [[ $DRY_RUN -eq 1 ]]; then return 0; fi
    rm -rf "$REPO_ROOT/memory"
}

wipe_report() {
    local label=$1
    echo "  wiping $DRB2/report/$label"
    if [[ $DRY_RUN -eq 1 ]]; then return 0; fi
    rm -rf "$DRB2/report/$label"
}

# Pre-flight: confirm DRB-II repo exists and api key is set
if [[ ! -d "$DRB2" ]]; then
    echo "ERROR: DRB-II repo not found at $DRB2" >&2
    exit 1
fi
if [[ -f "$REPO_ROOT/.env" ]]; then
    set -a; . "$REPO_ROOT/.env"; set +a
fi
if [[ -z "${DEEPSEEK_API_KEY:-}" ]]; then
    echo "ERROR: DEEPSEEK_API_KEY not set" >&2
    exit 1
fi

echo "[run_all] starting at $(date)"
echo "[run_all] STEPS=$STEPS DRY_RUN=$DRY_RUN RESUME=$RESUME"

###############################################################################
# Step 1: evoresearcher_n3 (default rerun, N=3) -- cold memory
###############################################################################
if step_enabled 1; then
    echo
    echo "########## STEP 1/6: evoresearcher_n3 (default rerun, N=3) ##########"
    if [[ $RESUME -ne 1 ]]; then
        wipe_memory
        wipe_report evoresearcher_n3
    fi
    run evoresearcher_n3 \
        $PY benchmarks/drb2/run_evoresearcher.py \
        --trials 3 \
        --tree-depth 2 --branching-factor 2 --max-sources 6 \
        --label evoresearcher_n3
    run evoresearcher_n3_judge \
        $PY benchmarks/drb2/evaluate_with_deepseek.py --label evoresearcher_n3
fi

###############################################################################
# Step 2: evoresearcher_warm_n3 (A3 warm-memory) -- DO NOT wipe memory
###############################################################################
if step_enabled 2; then
    echo
    echo "########## STEP 2/6: evoresearcher_warm_n3 (A3 warm pass, memory PRESERVED) ##########"
    if [[ $RESUME -ne 1 ]]; then
        wipe_report evoresearcher_warm_n3
        # NOTE: memory/ is intentionally NOT wiped between step 1 and step 2.
    fi
    run evoresearcher_warm_n3 \
        $PY benchmarks/drb2/run_evoresearcher.py \
        --trials 3 \
        --tree-depth 2 --branching-factor 2 --max-sources 6 \
        --label evoresearcher_warm_n3
    run evoresearcher_warm_n3_judge \
        $PY benchmarks/drb2/evaluate_with_deepseek.py --label evoresearcher_warm_n3
fi

###############################################################################
# Step 3: evoresearcher_blind_n3 (A_TREE) -- cold memory again
###############################################################################
if step_enabled 3; then
    echo
    echo "########## STEP 3/6: evoresearcher_blind_n3 (A_TREE blind expansion) ##########"
    if [[ $RESUME -ne 1 ]]; then
        wipe_memory
        wipe_report evoresearcher_blind_n3
    fi
    run evoresearcher_blind_n3 \
        $PY benchmarks/drb2/run_evoresearcher.py \
        --trials 3 --blind-expansion \
        --tree-depth 2 --branching-factor 2 --max-sources 6 \
        --label evoresearcher_blind_n3
    run evoresearcher_blind_n3_judge \
        $PY benchmarks/drb2/evaluate_with_deepseek.py --label evoresearcher_blind_n3
fi

###############################################################################
# Step 4: evoresearcher_noelo_n3 (A_ELO) -- cold memory again
###############################################################################
if step_enabled 4; then
    echo
    echo "########## STEP 4/6: evoresearcher_noelo_n3 (A_ELO sort-by-score) ##########"
    if [[ $RESUME -ne 1 ]]; then
        wipe_memory
        wipe_report evoresearcher_noelo_n3
    fi
    run evoresearcher_noelo_n3 \
        $PY benchmarks/drb2/run_evoresearcher.py \
        --trials 3 --no-elo \
        --tree-depth 2 --branching-factor 2 --max-sources 6 \
        --label evoresearcher_noelo_n3
    run evoresearcher_noelo_n3_judge \
        $PY benchmarks/drb2/evaluate_with_deepseek.py --label evoresearcher_noelo_n3
fi

###############################################################################
# Step 5: HF baselines (Perplexity-Research, Qwen-3-Max-DeepResearch)
# This step is conditional on hf_baselines.py probe+match succeeding.
# It does NOT touch memory or run EvoResearcher; it just stages PDFs for the
# DeepSeek judge.
###############################################################################
if step_enabled 5; then
    echo
    echo "########## STEP 5/6: HF baselines re-grade ##########"
    echo "[step 5] this step is conditional. Run the probe+match by hand first:"
    echo "    pip install datasets pypdf"
    echo "    $PY benchmarks/drb2/hf_baselines.py probe"
    echo "    # inspect output, identify --id-field and --pdf-field, then:"
    echo "    $PY benchmarks/drb2/hf_baselines.py match   --id-field <FIELD> [--via-task-id]"
    echo "    $PY benchmarks/drb2/hf_baselines.py extract --id-field <FIELD> --pdf-field <PDF_FIELD> [--via-task-id]"
    if [[ -d "$DRB2/report/perplexity_research" ]]; then
        run perplexity_research_judge \
            $PY benchmarks/drb2/evaluate_with_deepseek.py --label perplexity_research
    else
        echo "[step 5] $DRB2/report/perplexity_research not present, skipping perplexity judge"
    fi
    if [[ -d "$DRB2/report/qwen3_max" ]]; then
        run qwen3_max_judge \
            $PY benchmarks/drb2/evaluate_with_deepseek.py --label qwen3_max
    else
        echo "[step 5] $DRB2/report/qwen3_max not present, skipping qwen judge"
    fi
fi

###############################################################################
# Step 6: aggregate the entire matrix
###############################################################################
if step_enabled 6; then
    echo
    echo "########## STEP 6/6: aggregate final matrix ##########"
    run aggregate_final \
        $PY benchmarks/drb2/aggregate.py --out-prefix final_matrix
fi

echo
echo "[run_all] done at $(date)"
echo "[run_all] inspect benchmarks/drb2/results/final_matrix_summary.md"
