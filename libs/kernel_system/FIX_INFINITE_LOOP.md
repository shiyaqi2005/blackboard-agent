# 修复 interactive_demo 无限循环问题

## 问题描述

用户报告在测试 `interactive_demo.py` 时出现了"[步骤 3334] None: 执行任务"一直循环的情况。

## 根本原因

`interactive_demo.py` 使用的是 `build_dynamic_kernel_graph()` 函数，该函数内部的 `dynamic_router` 使用了旧的路由逻辑，**没有使用新实现的 `WorkflowRouter` 类**，因此三层终止机制（显式终止状态、无效更新检测、状态循环检测）没有生效。

## 修复内容

### 1. 更新 `build_dynamic_kernel_graph()` 使用 `WorkflowRouter`

**文件**: `langgraph_kernel/graph.py`

**修改前**:
```python
def dynamic_router(state: KernelState) -> str:
    """根据 workflow_rules 动态路由到 worker"""
    workflow_rules = state.get("workflow_rules", {})
    domain_state = state.get("domain_state", {})
    patch_error = state.get("patch_error", "")
    step_count = state.get("step_count", 0)

    # 错误处理
    if patch_error:
        return END

    # 步数限制
    if step_count >= max_steps:
        return END

    # 遍历 workflow_rules 查找匹配
    for field_name, rules in workflow_rules.items():
        current_value = domain_state.get(field_name)
        if current_value in rules:
            worker_name = rules[current_value]
            return "worker"

    return END
```

**修改后**:
```python
# 创建 WorkflowRouter 实例（支持动态 worker）
router = WorkflowRouter(
    worker_names=[],  # 动态 worker，不预定义
    max_steps=max_steps,
    max_no_update=2,
    loop_detection_window=3,
)

def dynamic_router(state: KernelState) -> str:
    """根据 workflow_rules 动态路由到 worker"""
    # 使用 WorkflowRouter 的路由逻辑（包含三层终止机制）
    result = router.route(state)

    # 如果 router 返回的是 worker 名称（而不是 END），返回 "worker" 节点
    if result != END:
        return "worker"
    return END
```

### 2. 更新 `WorkflowRouter` 支持动态 worker

**文件**: `langgraph_kernel/kernel/router.py`

**修改**: 允许 `worker_names` 为空列表，在动态模式下接受任何非空 worker 名称

```python
# 6. 正常路由：匹配 workflow_rules
for field, value_map in rules.items():
    current_value = domain.get(field)
    if current_value is not None and str(current_value) in value_map:
        worker = value_map[str(current_value)]
        # 如果 worker_names 为空（动态模式），接受任何非空 worker
        if not self.worker_names or worker in self.worker_names:
            return worker
```

## 现在的行为

修复后，`build_dynamic_kernel_graph()` 将使用完整的三层终止机制：

1. **显式终止状态**: Architect 可以在 workflow_rules 中将状态映射到 `null`
2. **无效更新检测**: 连续 2 次无有效业务数据更新后自动终止
3. **状态循环检测**: 检测到状态在最近 3 步中重复出现时自动终止
4. **步数限制**: 达到 `max_steps`（默认 50，interactive_demo 设置为 15）后自动终止

## 终止信息

修复后，当系统终止时会打印清晰的原因：

```
🛑 终止原因: 达到最大步数限制 (15)
🛑 终止原因: 连续 2 次无有效业务数据更新
🛑 终止原因: 检测到状态循环 ['analyzing', 'planning', 'analyzing']
🛑 终止原因: 到达显式终止状态 (status=done)
🛑 终止原因: 当前状态无匹配的 worker
```

## 测试建议

运行 `interactive_demo.py` 并观察：
1. 系统是否在合理的步数内终止（应该 <= 15 步）
2. 终止时是否打印了清晰的原因
3. 是否不再出现无限循环

如果仍然出现问题，请提供：
- 完整的输出日志
- Architect 生成的 workflow_rules
- 最后几步的状态变化
