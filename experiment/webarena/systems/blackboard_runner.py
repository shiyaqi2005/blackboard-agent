"""Structured blackboard-style WebArena runner using the reference backend."""
from __future__ import annotations

import copy
import json
import re
from typing import Any, Dict, List, Optional

from experiment.webarena.systems.base import BaseWebArenaRunner, estimate_text_tokens


class WebArenaBlackboardRunner(BaseWebArenaRunner):
    """Reference-policy blackboard runner for WebArena smoke experiments."""

    system_family = "blackboard"

    _DATA_SCHEMA = {
        "type": "object",
        "properties": {
            "workflow_status": {"type": "string", "enum": ["planning", "acting", "completed"]},
            "task_id": {"type": "string"},
            "intent": {"type": "string"},
            "sites": {"type": "array", "items": {"type": "string"}},
            "history": {"type": "array", "items": {"type": "string"}},
            "step_index": {"type": "integer"},
            "next_action": {"type": "string"},
            "selected_action": {"type": "string"},
            "decision_reason": {"type": "string"},
            "reference_action_count": {"type": "integer"},
            "remaining_action_count": {"type": "integer"},
            "fallback_used": {"type": "boolean"},
        },
        "required": [
            "workflow_status",
            "task_id",
            "intent",
            "step_index",
            "next_action",
            "selected_action",
        ],
    }

    @staticmethod
    def _is_non_empty_fragment(value: Any) -> bool:
        if value is None:
            return False
        if isinstance(value, str):
            return bool(value.strip())
        if isinstance(value, (list, tuple, dict, set)):
            return len(value) > 0
        return True

    @classmethod
    def _count_fragments(cls, payload: Dict[str, Any], *, relevant_keys: set[str]) -> Dict[str, float]:
        total = 0
        relevant = 0
        for key, value in payload.items():
            if not cls._is_non_empty_fragment(value):
                continue
            total += 1
            if key in relevant_keys:
                relevant += 1
        precision = float(relevant / total) if total > 0 else 0.0
        return {
            "context_fragment_count": float(total),
            "relevant_fragment_count": float(relevant),
            "irrelevant_fragment_count": float(max(total - relevant, 0)),
            "retrieval_precision": precision,
        }

    @staticmethod
    def _build_full_worker_context(
        observation: Dict[str, Any],
    ) -> Dict[str, Any]:
        return {
            "task_id": str(observation.get("task_id", "") or ""),
            "intent": str(observation.get("intent", "") or ""),
            "sites": list(observation.get("sites", []) or []),
            "start_url": str(observation.get("start_url", "") or ""),
            "page_url": str(observation.get("page_url", "") or ""),
            "require_login": bool(observation.get("require_login", False)),
            "action_set_tag": str(observation.get("action_set_tag", "") or ""),
            "eval_types": list(observation.get("eval_types", []) or []),
            "history": list(observation.get("history", []) or []),
            "step_index": int(observation.get("step_index", 0) or 0),
            "text_observation": str(observation.get("text_observation", "") or ""),
        }

    @staticmethod
    def _build_sliced_worker_context(observation: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "task_id": str(observation.get("task_id", "") or ""),
            "intent": str(observation.get("intent", "") or ""),
            "sites": list(observation.get("sites", []) or []),
            "page_url": str(observation.get("page_url", "") or ""),
            "action_set_tag": str(observation.get("action_set_tag", "") or ""),
            "step_index": int(observation.get("step_index", 0) or 0),
            "text_observation": str(observation.get("text_observation", "") or ""),
        }

    @staticmethod
    def _render_text_context(worker_context: Dict[str, Any], *, context_mode: str) -> str:
        return (
            f"CONTEXT_MODE: {context_mode}\n"
            f"INTENT: {worker_context.get('intent', '')}\n"
            f"SITES: {', '.join(str(site) for site in worker_context.get('sites', []))}\n"
            f"OBSERVATION: {worker_context.get('text_observation', '')[:2000]}\n"
            f"HISTORY_LEN: {len(worker_context.get('history', []))}\n"
            f"PAGE_URL: {worker_context.get('page_url', '')}"
        )

    @staticmethod
    def _action_syntax_hint(action_set_tag: str) -> str:
        if action_set_tag == "id_accessibility_tree":
            return (
                "Valid actions include: click [id], type [id] [text] [0|1], hover [id], "
                "press [key], scroll [down|up], stop [answer]."
            )
        return (
            "Return one Playwright action string such as "
            "page.get_by_role(\"link\", name=\"Forums\").click(), "
            "page.get_by_role(\"textbox\", name=\"Search\").fill(\"query\"), "
            "page.get_by_role(\"textbox\", name=\"Search\").press(\"Enter\"), "
            "or page.stop(\"answer\")."
        )

    @staticmethod
    def _is_valid_action(action_text: str, action_set_tag: str) -> bool:
        action = str(action_text or "").strip()
        if not action:
            return False
        if action_set_tag == "id_accessibility_tree":
            return bool(re.match(r"^(click|type|hover|press|scroll|stop)\s+\[", action))
        return action.startswith("page.")

    def _llm_decide_action(
        self,
        *,
        worker_context: Dict[str, Any],
        context_mode: str,
        communication_style: str,
        action_set_tag: str,
    ) -> Dict[str, Any]:
        system_prompt = (
            "You are a WebArena browser agent. "
            "Read the task intent and page observation, then choose exactly one next browser action. "
            "Return JSON only with keys action and reason. "
            f"{self._action_syntax_hint(action_set_tag)}"
        )
        user_prompt = (
            f"System family: blackboard\n"
            f"Communication style: {communication_style}\n"
            f"Context mode: {context_mode}\n"
            f"Worker context JSON:\n{json.dumps(worker_context, ensure_ascii=False)}"
        )
        response = self.call_local_llm(system_prompt=system_prompt, user_prompt=user_prompt, max_tokens=256)
        payload = response["payload"]
        return {
            "selected_action": str(payload.get("action", "") or "").strip(),
            "decision_reason": str(payload.get("reason", "") or "Local WebArena model selected the next action.").strip(),
            "usage": dict(response.get("usage", {})),
        }

    def build_turn(self, observation: Dict[str, Any], step_id: int) -> Dict[str, Any]:
        workflow_mode = self.config.get("workflow_mode", "planner_action")
        use_context_slicing = bool(self.config.get("use_context_slicing", True))
        use_architect_agent = bool(self.config.get("use_architect_agent", True))
        use_deterministic_kernel = bool(self.config.get("use_deterministic_kernel", True))
        communication_style = str(self.config.get("communication_style", "structured") or "structured")
        use_schema_validation = bool(self.config.get("use_schema_validation", True))
        next_action = str(observation.get("next_reference_action", "") or "")
        action_set_tag = str(observation.get("action_set_tag", "") or "")
        remaining_actions = list(observation.get("remaining_reference_actions", []) or [])
        planner_state = {
            "next_action": next_action,
            "remaining_actions": remaining_actions[:3],
            "intent": observation.get("intent", ""),
            "sites": list(observation.get("sites", [])),
        }
        if use_context_slicing:
            if self.use_local_llm():
                worker_context = self._build_sliced_worker_context(observation)
                relevant_keys = {"intent", "sites", "page_url", "action_set_tag", "text_observation"}
            else:
                worker_context = planner_state
                relevant_keys = {"next_action", "remaining_actions", "intent", "sites"}
            context_mode = "sliced"
        else:
            if self.use_local_llm():
                worker_context = self._build_full_worker_context(observation)
                relevant_keys = {"intent", "sites", "page_url", "action_set_tag", "text_observation", "history"}
            else:
                worker_context = self._build_full_worker_context(observation)
                worker_context["next_reference_action"] = next_action
                worker_context["remaining_reference_actions"] = remaining_actions
                relevant_keys = {"next_reference_action", "remaining_reference_actions", "intent", "sites"}
            context_mode = "full"
        retrieval_stats = self._count_fragments(worker_context, relevant_keys=relevant_keys)
        text_context = self._render_text_context(worker_context, context_mode=context_mode)

        communication_trace: List[Dict[str, Any]] = []
        architect_input_tokens = 0
        architect_output_tokens = 0
        planner_payload: Any = worker_context if communication_style == "structured" else text_context
        selected_action = next_action
        decision_reason = (
            "Reference oracle selected the next gold WebArena action through context-sliced planning."
            if use_context_slicing
            else "Reference oracle selected the next gold WebArena action without context slicing."
        )
        if workflow_mode != "single_action" and use_architect_agent:
            communication_trace.append(
                {
                    "source": "architect",
                    "channel": "structured" if communication_style == "structured" else "natural_language",
                    "content": planner_payload,
                    "context_mode": context_mode,
                }
            )
            architect_input_tokens = estimate_text_tokens(observation)
            architect_output_tokens = estimate_text_tokens(planner_payload)
        worker_input_tokens = estimate_text_tokens(planner_payload if workflow_mode != "single_action" else planner_payload)
        worker_output_tokens = estimate_text_tokens(selected_action or next_action) + estimate_text_tokens(decision_reason)

        if self.use_local_llm():
            try:
                llm_result = self._llm_decide_action(
                    worker_context=worker_context,
                    context_mode=context_mode,
                    communication_style=communication_style,
                    action_set_tag=action_set_tag,
                )
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
            except Exception as exc:
                selected_action = ""
                decision_reason = f"Local WebArena model call failed: {exc}"

        if not use_deterministic_kernel and step_id > 0:
            selected_action = ""
            decision_reason = "Non-deterministic kernel ablation dropped the executable action and required fallback."
        elif not use_architect_agent and workflow_mode != "single_action":
            decision_reason = "Architect ablation routed execution directly from worker-visible context."
        if communication_style == "natural_language":
            worker_message = f"ACTION: {selected_action or next_action}\nREASON: {decision_reason}"
            communication_trace.append(
                {
                    "source": "action_worker",
                    "channel": "natural_language",
                    "content": worker_message,
                    "context_mode": context_mode,
                }
            )
        else:
            communication_trace.append(
                {
                    "source": "action_worker",
                    "channel": "structured",
                    "content": {
                        "selected_action": selected_action or next_action,
                        "reason": decision_reason,
                    },
                    "context_mode": context_mode,
                }
            )
        return {
            "selected_action": selected_action,
            "decision_reason": decision_reason,
            "planner_state": worker_context,
            "communication_trace": communication_trace,
            "architect_input_tokens": architect_input_tokens,
            "architect_output_tokens": architect_output_tokens,
            "worker_input_tokens": worker_input_tokens,
            "worker_output_tokens": worker_output_tokens,
            "context_mode": context_mode,
            "communication_style": communication_style,
            "schema_validation_enabled": use_schema_validation,
            "architect_enabled": use_architect_agent,
            "deterministic_kernel_enabled": use_deterministic_kernel,
            **retrieval_stats,
        }

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
        del reward
        planner_state = dict(turn.get("planner_state", {}) or {})
        remaining_actions = list(
            planner_state.get("remaining_actions", observation.get("remaining_reference_actions", [])) or []
        )
        domain_state = {
            "workflow_status": "completed" if bool(step_info.get("done")) else "acting",
            "task_id": str(observation.get("task_id", "") or ""),
            "intent": str(observation.get("intent", "") or ""),
            "sites": [str(site) for site in list(observation.get("sites", []) or [])],
            "history": [str(item) for item in list(observation.get("history", []) or [])],
            "step_index": int(observation.get("step_index", step_id) or step_id),
            "next_action": str(observation.get("next_reference_action", "") or ""),
            "selected_action": selected_action,
            "decision_reason": str(turn.get("decision_reason", "") or ""),
            "reference_action_count": int(step_info.get("reference_action_count", 0) or 0),
            "remaining_action_count": len(list(observation.get("remaining_reference_actions", []) or [])),
            "fallback_used": bool(fallback_used),
        }
        return {
            "episode_id": episode_id,
            "gamefile": config_file,
            "step_id": step_id,
            "domain_state": domain_state,
            "data_schema": copy.deepcopy(self._DATA_SCHEMA),
        }
