from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from langchain_core.language_models import BaseChatModel
from pydantic import BaseModel

from langgraph_kernel.types import JsonPatch


class BaseWorkerAgent(ABC):
    """
    Worker 基类。子类需要：
    1. 声明 `input_schema`（TypedDict 类），Kernel 用它裁剪状态切片
    2. 实现 `_think(context)`，返回 JSON Patch 列表
    """

    # 子类覆盖：声明该 worker 需要的状态字段
    input_schema: type | None = None

    def __call__(self, state: dict[str, Any]) -> dict[str, Any]:
        patch = self._think(state)
        return {"pending_patch": patch}

    @abstractmethod
    def _think(self, context: dict[str, Any]) -> JsonPatch:
        """核心逻辑：根据状态切片生成 JSON Patch。"""


# ── LLM Worker ────────────────────────────────────────────────────────────────

class _PatchOutput(BaseModel):
    """LLM structured output 格式。"""
    patch: list[dict[str, Any]]
    reasoning: str = ""


class LLMWorkerAgent(BaseWorkerAgent):
    """
    调用 LLM 生成 JSON Patch 的 worker。

    LLM 接收状态切片作为 prompt，通过 structured output 输出合法的 patch 列表。
    子类可覆盖 `system_prompt` 来定制角色。
    """

    system_prompt: str = (
        "You are a worker agent. You receive a partial view of the system state "
        "and must return a JSON Patch (RFC 6902) to update it. "
        "Output only valid patch operations."
    )

    def __init__(self, llm: BaseChatModel) -> None:
        self._chain = llm.with_structured_output(_PatchOutput)

    def _think(self, context: dict[str, Any]) -> JsonPatch:
        from langchain_core.messages import HumanMessage, SystemMessage

        result: _PatchOutput = self._chain.invoke([
            SystemMessage(content=self.system_prompt),
            HumanMessage(content=f"Current state slice:\n{context}"),
        ])
        return result.patch


# ── Rule Worker ───────────────────────────────────────────────────────────────

class RuleWorkerAgent(BaseWorkerAgent):
    """
    纯规则 worker，不调用 LLM，适合确定性任务。

    子类实现 `_think()` 返回固定逻辑生成的 patch。
    """

    @abstractmethod
    def _think(self, context: dict[str, Any]) -> JsonPatch: ...
