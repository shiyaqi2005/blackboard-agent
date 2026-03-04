from __future__ import annotations

from typing import Any

from langchain_core.language_models import BaseChatModel
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph import END, START, StateGraph
from typing_extensions import TypedDict

from langgraph_kernel.architect.agent import ArchitectAgent
from langgraph_kernel.kernel.node import kernel_node
from langgraph_kernel.kernel.router import WorkflowRouter
from langgraph_kernel.types import KernelState
from langgraph_kernel.worker.base import BaseWorkerAgent, LLMWorkerAgent


def build_kernel_graph(
    llm: BaseChatModel,
    workers: dict[str, BaseWorkerAgent],
    max_steps: int = 50,
    checkpointer: BaseCheckpointSaver | None = None,
) -> Any:
    """
    组装完整的 Architect-Kernel-Worker 图。

    图结构：
        START → architect → kernel → [router] → worker_X → kernel → ...
                                              → END

    参数：
        llm: 兼容 OpenAI 格式的第三方模型，用于 Architect 和 LLM workers
        workers: {worker_name: worker_instance} 字典
        max_steps: 最大执行步数，防止无限循环
        checkpointer: 可选的检查点保存器（如 InMemorySaver）
    """
    builder = StateGraph(KernelState)

    # 节点
    builder.add_node("architect", ArchitectAgent(llm))
    builder.add_node("kernel", kernel_node)

    for name, worker in workers.items():
        if worker.input_schema is not None:
            builder.add_node(name, worker, input_schema=worker.input_schema)
        else:
            builder.add_node(name, worker)

    # 边
    builder.add_edge(START, "architect")
    builder.add_edge("architect", "kernel")

    router = WorkflowRouter(list(workers.keys()), max_steps=max_steps)
    builder.add_conditional_edges("kernel", router.route)

    for name in workers:
        builder.add_edge(name, "kernel")

    return builder.compile(checkpointer=checkpointer)


def build_dynamic_kernel_graph(
    llm: BaseChatModel,
    max_steps: int = 50,
    checkpointer: BaseCheckpointSaver | None = None,
) -> Any:
    """
    构建动态 Architect-Kernel-Worker 图（无需预定义 workers）。

    工作流程：
    1. Architect 分析用户 prompt，生成 data_schema、workflow_rules 和 worker_instructions
    2. 系统根据 worker_instructions 动态创建 LLM workers
    3. Kernel 根据 workflow_rules 路由到相应的 worker
    4. Workers 根据 Architect 提供的指令执行任务

    这种方式可以处理任意类型的模糊 prompt，无需预先定义 worker 类型。

    参数：
        llm: 兼容 OpenAI 格式的第三方模型
        max_steps: 最大执行步数
        checkpointer: 可选的检查点保存器

    示例：
        graph = build_dynamic_kernel_graph(llm)
        result = graph.invoke({
            "domain_state": {"user_prompt": "帮我分析这个问题"},
            "data_schema": {},
            "workflow_rules": {},
            "worker_instructions": {},
            "pending_patch": [],
            "patch_error": "",
            "step_count": 0,
        })
    """
    builder = StateGraph(KernelState)

    # 添加 Architect 和 Kernel 节点
    builder.add_node("architect", ArchitectAgent(llm))
    builder.add_node("kernel", kernel_node)

    # 创建动态 worker 节点的函数
    def create_dynamic_worker(worker_name: str):
        """为指定的 worker 名称创建一个动态 worker 节点"""
        class DynamicInputSchema(TypedDict):
            domain_state: dict
            worker_instructions: dict[str, str]

        def dynamic_worker_node(state: dict[str, Any]) -> dict[str, Any]:
            # 从状态中获取该 worker 的指令
            instruction = state.get("worker_instructions", {}).get(worker_name, "")

            # 创建临时 worker 实例
            worker = LLMWorkerAgent(llm, instruction=instruction)
            worker.input_schema = DynamicInputSchema

            # 执行 worker
            return worker(state)

        return dynamic_worker_node, DynamicInputSchema

    # 动态路由函数
    def dynamic_router(state: KernelState) -> str:
        """根据 workflow_rules 动态路由到 worker"""
        workflow_rules = state.get("workflow_rules", {})
        domain_state = state.get("domain_state", {})
        patch_error = state.get("patch_error", "")
        step_count = state.get("step_count", 0)

        # 错误处理
        if patch_error:
            print(f"⚠️  Patch 错误: {patch_error}")
            return END

        # 步数限制
        if step_count >= max_steps:
            print(f"⚠️  达到最大步数 {max_steps}")
            return END

        # 遍历 workflow_rules 查找匹配
        for field_name, rules in workflow_rules.items():
            current_value = domain_state.get(field_name)
            if current_value in rules:
                worker_name = rules[current_value]

                # 如果 worker 节点不存在，动态创建它
                if worker_name not in builder.nodes:
                    worker_node, input_schema = create_dynamic_worker(worker_name)
                    builder.add_node(worker_name, worker_node, input_schema=input_schema)
                    builder.add_edge(worker_name, "kernel")
                    print(f"🔧 动态创建 worker: {worker_name}")

                return worker_name

        # 无匹配规则，结束
        return END

    # 添加边
    builder.add_edge(START, "architect")
    builder.add_edge("architect", "kernel")
    builder.add_conditional_edges("kernel", dynamic_router)

    return builder.compile(checkpointer=checkpointer)
