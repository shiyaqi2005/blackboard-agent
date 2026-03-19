"""Reference-backed WebArena environment used for offline experiment plumbing."""
from __future__ import annotations

import re
from typing import Any, Dict, List, Tuple

from experiment.webarena.utils.task_loader import WebArenaTask, parse_task


_STOP_ANSWER_PATTERN = re.compile(r"page\.stop\((?P<quote>['\"])(?P<answer>.*?)(?P=quote)\)")


def extract_stop_answer(action_text: str) -> str:
    """Extract the answer payload from a WebArena stop action string."""
    match = _STOP_ANSWER_PATTERN.search(action_text.strip())
    if not match:
        return ""
    return match.group("answer")


class WebArenaReferenceEnv:
    """Offline environment that validates actions against reference trajectories."""

    def __init__(self) -> None:
        self.current_task: WebArenaTask | None = None
        self.reference_actions: List[str] = []
        self.history: List[str] = []
        self.step_index = 0
        self.match_count = 0
        self.all_matched = True

    def reset(self, config_file: str) -> Tuple[Dict[str, Any], Dict[str, Any]]:
        """Load one WebArena task config and return the initial observation."""
        task = parse_task(config_file)
        self.current_task = task
        self.reference_actions = list(task.reference_action_sequence)
        self.history = []
        self.step_index = 0
        self.match_count = 0
        self.all_matched = True
        observation = self._build_observation()
        info = self._build_info(
            action_matched=True,
            selected_action="",
            expected_action=self.current_expected_action,
            stop_reason="running",
            done=False,
        )
        return observation, info

    def step(self, action_text: str) -> Tuple[Dict[str, Any], float, bool, Dict[str, Any]]:
        """Advance the reference environment by one action string."""
        expected_action = self.current_expected_action
        action_matched = bool(expected_action) and action_text.strip() == expected_action
        if action_matched:
            self.match_count += 1
        else:
            self.all_matched = False
        self.history.append(action_text)
        self.step_index += 1
        done = self.step_index >= len(self.reference_actions)
        success = done and self.all_matched and bool(self.reference_actions)
        stop_reason = "reference_completed" if done else "running"
        observation = self._build_observation()
        info = self._build_info(
            action_matched=action_matched,
            selected_action=action_text,
            expected_action=expected_action,
            stop_reason=stop_reason,
            done=done,
        )
        info["success"] = success
        reward = 1.0 if action_matched else 0.0
        return observation, reward, done, info

    @property
    def current_expected_action(self) -> str:
        if 0 <= self.step_index < len(self.reference_actions):
            return self.reference_actions[self.step_index]
        return ""

    def close(self) -> None:
        """No-op close for API parity with real environments."""
        self.current_task = None

    def _build_observation(self) -> Dict[str, Any]:
        task = self.current_task
        if task is None:
            return {}
        return {
            "config_file": task.config_path,
            "task_id": task.task_id,
            "sites": list(task.sites),
            "intent": task.intent,
            "start_url": task.start_url,
            "require_login": task.require_login,
            "eval_types": list(task.eval_types),
            "history": list(self.history),
            "step_index": self.step_index,
            "next_reference_action": self.current_expected_action,
            "remaining_reference_actions": list(self.reference_actions[self.step_index :]),
        }

    def _build_info(
        self,
        *,
        action_matched: bool,
        selected_action: str,
        expected_action: str,
        stop_reason: str,
        done: bool,
    ) -> Dict[str, Any]:
        task = self.current_task
        if task is None:
            return {}
        total_actions = max(len(self.reference_actions), 1)
        return {
            "config_file": task.config_path,
            "task_id": task.task_id,
            "sites": list(task.sites),
            "intent": task.intent,
            "expected_action": expected_action,
            "selected_action": selected_action,
            "action_matched": action_matched,
            "matched_action_count": self.match_count,
            "reference_action_count": len(self.reference_actions),
            "progress_rate": float(self.match_count / total_actions) if self.reference_actions else 0.0,
            "done": done,
            "stop_reason": stop_reason,
            "stop_answer": extract_stop_answer(selected_action) if selected_action else "",
            "reference_stop_answer": extract_stop_answer(self.reference_actions[-1]) if self.reference_actions else "",
        }
