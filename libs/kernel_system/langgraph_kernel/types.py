from __future__ import annotations

from typing import Any

from typing_extensions import Annotated, TypedDict

# ── 基础类型别名 ──────────────────────────────────────────────────────────────

# JSON Schema dict，由 Architect 输出，约束 domain_state 的结构
DataSchema = dict[str, Any]

# Workflow Rules：字段名 -> {值 -> worker名}
# 例：{"status": {"planning": "planner_worker", "executing": "executor_worker"}}
WorkflowRules = dict[str, dict[str, str]]

# RFC 6902 JSON Patch 操作列表
# 例：[{"op": "replace", "path": "/status", "value": "planning"}]
JsonPatch = list[dict[str, Any]]


# ── Reducer ───────────────────────────────────────────────────────────────────

def _overwrite(current: dict[str, Any], new: dict[str, Any]) -> dict[str, Any]:
    """kernel_node 验证后直接覆盖 domain_state，不做合并。"""
    return new if new is not None else current


# ── 全局状态 ──────────────────────────────────────────────────────────────────

class KernelState(TypedDict):
    """贯穿整个图执行的全局状态。"""

    # Architect 输出（只写一次）
    data_schema: DataSchema
    workflow_rules: WorkflowRules

    # 业务状态（受 data_schema 约束，由 kernel_node 验证后更新）
    domain_state: Annotated[dict[str, Any], _overwrite]

    # 运行时控制
    pending_patch: JsonPatch   # worker 提交的 patch，等待 kernel 验证
    patch_error: str           # 验证失败时的错误信息，空字符串表示无错误
    step_count: int            # 已执行步数，防止无限循环
