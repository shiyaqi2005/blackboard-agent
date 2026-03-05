from __future__ import annotations

from langgraph.graph import END

from langgraph_kernel.types import KernelState


class WorkflowRouter:
    """
    根据 workflow_rules 和当前 domain_state 决定下一个节点。

    workflow_rules 格式：
        {"field_name": {"value": "worker_name", ...}, ...}
        特殊值：None, "END", "" 表示终止状态

    路由优先级（三层终止机制）：
        1. patch_error 非空 → END（错误终止）
        2. step_count >= max_steps → END（防止无限循环）
        3. 显式终止状态：workflow_rules 中状态映射到 None/"END"/"" → END
        4. 无效更新检测：连续 N 次无有效业务数据更新 → END
        5. 状态循环检测：状态在短期内重复出现 → END
        6. 遍历 workflow_rules，匹配 domain_state 中字段的当前值
        7. 无匹配 → END
    """

    def __init__(
        self,
        worker_names: list[str],
        max_steps: int = 50,
        max_no_update: int = 2,
        loop_detection_window: int = 3,
    ) -> None:
        self.worker_names = worker_names
        self.max_steps = max_steps
        self.max_no_update = max_no_update  # 最多允许连续 N 次无更新
        self.loop_detection_window = loop_detection_window  # 检测循环的窗口大小

    def route(self, state: KernelState) -> str:
        # 1. 错误终止
        if state.get("patch_error"):
            print("\n🛑 终止原因: patch 验证错误")
            return END

        # 2. 步数限制
        if state.get("step_count", 0) >= self.max_steps:
            print(f"\n🛑 终止原因: 达到最大步数限制 ({self.max_steps})")
            return END

        domain = state.get("domain_state") or {}
        rules = state.get("workflow_rules") or {}

        # 3. 显式终止状态检测
        for field, value_map in rules.items():
            current_value = domain.get(field)
            if current_value is not None and str(current_value) in value_map:
                worker = value_map[str(current_value)]
                # 检查是否是终止状态（None, "END", ""）
                if worker is None or worker == "END" or worker == "":
                    print(f"\n🛑 终止原因: 到达显式终止状态 ({field}={current_value})")
                    return END

        # 4. 无效更新检测
        no_update_count = state.get("no_update_count", 0)
        if no_update_count >= self.max_no_update:
            print(f"\n🛑 终止原因: 连续 {no_update_count} 次无有效业务数据更新")
            return END

        # 5. 状态循环检测
        status_history = state.get("status_history", [])
        if len(status_history) >= self.loop_detection_window:
            # 检查最近的状态是否有重复
            recent = status_history[-self.loop_detection_window:]
            if len(recent) != len(set(recent)):  # 有重复
                print(f"\n🛑 终止原因: 检测到状态循环 {recent}")
                return END

        # 6. 正常路由：匹配 workflow_rules
        for field, value_map in rules.items():
            current_value = domain.get(field)
            if current_value is not None and str(current_value) in value_map:
                worker = value_map[str(current_value)]
                # 如果 worker_names 为空（动态模式），接受任何非空 worker
                if not self.worker_names or worker in self.worker_names:
                    return worker

        # 7. 无匹配，终止
        print("\n🛑 终止原因: 当前状态无匹配的 worker")
        return END
