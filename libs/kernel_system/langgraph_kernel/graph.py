from __future__ import annotations

from typing import Any, Dict

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
    # 创建通用 worker 节点的 input schema
    class DynamicInputSchema(TypedDict):
        domain_state: dict
        worker_instructions: Dict[str, str]
        current_worker: str
        data_schema: dict  # 添加 schema 信息用于类型检查

    # 通用 worker 节点
    def universal_worker_node(state: dict[str, Any]) -> dict[str, Any]:
        """通用 worker 节点，根据 current_worker 字段执行相应的 worker"""
        worker_name = state.get("current_worker", "")
        instruction = state.get("worker_instructions", {}).get(worker_name, "")

        if not instruction:
            return {
                "pending_patch": [],
                "patch_error": f"No instruction found for worker: {worker_name}",
            }

        # 创建临时 worker 实例
        worker = LLMWorkerAgent(llm, instruction=instruction)
        worker.input_schema = DynamicInputSchema

        # 执行 worker
        return worker(state)

    # 动态路由：使用 WorkflowRouter 实现三层终止机制
    # 注意：这里 worker_names 是动态的，所以我们传入一个空列表
    # Router 会根据 workflow_rules 动态匹配
    router = WorkflowRouter(
        worker_names=[],  # 动态 worker，不预定义
        max_steps=max_steps,
        max_no_update=2,
        loop_detection_window=3,
    )

    def dynamic_router(state: KernelState) -> str:
        """根据 workflow_rules 动态路由到 worker"""
        # 使用 WorkflowRouter 的路由逻辑
        result = router.route(state)

        # 如果 router 返回的是 worker 名称（而不是 END），返回 "worker" 节点
        if result != END:
            return "worker"
        return END

    # 设置 current_worker 的中间节点
    def set_current_worker(state: KernelState) -> dict[str, Any]:
        """在路由到 worker 之前，设置 current_worker 字段"""
        workflow_rules = state.get("workflow_rules", {})
        domain_state = state.get("domain_state", {})

        for field_name, rules in workflow_rules.items():
            current_value = domain_state.get(field_name)
            if current_value in rules:
                worker_name = rules[current_value]
                return {"current_worker": worker_name}

        return {"current_worker": ""}

    builder = StateGraph(KernelState)

    # 添加节点
    builder.add_node("architect", ArchitectAgent(llm))
    builder.add_node("kernel", kernel_node)
    builder.add_node("set_worker", set_current_worker)
    builder.add_node("worker", universal_worker_node, input_schema=DynamicInputSchema)

    # 添加边
    builder.add_edge(START, "architect")
    builder.add_edge("architect", "kernel")

    # 条件边：从 kernel 到 set_worker 或 END
    builder.add_conditional_edges(
        "kernel",
        dynamic_router,
        {"worker": "set_worker", END: END}
    )

    builder.add_edge("set_worker", "worker")
    builder.add_edge("worker", "kernel")

    return builder.compile(checkpointer=checkpointer)
