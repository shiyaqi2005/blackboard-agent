"""LLM-backed ALFWorld architect for C5 experiments."""
from __future__ import annotations

import json
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage
from langgraph_kernel.types import KernelState

from .alfworld_architect import ALFWorldArchitect


class LLMALFWorldArchitect:
    """Use an LLM to specialize the ALFWorld workflow metadata for each turn."""

    system_prompt = """You are an ALFWorld architect.

You receive the current ALFWorld turn state plus a deterministic workflow template.
Your job is to specialize the workflow metadata for this specific task while preserving
the exact worker order and all execution constraints from the template.

Return ONLY a JSON object with:
- architect_decision: short string summarizing why this workflow is appropriate now
- task_flow: array of objects with keys subtask and worker
- worker_instructions: object keyed by worker name

Hard rules:
- Keep the same workers and the same worker order as the template
- Do not invent new worker names
- Preserve all hard action-validity / JSON-Patch constraints from the base instructions
- Keep instructions concise but specific to the current task, canonical goal object, target receptacle, and transform
- If the task text conflicts with canonical metadata, prefer the canonical metadata
"""

    def __init__(self, llm: Any, workflow_mode: str = "single_action") -> None:
        self._llm = llm
        self._workflow_mode = workflow_mode
        self._fallback = ALFWorldArchitect(workflow_mode=workflow_mode)
        self._last_token_usage = {
            "architect_input_tokens": 0,
            "architect_output_tokens": 0,
        }

    @staticmethod
    def _normalize_response_content(content: Any) -> str:
        if isinstance(content, str):
            return content
        return str(content)

    def _record_token_usage(self, response: Any) -> None:
        metadata = getattr(response, "response_metadata", {}) or {}
        usage = metadata.get("token_usage", {}) if isinstance(metadata, dict) else {}
        if not isinstance(usage, dict):
            usage = {}
        self._last_token_usage = {
            "architect_input_tokens": int(usage.get("prompt_tokens") or usage.get("input_tokens") or 0),
            "architect_output_tokens": int(usage.get("completion_tokens") or usage.get("output_tokens") or 0),
        }

    @staticmethod
    def _extract_json_object(content: str) -> dict[str, Any]:
        candidate = content.strip()
        if "```json" in candidate:
            candidate = candidate.split("```json", 1)[1].split("```", 1)[0].strip()
        elif "```" in candidate:
            candidate = candidate.split("```", 1)[1].split("```", 1)[0].strip()
        payload = json.loads(candidate)
        return payload if isinstance(payload, dict) else {}

    @staticmethod
    def _sanitize_task_flow(proposed: Any, fallback: list[dict[str, Any]]) -> list[dict[str, Any]]:
        if not isinstance(proposed, list) or len(proposed) != len(fallback):
            return fallback

        sanitized: list[dict[str, Any]] = []
        for expected, item in zip(fallback, proposed):
            if not isinstance(item, dict):
                return fallback
            if str(item.get("worker", "")).strip() != expected["worker"]:
                return fallback
            subtask = str(item.get("subtask", "")).strip() or expected["subtask"]
            sanitized.append({"subtask": subtask, "worker": expected["worker"]})
        return sanitized

    @staticmethod
    def _sanitize_worker_instructions(
        proposed: Any,
        fallback: dict[str, str],
        selected_workers: list[str],
    ) -> dict[str, str]:
        instructions = dict(fallback)
        if not isinstance(proposed, dict):
            return instructions

        for worker_name in selected_workers:
            value = proposed.get(worker_name)
            if isinstance(value, str) and value.strip():
                instructions[worker_name] = value.strip()
        return instructions

    @staticmethod
    def _build_context(
        *,
        workflow_mode: str,
        fallback_result: dict[str, Any],
    ) -> dict[str, Any]:
        domain_state = fallback_result.get("domain_state", {})
        return {
            "workflow_mode": workflow_mode,
            "task_goal": domain_state.get("task_goal", ""),
            "current_observation": domain_state.get("current_observation", ""),
            "available_actions": list(domain_state.get("available_actions", [])),
            "action_history": list(domain_state.get("action_history", []))[-5:],
            "observation_history": list(domain_state.get("observation_history", []))[-5:],
            "canonical_task_type": domain_state.get("canonical_task_type", ""),
            "canonical_goal_object": domain_state.get("canonical_goal_object", ""),
            "canonical_target_receptacle": domain_state.get("canonical_target_receptacle", ""),
            "base_task_flow": fallback_result.get("task_flow", []),
            "base_worker_instructions": fallback_result.get("worker_instructions", {}),
            "selected_workers": fallback_result.get("selected_workers", []),
        }

    def __call__(self, state: KernelState) -> dict[str, Any]:
        fallback_result = self._fallback(state)
        self._last_token_usage = {
            "architect_input_tokens": 0,
            "architect_output_tokens": 0,
        }
        context = self._build_context(
            workflow_mode=self._workflow_mode,
            fallback_result=fallback_result,
        )

        try:
            response = self._llm.invoke(
                [
                    SystemMessage(content=self.system_prompt),
                    HumanMessage(content=f"Architect context:\n{json.dumps(context, ensure_ascii=False, indent=2)}"),
                ]
            )
            self._record_token_usage(response)
            payload = self._extract_json_object(self._normalize_response_content(response.content))
        except Exception:
            payload = {}

        task_flow = self._sanitize_task_flow(payload.get("task_flow"), fallback_result["task_flow"])
        worker_instructions = self._sanitize_worker_instructions(
            payload.get("worker_instructions"),
            fallback_result["worker_instructions"],
            list(fallback_result["selected_workers"]),
        )
        architect_decision = str(payload.get("architect_decision", "")).strip()

        merged = dict(fallback_result)
        merged["task_flow"] = task_flow
        merged["worker_instructions"] = worker_instructions
        merged["domain_state"] = {
            **fallback_result["domain_state"],
            "architect_decision": architect_decision,
        }
        merged["turn_architect_input_tokens"] = self._last_token_usage["architect_input_tokens"]
        merged["turn_architect_output_tokens"] = self._last_token_usage["architect_output_tokens"]
        return merged
