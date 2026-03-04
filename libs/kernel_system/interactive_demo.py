"""
交互式 Architect-Kernel-Worker 系统演示

实时显示系统执行过程中的状态变化，包括：
- Architect 设计的 schema 和 workflow
- 每个 worker 的执行
- 状态更新
- 最终结果
"""
import json
import sys
from typing import Any

sys.path.insert(0, '/home/syq/Documents/ApexLab/langgraph/libs/kernel_system')

from langgraph_kernel import build_dynamic_kernel_graph
from langgraph_kernel.llm_wrapper import SimpleChatModel


class SystemMonitor:
    """监控系统执行过程"""

    def __init__(self):
        self.step = 0

    def print_header(self, title: str):
        """打印标题"""
        print("\n" + "=" * 80)
        print(f"  {title}")
        print("=" * 80)

    def print_section(self, title: str, emoji: str = "📋"):
        """打印章节"""
        print(f"\n{emoji} {title}")
        print("-" * 80)

    def print_json(self, data: Any, indent: int = 2):
        """打印 JSON 数据"""
        print(json.dumps(data, indent=indent, ensure_ascii=False))

    def print_state_update(self, old_state: dict, new_state: dict):
        """打印状态变化"""
        print("\n🔄 状态变化:")
        for key, new_value in new_state.items():
            old_value = old_state.get(key)
            if old_value != new_value:
                print(f"  • {key}:")
                print(f"      旧值: {old_value}")
                print(f"      新值: {new_value}")


def run_interactive_system(prompt: str, model: str = "deepseek-v3", verbose: bool = True):
    """
    运行交互式系统

    Args:
        prompt: 用户输入的 prompt
        model: 使用的模型名称
        verbose: 是否显示详细信息
    """
    monitor = SystemMonitor()

    # 打印用户输入
    monitor.print_header("🚀 启动 Architect-Kernel-Worker 系统")
    print(f"\n📝 用户输入: {prompt}")
    print(f"🤖 使用模型: {model}")

    # 配置 LLM
    llm = SimpleChatModel(
        model=model,
        api_key="sk-2OsXSnW0fVfpFVnT4HeOkGDue8bxgRflUSc9KqCx7mnNOTgb",
        base_url="https://tb.api.mkeai.com/v1",
        temperature=0.7,
    )

    # 构建图
    print("\n⚙️  构建动态图...")
    graph = build_dynamic_kernel_graph(llm, max_steps=15)

    # 初始状态
    initial_state = {
        "domain_state": {"user_prompt": prompt},
        "data_schema": {},
        "workflow_rules": {},
        "worker_instructions": {},
        "pending_patch": [],
        "patch_error": "",
        "step_count": 0,
        "current_worker": "",
        "retry_count": 0,
        "error_feedback": "",
    }

    # 使用 stream 模式执行，实时显示每个节点的输出
    monitor.print_header("📊 系统执行过程")

    current_state = initial_state.copy()
    node_count = 0

    try:
        for event in graph.stream(initial_state, stream_mode="updates"):
            node_count += 1

            # 获取节点名称和输出
            node_name = list(event.keys())[0]
            node_output = event[node_name]

            # 打印节点信息
            if node_name == "architect":
                monitor.print_section(f"🏗️  步骤 {node_count}: Architect Agent 设计系统", "🏗️")

                if verbose and "data_schema" in node_output:
                    print("\n📐 Data Schema:")
                    schema = node_output["data_schema"]
                    if "properties" in schema:
                        print(f"  字段数: {len(schema['properties'])}")
                        for field_name, field_def in schema["properties"].items():
                            field_type = field_def.get("type", "unknown")
                            print(f"    • {field_name}: {field_type}")
                    else:
                        monitor.print_json(schema, indent=2)

                if verbose and "workflow_rules" in node_output:
                    print("\n🔀 Workflow Rules:")
                    rules = node_output["workflow_rules"]
                    for field, transitions in rules.items():
                        print(f"  {field}:")
                        for value, worker in transitions.items():
                            print(f"    {value} → {worker}")

                if verbose and "worker_instructions" in node_output:
                    print("\n👷 Worker Instructions:")
                    instructions = node_output["worker_instructions"]
                    for worker_name, instruction in instructions.items():
                        print(f"  • {worker_name}:")
                        # 截断过长的指令
                        if len(instruction) > 100:
                            print(f"    {instruction[:100]}...")
                        else:
                            print(f"    {instruction}")

            elif node_name == "kernel":
                monitor.print_section(f"⚙️  步骤 {node_count}: Kernel 验证和更新状态", "⚙️")

                # 显示步数
                step_count = node_output.get("step_count", 0)
                print(f"  当前步数: {step_count}")

                # 显示错误
                if node_output.get("patch_error"):
                    print(f"  ❌ 错误: {node_output['patch_error']}")

                # 显示状态变化
                if "domain_state" in node_output and verbose:
                    new_domain = node_output["domain_state"]
                    old_domain = current_state.get("domain_state", {})

                    # 找出变化的字段
                    changed_fields = []
                    for key in set(list(old_domain.keys()) + list(new_domain.keys())):
                        if old_domain.get(key) != new_domain.get(key):
                            changed_fields.append(key)

                    if changed_fields:
                        print(f"  📝 更新字段: {', '.join(changed_fields)}")

            else:
                # Worker 节点
                monitor.print_section(f"🔧 步骤 {node_count}: Worker '{node_name}' 执行", "🔧")

                if verbose and "pending_patch" in node_output:
                    patch = node_output["pending_patch"]
                    if patch:
                        print(f"  提交 {len(patch)} 个 patch 操作:")
                        for i, op in enumerate(patch[:3], 1):  # 只显示前3个
                            print(f"    {i}. {op.get('op')} {op.get('path')}")
                        if len(patch) > 3:
                            print(f"    ... 还有 {len(patch) - 3} 个操作")

            # 更新当前状态
            current_state.update(node_output)

            # 显示当前关键状态
            if "domain_state" in current_state:
                domain = current_state["domain_state"]
                if "status" in domain:
                    print(f"  📍 当前状态: {domain['status']}")

        # 显示最终结果
        monitor.print_header("✅ 执行完成")

        final_state = current_state

        print(f"\n📊 执行统计:")
        print(f"  • 总步数: {final_state.get('step_count', 0)}")
        print(f"  • 节点数: {node_count}")
        print(f"  • 错误: {final_state.get('patch_error') or '无'}")

        monitor.print_section("📋 最终状态", "📋")
        domain_state = final_state.get("domain_state", {})

        # 排除 user_prompt，显示其他字段
        for key, value in domain_state.items():
            if key != "user_prompt":
                print(f"\n{key}:")
                if isinstance(value, (list, dict)):
                    monitor.print_json(value, indent=2)
                else:
                    print(f"  {value}")

        # 如果有 result 字段，特别突出显示
        if "result" in domain_state:
            monitor.print_section("🎯 最终结果", "🎯")
            result = domain_state["result"]
            if isinstance(result, str):
                print(result)
            else:
                monitor.print_json(result)

        return final_state

    except KeyboardInterrupt:
        print("\n\n⚠️  用户中断执行")
        return current_state
    except Exception as e:
        print(f"\n\n❌ 执行出错: {e}")
        import traceback
        traceback.print_exc()
        return current_state


def main():
    """主函数"""
    print("=" * 80)
    print("  🤖 Architect-Kernel-Worker 交互式演示系统")
    print("=" * 80)
    print("\n这个系统可以处理任意模糊的用户 prompt，自动设计工作流并执行。")
    print("\n示例 prompt:")
    print("  • 帮我规划一次旅行")
    print("  • 分析销售数据")
    print("  • 写一篇文章")
    print("  • 设计一个网站")
    print("  • 制定学习计划")

    # 获取用户输入
    print("\n" + "-" * 80)
    user_prompt = input("\n请输入你的 prompt (按 Ctrl+C 退出): ").strip()

    if not user_prompt:
        print("❌ Prompt 不能为空")
        return

    # 询问是否显示详细信息
    verbose_input = input("\n是否显示详细执行过程? (y/n, 默认 y): ").strip().lower()
    verbose = verbose_input != 'n'

    # 运行系统
    run_interactive_system(user_prompt, verbose=verbose)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n👋 再见!")
    except Exception as e:
        print(f"\n❌ 程序错误: {e}")
        import traceback
        traceback.print_exc()
