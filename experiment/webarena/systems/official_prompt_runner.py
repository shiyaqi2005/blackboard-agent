"""Runner that executes the official WebArena PromptAgent / TeacherForcingAgent."""
from __future__ import annotations

import argparse
from typing import Any, Dict, List

from experiment.webarena.systems.base import estimate_text_tokens
from experiment.webarena.utils.official_agent_runtime import ensure_prompt_jsons, load_official_agent_runtime
from experiment.webarena.utils.task_loader import parse_task


class WebArenaOfficialPromptRunner:
    """Execute the official WebArena agent loop inside the experiment scaffold."""

    system_family = "webarena_prompt"

    def __init__(
        self,
        env,
        config: Dict[str, Any] | None = None,
        runtime: Dict[str, Any] | None = None,
    ):
        self.env = env
        self.config = config or {}
        self.runtime = runtime or load_official_agent_runtime()

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
    ) -> Dict[str, Any]:
        """Run one WebArena task with the official prompt or teacher-forcing agent."""
        del token_callback  # official agent loop does not currently expose this callback
        task = parse_task(config_file)
        expected_action_set = str(self.config.get("action_set_tag", "id_accessibility_tree") or "id_accessibility_tree")
        if task.action_set_tag != expected_action_set:
            raise ValueError(
                f"official_prompt requires task action_set_tag={expected_action_set}, got {task.action_set_tag} for {config_file}"
            )
        observation, info = self.env.reset(config_file)
        raw_observation = dict(observation.get("raw_observation", {}))
        raw_info = dict(observation.get("raw_info", {}))
        trajectory: List[Dict[str, Any]] = [{"observation": raw_observation, "info": raw_info}]
        meta_data = {"action_history": ["None"]}

        agent = self._build_agent()
        agent.reset(config_file)
        prompt_agent_type = self.runtime["PromptAgent"]
        get_action_description = self.runtime["get_action_description"]
        action_types = self.runtime["ActionTypes"]

        worker_input_tokens = 0
        worker_output_tokens = 0
        communication_trace: List[Dict[str, Any]] = []
        episode_steps: List[Dict[str, Any]] = []
        stop_reason = "max_steps_reached"
        success = False
        goal_condition_rate = 0.0

        for step_id in range(max_steps):
            action = agent.next_action(trajectory, task.intent, meta_data=meta_data)
            prompt_constructor = agent.prompt_constructor if isinstance(agent, prompt_agent_type) else None
            action_description = get_action_description(
                action,
                raw_info.get("observation_metadata", {}),
                task.action_set_tag,
                prompt_constructor,
            )
            meta_data["action_history"].append(action_description)
            serialized_action = self._serialize_action(
                action=action,
                action_description=action_description,
                action_set_tag=task.action_set_tag,
                action_types=action_types,
            )

            prediction_text = str(action.get("raw_prediction", "") or serialized_action)
            worker_input_tokens += estimate_text_tokens(task.intent) + estimate_text_tokens(raw_observation)
            worker_output_tokens += estimate_text_tokens(prediction_text)
            communication_trace.append(
                {
                    "source": self.config.get("agent_type", "prompt_agent"),
                    "channel": "official_prompt",
                    "content": prediction_text,
                }
            )

            trajectory.append(action)
            next_observation, reward, done, step_info = self.env.step(serialized_action)
            episode_steps.append(
                {
                    "step_id": step_id,
                    "action": serialized_action,
                    "reward": reward,
                    "done": done,
                    "decision_reason": "Official WebArena agent prediction.",
                    "raw_prediction": prediction_text,
                }
            )
            goal_condition_rate = float(step_info.get("progress_rate", goal_condition_rate))

            if done:
                stop_reason = str(step_info.get("stop_reason", "official_evaluator") or "official_evaluator")
                success = bool(step_info.get("success", False))
                break

            raw_observation = dict(next_observation.get("raw_observation", {}))
            raw_info = dict(next_observation.get("raw_info", {}))
            trajectory.append({"observation": raw_observation, "info": raw_info})

        return {
            "episode_id": episode_id,
            "run_id": run_id,
            "experiment_id": experiment_id,
            "model_name": model_name,
            "task_set": task_set,
            "seed": seed,
            "config_file": config_file,
            "task_id": task.task_id,
            "success": success,
            "goal_condition_rate": goal_condition_rate,
            "steps": len(episode_steps),
            "stop_reason": stop_reason,
            "total_tokens": worker_input_tokens + worker_output_tokens,
            "worker_input_tokens": worker_input_tokens,
            "worker_output_tokens": worker_output_tokens,
            "architect_input_tokens": 0,
            "architect_output_tokens": 0,
            "fallback_action_count": 0,
            "patch_error_count": 0,
            "trajectory": episode_steps,
            "communication_trace": communication_trace,
            "final_status": "success" if success else "incomplete",
            "workflow_final_status": "completed" if episode_steps else "not_started",
            "metadata": {
                "sites": list(task.sites),
                "intent": task.intent,
                "action_set_tag": task.action_set_tag,
                "instruction_path": self.config.get("instruction_path", ""),
                "agent_type": self.config.get("agent_type", "prompt"),
                "execution_backend": self.config.get("execution_backend", "script_browser"),
            },
        }

    def _build_agent(self):
        construct_agent = self.runtime["construct_agent"]
        args = argparse.Namespace(
            agent_type=self.config.get("agent_type", "prompt"),
            action_set_tag=self.config.get("action_set_tag", "id_accessibility_tree"),
            instruction_path=self._instruction_path(),
            provider=self.config.get("provider", "openai"),
            model=self.config.get("model", ""),
            mode=self.config.get("mode", "chat"),
            temperature=self.config.get("temperature", 0.0),
            top_p=self.config.get("top_p", 0.9),
            context_length=self.config.get("context_length", 0),
            max_tokens=self.config.get("max_tokens", 384),
            stop_token=self.config.get("stop_token"),
            max_retry=self.config.get("max_retry", 1),
            max_obs_length=self.config.get("max_obs_length", 1920),
            model_endpoint=self.config.get("model_endpoint", ""),
        )
        return construct_agent(args)

    def _instruction_path(self) -> str:
        configured = str(self.config.get("instruction_path", "") or "").strip()
        if configured:
            return configured
        json_dir = ensure_prompt_jsons()
        return str(json_dir / "p_cot_id_actree_2s.json")

    @staticmethod
    def _serialize_action(
        *,
        action: Dict[str, Any],
        action_description: str,
        action_set_tag: str,
        action_types,
    ) -> str:
        action_type = int(action.get("action_type", action_types.NONE))
        if action_type == int(action_types.STOP):
            answer = str(action.get("answer", "") or "")
            if action_set_tag == "playwright":
                return f"page.stop({answer!r})"
            return f"stop [{answer}]"
        if action_set_tag == "playwright":
            return str(action.get("pw_code", "") or "")
        return action_description
