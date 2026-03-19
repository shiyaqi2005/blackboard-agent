"""Plain LangGraph-style WebArena runner using the reference backend."""
from __future__ import annotations

import json
import re
from typing import Any, Dict, List

from experiment.webarena.systems.base import BaseWebArenaRunner, estimate_text_tokens


class WebArenaLangGraphRunner(BaseWebArenaRunner):
    """Reference-policy LangGraph baseline for WebArena smoke experiments."""

    system_family = "langgraph"

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
            "You are a LangGraph-style WebArena planner. "
            "Choose the next browser action and return JSON only with keys action and reason. "
            f"{syntax_hint}"
        )
        visible_context = {
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
        planner_note = (
            f"Step {step_id}: execute reference action {next_action!r} for intent "
            f"{observation.get('intent', '')!r}."
        )
        decision_reason = "Plain LangGraph baseline followed the next reference action from the task context."
        communication_trace: List[Dict[str, Any]] = []
        architect_input_tokens = 0
        architect_output_tokens = 0
        if workflow_mode != "single_action":
            communication_trace.append(
                {
                    "source": "planner_node",
                    "channel": "text",
                    "content": planner_note,
                }
            )
            architect_input_tokens = estimate_text_tokens(observation)
            architect_output_tokens = estimate_text_tokens(planner_note)

        selected_action = next_action
        worker_input_tokens = estimate_text_tokens(planner_note if workflow_mode != "single_action" else observation)
        worker_output_tokens = estimate_text_tokens(next_action) + estimate_text_tokens(decision_reason)

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
                usage = llm_result.get("usage", {})
                worker_input_tokens = int(usage.get("prompt_tokens", worker_input_tokens) or worker_input_tokens)
                worker_output_tokens = int(usage.get("completion_tokens", worker_output_tokens) or worker_output_tokens)
                planner_note = (
                    f"Step {step_id}: local model selected {selected_action or '<fallback>'!r} "
                    f"for intent {observation.get('intent', '')!r}."
                )
            except Exception as exc:
                selected_action = ""
                decision_reason = f"Local WebArena model call failed: {exc}"
        communication_trace.append(
            {
                "source": "action_node",
                "channel": "text",
                "content": f"ACTION: {selected_action or next_action}\nREASON: {decision_reason}",
            }
        )
        return {
            "selected_action": selected_action,
            "decision_reason": decision_reason,
            "planner_state": {"planner_note": planner_note},
            "communication_trace": communication_trace,
            "architect_input_tokens": architect_input_tokens,
            "architect_output_tokens": architect_output_tokens,
            "worker_input_tokens": worker_input_tokens,
            "worker_output_tokens": worker_output_tokens,
        }
