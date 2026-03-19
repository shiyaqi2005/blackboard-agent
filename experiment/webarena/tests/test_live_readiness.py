"""Tests for WebArena live readiness checks."""
from __future__ import annotations

import json
from types import ModuleType
import sys

from experiment.webarena.utils.live_readiness import collect_script_browser_readiness


def test_collect_script_browser_readiness_reports_missing_prereqs_for_login_tasks(monkeypatch, tmp_path):
    config_path = tmp_path / "login_task.json"
    config_path.write_text(
        json.dumps(
            {
                "task_id": 1,
                "sites": ["reddit"],
                "intent": "login task",
                "require_login": True,
                "storage_state": "./.auth/reddit_state.json",
                "eval": {"eval_types": []},
                "reference_action_sequence": {"action_sequence": []},
            }
        ),
        encoding="utf-8",
    )

    for name in ["SHOPPING", "SHOPPING_ADMIN", "REDDIT", "GITLAB", "MAP", "WIKIPEDIA", "HOMEPAGE", "OPENAI_API_KEY"]:
        monkeypatch.delenv(name, raising=False)

    report = collect_script_browser_readiness(
        config_files=[str(config_path)],
        systems=["blackboard", "official_prompt"],
        official_provider="openai",
        official_model_endpoint="",
    )

    assert report["config_count"] == 1
    assert report["login_required_count"] == 1
    assert "SHOPPING" in report["missing_site_envs"]
    assert "OPENAI_API_KEY" in report["missing_provider_requirements"]


def test_collect_script_browser_readiness_skips_site_envs_for_non_login_tasks(monkeypatch, tmp_path):
    config_path = tmp_path / "non_login_task.json"
    config_path.write_text(
        json.dumps(
            {
                "task_id": 2,
                "sites": ["misc"],
                "intent": "public task",
                "require_login": False,
                "eval": {"eval_types": []},
                "reference_action_sequence": {"action_sequence": []},
            }
        ),
        encoding="utf-8",
    )

    for name in ["SHOPPING", "SHOPPING_ADMIN", "REDDIT", "GITLAB", "MAP", "WIKIPEDIA", "HOMEPAGE"]:
        monkeypatch.delenv(name, raising=False)

    report = collect_script_browser_readiness(
        config_files=[str(config_path)],
        systems=["blackboard"],
    )

    assert report["config_count"] == 1
    assert report["login_required_count"] == 0
    assert report["missing_site_envs"] == []
    assert "SHOPPING" in report["config_generation_missing_site_envs"]


def test_collect_script_browser_readiness_reports_missing_config_files(monkeypatch):
    for name in ["SHOPPING", "SHOPPING_ADMIN", "REDDIT", "GITLAB", "MAP", "WIKIPEDIA", "HOMEPAGE"]:
        monkeypatch.delenv(name, raising=False)

    report = collect_script_browser_readiness(
        config_files=["/tmp/does_not_exist.json"],
        systems=["blackboard"],
    )

    assert report["missing_config_count"] == 1
    assert report["missing_config_files"] == ["/tmp/does_not_exist.json"]
    assert report["missing_site_envs"] == []


def test_collect_script_browser_readiness_reports_runtime_import_errors(monkeypatch, tmp_path):
    config_path = tmp_path / "task.json"
    config_path.write_text(
        json.dumps(
            {
                "task_id": 3,
                "sites": ["misc"],
                "intent": "public task",
                "require_login": False,
                "eval": {"eval_types": ["string_match"]},
                "reference_action_sequence": {"action_sequence": []},
            }
        ),
        encoding="utf-8",
    )

    fake_script_env = ModuleType("experiment.webarena.core.script_env")
    fake_script_env._load_runtime = lambda: (_ for _ in ()).throw(RuntimeError("script runtime broken"))
    fake_official_runtime = ModuleType("experiment.webarena.utils.official_agent_runtime")
    fake_official_runtime.load_official_agent_runtime = lambda: (_ for _ in ()).throw(RuntimeError("official runtime broken"))
    monkeypatch.setitem(sys.modules, "experiment.webarena.core.script_env", fake_script_env)
    monkeypatch.setitem(sys.modules, "experiment.webarena.utils.official_agent_runtime", fake_official_runtime)

    from importlib import reload
    from experiment.webarena.utils import live_readiness as module

    reload(module)
    try:
        report = module.collect_script_browser_readiness(
            config_files=[str(config_path)],
            systems=["official_prompt"],
            official_provider="openai",
            official_model_endpoint="",
        )
    finally:
        sys.modules.pop("experiment.webarena.core.script_env", None)
        sys.modules.pop("experiment.webarena.utils.official_agent_runtime", None)
        reload(module)

    assert report["script_runtime_import_error"] == "script runtime broken"
    assert report["official_agent_import_error"] == "official runtime broken"
