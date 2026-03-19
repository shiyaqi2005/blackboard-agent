"""Tests for ScienceWorld task config loading and task manifests."""
from __future__ import annotations

import json
from pathlib import Path

from experiment.common.task_registry import load_task_paths, resolve_task_set
from experiment.scienceworld.utils.task_loader import parse_task, task_group


def test_parse_task_extracts_normalized_fields(tmp_path):
    config_path = tmp_path / "task.json"
    config_path.write_text(
        json.dumps(
            {
                "task_id": "1-1",
                "task_name": "1-1",
                "variation_idx": 2,
                "simplification_str": "easy",
                "split": "debug",
                "max_episode_steps": 60,
                "notes": "sample",
            }
        ),
        encoding="utf-8",
    )

    task = parse_task(config_path)

    assert task.task_id == "1-1"
    assert task.task_name == "1-1"
    assert task.variation_idx == 2
    assert task.simplification_str == "easy"
    assert task.max_episode_steps == 60
    assert task_group(task) == "1-1"


def test_checked_in_scienceworld_debug_manifest_resolves_configs():
    repo_root = Path(__file__).resolve().parents[3]
    manifest_path = repo_root / "experiment" / "common" / "task_sets" / "scienceworld_debug.json"

    task_paths = load_task_paths(manifest_path)

    assert len(task_paths) == 4
    assert task_paths[0].endswith("experiment/scienceworld/configs/boil_var0.json")


def test_checked_in_scienceworld_formal_manifest_resolves_configs():
    repo_root = Path(__file__).resolve().parents[3]
    manifest_path = repo_root / "experiment" / "common" / "task_sets" / "scienceworld_formal.json"

    resolved = resolve_task_set(manifest_path)

    assert resolved["n_tasks"] == 8
    assert all(Path(task_path).is_file() for task_path in resolved["task_paths"])
