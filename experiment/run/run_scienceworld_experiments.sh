#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
CONDA_ENV="${CONDA_ENV:-blackboard}"
MODEL_NAME="${MODEL_NAME:-deepseek-v3}"
OPENAI_API_BASE="${OPENAI_API_BASE:-https://tb.api.mkeai.com/v1}"
OPENAI_API_KEY="${OPENAI_API_KEY:-}"
OPENAI_API_TIMEOUT="${OPENAI_API_TIMEOUT:-300}"
OUTPUT_ROOT="${SCIENCEWORLD_OUTPUT_ROOT:-$ROOT_DIR/experiment/scienceworld/outputs}"
RUN_TAG="${RUN_TAG:-$(date +%Y%m%d_%H%M%S)}"

TASK_SET_DEBUG="${SCIENCEWORLD_TASK_SET_DEBUG:-$ROOT_DIR/experiment/common/task_sets/scienceworld_debug.json}"
TASK_SET_FORMAL="${SCIENCEWORLD_TASK_SET_FORMAL:-$ROOT_DIR/experiment/common/task_sets/scienceworld_formal.json}"

REQUIRED_PYTHONPATH="$ROOT_DIR"
if [[ -n "${PYTHONPATH:-}" ]]; then
  export PYTHONPATH="${REQUIRED_PYTHONPATH}:${PYTHONPATH}"
else
  export PYTHONPATH="${REQUIRED_PYTHONPATH}"
fi

usage() {
  cat <<'EOF'
Usage:
  run_scienceworld_experiments.sh [target]

Targets:
  exp1  Experiment 1: blackboard/langgraph/autogen compare + judge
  exp2  Experiment 2: schema-guard proxy (full vs ablate_c2)
  exp3  Experiment 3: blackboard/langgraph/autogen/ablate_c4 compare
  exp4  Experiment 4: blackboard/langgraph/autogen formal compare
  exp5  Experiment 5: blackboard/langgraph/autogen debug compare
  exp6  Experiment 6: blackboard full vs ablate_c1~c5
  all   Run all experiments sharing one debug task set run

Defaults:
  MODEL_NAME=deepseek-v3
  OPENAI_API_BASE=https://tb.api.mkeai.com/v1
  OPENAI_API_KEY=
EOF
}

log() {
  echo "[$(date '+%H:%M:%S')] $*"
}

RUN() {
  env PYTHONPATH="${PYTHONPATH}" \
    OPENAI_API_BASE="${OPENAI_API_BASE}" \
    OPENAI_API_KEY="${OPENAI_API_KEY}" \
    OPENAI_API_TIMEOUT="${OPENAI_API_TIMEOUT}" \
    conda run --no-capture-output -n "${CONDA_ENV}" python "$@"
}

run_comm_judge() {
  local judge_input="$1"
  [[ -f "${judge_input}" ]] || return 0
  RUN "$ROOT_DIR/experiment/common/run_communication_judge.py" \
    --input-path "${judge_input}" \
    --backend openai_compatible \
    --model "${MODEL_NAME}" \
    --base-url "${OPENAI_API_BASE}" \
    --api-key "${OPENAI_API_KEY}" \
    --timeout "${OPENAI_API_TIMEOUT}" \
    --sleep-between-requests 4.5 \
    --continue-on-error
}

run_ablation_experiment() {
  local exp_id="$1"
  local modes="$2"
  local task_set="$3"
  local out_dir="$4"
  local max_steps="$5"

  log "[${exp_id}] ablation modes=${modes} task_set=${task_set} -> ${out_dir}"
  RUN "$ROOT_DIR/experiment/scienceworld/examples/run_ablation.py" \
    --task-set-file "${task_set}" \
    --output-dir "${out_dir}" \
    --modes "${modes}" \
    --workflow-mode planner_action \
    --max-steps "${max_steps}" \
    --model-name "${MODEL_NAME}" \
    --use-local-llm \
    --llm-base-url "${OPENAI_API_BASE}" \
    --llm-api-key "${OPENAI_API_KEY}" \
    --llm-timeout "${OPENAI_API_TIMEOUT}"

  RUN "$ROOT_DIR/experiment/scienceworld/examples/run_result_analysis.py" \
    --summary-path "${out_dir}/ablation_summary.json"
}

run_exp1() {
  local task_set="${SCIENCEWORLD_EXP1_TASK_SET:-$TASK_SET_DEBUG}"
  local out_dir="${OUTPUT_ROOT}/exp1_scienceworld_comm_${RUN_TAG}"
  local max_steps="${SCIENCEWORLD_EXP1_MAX_STEPS:-50}"

  log "[exp1] system compare on ${task_set} -> ${out_dir}"
  RUN "$ROOT_DIR/experiment/scienceworld/examples/run_system_compare.py" \
    --task-set-file "${task_set}" \
    --output-dir "${out_dir}" \
    --systems blackboard,langgraph,autogen \
    --workflow-mode planner_action \
    --max-steps "${max_steps}" \
    --model-name "${MODEL_NAME}" \
    --use-local-llm \
    --llm-base-url "${OPENAI_API_BASE}" \
    --llm-api-key "${OPENAI_API_KEY}" \
    --llm-timeout "${OPENAI_API_TIMEOUT}"

  RUN "$ROOT_DIR/experiment/scienceworld/examples/run_result_analysis.py" \
    --summary-path "${out_dir}/system_compare_summary.json"

  run_comm_judge "${out_dir}/comm_judge.jsonl"
}

run_exp2() {
  local task_set="${SCIENCEWORLD_EXP2_TASK_SET:-$TASK_SET_DEBUG}"
  local out_dir="${OUTPUT_ROOT}/exp2_scienceworld_schema_guard_${RUN_TAG}"
  local max_steps="${SCIENCEWORLD_EXP2_MAX_STEPS:-50}"

  run_ablation_experiment exp2 "full,ablate_c2" "${task_set}" "${out_dir}" "${max_steps}"
}

run_exp3() {
  local task_set="${SCIENCEWORLD_EXP3_TASK_SET:-$TASK_SET_DEBUG}"
  local out_dir="${OUTPUT_ROOT}/exp3_scienceworld_context_${RUN_TAG}"
  local max_steps="${SCIENCEWORLD_EXP3_MAX_STEPS:-50}"

  log "[exp3] system compare + ablate_c4 on ${task_set} -> ${out_dir}"
  RUN "$ROOT_DIR/experiment/scienceworld/examples/run_system_compare.py" \
    --task-set-file "${task_set}" \
    --output-dir "${out_dir}/system_compare" \
    --systems blackboard,langgraph,autogen \
    --workflow-mode planner_action \
    --max-steps "${max_steps}" \
    --model-name "${MODEL_NAME}" \
    --use-local-llm \
    --llm-base-url "${OPENAI_API_BASE}" \
    --llm-api-key "${OPENAI_API_KEY}" \
    --llm-timeout "${OPENAI_API_TIMEOUT}"

  run_ablation_experiment exp3 "ablate_c4" "${task_set}" "${out_dir}/ablate_c4" "${max_steps}"

  RUN "$ROOT_DIR/experiment/scienceworld/examples/run_result_analysis.py" \
    --summary-path "${out_dir}/system_compare/system_compare_summary.json"
}

run_exp4() {
  local task_set="${SCIENCEWORLD_EXP4_TASK_SET:-$TASK_SET_FORMAL}"
  local out_dir="${OUTPUT_ROOT}/exp4_scienceworld_generalization_${RUN_TAG}"
  local max_steps="${SCIENCEWORLD_EXP4_MAX_STEPS:-50}"

  log "[exp4] generalization compare on ${task_set} -> ${out_dir}"
  RUN "$ROOT_DIR/experiment/scienceworld/examples/run_system_compare.py" \
    --task-set-file "${task_set}" \
    --output-dir "${out_dir}" \
    --systems blackboard,langgraph,autogen \
    --workflow-mode planner_action \
    --max-steps "${max_steps}" \
    --model-name "${MODEL_NAME}" \
    --use-local-llm \
    --llm-base-url "${OPENAI_API_BASE}" \
    --llm-api-key "${OPENAI_API_KEY}" \
    --llm-timeout "${OPENAI_API_TIMEOUT}"

  RUN "$ROOT_DIR/experiment/scienceworld/examples/run_result_analysis.py" \
    --summary-path "${out_dir}/system_compare_summary.json"
}

run_exp5() {
  local task_set="${SCIENCEWORLD_EXP5_TASK_SET:-$TASK_SET_DEBUG}"
  local out_dir="${OUTPUT_ROOT}/exp5_scienceworld_accuracy_${RUN_TAG}"
  local max_steps="${SCIENCEWORLD_EXP5_MAX_STEPS:-50}"

  log "[exp5] accuracy compare on ${task_set} -> ${out_dir}"
  RUN "$ROOT_DIR/experiment/scienceworld/examples/run_system_compare.py" \
    --task-set-file "${task_set}" \
    --output-dir "${out_dir}" \
    --systems blackboard,langgraph,autogen \
    --workflow-mode planner_action \
    --max-steps "${max_steps}" \
    --model-name "${MODEL_NAME}" \
    --use-local-llm \
    --llm-base-url "${OPENAI_API_BASE}" \
    --llm-api-key "${OPENAI_API_KEY}" \
    --llm-timeout "${OPENAI_API_TIMEOUT}"

  RUN "$ROOT_DIR/experiment/scienceworld/examples/run_result_analysis.py" \
    --summary-path "${out_dir}/system_compare_summary.json"
}

run_exp6() {
  local task_set="${SCIENCEWORLD_EXP6_TASK_SET:-$TASK_SET_DEBUG}"
  local out_dir="${OUTPUT_ROOT}/exp6_scienceworld_ablation_${RUN_TAG}"
  local max_steps="${SCIENCEWORLD_EXP6_MAX_STEPS:-50}"

  run_ablation_experiment exp6 "full,ablate_c1,ablate_c2,ablate_c3,ablate_c4,ablate_c5" "${task_set}" "${out_dir}" "${max_steps}"
}

run_all() {
  local task_set="${TASK_SET_DEBUG}"
  local max_steps="${SCIENCEWORLD_ALL_MAX_STEPS:-50}"
  local shared_dir="${OUTPUT_ROOT}/shared_debug_${RUN_TAG}"

  # Step 1: all blackboard modes (covers exp1/exp3/exp5/exp6)
  log "[all] ablation full+ablate_c1~c5 -> ${shared_dir}/ablation"
  RUN "$ROOT_DIR/experiment/scienceworld/examples/run_ablation.py" \
    --task-set-file "${task_set}" \
    --output-dir "${shared_dir}/ablation" \
    --modes full,ablate_c1,ablate_c2,ablate_c3,ablate_c4,ablate_c5 \
    --workflow-mode planner_action \
    --max-steps "${max_steps}" \
    --model-name "${MODEL_NAME}" \
    --use-local-llm \
    --llm-base-url "${OPENAI_API_BASE}" \
    --llm-api-key "${OPENAI_API_KEY}" \
    --llm-timeout "${OPENAI_API_TIMEOUT}"

  # Step 2: langgraph + autogen, same seed -> same tasks (covers exp1/exp3/exp5)
  log "[all] system compare langgraph+autogen -> ${shared_dir}/system_compare"
  RUN "$ROOT_DIR/experiment/scienceworld/examples/run_system_compare.py" \
    --task-set-file "${task_set}" \
    --output-dir "${shared_dir}/system_compare" \
    --systems langgraph,autogen \
    --workflow-mode planner_action \
    --max-steps "${max_steps}" \
    --model-name "${MODEL_NAME}" \
    --use-local-llm \
    --llm-base-url "${OPENAI_API_BASE}" \
    --llm-api-key "${OPENAI_API_KEY}" \
    --llm-timeout "${OPENAI_API_TIMEOUT}"

  # Step 4: exp4 formal task set (different tasks, must run separately)
  local formal_dir="${OUTPUT_ROOT}/exp4_scienceworld_generalization_${RUN_TAG}"
  log "[all/exp4] formal system compare -> ${formal_dir}"
  RUN "$ROOT_DIR/experiment/scienceworld/examples/run_system_compare.py" \
    --task-set-file "${TASK_SET_FORMAL}" \
    --output-dir "${formal_dir}" \
    --systems blackboard,langgraph,autogen \
    --workflow-mode planner_action \
    --max-steps "${max_steps}" \
    --model-name "${MODEL_NAME}" \
    --use-local-llm \
    --llm-base-url "${OPENAI_API_BASE}" \
    --llm-api-key "${OPENAI_API_KEY}" \
    --llm-timeout "${OPENAI_API_TIMEOUT}"

  # Analysis
  log "[all] analysis"
  RUN "$ROOT_DIR/experiment/scienceworld/examples/run_result_analysis.py" \
    --summary-path "${shared_dir}/ablation/ablation_summary.json"
  RUN "$ROOT_DIR/experiment/scienceworld/examples/run_result_analysis.py" \
    --summary-path "${shared_dir}/system_compare/system_compare_summary.json"
  RUN "$ROOT_DIR/experiment/scienceworld/examples/run_result_analysis.py" \
    --summary-path "${formal_dir}/system_compare_summary.json"

  run_comm_judge "${shared_dir}/system_compare/comm_judge.jsonl"

  log "[all] done. shared results in ${shared_dir}"
}

log "[config] model=${MODEL_NAME} base=${OPENAI_API_BASE}"

target="${1:-all}"
case "${target}" in
  exp1) run_exp1 ;;
  exp2) run_exp2 ;;
  exp3) run_exp3 ;;
  exp4) run_exp4 ;;
  exp5) run_exp5 ;;
  exp6) run_exp6 ;;
  all) run_all ;;
  -h|--help|help) usage ;;
  *)
    echo "Unknown target: ${target}" >&2
    usage
    exit 1
    ;;
esac
