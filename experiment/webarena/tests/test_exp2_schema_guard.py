"""Tests for WebArena Experiment 2 schema-guard support."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import pytest

from experiment.webarena.evaluators.schema_guard_evaluator import SchemaGuardEvaluator
from experiment.webarena.examples.run_schema_guard_eval import capture_states_from_task_set, load_jsonl
from experiment.webarena.utils.injection import build_injection_cases


def _write_config(path: Path, *, task_id: int = 9, site: str = "reddit") -> None:
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


def _write_manifest(path: Path, config_path: Path) -> None:
    path.write_text(
        json.dumps(
            {
                "env_name": "webarena",
                "task_set": "exp2_debug",
                "root_dir": str(config_path.parent),
                "selection": {
                    "mode": "explicit",
                    "items": [config_path.name],
                },
            }
        ),
        encoding="utf-8",
    )


def _make_args(manifest_path: Path, output_dir: Path) -> argparse.Namespace:
    return argparse.Namespace(
        states_file="",
        task_set_file=str(manifest_path),
        output_dir=str(output_dir),
        run_id="capture_states",
        limit=0,
        seed=42,
        max_steps=5,
        workflow_mode="planner_action",
        execution_backend="reference_oracle",
        model_name="webarena_reference",
        render=False,
        slow_mo=0,
        observation_type="accessibility_tree",
        current_viewport_only=False,
        viewport_width=1280,
        viewport_height=720,
        save_trace_enabled=False,
        sleep_after_execution=0.0,
        injection_types="",
    )


def test_capture_states_from_task_set_writes_schema_guard_ready_states(tmp_path):
    config_path = tmp_path / "task.json"
    manifest_path = tmp_path / "manifest.json"
    _write_config(config_path)
    _write_manifest(manifest_path, config_path)

    capture = capture_states_from_task_set(_make_args(manifest_path, tmp_path / "out"))
    states = load_jsonl(capture["states_path"])

    assert capture["task_set"]["n_tasks"] == 1
    assert len(states) == 2
    assert states[0]["domain_state"]["task_id"] == "9"
    assert "workflow_status" in states[0]["data_schema"]["properties"]


def test_schema_guard_evaluator_runs_from_captured_webarena_states(tmp_path):
    config_path = tmp_path / "task.json"
    manifest_path = tmp_path / "manifest.json"
    _write_config(config_path)
    _write_manifest(manifest_path, config_path)

    capture = capture_states_from_task_set(_make_args(manifest_path, tmp_path / "out"))
    states = load_jsonl(capture["states_path"])

    cases = build_injection_cases(states)
    assert any(case["injection_type"] == "invalid_enum" for case in cases)

    results, metrics = SchemaGuardEvaluator().evaluate_from_states(states)

    assert len(results) > 0
    assert metrics.n_cases >= len(states)
    assert metrics.c2_on_interception_rate >= metrics.c2_off_interception_rate
    assert "missing_op" in metrics.c2_on_interception_by_type


def test_capture_states_from_task_set_raises_for_empty_manifest(tmp_path):
    empty_root = tmp_path / "config_files"
    empty_root.mkdir(parents=True, exist_ok=True)
    manifest_path = tmp_path / "empty_manifest.json"
    manifest_path.write_text(
        json.dumps(
            {
                "env_name": "webarena",
                "task_set": "empty",
                "root_dir": str(empty_root),
                "selection": {
                    "mode": "glob",
                    "patterns": ["*.json"],
                },
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="resolved zero tasks"):
        capture_states_from_task_set(_make_args(manifest_path, tmp_path / "out"))
