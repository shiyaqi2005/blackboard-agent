"""Tests for ScienceWorld reference-policy system runners."""
from __future__ import annotations

import json

from experiment.scienceworld.core.reference_env import ScienceWorldReferenceEnv
from experiment.scienceworld.systems.autogen_runner import ScienceWorldAutoGenRunner
from experiment.scienceworld.systems.blackboard_runner import ScienceWorldBlackboardRunner
from experiment.scienceworld.systems.langgraph_runner import ScienceWorldLangGraphRunner


class _FakeScienceWorldEnv:
    def __init__(self):
        self.loaded = None
        self.actions = []
        self.reference_actions = ["open door", "look around"]

    def load(self, task_name, variation_idx, simplification_str, generateGoldPath=False):
        self.loaded = (task_name, variation_idx, simplification_str, generateGoldPath)

    def reset(self):
        return "You are in a room.", {
            "taskDesc": "boil water",
            "inv": "empty",
            "look": "room",
            "score": 0,
            "reward": 0,
            "moves": 0,
        }

    def get_gold_action_sequence(self):
        return list(self.reference_actions)

    def get_possible_actions(self):
        return ["open door", "look around"]

    def step(self, action_text):
        self.actions.append(action_text)
        done = len(self.actions) >= 2
        score = 100 if done else 0
        return (
            f"obs after {action_text}",
            1 if action_text else 0,
            done,
            {
                "taskDesc": "boil water",
                "inv": "empty",
                "look": "room",
                "score": score,
                "reward": 1,
                "moves": len(self.actions),
            },
        )

    def close(self):
        return None


def _write_config(path) -> None:
    path.write_text(
        json.dumps(
            {
                "task_id": "1-1",
                "task_name": "1-1",
                "variation_idx": 0,
                "simplification_str": "easy",
                "split": "debug",
                "max_episode_steps": 50,
            }
        ),
        encoding="utf-8",
    )


def test_blackboard_runner_episode_has_structured_trace(tmp_path):
    config_path = tmp_path / "task.json"
    _write_config(config_path)
    runner = ScienceWorldBlackboardRunner(
        ScienceWorldReferenceEnv(env_factory=_FakeScienceWorldEnv),
        config={"workflow_mode": "planner_action", "execution_backend": "reference_oracle"},
    )

    result = runner.run_episode(config_file=str(config_path), model_name="reference_model")

    assert result["success"] is True
    assert result["steps"] == 2
    assert result["trajectory"][0]["communication_trace"][0]["source"] == "architect"
    assert result["worker_input_tokens"] > 0


def test_langgraph_runner_episode_has_text_trace(tmp_path):
    config_path = tmp_path / "task.json"
    _write_config(config_path)
    runner = ScienceWorldLangGraphRunner(
        ScienceWorldReferenceEnv(env_factory=_FakeScienceWorldEnv),
        config={"workflow_mode": "planner_action", "execution_backend": "reference_oracle"},
    )

    result = runner.run_episode(config_file=str(config_path), model_name="reference_model")

    assert result["success"] is True
    assert result["trajectory"][0]["communication_trace"][0]["source"] == "planner_node"


def test_autogen_runner_episode_has_natural_language_trace(tmp_path):
    config_path = tmp_path / "task.json"
    _write_config(config_path)
    runner = ScienceWorldAutoGenRunner(
        ScienceWorldReferenceEnv(env_factory=_FakeScienceWorldEnv),
        config={"workflow_mode": "planner_action", "execution_backend": "reference_oracle"},
    )

    result = runner.run_episode(config_file=str(config_path), model_name="reference_model")

    assert result["success"] is True
    assert result["trajectory"][0]["communication_trace"][0]["source"] == "planner"
    assert result["trajectory"][0]["communication_trace"][1]["source"] == "executor"
