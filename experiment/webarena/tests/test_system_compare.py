"""Tests for the WebArena system comparison runner."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from experiment.common.result_writer import ResultWriter
from experiment.webarena.core.reference_env import WebArenaReferenceEnv
from experiment.webarena.evaluators.webarena_evaluator import WebArenaEvaluator
from experiment.webarena.examples.run_system_compare import run_named_system, run_system_compare
from experiment.webarena.systems.autogen_runner import WebArenaAutoGenRunner
from experiment.webarena.systems.blackboard_runner import WebArenaBlackboardRunner
from experiment.webarena.systems.langgraph_runner import WebArenaLangGraphRunner


def _write_config(path, *, task_id: int, site: str) -> None:
    path.write_text(
        json.dumps(
            {
                "task_id": task_id,
                "sites": [site],
                "intent": f"task {task_id}",
                "start_url": "http://example.com",
                "require_login": False,
                "eval": {"eval_types": ["string_match"]},
                "reference_action_sequence": {
                    "action_sequence": [
                        f"page.get_by_role('link', name='{site}').click()",
                        "page.stop('done')",
                    ]
                },
            }
        ),
        encoding="utf-8",
    )


def test_run_system_compare_writes_summary_with_real_reference_runners(tmp_path):
    config_a = tmp_path / "task_a.json"
    config_b = tmp_path / "task_b.json"
    _write_config(config_a, task_id=1, site="reddit")
    _write_config(config_b, task_id=2, site="shopping")
    config_files = [str(config_a), str(config_b)]

    def run_system_suite(system: str, system_output_dir: str):
        env = WebArenaReferenceEnv()
        config = {"workflow_mode": "planner_action", "execution_backend": "reference_oracle"}
        if system == "blackboard":
            runner = WebArenaBlackboardRunner(env, config=config)
        elif system == "langgraph":
            runner = WebArenaLangGraphRunner(env, config=config)
        else:
            runner = WebArenaAutoGenRunner(env, config=config)
        writer = ResultWriter(
            system_output_dir,
            run_id=f"{system}_reference",
            system_id=f"{system}_planner_action",
            system_family=system,
            env_name="webarena",
        )
        evaluator = WebArenaEvaluator(adapter=runner, result_writer=writer)
        evaluator.run_batch(
            config_files,
            run_id=f"{system}_reference",
            experiment_id=f"webarena:{system}",
            model_name="reference_model",
            max_steps=5,
            task_set="debug",
            seed=42,
        )
        summary = evaluator.finalize()
        return {
            "summary": summary,
            "episodes_path": str(writer.episodes_path),
            "standard_episodes_path": str(writer.standard_episodes_path),
        }

    consolidated = run_system_compare(
        config_files=config_files,
        systems=["blackboard", "langgraph", "autogen"],
        output_dir=str(tmp_path / "compare"),
        run_system_suite=run_system_suite,
        workflow_mode="planner_action",
        execution_backend="reference_oracle",
    )

    loaded = json.loads((tmp_path / "compare" / "system_compare_summary.json").read_text(encoding="utf-8"))
    assert consolidated["n_tasks"] == 2
    assert loaded["systems"] == ["blackboard", "langgraph", "autogen"]
    assert loaded["system_summaries"]["autogen"]["result"]["summary"]["success_rate"] == 1.0


def test_run_named_system_supports_official_prompt(monkeypatch, tmp_path):
    config_path = tmp_path / "task.json"
    _write_config(config_path, task_id=3, site="reddit")

    class _FakeEnv:
        def close(self):
            return None

    class _FakeOfficialPromptRunner:
        def __init__(self, env, config):
            self.env = env
            self.config = config

        def run_episode(self, *, config_file: str, **kwargs):
            return {
                "config_file": config_file,
                "task_id": "3",
                "success": True,
                "goal_condition_rate": 1.0,
                "steps": 2,
                "stop_reason": "official_evaluator",
                "total_tokens": 12,
                "worker_input_tokens": 5,
                "worker_output_tokens": 7,
                "architect_input_tokens": 0,
                "architect_output_tokens": 0,
                "fallback_action_count": 0,
                "patch_error_count": 0,
                "trajectory": [],
                "communication_trace": [],
                "final_status": "success",
                "workflow_final_status": "completed",
                "metadata": {"sites": ["reddit"], "agent_type": "prompt"},
            }

    monkeypatch.setattr(
        "experiment.webarena.examples.run_system_compare.build_env",
        lambda args: _FakeEnv(),
    )
    monkeypatch.setattr(
        "experiment.webarena.examples.run_system_compare.WebArenaOfficialPromptRunner",
        _FakeOfficialPromptRunner,
    )

    args = argparse.Namespace(
        task_set_file=str(tmp_path / "manifest.json"),
        workflow_mode="single_action",
        execution_backend="script_browser",
        max_steps=5,
        model_name="shared_model",
        render=False,
        slow_mo=0,
        observation_type="accessibility_tree",
        current_viewport_only=False,
        viewport_width=1280,
        viewport_height=720,
        save_trace_enabled=False,
        sleep_after_execution=0.0,
        seed=42,
        official_agent_type="prompt",
        official_instruction_path="",
        official_provider="openai",
        official_model="gpt-4o-mini",
        official_mode="chat",
        official_temperature=0.0,
        official_top_p=0.9,
        official_context_length=0,
        official_max_tokens=384,
        official_stop_token=None,
        official_max_retry=1,
        official_max_obs_length=1920,
        official_model_endpoint="",
    )
    task_set = {"task_set": "debug", "selection_mode": "explicit", "selection_seed": 42}

    result = run_named_system(
        args=args,
        system="official_prompt",
        system_output_dir=str(tmp_path / "official_prompt"),
        config_files=[str(config_path)],
        task_set=task_set,
    )

    assert result["system_family"] == "webarena_prompt"
    assert result["system_id"] == "official_prompt_prompt"
    assert result["summary"]["success_rate"] == 1.0
    assert Path(result["summary_path"]).exists()
