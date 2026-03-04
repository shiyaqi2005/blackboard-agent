from langgraph_kernel.types import DataSchema, JsonPatch, KernelState, WorkflowRules

# 延迟导入，避免在模块加载时导入 langgraph
def __getattr__(name):
    if name == "build_kernel_graph":
        from langgraph_kernel.graph import build_kernel_graph
        return build_kernel_graph
    elif name == "build_dynamic_kernel_graph":
        from langgraph_kernel.graph import build_dynamic_kernel_graph
        return build_dynamic_kernel_graph
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

__all__ = [
    "DataSchema",
    "JsonPatch",
    "KernelState",
    "WorkflowRules",
    "build_kernel_graph",
    "build_dynamic_kernel_graph",
]
