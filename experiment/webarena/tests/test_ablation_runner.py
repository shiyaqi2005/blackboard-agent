"""Tests for the WebArena ablation runner."""
from __future__ import annotations

import json

from experiment.webarena.examples.run_ablation import run_ablation
from experiment.webarena.tests.test_system_compare import _write_config
from experiment.webarena.utils.ablation_matrix import resolve_ablation_modes


def test_resolve_ablation_modes_preserves_canonical_order():
    assert resolve_ablation_modes(["ablate_c5", "ablate_c1"]) == ["ablate_c1", "ablate_c5"]


def test_run_ablation_writes_mode_summaries(tmp_path):
    config_a = tmp_path / "task_a.json"
    config_b = tmp_path / "task_b.json"
    _write_config(config_a, task_id=1, site="reddit")
    _write_config(config_b, task_id=2, site="shopping")
    config_files = [str(config_a), str(config_b)]

    def run_mode(mode: str, mode_output_dir: str):
        from experiment.common.result_writer import ResultWriter
        from experiment.webarena.core.reference_env import WebArenaReferenceEnv
        from experiment.webarena.evaluators.webarena_evaluator import WebArenaEvaluator
        from experiment.webarena.systems.blackboard_runner import WebArenaBlackboardRunner
        from experiment.webarena.utils.ablation_matrix import build_ablation_runner_config

        env = WebArenaReferenceEnv()
        runner = WebArenaBlackboardRunner(
            env,
            config={
                "workflow_mode": "planner_action",
                "execution_backend": "reference_oracle",
                **build_ablation_runner_config(mode),
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
                experiment_id=f"webarena:ablation:{mode}",
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

    consolidated = run_ablation(
        config_files=config_files,
        modes=["full", "ablate_c1", "ablate_c3", "ablate_c5"],
        output_dir=str(tmp_path / "ablation"),
        run_mode=run_mode,
        workflow_mode="planner_action",
        execution_backend="reference_oracle",
    )

    loaded = json.loads((tmp_path / "ablation" / "ablation_summary.json").read_text(encoding="utf-8"))
    assert consolidated["summary_type"] == "webarena_ablation"
    assert loaded["modes"] == ["full", "ablate_c1", "ablate_c3", "ablate_c5"]
    assert loaded["summaries"]["ablate_c3"]["result"]["summary"]["mean_fallback_rate"] > 0.0
