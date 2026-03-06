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
    task_flow: List[Dict[str, str]]  # 任务流：[{"subtask": "...", "worker": "..."}]
    data_schema: DataSchema
    workflow_rules: WorkflowRules
    worker_instructions: Dict[str, str]  # 新增：worker 指令 {"worker_name": "instruction"}
    selected_workers: List[str]  # 选中的 worker 列表

    # 业务状态（受 data_schema 约束，由 kernel_node 验证后更新）
    domain_state: Annotated[Dict[str, Any], _overwrite]

    # 运行时控制
    pending_patch: JsonPatch   # worker 提交的 patch，等待 kernel 验证
    patch_error: str           # 验证失败时的错误信息，空字符串表示无错误
    step_count: int            # 已执行步数，防止无限循环
    current_worker: str        # 当前要执行的 worker 名称

    # Layer 5: 反馈重试
    retry_count: int           # 当前 worker 的重试次数
    error_feedback: str        # 反馈给 worker 的错误信息

    # 终止检测
    no_update_count: int       # 连续无有效更新的次数（用于检测 worker 无实质工作）
    status_history: List[str]  # 最近的状态历史（用于检测循环）

    # 中间状态持久化：保留所有历史状态快照
    state_history: List[Dict[str, Any]]  # 每一步的 domain_state 快照

    # 多轮对话支持
    conversation_history: List[Dict[str, str]]  # 对话历史：[{"role": "user"/"system", "content": "..."}]
    pending_user_question: str  # 等待用户回答的问题
    user_response: str  # 用户的最新回复
    waiting_for_user: bool  # 是否正在等待用户输入
