"""
快速测试 interactive_demo 的核心功能
"""
import sys
sys.path.insert(0, '/home/syq/Documents/ApexLab/langgraph/libs/kernel_system')

from interactive_demo import run_interactive_system

# 测试用例
test_prompt = "帮我规划一次旅行"

print(f"测试 prompt: {test_prompt}\n")

result = run_interactive_system(test_prompt, verbose=True)

# 验证状态历史
print("\n" + "=" * 80)
print("  验证状态历史功能")
print("=" * 80)

state_history = result.get("state_history", [])
print(f"\n✓ 保存的状态历史数量: {len(state_history)}")

if state_history:
    print("\n每一步的状态变化:")
    for i, state in enumerate(state_history, 1):
        status = state.get("status", "未知")
        fields = [k for k in state.keys() if k not in ["user_prompt", "status"]]
        print(f"  步骤 {i}: status={status}, 业务字段={len(fields)}")
        if fields:
            print(f"         字段: {', '.join(fields[:5])}")
else:
    print("\n⚠️  没有保存状态历史")

print("\n测试完成！")
