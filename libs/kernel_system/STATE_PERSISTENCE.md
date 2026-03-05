# 全局状态持久化机制

## 设计概述

实现了**解耦存储与推理的记忆**机制：

```
┌─────────────────────────────────────────────────────────────┐
│                    架构设计                                  │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  存储层 (Storage)                                            │
│  ├─ state_history: 保留所有中间状态快照                      │
│  ├─ checkpointer: LangGraph 持久化机制                       │
│  └─ 完整保留任务的所有中间结果                               │
│                                                              │
│  推理层 (Inference)                                          │
│  ├─ input_schema: 动态过滤全局状态                           │
│  ├─ Worker 只接收声明的字段                                  │
│  └─ 最小化上下文窗口                                         │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

## 核心实现

### 1. 状态历史保存

在 `KernelState` 中添加 `state_history` 字段：

```python
class KernelState(TypedDict):
    # ... 其他字段 ...

    # 中间状态持久化：保留所有历史状态快照
    state_history: List[Dict[str, Any]]
```

### 2. Kernel 节点自动保存

每次 Kernel 验证并应用 patch 后，自动保存当前状态：

```python
def kernel_node(state: KernelState) -> dict:
    # ... 验证和应用 patch ...

    # 保存中间状态快照（完整保留所有历史）
    import copy
    state_history = state.get("state_history", [])
    state_history.append(copy.deepcopy(new_state))

    return {
        # ... 其他字段 ...
        "state_history": state_history,
    }
```

### 3. 动态过滤（已有机制）

通过 `input_schema` 实现最小化上下文：

```python
class MyWorker(BaseWorkerAgent):
    class InputSchema(TypedDict):
        domain_state: dict  # 只声明需要的字段

    input_schema = InputSchema
```

Worker 只接收 `domain_state`，不会看到 `state_history` 等其他字段。

## 使用方式

### 基础使用（无持久化）

```python
from langgraph_kernel import build_dynamic_kernel_graph

graph = build_dynamic_kernel_graph(llm)

result = graph.invoke({
    "domain_state": {"user_prompt": "写一篇文章"},
    "state_history": [],  # 初始化
    # ... 其他字段 ...
})

# 查看所有中间状态
for i, state in enumerate(result["state_history"], 1):
    print(f"步骤 {i}: {state}")
```

### 持久化使用

```python
from langgraph.checkpoint.memory import MemorySaver

# 创建 checkpointer
checkpointer = MemorySaver()

# 构建图（启用持久化）
graph = build_dynamic_kernel_graph(llm, checkpointer=checkpointer)

# 使用 thread_id 标识会话
config = {"configurable": {"thread_id": "session-1"}}

result = graph.invoke(initial_state, config=config)

# 从 checkpointer 恢复状态
saved_state = checkpointer.get(config)
print(f"保存的状态历史: {len(saved_state.values['state_history'])} 步")
```

### 回溯到特定步骤

```python
# 获取第 3 步的状态
state_at_step_3 = result["state_history"][2]

# 获取最后一步的状态
last_state = result["state_history"][-1]

# 比较两个步骤的差异
diff = compare_states(state_at_step_3, last_state)
```

## 运行示例

```bash
# 基础演示
python interactive_demo.py

# 持久化演示
python demo_with_persistence.py
```

## 特性总结

✅ **完整保留中间结果**
- `state_history` 保存每一步的完整状态快照
- 可以回溯到任意历史步骤

✅ **全局状态持久化**
- 通过 LangGraph checkpointer 持久化
- 支持断点续传和状态恢复

✅ **动态过滤最小化上下文**
- Worker 通过 `input_schema` 声明需要的字段
- LangGraph 自动过滤，Worker 只看到必要数据

✅ **存储与推理解耦**
- 存储：`state_history` + checkpointer
- 推理：`input_schema` 动态过滤
- 完全独立，互不影响

## 性能考虑

- `state_history` 会随着步数增长而增大
- 如果任务很长（>100 步），考虑：
  1. 只在需要时启用（通过配置开关）
  2. 使用外部存储（数据库）而非内存
  3. 定期清理旧的历史记录

## 文件修改

1. `langgraph_kernel/types.py` - 添加 `state_history` 字段
2. `langgraph_kernel/kernel/node.py` - 自动保存状态历史
3. `interactive_demo.py` - 初始化 `state_history`
4. `demo_with_persistence.py` - 持久化使用示例
