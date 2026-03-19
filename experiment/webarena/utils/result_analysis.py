"""Helpers for post-processing WebArena experiment outputs."""
from __future__ import annotations

import json
import statistics
from pathlib import Path
from typing import Any, Dict, List

from experiment.webarena.evaluators.metrics import compute_summary


def load_jsonl(path: str) -> List[Dict[str, Any]]:
    """Load a JSONL file into a list of dicts."""
    results: List[Dict[str, Any]] = []
    with open(path, encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if line:
                results.append(json.loads(line))
    return results


def build_site_summaries(results: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    """Group episode results by WebArena site family and summarize each group."""
    grouped: Dict[str, List[Dict[str, Any]]] = {}
    for result in results:
        metadata = result.get("metadata", {}) or {}
        sites = metadata.get("sites", []) or []
        site_group = "+".join(str(site) for site in sites) if sites else "unknown"
        grouped.setdefault(site_group, []).append(result)
    return {site_group: compute_summary(group_results) for site_group, group_results in grouped.items()}


def compute_robustness(site_summaries: Dict[str, Dict[str, Any]]) -> Dict[str, float]:
    """Compute cross-site variability metrics."""
    success_rates = [summary["success_rate"] for summary in site_summaries.values()]
    goal_rates = [summary["mean_goal_condition_rate"] for summary in site_summaries.values()]
    step_means = [summary["mean_steps"] for summary in site_summaries.values()]
    return {
        "site_group_count": float(len(site_summaries)),
        "success_rate_std": statistics.stdev(success_rates) if len(success_rates) > 1 else 0.0,
        "goal_condition_rate_std": statistics.stdev(goal_rates) if len(goal_rates) > 1 else 0.0,
        "mean_steps_std": statistics.stdev(step_means) if len(step_means) > 1 else 0.0,
    }


def analyze_system_compare_summary(summary_path: str) -> Dict[str, Any]:
    """Attach per-site summaries and robustness metrics to a WebArena system compare run."""
    path = Path(summary_path)
    summary = json.loads(path.read_text(encoding="utf-8"))
    analyzed_systems: Dict[str, Any] = {}

    for system, system_summary in summary.get("system_summaries", {}).items():
        result_payload = system_summary.get("result", {})
        episodes_path = result_payload.get("episodes_path") or result_payload.get("standard_episodes_path", "")
        episodes = load_jsonl(episodes_path) if episodes_path else []
        site_summaries = build_site_summaries(episodes)
        analyzed_systems[system] = {
            "system_output_dir": system_summary.get("system_output_dir", ""),
            "overall": result_payload.get("summary", {}),
            "site_summaries": site_summaries,
            "robustness": compute_robustness(site_summaries),
        }

    return {
        "analysis_type": "webarena_system_compare",
        "summary_path": str(path),
        "systems": summary.get("systems", []),
        "workflow_mode": summary.get("workflow_mode", ""),
        "execution_backend": summary.get("execution_backend", ""),
        "n_tasks": summary.get("n_tasks", 0),
        "system_summaries": analyzed_systems,
    }


def analyze_context_ablation_summary(summary_path: str) -> Dict[str, Any]:
    """Attach per-site summaries and mode deltas to a WebArena C4 ablation run."""
    path = Path(summary_path)
    summary = json.loads(path.read_text(encoding="utf-8"))
    analyzed_modes: Dict[str, Any] = {}

    for mode, mode_summary in summary.get("summaries", {}).items():
        result_payload = mode_summary.get("result", {})
        episodes_path = result_payload.get("episodes_path") or result_payload.get("standard_episodes_path", "")
        episodes = load_jsonl(episodes_path) if episodes_path else []
        site_summaries = build_site_summaries(episodes)
        analyzed_modes[mode] = {
            "mode_output_dir": mode_summary.get("mode_output_dir", ""),
            "overall": result_payload.get("summary", {}),
            "site_summaries": site_summaries,
            "robustness": compute_robustness(site_summaries),
        }

    delta: Dict[str, float] = {}
    full = analyzed_modes.get("full", {}).get("overall", {})
    ablate_c4 = analyzed_modes.get("ablate_c4", {}).get("overall", {})
    if full and ablate_c4:
        for key in (
            "success_rate",
            "mean_total_tokens",
            "mean_worker_input_tokens",
            "mean_retrieval_precision",
            "mean_context_fragment_count",
            "mean_relevant_fragment_count",
            "mean_irrelevant_fragment_count",
        ):
            delta[f"{key}_full_minus_ablate_c4"] = float(full.get(key, 0.0)) - float(ablate_c4.get(key, 0.0))

    return {
        "analysis_type": "webarena_context_ablation",
        "summary_path": str(path),
        "modes": summary.get("modes", []),
        "workflow_mode": summary.get("workflow_mode", ""),
        "execution_backend": summary.get("execution_backend", ""),
        "n_tasks": summary.get("n_tasks", 0),
        "mode_summaries": analyzed_modes,
        "delta": delta,
    }


def analyze_ablation_summary(summary_path: str) -> Dict[str, Any]:
    """Attach per-site summaries and full-vs-mode deltas to a WebArena ablation run."""
    path = Path(summary_path)
    summary = json.loads(path.read_text(encoding="utf-8"))
    analyzed_modes: Dict[str, Any] = {}

    for mode, mode_summary in summary.get("summaries", {}).items():
        result_payload = mode_summary.get("result", {})
        episodes_path = result_payload.get("episodes_path") or result_payload.get("standard_episodes_path", "")
        episodes = load_jsonl(episodes_path) if episodes_path else []
        site_summaries = build_site_summaries(episodes)
        analyzed_modes[mode] = {
            "mode_output_dir": mode_summary.get("mode_output_dir", ""),
            "disabled_components": mode_summary.get("disabled_components", []),
            "overall": result_payload.get("summary", {}),
            "site_summaries": site_summaries,
            "robustness": compute_robustness(site_summaries),
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
        "analysis_type": "webarena_ablation",
        "summary_path": str(path),
        "modes": summary.get("modes", []),
        "workflow_mode": summary.get("workflow_mode", ""),
        "execution_backend": summary.get("execution_backend", ""),
        "n_tasks": summary.get("n_tasks", 0),
        "mode_summaries": analyzed_modes,
        "delta_by_mode": delta_by_mode,
    }
