"""
交互式 Architect-Kernel-Worker 系统演示

清晰展示系统执行过程：
【步骤 N】模块名：执行内容
"""
import json
import sys
from typing import Any

sys.path.insert(0, '/home/syq/Documents/ApexLab/langgraph/libs/kernel_system')

from langgraph_kernel import build_dynamic_kernel_graph
from langgraph_kernel.llm_wrapper import SimpleChatModel


def run_interactive_system(prompt: str, model: str = "deepseek-v3", verbose: bool = True):
    """
    运行交互式系统

    Args:
        prompt: 用户输入的 prompt
        model: 使用的模型名称
        verbose: 是否显示详细信息
    """
    print("=" * 80)
    print("  🚀 Architect-Kernel-Worker 系统")
    print("=" * 80)
    print(f"\n📝 用户输入: {prompt}")
    print(f"🤖 使用模型: {model}\n")

    # 配置 LLM
    llm = SimpleChatModel(
        model=model,
        api_key="sk-2OsXSnW0fVfpFVnT4HeOkGDue8bxgRflUSc9KqCx7mnNOTgb",
        base_url="https://tb.api.mkeai.com/v1",
        temperature=0.7,
        timeout=60.0,  # 设置 60 秒超时
    )

    # 构建图
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
        "state_history": [],  # 初始化状态历史
    }

    print("=" * 80)
    print("  执行过程")
    print("=" * 80)

    step_number = 0
    current_state = initial_state.copy()

    # 用于跟踪实际的业务步骤（排除内部节点）
    business_step = 0

    try:
        for event in graph.stream(initial_state, stream_mode="updates"):
            node_name = list(event.keys())[0]
            node_output = event[node_name]

            # 跳过内部节点 set_worker
            if node_name == "set_worker":
                current_state.update(node_output)
                continue

            step_number += 1

            # 根据节点类型显示不同信息
            if node_name == "architect":
                business_step += 1
                print(f"\n【步骤 {business_step}】Architect: 分析用户需求并设计系统架构")

                if verbose and "data_schema" in node_output:
                    schema = node_output["data_schema"]
                    if "properties" in schema:
                        field_count = len(schema["properties"])
                        print(f"  • 设计了 {field_count} 个状态字段")

                if verbose and "workflow_rules" in node_output:
                    rules = node_output["workflow_rules"]
                    worker_count = len(set(w for r in rules.values() for w in r.values()))
                    print(f"  • 设计了 {worker_count} 个 worker")

                if verbose and "domain_state" in node_output:
                    domain = node_output["domain_state"]
                    if "status" in domain:
                        print(f"  • 初始状态: {domain['status']}")

            elif node_name == "kernel":
                # Kernel 不单独计数，它是验证和状态转换的中间步骤
                step_count = node_output.get("step_count", 0)

                # 检查是否有状态变化
                old_status = current_state.get("domain_state", {}).get("status", "")
                new_status = node_output.get("domain_state", {}).get("status", "")

                if new_status and new_status != old_status:
                    print(f"  → Kernel: 验证通过，状态转换 {old_status} → {new_status}")

                # 检查错误
                if node_output.get("patch_error"):
                    print(f"  → Kernel: ❌ 验证失败 - {node_output['patch_error'][:80]}...")

            elif node_name == "worker":
                # 获取当前 worker 名称
                worker_name = current_state.get("current_worker", "unknown")
                business_step += 1

                # 获取 worker 的指令来理解它的任务
                instructions = current_state.get("worker_instructions", {})
                instruction = instructions.get(worker_name, "")

                # 提取任务描述（取第一句话）
                task_desc = instruction.split('.')[0] if instruction else "执行任务"
                if len(task_desc) > 60:
                    task_desc = task_desc[:60] + "..."

                print(f"\n【步骤 {business_step}】{worker_name}: {task_desc}")

                # 显示提交的 patch
                if verbose and "pending_patch" in node_output:
                    patch = node_output["pending_patch"]
                    if patch:
                        print(f"  • 提交了 {len(patch)} 个状态更新")

                        # 显示每个 patch 操作的内容
                        for i, op in enumerate(patch, 1):
                            op_type = op.get("op", "unknown")
                            path = op.get("path", "")
                            value = op.get("value")

                            # 提取字段名
                            field_name = path.split("/")[-1] if "/" in path else path

                            if op_type in ["add", "replace"]:
                                # 格式化显示值
                                if isinstance(value, str):
                                    # 字符串：如果太长则截断
                                    if len(value) > 100:
                                        print(f"    {i}. {op_type} {field_name}: {value[:100]}...")
                                    else:
                                        print(f"    {i}. {op_type} {field_name}: {value}")
                                elif isinstance(value, (list, dict)):
                                    # 列表或对象：显示类型和大小
                                    if isinstance(value, list):
                                        print(f"    {i}. {op_type} {field_name}: [列表，{len(value)} 项]")
                                    else:
                                        print(f"    {i}. {op_type} {field_name}: {{对象，{len(value)} 个字段}}")
                                else:
                                    # 其他类型：直接显示
                                    print(f"    {i}. {op_type} {field_name}: {value}")
                            elif op_type == "remove":
                                print(f"    {i}. remove {field_name}")

            # 更新当前状态
            current_state.update(node_output)

        # 显示最终结果
        print("\n" + "=" * 80)
        print("  最终结果")
        print("=" * 80)

        final_state = current_state
        domain_state = final_state.get("domain_state", {})

        # 显示执行统计
        print(f"\n📊 执行统计:")
        print(f"  • 总步数: {final_state.get('step_count', 0)}")
        print(f"  • 最终状态: {domain_state.get('status', '未知')}")
        error = final_state.get('patch_error')
        print(f"  • 错误: {error if error else '无'}")

        # 显示业务数据（排除 user_prompt 和 status）
        print(f"\n📋 生成的内容:")
        has_content = False
        for key, value in domain_state.items():
            if key in ["user_prompt", "status", "error_feedback", "retry_count"]:
                continue

            has_content = True
            print(f"\n  {key}:")

            if isinstance(value, dict):
                # 格式化显示字典
                print(json.dumps(value, indent=4, ensure_ascii=False))
            elif isinstance(value, list):
                if len(value) > 0:
                    # 如果是对象列表，格式化显示
                    if isinstance(value[0], dict):
                        print(json.dumps(value, indent=4, ensure_ascii=False))
                    else:
                        # 简单列表，逐行显示
                        for i, item in enumerate(value, 1):
                            print(f"    {i}. {item}")
                else:
                    print("    (空)")
            else:
                # 字符串或其他类型
                value_str = str(value)
                if len(value_str) > 500:
                    print(f"    {value_str[:500]}...")
                else:
                    print(f"    {value_str}")

        if not has_content:
            print("  (无业务数据)")

        print("\n" + "=" * 80)

        return final_state

    except KeyboardInterrupt:
        print("\n\n⚠️  用户中断执行")
        return current_state
    except Exception as e:
        error_msg = str(e)
        print(f"\n\n❌ 执行出错: {error_msg}")

        # 针对不同类型的错误给出建议
        if "timed out" in error_msg.lower() or "timeout" in error_msg.lower():
            print("\n💡 建议:")
            print("  1. 检查网络连接是否正常")
            print("  2. API 服务可能繁忙，请稍后重试")
            print("  3. 尝试使用更简单的 prompt")
        elif "connection" in error_msg.lower():
            print("\n💡 建议:")
            print("  1. 检查网络连接")
            print("  2. 检查 API 地址是否正确")
            print("  3. 检查防火墙设置")
        elif "api" in error_msg.lower() or "key" in error_msg.lower():
            print("\n💡 建议:")
            print("  1. 检查 API Key 是否有效")
            print("  2. 检查 API 配额是否用尽")

        if verbose:
            print("\n详细错误信息:")
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

    print()  # 空行

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
