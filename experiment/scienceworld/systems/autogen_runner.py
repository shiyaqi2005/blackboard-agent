"""Natural-language AutoGen-style ScienceWorld runner using the reference backend."""
from __future__ import annotations

import json
from typing import Any, Dict, List

from experiment.scienceworld.systems.base import BaseScienceWorldRunner, estimate_text_tokens


class ScienceWorldAutoGenRunner(BaseScienceWorldRunner):
    """Reference-policy AutoGen baseline for ScienceWorld smoke experiments."""

    system_family = "autogen"

    def _llm_decide_action(self, *, observation: Dict[str, Any], step_id: int) -> Dict[str, Any]:
        system_prompt = (
            "You are an AutoGen-style ScienceWorld planner/executor team. "
            "Choose exactly one next action from possible_actions. "
            "Return JSON only with keys action and reason."
        )
        visible_context = {
            "task_name": observation.get("task_name", ""),
            "task_desc": observation.get("task_desc", ""),
            "observation": observation.get("observation", ""),
            "inventory": observation.get("inventory", ""),
            "look": observation.get("look", ""),
            "history": list(observation.get("history", []) or []),
            "possible_actions": list(observation.get("possible_actions", []) or []),
            "step_id": step_id,
        }
        response = self.call_local_llm(
            system_prompt=system_prompt,
            user_prompt=json.dumps(visible_context, ensure_ascii=False),
            max_tokens=256,
        )
        payload = response["payload"]
        return {
            "selected_action": str(payload.get("action", "") or "").strip(),
            "decision_reason": str(payload.get("reason", "") or "Local ScienceWorld model selected the next action."),
            "usage": dict(response.get("usage", {})),
        }

    def build_turn(self, observation: Dict[str, Any], step_id: int) -> Dict[str, Any]:
        workflow_mode = self.config.get("workflow_mode", "planner_action")
        next_action = str(observation.get("next_reference_action", "") or "")
        possible_actions = [str(action) for action in list(observation.get("possible_actions", []) or [])]
        planner_message = (
            f"SUBTASK: Advance ScienceWorld task {observation.get('task_name', '')}.\n"
            f"TASK_DESC: {observation.get('task_desc', '')}\n"
            f"NEXT_ACTION: {next_action}\n"
            "RATIONALE: Follow the remaining gold trajectory."
        )
        executor_message = (
            f"ACTION: {next_action}\n"
            "REASON: Execute the planner's proposed gold action."
        )
        communication_trace: List[Dict[str, Any]] = []
        selected_action = next_action
        decision_reason = "AutoGen planner/executor pair relayed the next reference action in natural language."

        worker_input_tokens = estimate_text_tokens(observation)
        worker_output_tokens = estimate_text_tokens(planner_message) + estimate_text_tokens(executor_message)

        if self.use_local_llm():
            try:
                llm_result = self._llm_decide_action(observation=observation, step_id=step_id)
                candidate_action = str(llm_result["selected_action"] or "").strip()
                if candidate_action and possible_actions and candidate_action not in possible_actions:
                    selected_action = ""
                    decision_reason = f"Model proposed an invalid action outside possible_actions: {candidate_action}"
                else:
                    selected_action = candidate_action
                    decision_reason = str(llm_result["decision_reason"] or decision_reason)
                planner_message = (
                    f"SUBTASK: Advance ScienceWorld task {observation.get('task_name', '')}.\n"
                    f"TASK_DESC: {observation.get('task_desc', '')}\n"
                    f"CHOSEN_ACTION: {selected_action or '<fallback>'}\n"
                    f"RATIONALE: {decision_reason}"
                )
                executor_message = (
                    f"ACTION: {selected_action or next_action}\n"
                    f"REASON: {decision_reason}"
                )
                usage = llm_result.get("usage", {})
                worker_input_tokens = int(usage.get("prompt_tokens", worker_input_tokens) or worker_input_tokens)
                worker_output_tokens = int(usage.get("completion_tokens", worker_output_tokens) or worker_output_tokens)
            except Exception as exc:
                selected_action = ""
                decision_reason = f"Local ScienceWorld model call failed: {exc}"
                planner_message = (
                    f"SUBTASK: Advance ScienceWorld task {observation.get('task_name', '')}.\n"
                    f"TASK_DESC: {observation.get('task_desc', '')}\n"
                    f"CHOSEN_ACTION: <fallback>\n"
                    f"RATIONALE: {decision_reason}"
                )
                executor_message = (
                    f"ACTION: {next_action}\n"
                    f"REASON: {decision_reason}"
                )

        if workflow_mode == "single_action":
            communication_trace.append(
                {
                    "source": "executor",
                    "channel": "natural_language",
                    "content": executor_message,
                }
            )
        else:
            communication_trace.extend(
                [
                    {
                        "source": "planner",
                        "channel": "natural_language",
                        "content": planner_message,
                    },
                    {
                        "source": "executor",
                        "channel": "natural_language",
                        "content": executor_message,
                    },
                ]
            )
            worker_input_tokens += estimate_text_tokens(planner_message)

        return {
            "selected_action": selected_action,
            "decision_reason": decision_reason,
            "planner_state": {"planner_message": planner_message},
            "communication_trace": communication_trace,
            "architect_input_tokens": 0,
            "architect_output_tokens": 0,
            "worker_input_tokens": worker_input_tokens,
            "worker_output_tokens": worker_output_tokens,
        }
