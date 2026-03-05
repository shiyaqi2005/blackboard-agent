#!/usr/bin/env python
"""测试写作任务 - 验证worker返回业务数据而不是只返回status"""

import os
from langgraph_kernel import build_dynamic_kernel_graph
from langgraph_kernel.llm_wrapper import get_llm

# 设置 API key
# os.environ["OPENAI_API_KEY"] = "sk-2OsXSnW0fVfpFVnT4HeOkGDue8bxgRflUSc9KqCx7mnNOTgb"  # 用户需要设置真实的key
# os.environ["OPENAI_API_BASE"] = "https://tb.api.mkeai.com/v1"


def test_writing_task():
    """测试写作任务"""
    print("=" * 80)
    print("  测试任务: 请写一篇关于人工智能的短文")
    print("=" * 80)

    # 创建 LLM
    llm = get_llm(
        api_key="sk-2OsXSnW0fVfpFVnT4HeOkGDue8bxgRflUSc9KqCx7mnNOTgb",
        base_url="https://tb.api.mkeai.com/v1",
        model="deepseek-v3",
        temperature=0.7,
        timeout=60.0,
    )

    # 构建图
    graph = build_dynamic_kernel_graph(
        llm=llm,
        max_steps=15,
    )

    # 运行
    user_prompt = "请写一篇关于人工智能的短文"
    initial_state = {
        "domain_state": {"user_prompt": user_prompt},
        "data_schema": {},
        "workflow_rules": {},
        "worker_instructions": {},
        "pending_patch": [],
        "patch_error": "",
        "step_count": 0,
        "retry_count": 0,
        "error_feedback": "",
        "no_update_count": 0,
        "status_history": [],
    }

    print(f"\n📝 用户输入: {user_prompt}\n")
    print("开始执行...\n")

    try:
        final_state = graph.invoke(initial_state)

        print("\n" + "=" * 80)
        print("  执行完成")
        print("=" * 80)

        domain_state = final_state.get("domain_state", {})
        step_count = final_state.get("step_count", 0)

        print(f"\n总步数: {step_count}")
        print(f"\n最终状态:")

        # 检查是否有业务数据
        has_business_data = False
        for key, value in domain_state.items():
            if key not in ["user_prompt", "status"]:
                has_business_data = True
                print(f"\n{key}:")
                if isinstance(value, str) and len(value) > 200:
                    print(f"  {value[:200]}...")
                else:
                    print(f"  {value}")

        if not has_business_data:
            print("\n⚠️  警告: 没有发现业务数据，只有status字段！")
        else:
            print("\n✅ 成功: Worker返回了业务数据")

    except Exception as e:
        print(f"\n❌ 执行失败: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_writing_task()
