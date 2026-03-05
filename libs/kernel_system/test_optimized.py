#!/usr/bin/env python
"""
直接测试 interactive_demo
"""
import sys
sys.path.insert(0, '/home/syq/Documents/ApexLab/langgraph/libs/kernel_system')

from langgraph_kernel import build_dynamic_kernel_graph
from langgraph_kernel.llm_wrapper import SimpleChatModel

# 配置 LLM
llm = SimpleChatModel(
    model="deepseek-v3",
    api_key="sk-2OsXSnW0fVfpFVnT4HeOkGDue8bxgRflUSc9KqCx7mnNOTgb",
    base_url="https://tb.api.mkeai.com/v1",
    temperature=0.7,
    timeout=60.0,
)

# 构建图
graph = build_dynamic_kernel_graph(llm, max_steps=15)

# 初始状态
initial_state = {
    "domain_state": {"user_prompt": "帮我规划一次旅行"},
    "data_schema": {},
    "workflow_rules": {},
    "worker_instructions": {},
    "pending_patch": [],
    "patch_error": "",
    "step_count": 0,
    "current_worker": "",
    "retry_count": 0,
    "error_feedback": "",
    "state_history": [],
}

print("测试: 帮我规划一次旅行")
print("=" * 80)

result = graph.invoke(initial_state)

print("\n" + "=" * 80)
print("测试结果")
print("=" * 80)
print(f"总步数: {result['step_count']}")
print(f"最终状态: {result['domain_state'].get('status', '未知')}")
print(f"状态历史数量: {len(result.get('state_history', []))}")

if result.get('patch_error'):
    print(f"\n⚠️  错误: {result['patch_error'][:200]}")
else:
    print("\n✓ 无错误，执行成功")

# 显示状态历史
state_history = result.get("state_history", [])
if state_history:
    print(f"\n中间状态变化:")
    for i, state in enumerate(state_history, 1):
        status = state.get("status", "未知")
        fields = [k for k in state.keys() if k not in ["user_prompt", "status"]]
        print(f"  步骤 {i}: status={status}, 业务字段={len(fields)}")
