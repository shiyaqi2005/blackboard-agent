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
        # 传递 domain_state 以及 Layer 5 的反馈信息
        context = {
            **state.get("domain_state", {}),
            "error_feedback": state.get("error_feedback", ""),
            "retry_count": state.get("retry_count", 0),
        }
        patch = self._think(context)
        return {"pending_patch": patch}

    @abstractmethod
    def _think(self, context: dict[str, Any]) -> JsonPatch:
        """核心逻辑：根据状态切片生成 JSON Patch。"""


# ── LLM Worker ────────────────────────────────────────────────────────────────

class LLMWorkerAgent(BaseWorkerAgent):
    """
    调用 LLM 生成 JSON Patch 的 worker。

    LLM 接收状态切片作为 prompt，输出 JSON Patch 列表。
    子类可覆盖 `system_prompt` 来定制角色。
    """

    system_prompt: str = (
        "You are a worker agent. You receive a partial view of the system state "
        "and must return a JSON Patch (RFC 6902) to update it. "
        "Output ONLY a valid JSON array of patch operations, no other text.\n"
        "Example: [{\"op\": \"add\", \"path\": \"/field\", \"value\": \"data\"}]"
    )

    def __init__(self, llm: BaseChatModel, instruction: str | None = None) -> None:
        self._llm = llm
        self._instruction = instruction  # 来自 Architect 的动态指令

    def _think(self, context: dict[str, Any]) -> JsonPatch:
        import json
        from langchain_core.messages import HumanMessage, SystemMessage

        # 如果有动态指令，使用它；否则使用默认 system_prompt
        system_content = self._instruction if self._instruction else self.system_prompt

        # 增强 system prompt，包含更多上下文
        # 构建增强的 prompt（避免 f-string 中的花括号冲突）
        example_patches = """- [{"op": "replace", "path": "/status", "value": "planning"}]
- [{"op": "add", "path": "/plan", "value": ["step1", "step2"]}]
- [{"op": "replace", "path": "/status", "value": "done"}, {"op": "add", "path": "/result", "value": "Final output"}]"""

        enhanced_prompt = f"""{system_content}

IMPORTANT: You must return a JSON Patch array (RFC 6902 format).
Each operation should have: "op" (add/replace/remove), "path" (JSON pointer), "value" (for add/replace).

Guidelines:
- The current state you see is the domain_state
- All JSON Patch paths should start from the root, e.g., "/status", "/plan", "/result"
- Use "add" for NEW fields that don't exist yet
- Use "replace" for EXISTING fields that need to be updated
- Analyze the current state carefully
- Make incremental, logical changes
- Always update the "status" field to indicate next step
- If you need more information, you can add a "clarification_needed" field
- Keep changes minimal and focused

Example patches:
{example_patches}

Output ONLY the JSON array, no explanations."""

        # Layer 5: 如果有错误反馈，添加到 prompt 中
        error_feedback = context.get("error_feedback", "")
        retry_count = context.get("retry_count", 0)

        if error_feedback and retry_count > 0:
            enhanced_prompt += f"""

⚠️ IMPORTANT: Your previous patch had errors. This is retry attempt #{retry_count}.

Previous Error Report:
{error_feedback}

Please fix these issues:
1. Check that all paths exist before using "replace" (use "add" for new fields)
2. Ensure all values match the expected types in the schema
3. If using enum fields, use ONLY the allowed values from the schema
4. Double-check the JSON Patch syntax

Generate a corrected patch that addresses these errors."""

        response = self._llm.invoke([
            SystemMessage(content=enhanced_prompt),
            HumanMessage(content=f"Current state slice:\n{json.dumps(context, indent=2, ensure_ascii=False)}"),
        ])

        # 解析 JSON 响应
        try:
            content = response.content
            # 尝试提取 JSON（处理可能的 markdown 代码块）
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0].strip()
            elif "```" in content:
                content = content.split("```")[1].split("```")[0].strip()

            patch = json.loads(content)
            if not isinstance(patch, list):
                print(f"⚠️  Worker 返回的不是列表: {patch}")
                return []
            return patch
        except (json.JSONDecodeError, IndexError, AttributeError) as e:
            print(f"⚠️  Worker 解析失败: {e}")
            print(f"原始响应: {response.content[:200]}")
            return []


# ── Rule Worker ───────────────────────────────────────────────────────────────

class RuleWorkerAgent(BaseWorkerAgent):
    """
    纯规则 worker，不调用 LLM，适合确定性任务。

    子类实现 `_think()` 返回固定逻辑生成的 patch。
    """

    @abstractmethod
    def _think(self, context: dict[str, Any]) -> JsonPatch: ...
