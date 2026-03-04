"""
简单示例：不使用 Architect，直接演示 Kernel-Worker 循环

演示流程：
1. 手动定义 schema 和 rules
2. PlannerWorker 生成旅行计划
3. ExecutorWorker 执行计划
"""
from typing_extensions import TypedDict

from langgraph.graph import StateGraph, START, END

from langgraph_kernel.types import KernelState, JsonPatch
from langgraph_kernel.kernel.node import kernel_node
from langgraph_kernel.kernel.router import WorkflowRouter
from langgraph_kernel.worker.base import RuleWorkerAgent
from langgraph_kernel.llm_wrapper import SimpleChatModel


# ── Workers ───────────────────────────────────────────────────────────────────

class PlannerWorker(RuleWorkerAgent):
    """规划阶段：生成旅行计划"""

    class InputSchema(TypedDict):
        domain_state: dict

    input_schema = InputSchema

    def _think(self, context: dict) -> JsonPatch:
        print("📝 PlannerWorker: 生成旅行计划...")
        return [
            {"op": "add", "path": "/plan", "value": ["预订机票", "预订酒店", "规划行程"]},
            {"op": "replace", "path": "/status", "value": "executing"},
        ]


class ExecutorWorker(RuleWorkerAgent):
    """执行阶段：标记完成"""

    class InputSchema(TypedDict):
        domain_state: dict

    input_schema = InputSchema

    def _think(self, context: dict) -> JsonPatch:
        print("✅ ExecutorWorker: 执行计划...")
        return [
            {"op": "add", "path": "/result", "value": "旅行计划已完成"},
            {"op": "replace", "path": "/status", "value": "done"},
        ]


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    # 构建图（不使用 Architect）
    builder = StateGraph(KernelState)

    # 添加 kernel 节点
    builder.add_node("kernel", kernel_node)

    # 添加 worker 节点
    planner = PlannerWorker()
    executor = ExecutorWorker()

    builder.add_node("planner_worker", planner, input_schema=planner.input_schema)
    builder.add_node("executor_worker", executor, input_schema=executor.input_schema)

    # 连接边
    builder.add_edge(START, "kernel")

    # 添加条件路由
    router = WorkflowRouter(["planner_worker", "executor_worker"], max_steps=10)
    builder.add_conditional_edges("kernel", router.route)

    # Worker -> Kernel
    builder.add_edge("planner_worker", "kernel")
    builder.add_edge("executor_worker", "kernel")

    # 编译图
    graph = builder.compile()

    # 执行
    print("🚀 启动旅行规划系统...\n")
    result = graph.invoke({
        "domain_state": {
            "user_prompt": "帮我规划一个去日本的旅行",
            "status": "planning",  # 初始状态触发 planner_worker
        },
        "data_schema": {
            "type": "object",
            "properties": {
                "user_prompt": {"type": "string"},
                "status": {"type": "string"},
                "plan": {"type": "array", "items": {"type": "string"}},
                "result": {"type": "string"},
            },
            "required": ["status"],
        },
        "workflow_rules": {
            "status": {
                "planning": "planner_worker",
                "executing": "executor_worker",
            }
        },
        "pending_patch": [],
        "patch_error": "",
        "step_count": 0,
    })

    # 输出结果
    print("\n" + "=" * 60)
    print("📊 最终状态:")
    print("=" * 60)
    print(f"Domain State: {result['domain_state']}")
    print(f"Step Count: {result['step_count']}")
    print(f"Patch Error: {result['patch_error'] or '无错误'}")


if __name__ == "__main__":
    main()
