from __future__ import annotations

from langgraph_kernel.kernel.patch_fixer import PatchFixer, PatchFixerConfig
from langgraph_kernel.types import KernelState

# 创建修复器实例（启用所有自动修复功能）
_fixer = PatchFixer(
    config=PatchFixerConfig(
        fix_structure=True,
        fix_spelling=True,
        fix_path_format=True,
        auto_switch_add_replace=True,
        create_missing_parents=False,  # 保守策略
        fix_type_mismatch=True,
        fuzzy_match_enum=True,
        fuzzy_match_threshold=0.8,
        skip_invalid_operations=False,
    )
)

# Layer 5 配置
MAX_RETRIES = 2  # 最多重试次数


def kernel_node(state: KernelState) -> dict:
    """
    Kernel 核心节点：
    1. 若无 pending_patch，直接跳过（首次进入）
    2. 使用 PatchFixer 自动修复常见错误（Layer 1-4）
    3. 验证 patch 是否符合 data_schema
    4. 如果失败且未超过重试次数，生成错误反馈并请求重试（Layer 5）
    5. 应用 patch 更新 domain_state
    6. 清空 pending_patch，写入 patch_error，递增 step_count
    """
    patch = state.get("pending_patch") or []
    if not patch:
        return {
            "patch_error": "",
            "step_count": state.get("step_count", 0),
            "retry_count": 0,
            "error_feedback": "",
        }

    # 使用修复器进行自动修复和验证（Layer 1-4）
    new_state, error, logs = _fixer.fix_and_validate(
        patch,
        state["domain_state"],
        state["data_schema"],
    )

    # 打印修复日志（如果有）
    if logs:
        print(f"\n🔧 Patch 自动修复 (Layer 1-4):")
        for log in logs:
            print(f"  {log}")

    # Layer 5: 如果修复失败，检查是否可以重试
    retry_count = state.get("retry_count", 0)

    if error and retry_count < MAX_RETRIES:
        # 生成详细的错误反馈
        error_feedback = _fixer.generate_error_report()
        if not error_feedback or error_feedback == "No errors":
            error_feedback = f"Error: {error}"

        print(f"\n🔄 Layer 5: 自动修复失败，请求 worker 重试 (尝试 {retry_count + 1}/{MAX_RETRIES})")
        print(f"📋 错误反馈:\n{error_feedback}")

        # 返回状态，触发重试
        return {
            "domain_state": state["domain_state"],  # 保持原状态
            "pending_patch": [],  # 清空 patch
            "patch_error": "",  # 清空错误（允许继续）
            "step_count": state.get("step_count", 0),  # 不增加步数
            "retry_count": retry_count + 1,  # 增加重试计数
            "error_feedback": error_feedback,  # 设置错误反馈
        }

    # 成功或重试次数用尽
    if error:
        print(f"\n❌ Layer 5: 已达到最大重试次数 ({MAX_RETRIES})，放弃修复")

    return {
        "domain_state": new_state,
        "pending_patch": [],
        "patch_error": error or "",
        "step_count": state.get("step_count", 0) + 1,
        "retry_count": 0,  # 重置重试计数
        "error_feedback": "",  # 清空错误反馈
    }
