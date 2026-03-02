from __future__ import annotations

from typing import Any

from langchain_core.language_models import BaseChatModel
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph import END, START, StateGraph

from langgraph_kernel.architect.agent import ArchitectAgent
from langgraph_kernel.kernel.node import kernel_node
from langgraph_kernel.kernel.router import WorkflowRouter
from langgraph_kernel.types import KernelState
from langgraph_kernel.worker.base import BaseWorkerAgent


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
