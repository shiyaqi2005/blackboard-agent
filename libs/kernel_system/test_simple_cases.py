"""
使用简单任务测试状态持久化功能
"""
import sys
sys.path.insert(0, '/home/syq/Documents/ApexLab/langgraph/libs/kernel_system')

from interactive_demo import run_interactive_system

# 使用更简单的测试用例
test_cases = [
    "计算 1+1",
    "今天天气怎么样",
]

for prompt in test_cases:
    print("\n" + "=" * 80)
    print(f"测试: {prompt}")
    print("=" * 80)

    try:
        result = run_interactive_system(prompt, verbose=False)

        # 检查状态历史
        state_history = result.get("state_history", [])
        print(f"\n✓ 状态历史数量: {len(state_history)}")
        print(f"✓ 最终状态: {result.get('domain_state', {}).get('status', '未知')}")
        print(f"✓ 总步数: {result.get('step_count', 0)}")

        if result.get('patch_error'):
            print(f"⚠️  有错误: {result['patch_error'][:100]}")
        else:
            print("✓ 无错误")

    except Exception as e:
        print(f"❌ 测试失败: {e}")

    print()
