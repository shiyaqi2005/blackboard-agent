"""
动态 Architect-Kernel-Worker 系统示例

这个示例展示了如何使用 build_dynamic_kernel_graph 处理模糊的用户 prompt。
系统会自动：
1. 分析用户意图
2. 设计合适的工作流
3. 动态创建所需的 workers
4. 执行任务

无需预先定义任何 worker 类型！
"""
from langgraph_kernel import build_dynamic_kernel_graph
from langgraph_kernel.llm_wrapper import SimpleChatModel


def test_vague_prompt(prompt: str):
    """测试系统处理模糊 prompt 的能力"""
    print("=" * 80)
    print(f"📝 用户输入: {prompt}")
    print("=" * 80)

    # 配置模型
    llm = SimpleChatModel(
        model="gemini-2.5-flash",
        api_key="sk-2OsXSnW0fVfpFVnT4HeOkGDue8bxgRflUSc9KqCx7mnNOTgb",
        base_url="https://tb.api.mkeai.com/v1",
        temperature=0.7,
    )

    # 构建动态图
    graph = build_dynamic_kernel_graph(llm, max_steps=10)

    # 执行
    result = graph.invoke({
        "domain_state": {"user_prompt": prompt},
        "data_schema": {},
        "workflow_rules": {},
        "worker_instructions": {},
        "pending_patch": [],
        "patch_error": "",
        "step_count": 0,
    })

    # 输出结果
    print("\n" + "=" * 80)
    print("📊 执行结果")
    print("=" * 80)

    print("\n🗺️  生成的 Data Schema:")
    import json
    print(json.dumps(result["data_schema"], indent=2, ensure_ascii=False))

    print("\n🔀 生成的 Workflow Rules:")
    print(json.dumps(result["workflow_rules"], indent=2, ensure_ascii=False))

    print("\n👷 生成的 Worker Instructions:")
    for worker_name, instruction in result.get("worker_instructions", {}).items():
        print(f"  • {worker_name}:")
        print(f"    {instruction}")

    print("\n📋 最终 Domain State:")
    for key, value in result["domain_state"].items():
        if key != "user_prompt":
            print(f"  • {key}: {value}")

    print(f"\n📈 执行统计:")
    print(f"  • 步骤数: {result['step_count']}")
    print(f"  • 错误: {result['patch_error'] or '无'}")
    print()


def main():
    """测试多个模糊 prompt"""

    # 测试 1: 非常模糊的旅行请求
    test_vague_prompt("帮我规划旅行")

    # 测试 2: 模糊的数据分析请求
    test_vague_prompt("分析一下销售数据")

    # 测试 3: 模糊的写作请求
    test_vague_prompt("写一篇文章")

    # 测试 4: 模糊的问题解决请求
    test_vague_prompt("解决这个问题")


if __name__ == "__main__":
    # 只运行第一个测试，避免太多 API 调用
    test_vague_prompt("帮我规划旅行")
