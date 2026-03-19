"""Shared runner logic for reference-backed WebArena baselines."""
from __future__ import annotations

import json
import re
import time
import uuid
from typing import Any, Dict, List, Optional

from experiment.common.openai_compatible_llm import chat_json


def estimate_text_tokens(value: Any) -> int:
    """Small deterministic token estimator for offline smoke runs."""
    if isinstance(value, (dict, list, tuple)):
        text = json.dumps(value, ensure_ascii=False, default=str)
    else:
        text = str(value or "")
    tokens = re.findall(r"[A-Za-z0-9_]+|[\u4e00-\u9fff]", text)
    return len(tokens)


class BaseWebArenaRunner:
    """Base class for WebArena reference-policy runners."""

    system_family = "unknown"

    def __init__(self, env, config: Dict[str, Any] | None = None):
        self.env = env
        self.config = config or {}

    def use_local_llm(self) -> bool:
        return bool(self.config.get("use_local_llm", False))

    def call_local_llm(self, *, system_prompt: str, user_prompt: str, max_tokens: int = 256) -> Dict[str, Any]:
        return chat_json(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            model=str(self.config.get("llm_model", "") or ""),
            base_url=str(self.config.get("llm_base_url", "") or ""),
            api_key=str(self.config.get("llm_api_key", "") or ""),
            timeout=float(self.config.get("llm_timeout", 60.0) or 60.0),
            temperature=float(self.config.get("llm_temperature", 0.0) or 0.0),
            max_tokens=max_tokens,
        )

    def build_turn(self, observation: Dict[str, Any], step_id: int) -> Dict[str, Any]:
        """Build the next turn decision for the current observation."""
        raise NotImplementedError

    def capture_runtime_state(
        self,
        *,
        episode_id: str,
        config_file: str,
        observation: Dict[str, Any],
        turn: Dict[str, Any],
        selected_action: str,
        fallback_used: bool,
        step_id: int,
        reward: float,
        step_info: Dict[str, Any],
    ) -> Optional[Dict[str, Any]]:
        """Return one captured state record for Experiment 2, or ``None``."""
        del episode_id, config_file, observation, turn, selected_action, fallback_used, step_id, reward, step_info
        return None

    def run_episode(
        self,
        *,
        config_file: str,
        max_steps: int = 30,
        episode_id: str = "",
        run_id: str = "",
        experiment_id: str = "",
        model_name: str = "",
        token_callback=None,
        task_set: str = "",
        seed: int = 0,
        capture_states: bool = False,
    ) -> Dict[str, Any]:
        """Run one WebArena task through the offline reference backend."""
        del token_callback  # not used in the reference backend yet
        if not episode_id:
            episode_id = str(uuid.uuid4())[:8]

        observation, info = self.env.reset(config_file)
        trajectory: List[Dict[str, Any]] = []
        episode_communication_trace: List[Dict[str, Any]] = []
        worker_input_tokens = 0
        worker_output_tokens = 0
        architect_input_tokens = 0
        architect_output_tokens = 0
        fallback_action_count = 0
        patch_error_count = 0
        stop_reason = "max_steps_reached"
        success = False
        latest_info = info
        captured_states: List[Dict[str, Any]] = []
        retrieval_precisions: List[float] = []
        context_fragment_counts: List[float] = []
        relevant_fragment_counts: List[float] = []
        irrelevant_fragment_counts: List[float] = []
        context_modes: List[str] = []

        for step_id in range(max_steps):
            observation_before = observation
            turn = self.build_turn(observation_before, step_id)
            if self.use_local_llm():
                time.sleep(self.config.get("step_sleep", 4.0))
            selected_action = str(turn.get("selected_action", "") or "").strip()
            fallback_used = False
            if not selected_action:
                selected_action = str(observation_before.get("next_reference_action", "") or "").strip()
                fallback_used = True
                fallback_action_count += 1

            worker_input_tokens += int(turn.get("worker_input_tokens", 0))
            worker_output_tokens += int(turn.get("worker_output_tokens", 0))
            architect_input_tokens += int(turn.get("architect_input_tokens", 0))
            architect_output_tokens += int(turn.get("architect_output_tokens", 0))

            next_observation, reward, done, step_info = self.env.step(selected_action)
            latest_info = step_info
            retrieval_precision = float(turn.get("retrieval_precision", 0.0) or 0.0)
            context_fragment_count = float(turn.get("context_fragment_count", 0.0) or 0.0)
            relevant_fragment_count = float(turn.get("relevant_fragment_count", 0.0) or 0.0)
            irrelevant_fragment_count = float(turn.get("irrelevant_fragment_count", 0.0) or 0.0)
            context_mode = str(turn.get("context_mode", "") or "")
            if context_fragment_count > 0:
                retrieval_precisions.append(retrieval_precision)
                context_fragment_counts.append(context_fragment_count)
                relevant_fragment_counts.append(relevant_fragment_count)
                irrelevant_fragment_counts.append(irrelevant_fragment_count)
            if context_mode:
                context_modes.append(context_mode)
            if capture_states:
                captured_state = self.capture_runtime_state(
                    episode_id=episode_id,
                    config_file=config_file,
                    observation=observation_before,
                    turn=turn,
                    selected_action=selected_action,
                    fallback_used=fallback_used,
                    step_id=step_id,
                    reward=reward,
                    step_info=step_info,
                )
                if captured_state is not None:
                    captured_states.append(captured_state)
            communication_trace = list(turn.get("communication_trace", []) or [])
            episode_communication_trace.extend(communication_trace)
            trajectory.append(
                {
                    "step_id": step_id,
                    "action": selected_action,
                    "reward": reward,
                    "done": done,
                    "fallback_used": fallback_used,
                    "expected_action": step_info.get("expected_action", ""),
                    "action_matched": step_info.get("action_matched", False),
                    "decision_reason": str(turn.get("decision_reason", "") or ""),
                    "communication_trace": communication_trace,
                    "planner_state": turn.get("planner_state", {}),
                    "context_mode": context_mode,
                    "retrieval_precision": retrieval_precision,
                    "context_fragment_count": context_fragment_count,
                    "relevant_fragment_count": relevant_fragment_count,
                    "irrelevant_fragment_count": irrelevant_fragment_count,
                }
            )
            observation = next_observation
            if done:
                stop_reason = str(step_info.get("stop_reason", "reference_completed") or "reference_completed")
                success = bool(step_info.get("success", False))
                break

        steps = len(trajectory)
        if not success and latest_info:
            success = bool(latest_info.get("success", False))

        mean_retrieval_precision = float(sum(retrieval_precisions) / len(retrieval_precisions)) if retrieval_precisions else 0.0
        mean_context_fragment_count = float(sum(context_fragment_counts) / len(context_fragment_counts)) if context_fragment_counts else 0.0
        mean_relevant_fragment_count = float(sum(relevant_fragment_counts) / len(relevant_fragment_counts)) if relevant_fragment_counts else 0.0
        mean_irrelevant_fragment_count = float(sum(irrelevant_fragment_counts) / len(irrelevant_fragment_counts)) if irrelevant_fragment_counts else 0.0
        context_mode = context_modes[0] if context_modes else ""

        return {
            "episode_id": episode_id,
            "run_id": run_id,
            "experiment_id": experiment_id,
            "model_name": model_name,
            "task_set": task_set,
            "seed": seed,
            "config_file": config_file,
            "task_id": observation.get("task_id", info.get("task_id", "")),
            "success": success,
            "goal_condition_rate": float(latest_info.get("progress_rate", 0.0)),
            "steps": steps,
            "stop_reason": stop_reason,
            "total_tokens": worker_input_tokens
            + worker_output_tokens
            + architect_input_tokens
            + architect_output_tokens,
            "worker_input_tokens": worker_input_tokens,
            "worker_output_tokens": worker_output_tokens,
            "architect_input_tokens": architect_input_tokens,
            "architect_output_tokens": architect_output_tokens,
            "fallback_action_count": fallback_action_count,
            "patch_error_count": patch_error_count,
            "retrieval_precision": mean_retrieval_precision,
            "context_fragment_count": mean_context_fragment_count,
            "relevant_fragment_count": mean_relevant_fragment_count,
            "irrelevant_fragment_count": mean_irrelevant_fragment_count,
            "trajectory": trajectory,
            "communication_trace": episode_communication_trace,
            "final_status": "success" if success else "incomplete",
            "workflow_final_status": "completed" if steps > 0 else "not_started",
            "metadata": {
                "sites": list(info.get("sites", [])),
                "intent": info.get("intent", ""),
                "execution_backend": self.config.get("execution_backend", "reference_oracle"),
                "workflow_mode": self.config.get("workflow_mode", "planner_action"),
                "context_mode": context_mode,
                "reference_action_count": int(latest_info.get("reference_action_count", 0)),
            },
            "captured_states": captured_states,
        }
