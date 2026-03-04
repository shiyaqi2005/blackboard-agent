"""
完整示例：使用 Architect + LLM Workers

演示完整的 Architect-Kernel-Worker 流程：
1. Architect 根据用户 prompt 生成 schema 和 rules
2. LLM Workers 根据状态自动生成 JSON Patch
"""
from typing_extensions import TypedDict

from langgraph_kernel import build_kernel_graph
from langgraph_kernel.worker.base import LLMWorkerAgent
from langgraph_kernel.llm_wrapper import SimpleChatModel


# ── LLM Workers ───────────────────────────────────────────────────────────────

class PlannerLLMWorker(LLMWorkerAgent):
    """使用 LLM 生成旅行计划"""

    class InputSchema(TypedDict):
        domain_state: dict

    input_schema = InputSchema

    system_prompt = """
你是一个旅行规划助手。根据用户的旅行需求，生成详细的旅行计划。

请返回 JSON Patch 格式的操作，例如：
[
  {"op": "add", "path": "/plan", "value": ["第一天：...", "第二天：..."]},
  {"op": "replace", "path": "/status", "value": "reviewing"}
]

只返回 JSON 数组，不要其他文字。
"""


class ReviewerLLMWorker(LLMWorkerAgent):
    """使用 LLM 审核计划"""

    class InputSchema(TypedDict):
        domain_state: dict

    input_schema = InputSchema

    system_prompt = """
你是一个旅行计划审核员。检查计划是否合理，并提供建议。

请返回 JSON Patch 格式的操作，例如：
[
  {"op": "add", "path": "/review_comments", "value": "计划看起来不错！"},
  {"op": "replace", "path": "/status", "value": "approved"}
]

只返回 JSON 数组，不要其他文字。
"""


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    # 配置模型
    llm = SimpleChatModel(
        model="gemini-2.5-flash",
        api_key="sk-2OsXSnW0fVfpFVnT4HeOkGDue8bxgRflUSc9KqCx7mnNOTgb",
        base_url="https://tb.api.mkeai.com/v1",
        temperature=0.7,
    )

    # 构建图（包含 Architect）
    workers = {
        "planner_worker": PlannerLLMWorker(llm),
        "reviewer_worker": ReviewerLLMWorker(llm),
    }
    graph = build_kernel_graph(llm, workers, max_steps=10)

    # 执行
    print("🚀 启动智能旅行规划系统...\n")
    print("📝 用户需求: 帮我规划一个为期5天的东京之旅\n")

    result = graph.invoke({
        "domain_state": {"user_prompt": "帮我规划一个为期5天的东京之旅，预算中等，喜欢美食和文化"},
        "data_schema": {},
        "workflow_rules": {},
        "pending_patch": [],
        "patch_error": "",
        "step_count": 0,
    })

    # 输出结果
    print("\n" + "=" * 60)
    print("📊 最终状态:")
    print("=" * 60)
    print(f"\n🗺️  Data Schema:")
    print(f"  {result['data_schema']}")
    print(f"\n🔀 Workflow Rules:")
    print(f"  {result['workflow_rules']}")
    print(f"\n📋 Domain State:")
    for key, value in result['domain_state'].items():
        print(f"  {key}: {value}")
    print(f"\n📈 执行统计:")
    print(f"  步骤数: {result['step_count']}")
    print(f"  错误: {result['patch_error'] or '无'}")


if __name__ == "__main__":
    main()
