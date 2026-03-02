from __future__ import annotations

from langgraph.graph import END

from langgraph_kernel.types import KernelState


class WorkflowRouter:
    """
    根据 workflow_rules 和当前 domain_state 决定下一个节点。

    workflow_rules 格式：
        {"field_name": {"value": "worker_name", ...}, ...}

    路由优先级：
        1. patch_error 非空 → END（错误终止）
        2. step_count >= max_steps → END（防止无限循环）
        3. 遍历 workflow_rules，匹配 domain_state 中字段的当前值
        4. 无匹配 → END
    """

    def __init__(self, worker_names: list[str], max_steps: int = 50) -> None:
        self.worker_names = worker_names
        self.max_steps = max_steps

    def route(self, state: KernelState) -> str:
        if state.get("patch_error"):
            return END

        if state.get("step_count", 0) >= self.max_steps:
            return END

        domain = state.get("domain_state") or {}
        rules = state.get("workflow_rules") or {}

        for field, value_map in rules.items():
            current_value = domain.get(field)
            if current_value is not None and str(current_value) in value_map:
                worker = value_map[str(current_value)]
                if worker in self.worker_names:
                    return worker

        return END
