"""
示例：旅行规划系统

演示完整的 Architect-Kernel-Worker 流程：
1. Architect 生成 schema 和 rules
2. PlannerWorker 生成旅行计划
3. ExecutorWorker 执行计划
"""
from typing_extensions import TypedDict

from langchain_openai import ChatOpenAI

from langgraph_kernel import build_kernel_graph
from langgraph_kernel.worker.base import RuleWorkerAgent
from langgraph_kernel.types import JsonPatch


# ── Workers ───────────────────────────────────────────────────────────────────

class PlannerWorker(RuleWorkerAgent):
    """规划阶段：生成旅行计划"""

    class InputSchema(TypedDict):
        domain_state: dict

    input_schema = InputSchema

    def _think(self, context: dict) -> JsonPatch:
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
        return [
            {"op": "add", "path": "/result", "value": "旅行计划已完成"},
            {"op": "replace", "path": "/status", "value": "done"},
        ]


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    # 配置模型（使用你的第三方 API）
    llm = ChatOpenAI(
        model="gpt-4",  # 替换为你的模型
        api_key="your-api-key",  # 替换为你的 key
        base_url="https://api.openai.com/v1",  # 替换为你的 API 地址
    )

    # 构建图
    workers = {
        "planner_worker": PlannerWorker(),
        "executor_worker": ExecutorWorker(),
    }
    graph = build_kernel_graph(llm, workers)

    # 执行
    print("🚀 启动旅行规划系统...\n")
    result = graph.invoke({
        "domain_state": {"user_prompt": "帮我规划一个去日本的旅行"},
        "data_schema": {},
        "workflow_rules": {},
        "pending_patch": [],
        "patch_error": "",
        "step_count": 0,
    })

    # 输出结果
    print("=" * 60)
    print("📊 最终状态:")
    print("=" * 60)
    print(f"Data Schema: {result['data_schema']}")
    print(f"Workflow Rules: {result['workflow_rules']}")
    print(f"Domain State: {result['domain_state']}")
    print(f"Step Count: {result['step_count']}")
    print(f"Patch Error: {result['patch_error'] or '无错误'}")


if __name__ == "__main__":
    main()
