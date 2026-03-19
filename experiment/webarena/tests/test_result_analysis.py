"""Tests for WebArena result analysis helpers."""
from __future__ import annotations

import json

from experiment.webarena.utils.result_analysis import (
    analyze_ablation_summary,
    analyze_context_ablation_summary,
    analyze_system_compare_summary,
)


def test_analyze_system_compare_summary_adds_site_breakdowns(tmp_path):
    episodes_path = tmp_path / "autogen_episodes.jsonl"
    episodes_path.write_text(
        "\n".join(
            [
                json.dumps(
                    {
                        "task_id": "1",
                        "success": True,
                        "steps": 2,
                        "total_tokens": 10,
                        "goal_condition_rate": 1.0,
                        "worker_input_tokens": 3,
                        "worker_output_tokens": 4,
                        "architect_input_tokens": 1,
                        "architect_output_tokens": 2,
                        "fallback_action_count": 0,
                        "patch_error_count": 0,
                        "stop_reason": "reference_completed",
                        "final_status": "success",
                        "workflow_final_status": "completed",
                        "metadata": {"sites": ["reddit"]},
                    }
                )
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    summary_path = tmp_path / "system_compare_summary.json"
    summary_path.write_text(
        json.dumps(
            {
                "systems": ["autogen"],
                "n_tasks": 1,
                "workflow_mode": "planner_action",
                "execution_backend": "reference_oracle",
                "system_summaries": {
                    "autogen": {
                        "system_output_dir": str(tmp_path / "autogen"),
                        "result": {
                            "summary": {"success_rate": 1.0, "mean_steps": 2.0},
                            "episodes_path": str(episodes_path),
                        },
                    }
                },
            }
        ),
        encoding="utf-8",
    )

    analysis = analyze_system_compare_summary(str(summary_path))

    assert analysis["analysis_type"] == "webarena_system_compare"
    assert analysis["system_summaries"]["autogen"]["site_summaries"]["reddit"]["success_rate"] == 1.0


def test_analyze_context_ablation_summary_adds_mode_deltas(tmp_path):
    full_episodes = tmp_path / "full_episodes.jsonl"
    full_episodes.write_text(
        json.dumps(
            {
                "task_id": "1",
                "success": True,
                "steps": 2,
                "total_tokens": 10,
                "goal_condition_rate": 1.0,
                "worker_input_tokens": 3,
                "worker_output_tokens": 4,
                "architect_input_tokens": 1,
                "architect_output_tokens": 2,
                "fallback_action_count": 0,
                "patch_error_count": 0,
                "retrieval_precision": 1.0,
                "context_fragment_count": 4.0,
                "relevant_fragment_count": 4.0,
                "irrelevant_fragment_count": 0.0,
                "stop_reason": "reference_completed",
                "final_status": "success",
                "workflow_final_status": "completed",
                "metadata": {"sites": ["reddit"], "context_mode": "sliced"},
            }
        )
        + "\n",
        encoding="utf-8",
    )
    ablate_episodes = tmp_path / "ablate_episodes.jsonl"
    ablate_episodes.write_text(
        json.dumps(
            {
                "task_id": "1",
                "success": True,
                "steps": 2,
                "total_tokens": 15,
                "goal_condition_rate": 1.0,
                "worker_input_tokens": 6,
                "worker_output_tokens": 4,
                "architect_input_tokens": 2,
                "architect_output_tokens": 3,
                "fallback_action_count": 0,
                "patch_error_count": 0,
                "retrieval_precision": 0.5,
                "context_fragment_count": 8.0,
                "relevant_fragment_count": 4.0,
                "irrelevant_fragment_count": 4.0,
                "stop_reason": "reference_completed",
                "final_status": "success",
                "workflow_final_status": "completed",
                "metadata": {"sites": ["reddit"], "context_mode": "full"},
            }
        )
        + "\n",
        encoding="utf-8",
    )
    summary_path = tmp_path / "context_ablation_summary.json"
    summary_path.write_text(
        json.dumps(
            {
                "summary_type": "context_ablation",
                "modes": ["full", "ablate_c4"],
                "n_tasks": 1,
                "workflow_mode": "planner_action",
                "execution_backend": "reference_oracle",
                "summaries": {
                    "full": {
                        "mode_output_dir": str(tmp_path / "full"),
                        "result": {
                            "summary": {
                                "success_rate": 1.0,
                                "mean_steps": 2.0,
                                "mean_total_tokens": 10.0,
                                "mean_worker_input_tokens": 3.0,
                                "mean_retrieval_precision": 1.0,
                                "mean_context_fragment_count": 4.0,
                                "mean_relevant_fragment_count": 4.0,
                                "mean_irrelevant_fragment_count": 0.0,
                            },
                            "episodes_path": str(full_episodes),
                        },
                    },
                    "ablate_c4": {
                        "mode_output_dir": str(tmp_path / "ablate_c4"),
                        "result": {
                            "summary": {
                                "success_rate": 1.0,
                                "mean_steps": 2.0,
                                "mean_total_tokens": 15.0,
                                "mean_worker_input_tokens": 6.0,
                                "mean_retrieval_precision": 0.5,
                                "mean_context_fragment_count": 8.0,
                                "mean_relevant_fragment_count": 4.0,
                                "mean_irrelevant_fragment_count": 4.0,
                            },
                            "episodes_path": str(ablate_episodes),
                        },
                    },
                },
            }
        ),
        encoding="utf-8",
    )

    analysis = analyze_context_ablation_summary(str(summary_path))

    assert analysis["analysis_type"] == "webarena_context_ablation"
    assert analysis["mode_summaries"]["full"]["site_summaries"]["reddit"]["mean_retrieval_precision"] == 1.0
    assert analysis["delta"]["mean_retrieval_precision_full_minus_ablate_c4"] == 0.5


def test_analyze_ablation_summary_adds_delta_by_mode(tmp_path):
    full_episodes = tmp_path / "full_episodes.jsonl"
    full_episodes.write_text(
        json.dumps(
            {
                "task_id": "1",
                "success": True,
                "steps": 2,
                "total_tokens": 10,
                "goal_condition_rate": 1.0,
                "worker_input_tokens": 3,
                "worker_output_tokens": 4,
                "architect_input_tokens": 1,
                "architect_output_tokens": 2,
                "fallback_action_count": 0,
                "patch_error_count": 0,
                "retrieval_precision": 1.0,
                "context_fragment_count": 4.0,
                "relevant_fragment_count": 4.0,
                "irrelevant_fragment_count": 0.0,
                "stop_reason": "reference_completed",
                "final_status": "success",
                "workflow_final_status": "completed",
                "metadata": {"sites": ["reddit"], "context_mode": "sliced"},
            }
        )
        + "\n",
        encoding="utf-8",
    )
    ablate_episodes = tmp_path / "ablate_episodes.jsonl"
    ablate_episodes.write_text(
        json.dumps(
            {
                "task_id": "1",
                "success": True,
                "steps": 2,
                "total_tokens": 15,
                "goal_condition_rate": 1.0,
                "worker_input_tokens": 6,
                "worker_output_tokens": 4,
                "architect_input_tokens": 2,
                "architect_output_tokens": 3,
                "fallback_action_count": 1,
                "patch_error_count": 0,
                "retrieval_precision": 0.8,
                "context_fragment_count": 5.0,
                "relevant_fragment_count": 4.0,
                "irrelevant_fragment_count": 1.0,
                "stop_reason": "reference_completed",
                "final_status": "success",
                "workflow_final_status": "completed",
                "metadata": {"sites": ["reddit"], "context_mode": "sliced"},
            }
        )
        + "\n",
        encoding="utf-8",
    )
    summary_path = tmp_path / "ablation_summary.json"
    summary_path.write_text(
        json.dumps(
            {
                "summary_type": "webarena_ablation",
                "modes": ["full", "ablate_c3"],
                "n_tasks": 1,
                "workflow_mode": "planner_action",
                "execution_backend": "reference_oracle",
                "summaries": {
                    "full": {
                        "mode_output_dir": str(tmp_path / "full"),
                        "disabled_components": [],
                        "result": {
                            "summary": {
                                "success_rate": 1.0,
                                "mean_total_tokens": 10.0,
                                "mean_worker_input_tokens": 3.0,
                                "mean_fallback_rate": 0.0,
                                "mean_patch_error_rate": 0.0,
                                "mean_retrieval_precision": 1.0,
                                "mean_context_fragment_count": 4.0,
                                "mean_relevant_fragment_count": 4.0,
                                "mean_irrelevant_fragment_count": 0.0,
                            },
                            "episodes_path": str(full_episodes),
                        },
                    },
                    "ablate_c3": {
                        "mode_output_dir": str(tmp_path / "ablate_c3"),
                        "disabled_components": ["C3"],
                        "result": {
                            "summary": {
                                "success_rate": 1.0,
                                "mean_total_tokens": 15.0,
                                "mean_worker_input_tokens": 6.0,
                                "mean_fallback_rate": 0.5,
                                "mean_patch_error_rate": 0.0,
                                "mean_retrieval_precision": 0.8,
                                "mean_context_fragment_count": 5.0,
                                "mean_relevant_fragment_count": 4.0,
                                "mean_irrelevant_fragment_count": 1.0,
                            },
                            "episodes_path": str(ablate_episodes),
                        },
                    },
                },
            }
        ),
        encoding="utf-8",
    )

    analysis = analyze_ablation_summary(str(summary_path))

    assert analysis["analysis_type"] == "webarena_ablation"
    assert analysis["mode_summaries"]["ablate_c3"]["disabled_components"] == ["C3"]
    assert analysis["delta_by_mode"]["ablate_c3"]["mean_fallback_rate_full_minus_ablate_c3"] == -0.5
