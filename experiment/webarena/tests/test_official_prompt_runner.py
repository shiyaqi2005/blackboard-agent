"""Tests for the official WebArena prompt-agent runner."""
from __future__ import annotations

import json
from enum import IntEnum

import pytest

from experiment.webarena.systems.official_prompt_runner import WebArenaOfficialPromptRunner


class _FakeActionTypes(IntEnum):
    NONE = 0
    STOP = 17
    CLICK = 2


class _FakePromptAgentBase:
    pass


class _FakePromptAgent(_FakePromptAgentBase):
    def __init__(self):
        self.prompt_constructor = object()
        self._actions = [
            {
                "action_type": _FakeActionTypes.CLICK,
                "pw_code": "",
                "answer": "",
                "raw_prediction": "click [15]",
            },
            {
                "action_type": _FakeActionTypes.STOP,
                "pw_code": "",
                "answer": "done",
                "raw_prediction": "stop [done]",
            },
        ]

    def reset(self, config_file: str) -> None:
        del config_file

    def next_action(self, trajectory, intent, meta_data):
        del trajectory, intent, meta_data
        return self._actions.pop(0)


class _FakeScriptEnv:
    def __init__(self):
        self.calls = []

    def reset(self, config_file: str):
        return (
            {
                "raw_observation": {"text": "Initial observation"},
                "raw_info": {
                    "page": type("Page", (), {"url": "http://example.com"})(),
                    "observation_metadata": {},
                },
            },
            {},
        )

    def step(self, action_text: str):
        self.calls.append(action_text)
        if action_text.startswith("stop ["):
            return (
                {"raw_observation": {}, "raw_info": {}},
                1.0,
                True,
                {"progress_rate": 1.0, "success": True, "stop_reason": "official_evaluator"},
            )
        return (
            {
                "raw_observation": {"text": "After click"},
                "raw_info": {
                    "page": type("Page", (), {"url": "http://example.com/after"})(),
                    "observation_metadata": {},
                },
            },
            1.0,
            False,
            {},
        )

    def close(self):
        return None


def _write_config(path) -> None:
    path.write_text(
        json.dumps(
            {
                "task_id": 99,
                "sites": ["reddit"],
                "intent": "finish the task",
                "start_url": "http://example.com",
                "require_login": False,
                "eval": {"eval_types": ["string_match"]},
                "reference_action_sequence": {
                    "action_set_tag": "id_accessibility_tree",
                    "action_sequence": ["click [15]", "stop [done]"],
                },
            }
        ),
        encoding="utf-8",
    )


def test_official_prompt_runner_executes_fake_agent_loop(tmp_path):
    config_path = tmp_path / "task.json"
    _write_config(config_path)

    runtime = {
        "PromptAgent": _FakePromptAgentBase,
        "construct_agent": lambda args: _FakePromptAgent(),
        "ActionTypes": _FakeActionTypes,
        "get_action_description": lambda action, observation_metadata, action_set_tag, prompt_constructor: (
            action.get("raw_prediction", "")
        ),
    }
    runner = WebArenaOfficialPromptRunner(
        _FakeScriptEnv(),
        config={
            "agent_type": "prompt",
            "instruction_path": "/tmp/fake_instruction.json",
            "provider": "openai",
            "model": "fake-model",
            "mode": "chat",
            "action_set_tag": "id_accessibility_tree",
            "execution_backend": "script_browser",
        },
        runtime=runtime,
    )

    result = runner.run_episode(
        config_file=str(config_path),
        run_id="run1",
        experiment_id="official_prompt",
        model_name="fake-model",
        task_set="debug",
        seed=42,
    )

    assert result["success"] is True
    assert result["steps"] == 2
    assert result["stop_reason"] == "official_evaluator"
    assert result["communication_trace"][0]["source"] == "prompt"
    assert result["metadata"]["agent_type"] == "prompt"


def test_official_prompt_runner_rejects_playwright_tasks(tmp_path):
    config_path = tmp_path / "playwright_task.json"
    config_path.write_text(
        json.dumps(
            {
                "task_id": 100,
                "sites": ["misc"],
                "intent": "finish the task",
                "start_url": "http://example.com",
                "require_login": False,
                "eval": {"eval_types": ["string_match"]},
                "reference_action_sequence": {
                    "action_set_tag": "playwright",
                    "action_sequence": ["page.stop('done')"],
                },
            }
        ),
        encoding="utf-8",
    )

    runner = WebArenaOfficialPromptRunner(
        _FakeScriptEnv(),
        config={
            "agent_type": "prompt",
            "instruction_path": "/tmp/fake_instruction.json",
            "provider": "openai",
            "model": "fake-model",
            "mode": "chat",
            "action_set_tag": "id_accessibility_tree",
            "execution_backend": "script_browser",
        },
        runtime={
            "PromptAgent": _FakePromptAgentBase,
            "construct_agent": lambda args: _FakePromptAgent(),
            "ActionTypes": _FakeActionTypes,
            "get_action_description": lambda action, observation_metadata, action_set_tag, prompt_constructor: "",
        },
    )

    with pytest.raises(ValueError, match="official_prompt requires task action_set_tag=id_accessibility_tree"):
        runner.run_episode(config_file=str(config_path))
