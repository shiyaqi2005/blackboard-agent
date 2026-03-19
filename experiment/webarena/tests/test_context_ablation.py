"""Tests for the WebArena context-slicing ablation runner."""
from __future__ import annotations

import json
from pathlib import Path

from experiment.webarena.examples.run_context_ablation import run_context_ablation
from experiment.webarena.tests.test_system_compare import _write_config


def test_run_context_ablation_writes_mode_summaries(tmp_path):
    config_a = tmp_path / "task_a.json"
    config_b = tmp_path / "task_b.json"
    _write_config(config_a, task_id=1, site="reddit")
    _write_config(config_b, task_id=2, site="shopping")
    config_files = [str(config_a), str(config_b)]

    def run_mode(mode: str, mode_output_dir: str):
        from experiment.webarena.core.reference_env import WebArenaReferenceEnv
        from experiment.webarena.evaluators.webarena_evaluator import WebArenaEvaluator
        from experiment.webarena.systems.blackboard_runner import WebArenaBlackboardRunner
        from experiment.common.result_writer import ResultWriter

        env = WebArenaReferenceEnv()
        runner = WebArenaBlackboardRunner(
            env,
            config={
                "workflow_mode": "planner_action",
                "execution_backend": "reference_oracle",
                "use_context_slicing": mode != "ablate_c4",
            },
        )
        writer = ResultWriter(
            mode_output_dir,
            run_id=mode,
            system_id=f"blackboard_{mode}",
            system_family="blackboard",
            env_name="webarena",
        )
        evaluator = WebArenaEvaluator(adapter=runner, result_writer=writer)
        try:
            evaluator.run_batch(
                config_files,
                run_id=mode,
                experiment_id=f"webarena:context_ablation:{mode}",
                model_name="reference_model",
                max_steps=5,
                task_set="debug",
                seed=42,
            )
            summary = evaluator.finalize()
        finally:
            env.close()
        return {
            "summary": summary,
            "episodes_path": str(writer.episodes_path),
            "standard_episodes_path": str(writer.standard_episodes_path),
            "summary_path": str(writer.summary_path),
        }

    consolidated = run_context_ablation(
        config_files=config_files,
        output_dir=str(tmp_path / "context"),
        run_mode=run_mode,
        workflow_mode="planner_action",
        execution_backend="reference_oracle",
    )

    loaded = json.loads((tmp_path / "context" / "context_ablation_summary.json").read_text(encoding="utf-8"))
    assert consolidated["summary_type"] == "context_ablation"
    assert loaded["modes"] == ["full", "ablate_c4"]
    assert loaded["summaries"]["full"]["result"]["summary"]["mean_retrieval_precision"] == 1.0
    assert loaded["summaries"]["ablate_c4"]["result"]["summary"]["mean_retrieval_precision"] < 1.0
