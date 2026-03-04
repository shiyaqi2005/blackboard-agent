# 泛化改进报告

## 概述

为了让 Architect-Kernel-Worker 系统能够处理模糊的用户 prompt，我们进行了以下改进：

## 主要改进

### 1. 增强的 Architect Agent

**改进前**：
- 简单的 prompt，只要求输出 data_schema 和 workflow_rules
- 缺乏对模糊需求的理解能力
- 没有提供示例指导

**改进后**：
- 详细的 prompt，包含任务分解指导
- 提供多个场景示例（旅行规划、数据分析等）
- 新增 `worker_instructions` 输出，为每个 worker 提供具体指令
- 包含处理模糊 prompt 的指南

**关键特性**：
```python
# Architect 现在输出三个部分：
{
  "data_schema": {...},           # 状态结构定义
  "workflow_rules": {...},        # 路由规则
  "worker_instructions": {...}    # 每个 worker 的具体指令
}
```

### 2. 动态 Worker 创建

**改进前**：
- Workers 必须预先定义和硬编码
- 每个任务类型需要单独的 worker 类
- 无法适应新的任务类型

**改进后**：
- Workers 根据 Architect 的输出动态创建
- 使用 `LLMWorkerAgent` 的 `instruction` 参数注入动态指令
- 无需预定义任何 worker 类型

**实现**：
```python
# LLMWorkerAgent 现在接受动态指令
worker = LLMWorkerAgent(llm, instruction="从用户请求中提取旅行详情...")
```

### 3. 新的图构建函数

**`build_dynamic_kernel_graph()`**：
- 无需预定义 workers
- 根据 workflow_rules 动态创建 worker 节点
- 自动处理任意类型的任务

**使用方式**：
```python
from langgraph_kernel import build_dynamic_kernel_graph

# 无需定义任何 worker 类
graph = build_dynamic_kernel_graph(llm, max_steps=10)

# 直接处理模糊 prompt
result = graph.invoke({
    "domain_state": {"user_prompt": "帮我规划旅行"},  # 非常模糊
    "data_schema": {},
    "workflow_rules": {},
    "worker_instructions": {},
    "pending_patch": [],
    "patch_error": "",
    "step_count": 0,
})
```

### 4. 增强的 Worker Prompt

**改进**：
- 更详细的指导说明
- 包含 JSON Patch 格式要求
- 提供处理不确定性的建议（如添加 clarification_needed 字段）
- 使用 JSON 格式化输出，提高可读性

## 工作流程

```
用户输入模糊 prompt
    ↓
[Architect Agent]
    • 分析用户意图
    • 设计状态结构 (data_schema)
    • 设计工作流 (workflow_rules)
    • 为每个步骤生成指令 (worker_instructions)
    ↓
[Kernel]
    • 初始化状态
    • 根据 workflow_rules 路由
    ↓
[动态创建 Worker]
    • 根据 worker_instructions 创建 LLMWorkerAgent
    • 执行任务，生成 JSON Patch
    ↓
[Kernel]
    • 验证并应用 patch
    • 继续路由到下一个 worker
    ↓
[循环直到完成]
```

## 示例场景

### 场景 1：模糊的旅行请求

**输入**：`"帮我规划旅行"`

**Architect 输出**：
```json
{
  "data_schema": {
    "properties": {
      "status": {"enum": ["analyzing", "planning", "reviewing", "done"]},
      "destination": {"type": "string"},
      "duration": {"type": "string"},
      "plan": {"type": "array"},
      "result": {"type": "string"}
    }
  },
  "workflow_rules": {
    "status": {
      "analyzing": "analyzer_worker",
      "planning": "planner_worker",
      "reviewing": "reviewer_worker"
    }
  },
  "worker_instructions": {
    "analyzer_worker": "提取旅行详情（目的地、时长、偏好）。如果缺失，做合理假设。设置 status 为 'planning'。",
    "planner_worker": "基于提取的详情创建详细行程。设置 status 为 'reviewing'。",
    "reviewer_worker": "审核计划的完整性和可行性。设置 status 为 'done' 并填充 'result'。"
  }
}
```

**执行流程**：
1. analyzer_worker 被动态创建，分析需求
2. planner_worker 被动态创建，生成计划
3. reviewer_worker 被动态创建，审核计划
4. 完成

### 场景 2：模糊的数据分析请求

**输入**：`"分析这些数据"`

**系统会自动**：
- 设计 understanding → analyzing → summarizing 流程
- 创建相应的 workers
- 执行分析任务

## 优势

1. **真正的泛化**：无需为每种任务类型编写代码
2. **智能适应**：Architect 根据 prompt 设计最合适的工作流
3. **易于使用**：用户只需提供 LLM 实例，无需其他配置
4. **灵活扩展**：可以处理任何类型的任务
5. **自我文档化**：worker_instructions 清楚说明每个步骤的作用

## 向后兼容

- 保留了原有的 `build_kernel_graph()` 函数
- 现有代码无需修改
- 新功能通过 `build_dynamic_kernel_graph()` 提供

## 使用建议

### 使用 `build_kernel_graph()` 当：
- 任务类型明确且固定
- 需要精确控制 worker 行为
- 有特殊的 worker 实现需求

### 使用 `build_dynamic_kernel_graph()` 当：
- 处理用户的自由输入
- 任务类型不确定
- 希望系统自动适应不同场景
- 快速原型开发

## 测试

运行 `example_dynamic.py` 来测试系统处理模糊 prompt 的能力：

```bash
cd libs/kernel_system
python example_dynamic.py
```

## 文件变更

1. `langgraph_kernel/architect/agent.py` - 增强 Architect prompt
2. `langgraph_kernel/types.py` - 添加 worker_instructions 字段
3. `langgraph_kernel/worker/base.py` - LLMWorkerAgent 支持动态指令
4. `langgraph_kernel/graph.py` - 新增 build_dynamic_kernel_graph()
5. `langgraph_kernel/__init__.py` - 导出新函数
6. `example_dynamic.py` - 新的示例文件

## 下一步

可以进一步改进：
1. 添加澄清机制：当 prompt 太模糊时，生成问题询问用户
2. 添加记忆功能：记住用户偏好，改进后续交互
3. 添加反馈循环：根据执行结果调整工作流
4. 支持多轮对话：允许用户在执行过程中提供额外信息
