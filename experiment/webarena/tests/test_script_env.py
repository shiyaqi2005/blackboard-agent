"""Tests for the ScriptBrowserEnv-backed WebArena wrapper using a fake runtime."""
from __future__ import annotations

import json
from enum import IntEnum
from pathlib import Path
from types import SimpleNamespace

from experiment.webarena.core import script_env as script_env_module
from experiment.webarena.core.script_env import WebArenaScriptEnv


class _FakeActionTypes(IntEnum):
    NONE = 0
    STOP = 17
    CLICK = 2


class _FakeScriptBrowserEnv:
    def __init__(self, **kwargs):
        self.kwargs = kwargs
        self.page = SimpleNamespace(url="http://example.com/start")

    def reset(self, *, options=None):
        del options
        self.page = SimpleNamespace(url="http://example.com/start")
        return {"text": "Initial page"}, {"page": self.page, "fail_error": "", "observation_metadata": {}}

    def step(self, action):
        if action["action_type"] == _FakeActionTypes.CLICK:
            self.page = SimpleNamespace(url="http://example.com/after-click")
        return (
            {"text": "After step"},
            1.0,
            False,
            False,
            {"page": self.page, "fail_error": "", "observation_metadata": {}},
        )

    def get_page_client(self, page):
        return SimpleNamespace(page=page)

    def close(self):
        return None


def _fake_create_playwright_action(action_text: str):
    if action_text.startswith("page.stop("):
        return {"action_type": _FakeActionTypes.STOP, "answer": "done", "raw_prediction": action_text}
    return {"action_type": _FakeActionTypes.CLICK, "raw_prediction": action_text}


def _fake_create_id_based_action(action_text: str):
    return {"action_type": _FakeActionTypes.CLICK, "raw_prediction": action_text}


def _fake_evaluator_router(config_file):
    def _evaluate(*, trajectory, config_file, page, client):
        del config_file, page, client
        last_action = trajectory[-1]
        return 1.0 if last_action.get("answer", "") == "done" else 0.0

    return _evaluate


def _write_config(path) -> None:
    path.write_text(
        json.dumps(
            {
                "task_id": 11,
                "sites": ["reddit"],
                "intent": "finish the task",
                "start_url": "http://example.com/start",
                "require_login": False,
                "eval": {"eval_types": ["string_match"]},
                "reference_action_sequence": {
                    "action_set_tag": "playwright",
                    "action_sequence": [
                        "page.get_by_role('link', name='Forums').click()",
                        "page.stop('done')",
                    ],
                },
            }
        ),
        encoding="utf-8",
    )


def _write_login_config(path) -> None:
    path.write_text(
        json.dumps(
            {
                "task_id": 12,
                "sites": ["reddit"],
                "intent": "finish the login task",
                "start_url": "http://example.com/start",
                "require_login": True,
                "storage_state": "./.auth/reddit_state.json",
                "eval": {"eval_types": ["string_match"]},
                "reference_action_sequence": {
                    "action_set_tag": "playwright",
                    "action_sequence": [
                        "page.get_by_role('link', name='Forums').click()",
                        "page.stop('done')",
                    ],
                },
            }
        ),
        encoding="utf-8",
    )


def test_script_env_reset_and_step_with_fake_runtime(tmp_path):
    config_path = tmp_path / "task.json"
    _write_config(config_path)
    runtime = {
        "ScriptBrowserEnv": _FakeScriptBrowserEnv,
        "create_playwright_action": _fake_create_playwright_action,
        "create_id_based_action": _fake_create_id_based_action,
        "ActionTypes": _FakeActionTypes,
        "StateInfo": dict,
        "evaluator_router": _fake_evaluator_router,
    }
    env = WebArenaScriptEnv(runtime=runtime)

    observation, info = env.reset(str(config_path))
    assert observation["action_set_tag"] == "playwright"
    assert info["expected_action"].startswith("page.get_by_role")

    observation, reward, done, info = env.step("page.get_by_role('link', name='Forums').click()")
    assert reward == 1.0
    assert done is False
    assert info["page_url"] == "http://example.com/after-click"
    assert observation["next_reference_action"] == "page.stop('done')"

    observation, reward, done, info = env.step("page.stop('done')")
    assert done is True
    assert reward == 1.0
    assert info["success"] is True
    assert info["stop_reason"] == "official_evaluator"


def test_script_env_refreshes_storage_state_via_runtime_helpers(tmp_path):
    config_path = tmp_path / "login_task.json"
    _write_login_config(config_path)

    def _fake_get_site_comb_from_filepath(file_path: str):
        assert file_path == "reddit_state.json"
        return ["reddit"]

    def _fake_renew_comb(site_comb, auth_folder: str):
        assert site_comb == ["reddit"]
        auth_path = Path(auth_folder) / "reddit_state.json"
        auth_path.write_text("{}", encoding="utf-8")

    runtime = {
        "ScriptBrowserEnv": _FakeScriptBrowserEnv,
        "create_playwright_action": _fake_create_playwright_action,
        "create_id_based_action": _fake_create_id_based_action,
        "get_site_comb_from_filepath": _fake_get_site_comb_from_filepath,
        "renew_comb": _fake_renew_comb,
        "ActionTypes": _FakeActionTypes,
        "StateInfo": dict,
        "evaluator_router": _fake_evaluator_router,
    }
    env = WebArenaScriptEnv(runtime=runtime)

    observation, _ = env.reset(str(config_path))

    assert observation["config_file"] != str(config_path)
    refreshed_config = json.loads(Path(observation["config_file"]).read_text(encoding="utf-8"))
    assert refreshed_config["storage_state"].endswith("reddit_state.json")


def test_script_env_normalizes_legacy_reference_answers(tmp_path, monkeypatch):
    config_path = tmp_path / "legacy_task.json"
    config_path.write_text(
        json.dumps(
            {
                "task_id": 13,
                "sites": ["misc"],
                "intent": "answer the question",
                "start_url": "http://example.com/start",
                "require_login": False,
                "eval": {
                    "eval_types": ["string_match"],
                    "reference_answers": ["Wilson and Reader"],
                },
                "reference_action_sequence": {
                    "action_set_tag": "playwright",
                    "action_sequence": ["page.stop('Wilson and Reader')"],
                },
            }
        ),
        encoding="utf-8",
    )

    runtime = {
        "ScriptBrowserEnv": _FakeScriptBrowserEnv,
        "create_playwright_action": _fake_create_playwright_action,
        "create_id_based_action": _fake_create_id_based_action,
        "ActionTypes": _FakeActionTypes,
    }
    monkeypatch.setattr(script_env_module, "_load_evaluator_router", lambda: lambda config_file: _fake_evaluator_router(config_file))
    env = WebArenaScriptEnv(runtime=runtime)

    observation, _ = env.reset(str(config_path))

    normalized = json.loads(Path(observation["config_file"]).read_text(encoding="utf-8"))
    assert normalized["eval"]["reference_answers"] == {"exact_match": "Wilson and Reader"}
