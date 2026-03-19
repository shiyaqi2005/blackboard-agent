"""Natural-language AutoGen-style WebArena runner using the reference backend."""
from __future__ import annotations

import json
import re
from typing import Any, Dict, List

from experiment.webarena.systems.base import BaseWebArenaRunner, estimate_text_tokens


class WebArenaAutoGenRunner(BaseWebArenaRunner):
    """Reference-policy AutoGen baseline for WebArena smoke experiments."""

    system_family = "autogen"

    @staticmethod
    def _is_valid_action(action_text: str, action_set_tag: str) -> bool:
        action = str(action_text or "").strip()
        if not action:
            return False
        if action_set_tag == "id_accessibility_tree":
            return bool(re.match(r"^(click|type|hover|press|scroll|stop)\s+\[", action))
        return action.startswith("page.")

    def _llm_decide_action(self, *, observation: Dict[str, Any], step_id: int) -> Dict[str, Any]:
        action_set_tag = str(observation.get("action_set_tag", "") or "")
        syntax_hint = (
            "Valid actions include: click [id], type [id] [text] [0|1], hover [id], press [key], scroll [down|up], stop [answer]."
            if action_set_tag == "id_accessibility_tree"
            else "Return one Playwright action string beginning with page., or page.stop(\"answer\")."
        )
        system_prompt = (
            "You are an AutoGen-style WebArena planner/executor pair. "
            "Choose the next browser action and return JSON only with keys action and reason. "
            f"{syntax_hint}"
        )
        visible_context = {
            "task_id": observation.get("task_id", ""),
            "intent": observation.get("intent", ""),
            "sites": list(observation.get("sites", []) or []),
            "page_url": observation.get("page_url", ""),
            "text_observation": observation.get("text_observation", ""),
            "history": list(observation.get("history", []) or []),
            "action_set_tag": action_set_tag,
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
            "decision_reason": str(payload.get("reason", "") or "Local WebArena model selected the next action."),
            "usage": dict(response.get("usage", {})),
        }

    def build_turn(self, observation: Dict[str, Any], step_id: int) -> Dict[str, Any]:
        workflow_mode = self.config.get("workflow_mode", "planner_action")
        next_action = str(observation.get("next_reference_action", "") or "")
        action_set_tag = str(observation.get("action_set_tag", "") or "")
        planner_message = (
            f"SUBTASK: Advance task {observation.get('task_id', '')}.\n"
            f"INTENT: {observation.get('intent', '')}\n"
            f"NEXT_ACTION: {next_action}\n"
            "RATIONALE: Follow the remaining reference trajectory."
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
                if candidate_action and not self._is_valid_action(candidate_action, action_set_tag):
                    selected_action = ""
                    decision_reason = f"Model proposed an invalid WebArena action: {candidate_action}"
                else:
                    selected_action = candidate_action
                    decision_reason = str(llm_result["decision_reason"] or decision_reason)
                planner_message = (
                    f"SUBTASK: Advance task {observation.get('task_id', '')}.\n"
                    f"INTENT: {observation.get('intent', '')}\n"
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
                decision_reason = f"Local WebArena model call failed: {exc}"
                planner_message = (
                    f"SUBTASK: Advance task {observation.get('task_id', '')}.\n"
                    f"INTENT: {observation.get('intent', '')}\n"
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
