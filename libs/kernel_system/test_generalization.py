"""
测试泛化改进 - 简化版本

直接测试 Architect Agent 的输出，不需要完整的图执行
"""
import json
import sys
sys.path.insert(0, '/home/syq/Documents/ApexLab/langgraph/libs/kernel_system')

from langgraph_kernel.llm_wrapper import SimpleChatModel
from langgraph_kernel.architect.agent import ArchitectAgent


def test_architect_with_vague_prompt(prompt: str):
    """测试 Architect 处理模糊 prompt 的能力"""
    print("=" * 80)
    print(f"📝 用户输入: {prompt}")
    print("=" * 80)

    # 配置模型
    llm = SimpleChatModel(
        model="deepseek-v3",
        api_key="sk-2OsXSnW0fVfpFVnT4HeOkGDue8bxgRflUSc9KqCx7mnNOTgb",
        base_url="https://tb.api.mkeai.com/v1",
        temperature=0.7,
    )

    # 创建 Architect
    architect = ArchitectAgent(llm)

    # 调用 Architect
    result = architect({
        "domain_state": {"user_prompt": prompt},
        "data_schema": {},
        "workflow_rules": {},
        "worker_instructions": {},
        "pending_patch": [],
        "patch_error": "",
        "step_count": 0,
    })

    # 输出结果
    print("\n🗺️  生成的 Data Schema:")
    print(json.dumps(result["data_schema"], indent=2, ensure_ascii=False))

    print("\n🔀 生成的 Workflow Rules:")
    print(json.dumps(result["workflow_rules"], indent=2, ensure_ascii=False))

    print("\n👷 生成的 Worker Instructions:")
    for worker_name, instruction in result.get("worker_instructions", {}).items():
        print(f"  • {worker_name}:")
        print(f"    {instruction}")

    print("\n" + "=" * 80)
    print()


def main():
    """测试多个模糊 prompt"""

    # 测试 1: 非常模糊的旅行请求
    # test_architect_with_vague_prompt("帮我规划旅行")

    # 测试 2: 模糊的数据分析请求
    test_architect_with_vague_prompt("分析一下销售数据")

    # 测试 3: 模糊的写作请求
    # test_architect_with_vague_prompt("写一篇文章")


if __name__ == "__main__":
    main()
