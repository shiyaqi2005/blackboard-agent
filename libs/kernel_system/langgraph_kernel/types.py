from __future__ import annotations

from typing import Any, Dict, List

from typing_extensions import Annotated, TypedDict

# ── 基础类型别名 ──────────────────────────────────────────────────────────────

# JSON Schema dict，由 Architect 输出，约束 domain_state 的结构
DataSchema = Dict[str, Any]

# Workflow Rules：字段名 -> {值 -> worker名}
# 例：{"status": {"planning": "planner_worker", "executing": "executor_worker"}}
WorkflowRules = Dict[str, Dict[str, str]]

# RFC 6902 JSON Patch 操作列表
# 例：[{"op": "replace", "path": "/status", "value": "planning"}]
JsonPatch = List[Dict[str, Any]]


# ── Reducer ───────────────────────────────────────────────────────────────────

def _overwrite(current: Dict[str, Any], new: Dict[str, Any]) -> Dict[str, Any]:
    """kernel_node 验证后直接覆盖 domain_state，不做合并。"""
    return new if new is not None else current


# ── 全局状态 ──────────────────────────────────────────────────────────────────

class KernelState(TypedDict):
    """贯穿整个图执行的全局状态。"""

    # Architect 输出（只写一次）
    data_schema: DataSchema
    workflow_rules: WorkflowRules
    worker_instructions: Dict[str, str]  # worker名 -> 指令文本

    # 业务状态（受 data_schema 约束，由 kernel_node 验证后更新）
    domain_state: Annotated[Dict[str, Any], _overwrite]

    # 运行时控制
    pending_patch: JsonPatch   # worker 提交的 patch，等待 kernel 验证
    patch_error: str           # 验证失败时的错误信息，空字符串表示无错误
    step_count: int            # 已执行步数，防止无限循环
    current_worker: str        # 当前要执行的 worker 名称（用于动态图）

    # Layer 5: 反馈重试
    retry_count: int           # 当前 worker 的重试次数
    error_feedback: str        # 反馈给 worker 的错误信息
