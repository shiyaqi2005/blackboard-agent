from __future__ import annotations

from typing import Any

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel

from langgraph_kernel.types import KernelState


class _ArchitectOutput(BaseModel):
    data_schema: dict[str, Any]
    workflow_rules: dict[str, dict[str, str]]


_SYSTEM_PROMPT = """\
You are an Architect Agent. Given a user prompt, you must output:

1. `data_schema`: A valid JSON Schema (draft-07) that defines the structure of the
   system's domain state. Include type constraints and required fields.

2. `workflow_rules`: A mapping that drives agent routing based on state values.
   Format: {"field_name": {"state_value": "worker_name", ...}, ...}
   Example: {"status": {"planning": "planner_worker", "executing": "executor_worker"}}

Keep both outputs minimal and focused on what the prompt actually requires.
"""


class ArchitectAgent:
    """
    接收用户 prompt，输出 data_schema 和 workflow_rules。
    作为图的第一个节点（START -> architect -> kernel）。
    """

    def __init__(self, llm: BaseChatModel) -> None:
        self._chain = llm.with_structured_output(_ArchitectOutput)

    def __call__(self, state: KernelState) -> dict[str, Any]:
        user_prompt = (state.get("domain_state") or {}).get("user_prompt", "")

        result: _ArchitectOutput = self._chain.invoke([
            SystemMessage(content=_SYSTEM_PROMPT),
            HumanMessage(content=f"User prompt: {user_prompt}"),
        ])

        return {
            "data_schema": result.data_schema,
            "workflow_rules": result.workflow_rules,
            "domain_state": {"user_prompt": user_prompt},
            "pending_patch": [],
            "patch_error": "",
            "step_count": 0,
        }
