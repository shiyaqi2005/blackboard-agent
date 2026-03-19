"""Tests for the ScienceWorld system comparison runner."""
from __future__ import annotations

import json
from pathlib import Path

from experiment.common.result_writer import ResultWriter
from experiment.scienceworld.core.reference_env import ScienceWorldReferenceEnv
from experiment.scienceworld.evaluators.scienceworld_evaluator import ScienceWorldEvaluator
from experiment.scienceworld.examples.run_system_compare import run_system_compare
from experiment.scienceworld.systems.autogen_runner import ScienceWorldAutoGenRunner
from experiment.scienceworld.systems.blackboard_runner import ScienceWorldBlackboardRunner
from experiment.scienceworld.systems.langgraph_runner import ScienceWorldLangGraphRunner
from experiment.scienceworld.tests.test_system_runners import _FakeScienceWorldEnv, _write_config


def test_run_system_compare_writes_summary_with_reference_runners(tmp_path):
    config_a = tmp_path / "task_a.json"
    config_b = tmp_path / "task_b.json"
    _write_config(config_a)
    _write_config(config_b)
    config_files = [str(config_a), str(config_b)]

    def run_system_suite(system: str, system_output_dir: str):
        env = ScienceWorldReferenceEnv(env_factory=_FakeScienceWorldEnv)
        config = {"workflow_mode": "planner_action", "execution_backend": "reference_oracle"}
        if system == "blackboard":
            runner = ScienceWorldBlackboardRunner(env, config=config)
        elif system == "langgraph":
            runner = ScienceWorldLangGraphRunner(env, config=config)
        else:
            runner = ScienceWorldAutoGenRunner(env, config=config)
        writer = ResultWriter(
            system_output_dir,
            run_id=f"{system}_reference",
            system_id=f"{system}_planner_action",
            system_family=system,
            env_name="scienceworld",
        )
        evaluator = ScienceWorldEvaluator(adapter=runner, result_writer=writer)
        evaluator.run_batch(
            config_files,
            run_id=f"{system}_reference",
            experiment_id=f"scienceworld:{system}",
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
    )

    loaded = json.loads((tmp_path / "compare" / "system_compare_summary.json").read_text(encoding="utf-8"))
    assert consolidated["n_tasks"] == 2
    assert loaded["systems"] == ["blackboard", "langgraph", "autogen"]
    assert loaded["system_summaries"]["autogen"]["result"]["summary"]["success_rate"] == 1.0
