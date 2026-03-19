#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
CONDA_ENV="${CONDA_ENV:-blackboard}"
MODEL_NAME="${MODEL_NAME:-deepseek-v3}"
OPENAI_API_BASE="${OPENAI_API_BASE:-https://tb.api.mkeai.com/v1}"
OPENAI_API_KEY="${OPENAI_API_KEY:-}"
OPENAI_API_TIMEOUT="${OPENAI_API_TIMEOUT:-300}"
OUTPUT_ROOT="${WEBARENA_OUTPUT_ROOT:-$ROOT_DIR/experiment/webarena/outputs}"
RUN_TAG="${RUN_TAG:-$(date +%Y%m%d_%H%M%S)}"

TASK_SET_SMOKE="${WEBARENA_TASK_SET_SMOKE:-$ROOT_DIR/experiment/common/task_sets/webarena_script_browser_smoke.json}"
TASK_SET_DEBUG="${WEBARENA_TASK_SET_DEBUG:-$ROOT_DIR/experiment/common/task_sets/webarena_debug.json}"
TASK_SET_LIVE="${WEBARENA_TASK_SET_LIVE:-$ROOT_DIR/experiment/common/task_sets/webarena_live_debug.json}"
TASK_SET_FORMAL="${WEBARENA_TASK_SET_FORMAL:-$ROOT_DIR/experiment/common/task_sets/webarena_formal.json}"

REQUIRED_PYTHONPATH="$ROOT_DIR:$ROOT_DIR/webarena"
if [[ -n "${PYTHONPATH:-}" ]]; then
  export PYTHONPATH="${REQUIRED_PYTHONPATH}:${PYTHONPATH}"
else
  export PYTHONPATH="${REQUIRED_PYTHONPATH}"
fi

usage() {
  cat <<'EOF'
Usage:
  run_webarena_experiments.sh [target]

Targets:
  exp1       Experiment 1: blackboard/langgraph/autogen compare + judge
  exp2       Experiment 2: schema guard evaluation
  exp3       Experiment 3: blackboard/langgraph/autogen/ablate_c4 compare
  exp4       Experiment 4: blackboard/langgraph/autogen compare
  exp5       Experiment 5: blackboard/langgraph/autogen compare
  exp6       Experiment 6: blackboard full vs ablate_c1~c5
  all        Run all experiments sharing one debug task set run

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

webarena_site_envs_ready() {
  [[ -n "${SHOPPING:-}" ]] && \
  [[ -n "${SHOPPING_ADMIN:-}" ]] && \
  [[ -n "${REDDIT:-}" ]] && \
  [[ -n "${GITLAB:-}" ]] && \
  [[ -n "${MAP:-}" ]] && \
  [[ -n "${WIKIPEDIA:-}" ]] && \
  [[ -n "${HOMEPAGE:-}" ]]
}

resolve_existing_webarena_task_set() {
  local preferred="$1"
  shift
  local selected=""
  local require_site_envs=1
  if webarena_site_envs_ready; then
    require_site_envs=0
  fi
  for candidate in "${preferred}" "$@"; do
    case "${candidate}" in
      */webarena_script_browser_smoke.json)
        if [[ -f "${ROOT_DIR}/webarena/config_files/examples/3.json" ]]; then
          selected="${candidate}"
          break
        fi
        ;;
      */webarena_formal.json)
        [[ ${require_site_envs} -eq 0 ]] || continue
        if compgen -G "${ROOT_DIR}/webarena/config_files/[0-9]*.json" > /dev/null; then
          selected="${candidate}"
          break
        fi
        ;;
      */webarena_live_debug.json)
        [[ ${require_site_envs} -eq 0 ]] || continue
        if [[ -f "${ROOT_DIR}/webarena/config_files/0.json" ]] && \
           [[ -f "${ROOT_DIR}/webarena/config_files/1.json" ]] && \
           [[ -f "${ROOT_DIR}/webarena/config_files/2.json" ]] && \
           [[ -f "${ROOT_DIR}/webarena/config_files/3.json" ]]; then
          selected="${candidate}"
          break
        fi
        ;;
      */webarena_debug.json)
        [[ ${require_site_envs} -eq 0 ]] || continue
        if [[ -f "${ROOT_DIR}/webarena/config_files/examples/1.json" ]] && \
           [[ -f "${ROOT_DIR}/webarena/config_files/examples/2.json" ]] && \
           [[ -f "${ROOT_DIR}/webarena/config_files/examples/3.json" ]] && \
           [[ -f "${ROOT_DIR}/webarena/config_files/examples/4.json" ]]; then
          selected="${candidate}"
          break
        fi
        ;;
    esac
  done
  if [[ -z "${selected}" ]]; then
    echo "[ERROR] No runnable WebArena task set found." >&2
    echo "[ERROR] Checked: ${preferred} $*" >&2
    exit 1
  fi
  if [[ "${selected}" != "${preferred}" ]]; then
    echo "[warn] fallback task set: ${preferred} -> ${selected}" >&2
  fi
  printf '%s\n' "${selected}"
}

run_exp1() {
  local task_set="${WEBARENA_EXP1_TASK_SET:-$TASK_SET_DEBUG}"
  local backend="${WEBARENA_EXP1_BACKEND:-script_browser}"
  local out_dir="${OUTPUT_ROOT}/exp1_webarena_comm_${RUN_TAG}"

  log "[exp1] system compare on ${task_set} (${backend}) -> ${out_dir}"
  RUN "$ROOT_DIR/experiment/webarena/examples/run_system_compare.py" \
    --task-set-file "${task_set}" \
    --output-dir "${out_dir}" \
    --systems blackboard,langgraph,autogen \
    --workflow-mode planner_action \
    --execution-backend "${backend}" \
    --model-name "${MODEL_NAME}" \
    --use-local-llm \
    --llm-base-url "${OPENAI_API_BASE}" \
    --llm-api-key "${OPENAI_API_KEY}" \
    --llm-timeout "${OPENAI_API_TIMEOUT}"

  RUN "$ROOT_DIR/experiment/webarena/examples/run_result_analysis.py" \
    --summary-path "${out_dir}/system_compare_summary.json"

  run_comm_judge "${out_dir}/comm_judge.jsonl"
}

run_exp2() {
  local task_set="${WEBARENA_EXP2_TASK_SET:-$TASK_SET_DEBUG}"
  local backend="${WEBARENA_EXP2_BACKEND:-script_browser}"
  local out_dir="${OUTPUT_ROOT}/exp2_webarena_schema_guard_${RUN_TAG}"

  log "[exp2] schema guard on ${task_set} (${backend}) -> ${out_dir}"
  RUN "$ROOT_DIR/experiment/webarena/examples/run_schema_guard_eval.py" \
    --task-set-file "${task_set}" \
    --output-dir "${out_dir}" \
    --run-id "capture_states_${RUN_TAG}" \
    --workflow-mode planner_action \
    --execution-backend "${backend}" \
    --model-name "${MODEL_NAME}" \
    --use-local-llm \
    --llm-base-url "${OPENAI_API_BASE}" \
    --llm-api-key "${OPENAI_API_KEY}" \
    --llm-timeout "${OPENAI_API_TIMEOUT}"
}

run_exp3() {
  local task_set="${WEBARENA_EXP3_TASK_SET:-$TASK_SET_DEBUG}"
  local backend="${WEBARENA_EXP3_BACKEND:-script_browser}"
  local out_dir="${OUTPUT_ROOT}/exp3_webarena_context_${RUN_TAG}"

  log "[exp3] system compare + ablate_c4 on ${task_set} (${backend}) -> ${out_dir}"
  RUN "$ROOT_DIR/experiment/webarena/examples/run_system_compare.py" \
    --task-set-file "${task_set}" \
    --output-dir "${out_dir}/system_compare" \
    --systems blackboard,langgraph,autogen \
    --workflow-mode planner_action \
    --execution-backend "${backend}" \
    --model-name "${MODEL_NAME}" \
    --use-local-llm \
    --llm-base-url "${OPENAI_API_BASE}" \
    --llm-api-key "${OPENAI_API_KEY}" \
    --llm-timeout "${OPENAI_API_TIMEOUT}"

  RUN "$ROOT_DIR/experiment/webarena/examples/run_context_ablation.py" \
    --task-set-file "${task_set}" \
    --output-dir "${out_dir}/ablate_c4" \
    --workflow-mode planner_action \
    --execution-backend "${backend}" \
    --model-name "${MODEL_NAME}" \
    --use-local-llm \
    --llm-base-url "${OPENAI_API_BASE}" \
    --llm-api-key "${OPENAI_API_KEY}" \
    --llm-timeout "${OPENAI_API_TIMEOUT}"

  RUN "$ROOT_DIR/experiment/webarena/examples/run_result_analysis.py" \
    --summary-path "${out_dir}/system_compare/system_compare_summary.json"
}

run_exp4() {
  local preferred_task_set="${WEBARENA_EXP4_TASK_SET:-$TASK_SET_FORMAL}"
  local task_set
  task_set="$(resolve_existing_webarena_task_set \
    "${preferred_task_set}" \
    "${TASK_SET_LIVE}" \
    "${TASK_SET_DEBUG}" \
    "${TASK_SET_SMOKE}")"
  local out_dir="${OUTPUT_ROOT}/exp4_webarena_generalization_${RUN_TAG}"

  log "[exp4] generalization compare on ${task_set} -> ${out_dir}"
  RUN "$ROOT_DIR/experiment/webarena/examples/run_system_compare.py" \
    --task-set-file "${task_set}" \
    --output-dir "${out_dir}" \
    --systems blackboard,langgraph,autogen \
    --workflow-mode planner_action \
    --execution-backend script_browser \
    --model-name "${MODEL_NAME}" \
    --use-local-llm \
    --llm-base-url "${OPENAI_API_BASE}" \
    --llm-api-key "${OPENAI_API_KEY}" \
    --llm-timeout "${OPENAI_API_TIMEOUT}"

  RUN "$ROOT_DIR/experiment/webarena/examples/run_result_analysis.py" \
    --summary-path "${out_dir}/system_compare_summary.json"
}

run_exp5() {
  local preferred_task_set="${WEBARENA_EXP5_TASK_SET:-$TASK_SET_LIVE}"
  local task_set
  task_set="$(resolve_existing_webarena_task_set \
    "${preferred_task_set}" \
    "${TASK_SET_DEBUG}" \
    "${TASK_SET_SMOKE}")"
  local out_dir="${OUTPUT_ROOT}/exp5_webarena_accuracy_${RUN_TAG}"

  log "[exp5] accuracy compare on ${task_set} -> ${out_dir}"
  RUN "$ROOT_DIR/experiment/webarena/examples/run_system_compare.py" \
    --task-set-file "${task_set}" \
    --output-dir "${out_dir}" \
    --systems blackboard,langgraph,autogen \
    --workflow-mode planner_action \
    --execution-backend script_browser \
    --model-name "${MODEL_NAME}" \
    --use-local-llm \
    --llm-base-url "${OPENAI_API_BASE}" \
    --llm-api-key "${OPENAI_API_KEY}" \
    --llm-timeout "${OPENAI_API_TIMEOUT}"

  RUN "$ROOT_DIR/experiment/webarena/examples/run_result_analysis.py" \
    --summary-path "${out_dir}/system_compare_summary.json"
}

run_exp6() {
  local task_set="${WEBARENA_EXP6_TASK_SET:-$TASK_SET_DEBUG}"
  local backend="${WEBARENA_EXP6_BACKEND:-script_browser}"
  local out_dir="${OUTPUT_ROOT}/exp6_webarena_ablation_${RUN_TAG}"

  log "[exp6] ablation on ${task_set} (${backend}) -> ${out_dir}"
  RUN "$ROOT_DIR/experiment/webarena/examples/run_ablation.py" \
    --task-set-file "${task_set}" \
    --output-dir "${out_dir}" \
    --workflow-mode planner_action \
    --execution-backend "${backend}" \
    --model-name "${MODEL_NAME}" \
    --modes full,ablate_c1,ablate_c2,ablate_c3,ablate_c4,ablate_c5 \
    --use-local-llm \
    --llm-base-url "${OPENAI_API_BASE}" \
    --llm-api-key "${OPENAI_API_KEY}" \
    --llm-timeout "${OPENAI_API_TIMEOUT}"

  RUN "$ROOT_DIR/experiment/webarena/examples/run_result_analysis.py" \
    --summary-path "${out_dir}/ablation_summary.json"
}

run_all() {
  local backend="${WEBARENA_ALL_BACKEND:-script_browser}"
  local max_steps="${WEBARENA_ALL_MAX_STEPS:-10}"
  local shared_dir="${OUTPUT_ROOT}/shared_debug_${RUN_TAG}"

  local task_set
  task_set="$(resolve_existing_webarena_task_set \
    "${TASK_SET_DEBUG}" \
    "${TASK_SET_SMOKE}")"

  # Step 1: all blackboard modes (covers exp1/exp3/exp5/exp6)
  log "[all] ablation full+ablate_c1~c5 -> ${shared_dir}/ablation"
  RUN "$ROOT_DIR/experiment/webarena/examples/run_ablation.py" \
    --task-set-file "${task_set}" \
    --output-dir "${shared_dir}/ablation" \
    --modes full,ablate_c1,ablate_c2,ablate_c3,ablate_c4,ablate_c5 \
    --workflow-mode planner_action \
    --execution-backend "${backend}" \
    --model-name "${MODEL_NAME}" \
    --use-local-llm \
    --llm-base-url "${OPENAI_API_BASE}" \
    --llm-api-key "${OPENAI_API_KEY}" \
    --llm-timeout "${OPENAI_API_TIMEOUT}"

  # Step 2: langgraph + autogen, same seed -> same tasks (covers exp1/exp3/exp5)
  log "[all] system compare langgraph+autogen -> ${shared_dir}/system_compare"
  RUN "$ROOT_DIR/experiment/webarena/examples/run_system_compare.py" \
    --task-set-file "${task_set}" \
    --output-dir "${shared_dir}/system_compare" \
    --systems langgraph,autogen \
    --workflow-mode planner_action \
    --execution-backend "${backend}" \
    --model-name "${MODEL_NAME}" \
    --use-local-llm \
    --llm-base-url "${OPENAI_API_BASE}" \
    --llm-api-key "${OPENAI_API_KEY}" \
    --llm-timeout "${OPENAI_API_TIMEOUT}"

  # Step 3: exp2 schema guard
  log "[all/exp2] schema guard -> ${shared_dir}/exp2_schema_guard"
  RUN "$ROOT_DIR/experiment/webarena/examples/run_schema_guard_eval.py" \
    --task-set-file "${task_set}" \
    --output-dir "${shared_dir}/exp2_schema_guard" \
    --run-id "capture_states_${RUN_TAG}" \
    --workflow-mode planner_action \
    --execution-backend "${backend}" \
    --model-name "${MODEL_NAME}" \
    --use-local-llm \
    --llm-base-url "${OPENAI_API_BASE}" \
    --llm-api-key "${OPENAI_API_KEY}" \
    --llm-timeout "${OPENAI_API_TIMEOUT}"

  # Step 4: exp4 formal task set (different tasks, must run separately)
  local formal_task_set
  formal_task_set="$(resolve_existing_webarena_task_set \
    "${TASK_SET_FORMAL}" \
    "${TASK_SET_LIVE}" \
    "${TASK_SET_DEBUG}" \
    "${TASK_SET_SMOKE}")"
  local formal_dir="${OUTPUT_ROOT}/exp4_webarena_generalization_${RUN_TAG}"
  log "[all/exp4] formal system compare -> ${formal_dir}"
  RUN "$ROOT_DIR/experiment/webarena/examples/run_system_compare.py" \
    --task-set-file "${formal_task_set}" \
    --output-dir "${formal_dir}" \
    --systems blackboard,langgraph,autogen \
    --workflow-mode planner_action \
    --execution-backend script_browser \
    --model-name "${MODEL_NAME}" \
    --use-local-llm \
    --llm-base-url "${OPENAI_API_BASE}" \
    --llm-api-key "${OPENAI_API_KEY}" \
    --llm-timeout "${OPENAI_API_TIMEOUT}"

  # Analysis
  log "[all] analysis"
  RUN "$ROOT_DIR/experiment/webarena/examples/run_result_analysis.py" \
    --summary-path "${shared_dir}/ablation/ablation_summary.json"
  RUN "$ROOT_DIR/experiment/webarena/examples/run_result_analysis.py" \
    --summary-path "${shared_dir}/system_compare/system_compare_summary.json"
  RUN "$ROOT_DIR/experiment/webarena/examples/run_result_analysis.py" \
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
