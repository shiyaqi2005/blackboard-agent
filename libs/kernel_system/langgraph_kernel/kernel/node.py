from __future__ import annotations

from langgraph_kernel.kernel.validator import PatchValidator
from langgraph_kernel.types import KernelState

_validator = PatchValidator()


def kernel_node(state: KernelState) -> dict:
    """
    Kernel 核心节点：
    1. 若无 pending_patch，直接跳过（首次进入）
    2. 验证 patch 是否符合 data_schema
    3. 应用 patch 更新 domain_state
    4. 清空 pending_patch，写入 patch_error，递增 step_count
    """
    patch = state.get("pending_patch") or []
    if not patch:
        return {"patch_error": "", "step_count": state.get("step_count", 0)}

    new_state, error = _validator.validate(
        state["domain_state"],
        patch,
        state["data_schema"],
    )

    return {
        "domain_state": new_state,
        "pending_patch": [],
        "patch_error": error or "",
        "step_count": state.get("step_count", 0) + 1,
    }
