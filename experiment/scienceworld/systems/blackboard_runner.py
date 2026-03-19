"""Structured blackboard-style ScienceWorld runner using the reference backend."""
from __future__ import annotations

import json
from typing import Any, Dict, List

from experiment.scienceworld.systems.base import BaseScienceWorldRunner, estimate_text_tokens


class ScienceWorldBlackboardRunner(BaseScienceWorldRunner):
    """Reference-policy blackboard runner for ScienceWorld smoke experiments."""

    system_family = "blackboard"

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
        *,
        possible_actions: List[str],
    ) -> Dict[str, Any]:
        return {
            "task_id": str(observation.get("task_id", "") or ""),
            "task_name": str(observation.get("task_name", "") or ""),
            "variation_idx": int(observation.get("variation_idx", 0) or 0),
            "simplification_str": str(observation.get("simplification_str", "") or ""),
            "task_desc": str(observation.get("task_desc", "") or ""),
            "inventory": str(observation.get("inventory", "") or ""),
            "look": str(observation.get("look", "") or ""),
            "observation": str(observation.get("observation", "") or ""),
            "history": list(observation.get("history", []) or []),
            "step_index": int(observation.get("step_index", 0) or 0),
            "possible_actions": possible_actions,
        }

    @staticmethod
    def _build_sliced_worker_context(observation: Dict[str, Any], *, possible_actions: List[str]) -> Dict[str, Any]:
        return {
            "task_id": str(observation.get("task_id", "") or ""),
            "task_name": str(observation.get("task_name", "") or ""),
            "task_desc": str(observation.get("task_desc", "") or ""),
            "observation": str(observation.get("observation", "") or ""),
            "step_index": int(observation.get("step_index", 0) or 0),
            "possible_actions": possible_actions,
        }

    @staticmethod
    def _render_text_context(worker_context: Dict[str, Any], *, context_mode: str) -> str:
        return (
            f"CONTEXT_MODE: {context_mode}\n"
            f"TASK_NAME: {worker_context.get('task_name', '')}\n"
            f"TASK_DESC: {worker_context.get('task_desc', '')}\n"
            f"OBSERVATION: {worker_context.get('observation', '')}\n"
            f"POSSIBLE_ACTIONS: {worker_context.get('possible_actions', [])[:10]}\n"
            f"HISTORY_LEN: {len(worker_context.get('history', []))}"
        )

    def _llm_decide_action(
        self,
        *,
        worker_context: Dict[str, Any],
        context_mode: str,
        communication_style: str,
    ) -> Dict[str, Any]:
        system_prompt = (
            "You are a ScienceWorld action planner. "
            "Pick exactly one next action from possible_actions. "
            "Return JSON only with keys action and reason."
        )
        user_prompt = (
            f"System family: blackboard\n"
            f"Communication style: {communication_style}\n"
            f"Context mode: {context_mode}\n"
            f"Worker context JSON:\n{json.dumps(worker_context, ensure_ascii=False)}"
        )
        response = self.call_local_llm(system_prompt=system_prompt, user_prompt=user_prompt, max_tokens=256)
        payload = response["payload"]
        selected_action = str(payload.get("action", "") or "").strip()
        reason = str(payload.get("reason", "") or "Local ScienceWorld model selected the next action.").strip()
        return {
            "selected_action": selected_action,
            "decision_reason": reason,
            "usage": dict(response.get("usage", {})),
            "raw_text": str(response.get("raw_text", "") or ""),
        }

    def build_turn(self, observation: Dict[str, Any], step_id: int) -> Dict[str, Any]:
        workflow_mode = self.config.get("workflow_mode", "planner_action")
        use_context_slicing = bool(self.config.get("use_context_slicing", True))
        use_architect_agent = bool(self.config.get("use_architect_agent", True))
        use_deterministic_kernel = bool(self.config.get("use_deterministic_kernel", True))
        communication_style = str(self.config.get("communication_style", "structured") or "structured")
        use_schema_validation = bool(self.config.get("use_schema_validation", True))
        next_action = str(observation.get("next_reference_action", "") or "")
        possible_actions = [str(action) for action in list(observation.get("possible_actions", []) or [])]
        if use_context_slicing:
            worker_context = self._build_sliced_worker_context(observation, possible_actions=possible_actions)
            context_mode = "sliced"
            relevant_keys = {"task_name", "task_desc", "observation", "possible_actions"}
        else:
            worker_context = self._build_full_worker_context(
                observation,
                possible_actions=possible_actions,
            )
            context_mode = "full"
            relevant_keys = {"task_name", "task_desc", "observation", "inventory", "look", "history", "possible_actions"}
        retrieval_stats = self._count_fragments(worker_context, relevant_keys=relevant_keys)
        text_context = self._render_text_context(worker_context, context_mode=context_mode)

        communication_trace: List[Dict[str, Any]] = []
        architect_input_tokens = 0
        architect_output_tokens = 0
        planner_payload: Any = worker_context if communication_style == "structured" else text_context
        selected_action = next_action
        decision_reason = (
            "Reference oracle selected the next gold ScienceWorld action through context-sliced planning."
            if use_context_slicing
            else "Reference oracle selected the next gold ScienceWorld action without context slicing."
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
                )
                candidate_action = str(llm_result["selected_action"] or "").strip()
                if candidate_action and possible_actions and candidate_action not in possible_actions:
                    selected_action = ""
                    decision_reason = (
                        f"Model proposed an invalid action outside possible_actions: {candidate_action}"
                    )
                else:
                    selected_action = candidate_action
                    decision_reason = str(llm_result["decision_reason"] or decision_reason)
                usage = llm_result.get("usage", {})
                worker_input_tokens = int(usage.get("prompt_tokens", worker_input_tokens) or worker_input_tokens)
                worker_output_tokens = int(usage.get("completion_tokens", worker_output_tokens) or worker_output_tokens)
            except Exception as exc:
                selected_action = ""
                decision_reason = f"Local ScienceWorld model call failed: {exc}"

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
