"""Metrics computation for ScienceWorld experiment runs."""
from __future__ import annotations

from typing import Any, Dict, List


def compute_summary(results: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Aggregate ScienceWorld episode results into summary metrics."""
    n = len(results)
    if n == 0:
        return {
            "n_episodes": 0,
            "success_rate": 0.0,
            "mean_steps": 0.0,
            "mean_total_tokens": 0.0,
            "mean_worker_input_tokens": 0.0,
            "mean_worker_output_tokens": 0.0,
            "mean_architect_input_tokens": 0.0,
            "mean_architect_output_tokens": 0.0,
            "mean_architect_total_tokens": 0.0,
            "mean_goal_condition_rate": 0.0,
            "mean_fallback_rate": 0.0,
            "mean_patch_error_rate": 0.0,
            "mean_retrieval_precision": 0.0,
            "mean_context_fragment_count": 0.0,
            "mean_relevant_fragment_count": 0.0,
            "mean_irrelevant_fragment_count": 0.0,
            "task_breakdown": {},
            "stop_reason_breakdown": {},
            "final_status_breakdown": {},
            "workflow_final_status_breakdown": {},
        }

    success_rate = sum(1 for result in results if result.get("success")) / n
    mean_steps = sum(int(result.get("steps", 0)) for result in results) / n
    mean_total_tokens = sum(int(result.get("total_tokens", 0)) for result in results) / n
    mean_worker_input_tokens = sum(int(result.get("worker_input_tokens", 0)) for result in results) / n
    mean_worker_output_tokens = sum(int(result.get("worker_output_tokens", 0)) for result in results) / n
    mean_architect_input_tokens = sum(int(result.get("architect_input_tokens", 0)) for result in results) / n
    mean_architect_output_tokens = sum(int(result.get("architect_output_tokens", 0)) for result in results) / n
    mean_goal_condition_rate = sum(float(result.get("goal_condition_rate", 0.0)) for result in results) / n
    mean_retrieval_precision = sum(float(result.get("retrieval_precision", 0.0)) for result in results) / n
    mean_context_fragment_count = sum(float(result.get("context_fragment_count", 0.0)) for result in results) / n
    mean_relevant_fragment_count = sum(float(result.get("relevant_fragment_count", 0.0)) for result in results) / n
    mean_irrelevant_fragment_count = sum(float(result.get("irrelevant_fragment_count", 0.0)) for result in results) / n

    fallback_rates = [
        int(result.get("fallback_action_count", 0)) / max(int(result.get("steps", 1)), 1)
        for result in results
    ]
    patch_error_rates = [
        int(result.get("patch_error_count", 0)) / max(int(result.get("steps", 1)), 1)
        for result in results
    ]

    stop_reason_breakdown: Dict[str, int] = {}
    final_status_breakdown: Dict[str, int] = {}
    workflow_final_status_breakdown: Dict[str, int] = {}
    task_breakdown: Dict[str, Dict[str, float]] = {}

    grouped_by_task: Dict[str, List[Dict[str, Any]]] = {}
    for result in results:
        stop_reason = str(result.get("stop_reason", "") or "")
        if stop_reason:
            stop_reason_breakdown[stop_reason] = stop_reason_breakdown.get(stop_reason, 0) + 1
        final_status = str(result.get("final_status", "") or "")
        if final_status:
            final_status_breakdown[final_status] = final_status_breakdown.get(final_status, 0) + 1
        workflow_final_status = str(result.get("workflow_final_status", "") or "")
        if workflow_final_status:
            workflow_final_status_breakdown[workflow_final_status] = (
                workflow_final_status_breakdown.get(workflow_final_status, 0) + 1
            )

        metadata = result.get("metadata", {}) or {}
        task_group = str(metadata.get("task_name", result.get("task_id", "unknown")) or "unknown")
        grouped_by_task.setdefault(task_group, []).append(result)

    for task_group, task_results in grouped_by_task.items():
        task_breakdown[task_group] = {
            "n_episodes": float(len(task_results)),
            "success_rate": float(sum(1 for result in task_results if result.get("success")) / len(task_results)),
            "mean_goal_condition_rate": float(
                sum(float(result.get("goal_condition_rate", 0.0)) for result in task_results) / len(task_results)
            ),
            "mean_retrieval_precision": float(
                sum(float(result.get("retrieval_precision", 0.0)) for result in task_results) / len(task_results)
            ),
        }

    return {
        "n_episodes": n,
        "success_rate": success_rate,
        "mean_steps": mean_steps,
        "mean_total_tokens": mean_total_tokens,
        "mean_worker_input_tokens": mean_worker_input_tokens,
        "mean_worker_output_tokens": mean_worker_output_tokens,
        "mean_architect_input_tokens": mean_architect_input_tokens,
        "mean_architect_output_tokens": mean_architect_output_tokens,
        "mean_architect_total_tokens": mean_architect_input_tokens + mean_architect_output_tokens,
        "mean_goal_condition_rate": mean_goal_condition_rate,
        "mean_fallback_rate": sum(fallback_rates) / n,
        "mean_patch_error_rate": sum(patch_error_rates) / n,
        "mean_retrieval_precision": mean_retrieval_precision,
        "mean_context_fragment_count": mean_context_fragment_count,
        "mean_relevant_fragment_count": mean_relevant_fragment_count,
        "mean_irrelevant_fragment_count": mean_irrelevant_fragment_count,
        "task_breakdown": task_breakdown,
        "stop_reason_breakdown": stop_reason_breakdown,
        "final_status_breakdown": final_status_breakdown,
        "workflow_final_status_breakdown": workflow_final_status_breakdown,
    }
