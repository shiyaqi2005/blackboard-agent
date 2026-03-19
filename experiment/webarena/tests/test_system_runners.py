"""Tests for WebArena reference-policy system runners."""
from __future__ import annotations

import json

from experiment.webarena.core.reference_env import WebArenaReferenceEnv
from experiment.webarena.systems.autogen_runner import WebArenaAutoGenRunner
from experiment.webarena.systems.blackboard_runner import WebArenaBlackboardRunner
from experiment.webarena.systems.langgraph_runner import WebArenaLangGraphRunner


def _write_config(path, *, task_id: int = 7, site: str = "reddit") -> None:
    path.write_text(
        json.dumps(
            {
                "task_id": task_id,
                "sites": [site],
                "intent": "reach the answer page",
                "start_url": "http://example.com",
                "require_login": False,
                "eval": {"eval_types": ["url_match"]},
                "reference_action_sequence": {
                    "action_sequence": [
                        "page.get_by_role('link', name='Forums').click()",
                        "page.stop('answer')",
                    ]
                },
            }
        ),
        encoding="utf-8",
    )


def test_blackboard_runner_episode_has_structured_trace(tmp_path):
    config_path = tmp_path / "task.json"
    _write_config(config_path)
    runner = WebArenaBlackboardRunner(
        WebArenaReferenceEnv(),
        config={"workflow_mode": "planner_action", "execution_backend": "reference_oracle"},
    )

    result = runner.run_episode(
        config_file=str(config_path),
        run_id="run1",
        experiment_id="webarena:blackboard",
        model_name="reference_model",
        task_set="debug",
        seed=42,
        capture_states=True,
    )

    assert result["success"] is True
    assert result["steps"] == 2
    assert result["task_set"] == "debug"
    assert result["trajectory"][0]["communication_trace"][0]["source"] == "architect"
    assert result["worker_input_tokens"] > 0
    assert len(result["captured_states"]) == 2
    assert result["captured_states"][0]["data_schema"]["properties"]["workflow_status"]["enum"] == [
        "planning",
        "acting",
        "completed",
    ]
    assert result["retrieval_precision"] == 1.0
    assert result["metadata"]["context_mode"] == "sliced"


def test_blackboard_runner_ablate_c4_uses_full_context(tmp_path):
    config_path = tmp_path / "task.json"
    _write_config(config_path)
    runner = WebArenaBlackboardRunner(
        WebArenaReferenceEnv(),
        config={
            "workflow_mode": "planner_action",
            "execution_backend": "reference_oracle",
            "use_context_slicing": False,
        },
    )

    result = runner.run_episode(config_file=str(config_path), model_name="reference_model")

    assert result["success"] is True
    assert result["metadata"]["context_mode"] == "full"
    assert result["retrieval_precision"] < 1.0
    assert result["context_fragment_count"] > result["relevant_fragment_count"]


def test_blackboard_runner_ablate_c1_uses_natural_language_trace(tmp_path):
    config_path = tmp_path / "task.json"
    _write_config(config_path)
    runner = WebArenaBlackboardRunner(
        WebArenaReferenceEnv(),
        config={
            "workflow_mode": "planner_action",
            "execution_backend": "reference_oracle",
            "communication_style": "natural_language",
        },
    )

    result = runner.run_episode(config_file=str(config_path), model_name="reference_model")

    assert result["success"] is True
    assert result["communication_trace"][0]["channel"] == "natural_language"


def test_blackboard_runner_ablate_c3_increases_fallbacks(tmp_path):
    config_path = tmp_path / "task.json"
    _write_config(config_path)
    runner = WebArenaBlackboardRunner(
        WebArenaReferenceEnv(),
        config={
            "workflow_mode": "planner_action",
            "execution_backend": "reference_oracle",
            "use_deterministic_kernel": False,
        },
    )

    result = runner.run_episode(config_file=str(config_path), model_name="reference_model")

    assert result["success"] is True
    assert result["fallback_action_count"] > 0


def test_blackboard_runner_ablate_c5_disables_architect_tokens(tmp_path):
    config_path = tmp_path / "task.json"
    _write_config(config_path)
    runner = WebArenaBlackboardRunner(
        WebArenaReferenceEnv(),
        config={
            "workflow_mode": "planner_action",
            "execution_backend": "reference_oracle",
            "use_architect_agent": False,
        },
    )

    result = runner.run_episode(config_file=str(config_path), model_name="reference_model")

    assert result["success"] is True
    assert result["architect_input_tokens"] == 0
    assert result["communication_trace"][0]["source"] == "action_worker"


def test_langgraph_runner_episode_has_text_trace(tmp_path):
    config_path = tmp_path / "task.json"
    _write_config(config_path)
    runner = WebArenaLangGraphRunner(
        WebArenaReferenceEnv(),
        config={"workflow_mode": "planner_action", "execution_backend": "reference_oracle"},
    )

    result = runner.run_episode(config_file=str(config_path), model_name="reference_model")

    assert result["success"] is True
    assert result["trajectory"][0]["communication_trace"][0]["source"] == "planner_node"
    assert "reference action" in result["trajectory"][0]["communication_trace"][0]["content"]


def test_autogen_runner_episode_has_natural_language_trace(tmp_path):
    config_path = tmp_path / "task.json"
    _write_config(config_path)
    runner = WebArenaAutoGenRunner(
        WebArenaReferenceEnv(),
        config={"workflow_mode": "planner_action", "execution_backend": "reference_oracle"},
    )

    result = runner.run_episode(config_file=str(config_path), model_name="reference_model")

    assert result["success"] is True
    assert result["trajectory"][0]["communication_trace"][0]["source"] == "planner"
    assert result["trajectory"][0]["communication_trace"][1]["source"] == "executor"
    assert result["worker_output_tokens"] > 0
