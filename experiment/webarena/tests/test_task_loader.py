"""Tests for WebArena task config loading and task manifests."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from experiment.common.task_registry import load_task_paths, preview_task_set, resolve_task_set
from experiment.webarena.utils.task_loader import parse_task, site_group


def test_parse_task_extracts_normalized_fields(tmp_path):
    config_path = tmp_path / "task.json"
    config_path.write_text(
        json.dumps(
            {
                "task_id": 17,
                "sites": ["reddit"],
                "intent": "find the title",
                "start_url": "http://example.com",
                "require_login": True,
                "eval": {"eval_types": ["string_match"]},
                "reference_action_sequence": {
                    "action_sequence": [
                        "page.click('foo')",
                        "page.stop('answer')",
                    ]
                },
            }
        ),
        encoding="utf-8",
    )

    task = parse_task(config_path)

    assert task.task_id == "17"
    assert task.sites == ["reddit"]
    assert task.intent == "find the title"
    assert task.start_url == "http://example.com"
    assert task.require_login is True
    assert task.eval_types == ["string_match"]
    assert task.action_set_tag == "playwright"
    assert task.reference_action_sequence[-1] == "page.stop('answer')"
    assert site_group(task) == "reddit"


def test_checked_in_webarena_debug_manifest_resolves_example_configs():
    repo_root = Path(__file__).resolve().parents[3]
    manifest_path = repo_root / "experiment" / "common" / "task_sets" / "webarena_debug.json"

    task_paths = load_task_paths(manifest_path)

    assert len(task_paths) == 4
    assert task_paths[0].endswith("webarena/config_files/examples/1.json")
    assert all(Path(task_path).is_file() for task_path in task_paths)


def test_checked_in_webarena_script_browser_smoke_manifest_resolves_non_login_example():
    repo_root = Path(__file__).resolve().parents[3]
    manifest_path = repo_root / "experiment" / "common" / "task_sets" / "webarena_script_browser_smoke.json"

    resolved = resolve_task_set(manifest_path)

    assert resolved["n_tasks"] == 1
    assert resolved["task_paths"][0].endswith("webarena/config_files/examples/3.json")


def test_resolve_task_set_group_sample_by_webarena_site(tmp_path):
    config_root = tmp_path / "config_files"
    config_root.mkdir(parents=True, exist_ok=True)

    for filename, site in (
        ("reddit_1.json", "reddit"),
        ("reddit_2.json", "reddit"),
        ("shopping_1.json", "shopping"),
        ("shopping_2.json", "shopping"),
    ):
        (config_root / filename).write_text(
            json.dumps(
                {
                    "task_id": filename,
                    "sites": [site],
                    "intent": filename,
                    "eval": {"eval_types": []},
                    "reference_action_sequence": {"action_sequence": []},
                }
            ),
            encoding="utf-8",
        )

    manifest_path = tmp_path / "webarena_group_manifest.json"
    manifest_path.write_text(
        json.dumps(
            {
                "env_name": "webarena",
                "task_set": "sampled",
                "root_dir": str(config_root),
                "selection": {
                    "mode": "group_sample",
                    "patterns": ["*.json"],
                    "group_by": "webarena_site",
                    "n_per_group": 1,
                    "seed": 13,
                },
            }
        ),
        encoding="utf-8",
    )

    resolved = resolve_task_set(manifest_path)

    assert resolved["n_tasks"] == 2
    selected_sites = [site_group(parse_task(task_path)) for task_path in resolved["task_paths"]]
    assert selected_sites == ["reddit", "shopping"]


def test_resolve_task_set_raises_for_missing_explicit_file(tmp_path):
    manifest_path = tmp_path / "missing_manifest.json"
    manifest_path.write_text(
        json.dumps(
            {
                "env_name": "webarena",
                "task_set": "missing",
                "root_dir": str(tmp_path),
                "selection": {
                    "mode": "explicit",
                    "items": ["nope.json"],
                },
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="missing files"):
        resolve_task_set(manifest_path)


def test_preview_task_set_reports_missing_explicit_file_without_raising(tmp_path):
    manifest_path = tmp_path / "missing_manifest.json"
    manifest_path.write_text(
        json.dumps(
            {
                "env_name": "webarena",
                "task_set": "missing",
                "root_dir": str(tmp_path),
                "selection": {
                    "mode": "explicit",
                    "items": ["nope.json"],
                },
            }
        ),
        encoding="utf-8",
    )

    resolved = preview_task_set(manifest_path)

    assert resolved["n_tasks"] == 1
    assert resolved["existing_task_paths"] == []
    assert len(resolved["missing_task_paths"]) == 1
