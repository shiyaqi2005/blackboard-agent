"""Helpers for post-processing ScienceWorld experiment outputs."""
from __future__ import annotations

import json
import statistics
from pathlib import Path
from typing import Any, Dict, List

from experiment.scienceworld.evaluators.metrics import compute_summary


def load_jsonl(path: str) -> List[Dict[str, Any]]:
    """Load a JSONL file into a list of dicts."""
    results: List[Dict[str, Any]] = []
    with open(path, encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if line:
                results.append(json.loads(line))
    return results


def build_task_summaries(results: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    """Group episode results by ScienceWorld task name and summarize each group."""
    grouped: Dict[str, List[Dict[str, Any]]] = {}
    for result in results:
        metadata = result.get("metadata", {}) or {}
        task_name = str(metadata.get("task_name", result.get("task_id", "unknown")) or "unknown")
        grouped.setdefault(task_name, []).append(result)
    return {task_name: compute_summary(group_results) for task_name, group_results in grouped.items()}


def compute_robustness(task_summaries: Dict[str, Dict[str, Any]]) -> Dict[str, float]:
    """Compute cross-task variability metrics."""
    success_rates = [summary["success_rate"] for summary in task_summaries.values()]
    goal_rates = [summary["mean_goal_condition_rate"] for summary in task_summaries.values()]
    step_means = [summary["mean_steps"] for summary in task_summaries.values()]
    return {
        "task_group_count": float(len(task_summaries)),
        "success_rate_std": statistics.stdev(success_rates) if len(success_rates) > 1 else 0.0,
        "goal_condition_rate_std": statistics.stdev(goal_rates) if len(goal_rates) > 1 else 0.0,
        "mean_steps_std": statistics.stdev(step_means) if len(step_means) > 1 else 0.0,
    }


def analyze_system_compare_summary(summary_path: str) -> Dict[str, Any]:
    """Attach per-task summaries and robustness metrics to a ScienceWorld compare run."""
    path = Path(summary_path)
    summary = json.loads(path.read_text(encoding="utf-8"))
    analyzed_systems: Dict[str, Any] = {}

    for system, system_summary in summary.get("system_summaries", {}).items():
        result_payload = system_summary.get("result", {})
        episodes_path = result_payload.get("episodes_path") or result_payload.get("standard_episodes_path", "")
        episodes = load_jsonl(episodes_path) if episodes_path else []
        task_summaries = build_task_summaries(episodes)
        analyzed_systems[system] = {
            "system_output_dir": system_summary.get("system_output_dir", ""),
            "overall": result_payload.get("summary", {}),
            "task_summaries": task_summaries,
            "robustness": compute_robustness(task_summaries),
        }

    return {
        "analysis_type": "scienceworld_system_compare",
        "summary_path": str(path),
        "systems": summary.get("systems", []),
        "workflow_mode": summary.get("workflow_mode", ""),
        "n_tasks": summary.get("n_tasks", 0),
        "system_summaries": analyzed_systems,
    }


def analyze_ablation_summary(summary_path: str) -> Dict[str, Any]:
    """Attach per-task summaries and full-vs-mode deltas to a ScienceWorld ablation run."""
    path = Path(summary_path)
    summary = json.loads(path.read_text(encoding="utf-8"))
    analyzed_modes: Dict[str, Any] = {}

    for mode, mode_summary in summary.get("summaries", {}).items():
        result_payload = mode_summary.get("result", {})
        episodes_path = result_payload.get("episodes_path") or result_payload.get("standard_episodes_path", "")
        episodes = load_jsonl(episodes_path) if episodes_path else []
        task_summaries = build_task_summaries(episodes)
        analyzed_modes[mode] = {
            "mode_output_dir": mode_summary.get("mode_output_dir", ""),
            "disabled_components": mode_summary.get("disabled_components", []),
            "overall": result_payload.get("summary", {}),
            "task_summaries": task_summaries,
            "robustness": compute_robustness(task_summaries),
        }

    delta_by_mode: Dict[str, Dict[str, float]] = {}
    full = analyzed_modes.get("full", {}).get("overall", {})
    for mode, mode_summary in analyzed_modes.items():
        if mode == "full":
            continue
        overall = mode_summary.get("overall", {})
        delta_by_mode[mode] = {}
        for key in (
            "success_rate",
            "mean_total_tokens",
            "mean_worker_input_tokens",
            "mean_fallback_rate",
            "mean_patch_error_rate",
            "mean_retrieval_precision",
            "mean_context_fragment_count",
            "mean_relevant_fragment_count",
            "mean_irrelevant_fragment_count",
        ):
            delta_by_mode[mode][f"{key}_full_minus_{mode}"] = float(full.get(key, 0.0)) - float(overall.get(key, 0.0))

    return {
        "analysis_type": "scienceworld_ablation",
        "summary_path": str(path),
        "modes": summary.get("modes", []),
        "workflow_mode": summary.get("workflow_mode", ""),
        "n_tasks": summary.get("n_tasks", 0),
        "mode_summaries": analyzed_modes,
        "delta_by_mode": delta_by_mode,
    }
