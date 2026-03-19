# 实验运行手册

最后更新时间：2026-03-16

## 1. 适用范围

这份 runbook 现在覆盖 `experiment.md` 的六类实验，但要先说明边界：

- **当前最成熟、已经产出真实结果的主线仍然是 ALFWorld**
- **WebArena 相关代码已经接入实验目录，最小 `script_browser` smoke 已经跑通**
- **WebArena 侧当前实验 2 / 3 / 6 都已有 `reference_oracle` 版评估链路，但 `script_browser` 正式结果仍待补齐**
- **对照组当前按最新约定使用 `langgraph` 和 `autogen`，不再把 `CrewAI` 作为当前 runbook 的默认对照组**
- **第三数据集当前已确定为 `ScienceWorld`，基础 compare + ablation scaffolding 已接入，最小真实 compare 已验证**
- **实验 1 的通信分析产物现在已经可以自动导出 `comm_summary.json`、`comm_trace.jsonl`、`comm_judge.jsonl`**
- 因此，`experiment.md` 中实验 1 / 3 / 4 / 5 / 6 的当前执行策略是：
  - `ALFWorld`：已经有可复用 runner 和已跑结果
  - `WebArena`：已经有 task set / compare / analysis / official prompt baseline 代码路径，且已完成最小 smoke 验证；实验 2 / 3 / 6 在 `reference_oracle` 下已可运行，但正式结果仍待补齐
    - 最小 smoke：`experiment/common/task_sets/webarena_script_browser_smoke.json`
    - 真实本地 live subset：`experiment/common/task_sets/webarena_live_debug.json`
  - `ScienceWorld`：已经确定为实验 4 / 5 / 6 的第三数据集，基础 compare + ablation scaffolding 已接入，最小真实运行已验证

当前已经完成或补齐的重要点：

- ALFWorld 真实数据链路已打通
- Experiment 2 的 schema-guard 注入评估已跑通
- C2 / C3 的 debug 与 formal 消融已完成
- `planner_action` / `planner_llm_action` 的 workflow runner 已具备
- 固定同一组 `gamefiles` 的 workflow compare runner 已具备
- `planner_llm_action + real provider` 的 `full vs ablate_c1` 小规模消融已完成
- `planner_llm_action + real provider` 的 `ablate_c4` 小规模实验已完成
- `planner_llm_action` 已完成两轮真实小样本策略优化回归
- `architect_mode=llm` 的 ALFWorld `LLM architect` 路径已接通
- `state_bridge` 已显式注入 canonical task metadata（来自 `traj_data.json / pddl_params`）
- **C4 在 ALFWorld adapter 中现已完整接线**
- **LLM token 统计链路现已接通：`SimpleChatModel -> architect/worker -> adapter -> episode summary`**
- 结果按 task family 的分析工具现已补齐：`run_result_analysis.py`
- **WebArena `official_prompt` 默认 smoke manifest 已切到非登录 `script_browser_smoke`**
- **WebArena live preflight 现在会继续输出完整 readiness 报告，而不是只在缺少 `0.json~3.json` 时直接终止**

仍然存在的硬边界：

- **真实 LLM provider 当前可用，但更大规模实验仍受 token 成本 / 额度约束**
- **ALFWorld 的 C5 现在已经有可执行的 `LLM architect` 路径，但仍是受控版本**
  - 使用 `--architect-mode llm` 时，`full` 会走 `LLMALFWorldArchitect`
  - `ablate_c5` 会自动回退到确定性的 `ALFWorldArchitect`
  - 当前 workflow 拓扑仍由 `--workflow-mode` 约束，不是完全自由编排的 architect

## 2. 固定环境

工作目录：

- `/home/syq/Documents/blackboard`

conda 环境：

- `blackboard`

ALFWorld 仓库：

- `/home/syq/Documents/blackboard/alfworld`

ALFWorld 数据目录：

- `/home/syq/.cache/alfworld`
- `/home/syq/.cache/alfworld/json_2.1.1/valid_seen`

推荐环境变量：

```bash
conda activate blackboard
export ALFWORLD_DATA=/home/syq/.cache/alfworld
export PYTHONPATH=/home/syq/Documents/blackboard/alfworld:/home/syq/Documents/blackboard/blackboard/libs/kernel_system:/home/syq/Documents/blackboard/blackboard/libs/blackboard:/home/syq/Documents/blackboard/experiment/alfworld
```

如果不想手动 `activate`，也可以直接用 `conda run -n blackboard ...`。

## 3. 当前代码状态与快速检查

### 3.1 关键脚本

- `experiment/alfworld/examples/run_capture_states.py`
- `experiment/alfworld/examples/run_schema_guard_eval.py`
- `experiment/alfworld/examples/run_ablation.py`
- `experiment/alfworld/examples/run_workflow_compare.py`
- `experiment/alfworld/examples/run_result_analysis.py`

### 3.2 本轮新增/确认可用的能力

- `run_result_analysis.py` 可以把 `ablation_summary.json` / `workflow_compare_summary.json` 转成按 task family 的分析报告
- `run_ablation.py` 和 `run_workflow_compare.py` 的 episode summary 现在可以记录真实 LLM token（前提是真实 provider 返回 usage）
- `ablate_c4` 在 ALFWorld adapter 中已完整生效
- `run_ablation.py` 和 `run_workflow_compare.py` 现已支持 `--architect-mode llm`
- `ablate_c5` 现在可以在 ALFWorld 上形成真实有效的 `full vs deterministic architect` 对照

### 3.3 本轮增量测试

已验证通过：

- `experiment/alfworld/tests/test_adapter.py`
- `experiment/alfworld/tests/test_llm_factory.py`
- `experiment/alfworld/tests/test_ablation_runner.py`
- `experiment/alfworld/tests/test_result_analysis.py`
- `experiment/alfworld/tests/test_workers.py`
- `experiment/alfworld/tests/test_state_bridge.py`
- `experiment/alfworld/tests/test_m1_infrastructure.py`

最近一次组合结果：

- `107 passed`

历史全量实验测试记录：

- `experiment/alfworld/tests` 当前最新一次为 `107 passed`

如果要重新回归：

```bash
env PYTHONPATH=/home/syq/Documents/blackboard/blackboard/libs/kernel_system:/home/syq/Documents/blackboard/blackboard/libs/blackboard:/home/syq/Documents/blackboard/experiment/alfworld \
conda run -n blackboard python -m pytest experiment/alfworld/tests -q
```

## 4. 真实 provider 环境变量检查

真实 LLM 目前仍依赖下面这些变量中的一组：

- `ALFWORLD_LLM_MODEL`
- `ALFWORLD_LLM_BASE_URL`
- `ALFWORLD_LLM_API_KEY`

兼容回退：

- `OPENAI_MODEL_NAME` 或 `OPENAI_MODEL`
- `OPENAI_BASE_URL`
- `OPENAI_API_KEY`

检查命令：

```bash
conda run -n blackboard python -c "import os; print('api_key', int(bool(os.getenv('ALFWORLD_LLM_API_KEY') or os.getenv('OPENAI_API_KEY')))); print('base_url', int(bool(os.getenv('ALFWORLD_LLM_BASE_URL') or os.getenv('OPENAI_BASE_URL')))); print('model', int(bool(os.getenv('ALFWORLD_LLM_MODEL') or os.getenv('OPENAI_MODEL_NAME') or os.getenv('OPENAI_MODEL'))))"
```

如果不是三项都为 `1`，就不能产出真实 provider 结果。

## 5. 实验 1：通信效率与信息密度对比

### 5.1 在当前仓库里的落地方式

`experiment.md` 原意是比较结构化通信 vs 自然语言通信。

当前按最新设计，对应为：

- 实验组：`blackboard full`
  - 开启 `C1 = JSON Patch 通信`
- 组内消融对照：`blackboard ablate_c1`
  - 关闭 `C1`，退化为自然语言/非结构化通信
- 外部对照组：
  - `langgraph`
  - `autogen`

当前 runbook 不再把 `CrewAI` 作为实验 1 的默认对照组。

建议 workflow：

- `planner_llm_action`

核心指标：

- `mean_total_tokens`
- `mean_patch_error_rate`
- `mean_fallback_rate`
- `success_rate`
- `mean_steps`

### 5.2 当前状态

- 代码与 runner 已具备
- token 统计链路已接通
- 已完成一轮真实小规模 C1 消融：
  - `experiment/alfworld/outputs/planner_llm_ablation_real_limit3_steps10/full/full_summary.json`
  - `experiment/alfworld/outputs/planner_llm_ablation_real_limit3_steps10/ablate_c1/ablate_c1_summary.json`
- 当前真实结果：
  - `full`
    - `n_episodes = 3`
    - `success_rate = 0.333`
    - `mean_steps = 8.333`
    - `mean_total_tokens = 21018.0`
    - `circuit_breaker_trigger_rate = 0.000`
  - `ablate_c1`
    - `n_episodes = 3`
    - `success_rate = 0.000`
    - `mean_steps = 3.000`
    - `mean_total_tokens = 6150.667`
    - `mean_fallback_rate = 1.000`
    - `circuit_breaker_trigger_rate = 1.000`
- 当前可解释结论：
  1. 真实 provider 下，关闭 `C1` 后动作质量显著下降
  2. `ablate_c1` 已退化为“自然语言无法稳定落到可执行动作”，fallback 拉满
- 现有 `planner_llm_action + mock` 只能证明基础设施，不足以支撑实验 1 的正式结论

### 5.3 最小运行命令

```bash
env ALFWORLD_DATA=/home/syq/.cache/alfworld \
PYTHONPATH=/home/syq/Documents/blackboard/alfworld:/home/syq/Documents/blackboard/blackboard/libs/kernel_system:/home/syq/Documents/blackboard/blackboard/libs/blackboard:/home/syq/Documents/blackboard/experiment/alfworld \
conda run -n blackboard python experiment/alfworld/examples/run_ablation.py \
  --data-root /home/syq/.cache/alfworld/json_2.1.1/valid_seen \
  --output-dir /home/syq/Documents/blackboard/experiment/alfworld/outputs/exp1_comm_debug_real \
  --split debug \
  --max-steps 20 \
  --workflow-mode planner_llm_action \
  --modes full,ablate_c1 \
  --llm-backend openai_compatible
```

分析命令：

```bash
env PYTHONPATH=/home/syq/Documents/blackboard/blackboard/libs/kernel_system:/home/syq/Documents/blackboard/blackboard/libs/blackboard:/home/syq/Documents/blackboard/experiment/alfworld \
conda run -n blackboard python experiment/alfworld/examples/run_result_analysis.py \
  --summary-file /home/syq/Documents/blackboard/experiment/alfworld/outputs/exp1_comm_debug_real/ablation_summary.json
```

## 6. 实验 2：Schema 强制校验对比实验

### 6.1 当前状态

这个实验是当前完成度最高的一项，已经在真实 ALFWorld 数据上跑通。

已验证链路：

1. 从真实 ALFWorld 数据集中采样任务
2. 运行 `capture_states`
3. 把 `states.jsonl` 输入 `run_schema_guard_eval.py`
4. 输出注入评估结果

### 6.2 已完成真实 smoke

capture 命令：

```bash
env ALFWORLD_DATA=/home/syq/.cache/alfworld \
PYTHONPATH=/home/syq/Documents/blackboard/alfworld:/home/syq/Documents/blackboard/blackboard/libs/kernel_system:/home/syq/Documents/blackboard/blackboard/libs/blackboard:/home/syq/Documents/blackboard/experiment/alfworld \
conda run -n blackboard python experiment/alfworld/examples/run_capture_states.py \
  --data-root /home/syq/.cache/alfworld/json_2.1.1/valid_seen \
  --output-dir /home/syq/Documents/blackboard/experiment/alfworld/outputs/exp1_real_smoke \
  --run-id real_smoke \
  --split debug \
  --max-steps 1
```

schema-guard 命令：

```bash
env ALFWORLD_DATA=/home/syq/.cache/alfworld \
PYTHONPATH=/home/syq/Documents/blackboard/alfworld:/home/syq/Documents/blackboard/blackboard/libs/kernel_system:/home/syq/Documents/blackboard/blackboard/libs/blackboard:/home/syq/Documents/blackboard/experiment/alfworld \
conda run -n blackboard python experiment/alfworld/examples/run_schema_guard_eval.py \
  --states-file /home/syq/Documents/blackboard/experiment/alfworld/outputs/exp1_real_smoke/real_smoke_states.jsonl \
  --output-dir /home/syq/Documents/blackboard/experiment/alfworld/outputs/exp2_real_smoke
```

### 6.3 已有结果

- `12` 个真实 states
- `60` 个 injection cases
- `C2 on interception_rate = 1.000`
- `C2 off interception_rate = 0.000`

输出文件：

- `experiment/alfworld/outputs/exp2_real_smoke/schema_guard_metrics.json`
- `experiment/alfworld/outputs/exp2_real_smoke/schema_guard_cases.jsonl`

### 6.4 formal 版本

```bash
env ALFWORLD_DATA=/home/syq/.cache/alfworld \
PYTHONPATH=/home/syq/Documents/blackboard/alfworld:/home/syq/Documents/blackboard/blackboard/libs/kernel_system:/home/syq/Documents/blackboard/blackboard/libs/blackboard:/home/syq/Documents/blackboard/experiment/alfworld \
conda run -n blackboard python experiment/alfworld/examples/run_capture_states.py \
  --data-root /home/syq/.cache/alfworld/json_2.1.1/valid_seen \
  --output-dir /home/syq/Documents/blackboard/experiment/alfworld/outputs/exp1_formal \
  --run-id formal_capture \
  --split formal \
  --max-steps 20
```

然后：

```bash
env ALFWORLD_DATA=/home/syq/.cache/alfworld \
PYTHONPATH=/home/syq/Documents/blackboard/alfworld:/home/syq/Documents/blackboard/blackboard/libs/kernel_system:/home/syq/Documents/blackboard/blackboard/libs/blackboard:/home/syq/Documents/blackboard/experiment/alfworld \
conda run -n blackboard python experiment/alfworld/examples/run_schema_guard_eval.py \
  --states-file /home/syq/Documents/blackboard/experiment/alfworld/outputs/exp1_formal/formal_capture_states.jsonl \
  --output-dir /home/syq/Documents/blackboard/experiment/alfworld/outputs/exp2_formal
```

## 7. 实验 3：Context Slicing 对比实验

### 7.1 在当前仓库里的落地方式

对应消融：

- 实验组：`full`
- 对照组：`ablate_c4`

建议 workflow：

- `planner_llm_action`

核心指标：

- `success_rate`
- `mean_steps`
- `mean_total_tokens`
- `mean_patch_error_rate`
- `mean_fallback_rate`
- task family robustness（通过分析脚本得到）

### 7.2 当前状态

- **C4 在 ALFWorld adapter 里现在已经完整接线**
- deterministic `single_action` 路径下，C4 差异通常不明显
- 真正有研究价值的是 `planner_llm_action + real provider`
- 已完成一轮真实 provider 的 `ablate_c4` 小规模实验
- 运行配置：
  - `workflow_mode=planner_llm_action`
  - `limit=3`
  - `max_steps=10`
  - `gamefiles` 与 `workflow_compare_debug_real_limit3_steps10` 保持一致
- 输出文件：
  - `experiment/alfworld/outputs/planner_llm_ablate_c4_real_limit3_steps10_rerun/ablate_c4/ablate_c4_summary.json`
  - `experiment/alfworld/outputs/planner_llm_ablate_c4_real_limit3_steps10_rerun/ablation_summary.json`
  - `experiment/alfworld/outputs/planner_llm_ablate_c4_real_limit3_steps10_rerun/ablation_summary_analysis.json`
- 结果：
  - `ablate_c4.success_rate = 0.333`
  - `ablate_c4.mean_steps = 8.333`
  - `ablate_c4.mean_total_tokens = 22994.667`
  - `ablate_c4.stop_reason_breakdown = {environment_done: 1, max_steps_reached: 2}`
- 与同一批任务上的 `full` 对照相比：
  - `full.success_rate = 0.333`
  - `full.mean_steps = 8.333`
  - `full.mean_total_tokens = 21018.0`
  - 在这个 3-task slice 上，关闭 C4 没有改变成功率和步数，但额外增加了约 `1976.667` 平均 token
- 当前解释：
  - 这批结果更像是在说明 C4 主要影响上下文效率，而不是在这个极小样本上直接决定成功率
  - 这是基于 `n=3` 的小规模真实实验结论，后续仍应扩大样本验证

### 7.3 运行命令

```bash
env ALFWORLD_DATA=/home/syq/.cache/alfworld \
PYTHONPATH=/home/syq/Documents/blackboard/alfworld:/home/syq/Documents/blackboard/blackboard/libs/kernel_system:/home/syq/Documents/blackboard/blackboard/libs/blackboard:/home/syq/Documents/blackboard/experiment/alfworld \
conda run -n blackboard python experiment/alfworld/examples/run_ablation.py \
  --data-root /home/syq/.cache/alfworld/json_2.1.1/valid_seen \
  --output-dir /home/syq/Documents/blackboard/experiment/alfworld/outputs/exp3_context_debug_real \
  --split debug \
  --max-steps 20 \
  --workflow-mode planner_llm_action \
  --modes full,ablate_c4 \
  --llm-backend openai_compatible
```

如果要复现实验 3 当前已经完成的真实小规模结果，使用这条命令：

```bash
env ALFWORLD_DATA=/home/syq/.cache/alfworld \
PYTHONPATH=/home/syq/Documents/blackboard/alfworld:/home/syq/Documents/blackboard/blackboard/libs/kernel_system:/home/syq/Documents/blackboard/blackboard/libs/blackboard:/home/syq/Documents/blackboard/experiment/alfworld \
conda run -n blackboard python experiment/alfworld/examples/run_ablation.py \
  --data-root /home/syq/.cache/alfworld/json_2.1.1/valid_seen \
  --gamefiles-file /home/syq/Documents/blackboard/experiment/alfworld/outputs/workflow_compare_debug_real_limit3_steps10/selected_gamefiles.json \
  --output-dir /home/syq/Documents/blackboard/experiment/alfworld/outputs/planner_llm_ablate_c4_real_limit3_steps10_rerun \
  --split debug \
  --max-steps 10 \
  --workflow-mode planner_llm_action \
  --modes ablate_c4 \
  --llm-backend openai_compatible
```

分析命令：

```bash
env PYTHONPATH=/home/syq/Documents/blackboard/blackboard/libs/kernel_system:/home/syq/Documents/blackboard/blackboard/libs/blackboard:/home/syq/Documents/blackboard/experiment/alfworld \
conda run -n blackboard python experiment/alfworld/examples/run_result_analysis.py \
  --summary-file /home/syq/Documents/blackboard/experiment/alfworld/outputs/exp3_context_debug_real/ablation_summary.json
```

## 8. 实验 4：泛化性

### 8.1 在当前仓库里的落地方式

`experiment.md` 原始设想是跨知识领域 / 跨数据集泛化。

按最新约定，实验 4 的目标数据集应为：

- `ALFWorld`
- `WebArena`
- `ScienceWorld`

当前代码与结果状态要分开看：

- `ALFWorld`：已经有可执行结果，因此目前这一节已有结论主要来自 ALFWorld
- `WebArena`：最小 live smoke 已完成，实验 2 / 3 / 6 已有 `reference_oracle` 版评估链路，但正式 compare 结果仍未补齐
- `ScienceWorld`：基础 compare + ablation scaffolding 已接入，最小 compare 已跑通，正式运行规模仍待扩展
- 三数据集统一汇总入口已补齐：
  - `experiment/common/run_cross_dataset_analysis.py`
  - `experiment/run/run_multidataset_experiments.sh`

因此，当前这一节的**已产出版本**仍然主要是：

- 在 ALFWorld 六类 task family 上统计分组结果
- 用 task family 间的性能方差近似衡量 robustness

后续补齐 WebArena 正式结果并跑出 ScienceWorld 正式规模后，需要把这一节扩成真正的跨数据集泛化结果。

当前 task family：

- `pick_and_place`
- `pick_clean_then_place`
- `pick_heat_then_place`
- `pick_cool_then_place`
- `look_at_obj`
- `pick_two_obj`

robustness 指标：

- `success_rate_std`
- `goal_condition_rate_std`
- `mean_steps_std`

### 8.2 已有 ALFWorld formal 结果

已有分析文件：

- `experiment/alfworld/outputs/ablation_formal_20/ablation_summary_analysis.json`

其中：

- `full`
  - `success_rate_std = 0.1862`
  - `mean_steps_std = 0.9852`
- `ablate_c3`
  - `success_rate_std = 0.2530`
  - `mean_steps_std = 2.6235`

当前基于 ALFWorld 的可解释结论：

1. 在 formal 规模真实 ALFWorld 上，关闭 `C3` 会显著增加不同 task family 之间的性能波动
2. 当前 deterministic 系统在 task family 维度上并不均匀
3. `pick_clean_then_place` / `pick_heat_then_place` 明显好于 `pick_and_place` / `pick_two_obj`

### 8.3 当前运行与分析方式

下面这组命令当前对应的是 **ALFWorld 子集**。

后续补 WebArena 正式结果与 ScienceWorld 时，应把这一节扩展为：

- `ALFWorld`
- `WebArena`
- `ScienceWorld`

运行：

```bash
env ALFWORLD_DATA=/home/syq/.cache/alfworld \
PYTHONPATH=/home/syq/Documents/blackboard/alfworld:/home/syq/Documents/blackboard/blackboard/libs/kernel_system:/home/syq/Documents/blackboard/blackboard/libs/blackboard:/home/syq/Documents/blackboard/experiment/alfworld \
conda run -n blackboard python experiment/alfworld/examples/run_ablation.py \
  --data-root /home/syq/.cache/alfworld/json_2.1.1/valid_seen \
  --output-dir /home/syq/Documents/blackboard/experiment/alfworld/outputs/exp4_generalization_formal \
  --split formal \
  --max-steps 20 \
  --modes full
```

分析：

```bash
env PYTHONPATH=/home/syq/Documents/blackboard/blackboard/libs/kernel_system:/home/syq/Documents/blackboard/blackboard/libs/blackboard:/home/syq/Documents/blackboard/experiment/alfworld \
conda run -n blackboard python experiment/alfworld/examples/run_result_analysis.py \
  --summary-file /home/syq/Documents/blackboard/experiment/alfworld/outputs/exp4_generalization_formal/ablation_summary.json
```

### 8.4 三数据集统一汇总入口

实验 4 / 5 / 6 现在都可以用统一脚本把三套环境的 summary 聚合成一份 cross-dataset 报告。

脚本：

- `experiment/run/run_multidataset_experiments.sh`
- `experiment/common/run_cross_dataset_analysis.py`

用法：

```bash
bash /home/syq/Documents/blackboard/experiment/run/run_multidataset_experiments.sh \
  exp4 \
  /path/to/alfworld/system_compare_summary.json \
  /path/to/webarena/system_compare_summary.json \
  /path/to/scienceworld/system_compare_summary.json
```

```bash
bash /home/syq/Documents/blackboard/experiment/run/run_multidataset_experiments.sh \
  exp5 \
  /path/to/alfworld/system_compare_summary.json \
  /path/to/webarena/system_compare_summary.json \
  /path/to/scienceworld/system_compare_summary.json
```

```bash
bash /home/syq/Documents/blackboard/experiment/run/run_multidataset_experiments.sh \
  exp6 \
  /path/to/alfworld/ablation_summary.json \
  /path/to/webarena/ablation_summary.json \
  /path/to/scienceworld/ablation_summary.json
```

输出：

- `experiment/common/outputs/<exp>_cross_dataset_<timestamp>.json`
- `experiment/common/outputs/<exp>_cross_dataset_<timestamp>.md`

## 9. 实验 5：准确性

### 9.1 在当前仓库里的落地方式

按最新约定，实验 5 的目标数据集应为：

- `ALFWorld`
- `WebArena`
- `ScienceWorld`

当前已落地的版本主要还是 ALFWorld，对应为：

- 固定同一批 `gamefiles`
- 比较不同 workflow 的最终任务完成表现

WebArena 与 ScienceWorld 已接到同一套 compare + analysis 协议下，但正式结果仍待补齐。

推荐 workflow compare：

- `single_action`
- `planner_action`
- `planner_llm_action`

核心指标：

- `success_rate`
- `mean_steps`
- `stop_reason_breakdown`
- task family 分组准确率

### 9.2 已有 ALFWorld debug mock 结果

已有输出：

- `experiment/alfworld/outputs/workflow_compare_debug_mock/workflow_compare_summary.json`
- `experiment/alfworld/outputs/workflow_compare_debug_mock/workflow_compare_summary_analysis.json`

关键结果：

- `single_action`
  - `success_rate = 0.500`
  - `mean_steps = 8.917`
- `planner_action`
  - `success_rate = 0.500`
  - `mean_steps = 8.917`
- `planner_llm_action + mock`
  - `success_rate = 0.000`
  - `mean_steps = 10.667`

当前结论：

1. compare runner 已经可用
2. `single_action` 与 `planner_action` 仍基本一致
3. `planner_llm_action + mock` 只能证明链路，不代表真实准确率

### 9.3 已有 ALFWorld 真实 provider 小规模结果

已完成输出：

- `experiment/alfworld/outputs/workflow_compare_debug_real_limit3_steps10/workflow_compare_summary.json`
- `experiment/alfworld/outputs/workflow_compare_debug_real_limit3_steps10/workflow_compare_summary_analysis.json`

配置：

- `limit = 3`
- `max_steps = 10`

真实结果：

- `single_action`
  - `success_rate = 0.333`
  - `mean_steps = 8.333`
  - `circuit_breaker_trigger_rate = 0.333`
- `planner_action`
  - `success_rate = 0.333`
  - `mean_steps = 8.333`
  - `circuit_breaker_trigger_rate = 0.333`
- `planner_llm_action`
  - `success_rate = 0.333`
  - `mean_steps = 8.333`
  - `mean_total_tokens = 20808.667`
  - `circuit_breaker_trigger_rate = 0.000`

当前可解释结论：

1. 真实 provider 已经确认可用，token 统计也已经非零
2. 在这 3 个 task 上，`planner_llm_action` 还没有提高成功率
3. 但它把一部分终止模式从 `stagnation_detected` 变成了 `max_steps_reached`
4. 这说明当前真实 LLM 已经能做更长的结构化探索，但搜索效率还不够

### 9.3.1 最新优化版 `planner_llm_action` 开发集结果

为了让实验组系统本身变强，已经在 `planner_llm_action` 上做了两轮针对性优化：

- 第一轮：加入 `searched_locations` / `failed_search_locations` / `recommended_actions` / `search_guidance`
- 第二轮：加入 `goal_object_guidance`，在 `task_goal` 文本和 `focus_object` 冲突时，强制以 planner 的规范目标对象为准

相关代码：

- `experiment/alfworld/workers/planner_worker.py`
- `experiment/alfworld/workers/llm_action_worker.py`
- `experiment/alfworld/workers/alfworld_architect.py`

真实输出：

- 第一轮搜索优化：
  - `experiment/alfworld/outputs/planner_llm_ablation_real_limit3_steps10_search_guidance/full/full_summary.json`
- 第二轮对象消歧优化：
  - `experiment/alfworld/outputs/planner_llm_ablation_real_limit3_steps10_search_guidance_v2/full/full_summary.json`
  - `experiment/alfworld/outputs/planner_llm_ablation_real_limit3_steps10_search_guidance_v2/ablation_summary.json`
  - `experiment/alfworld/outputs/planner_llm_ablation_real_limit3_steps10_search_guidance_v2/ablation_summary_analysis.json`

同一批 3-task slice 上，`planner_llm_action full` 的演进结果：

- 旧版 `full`
  - `success_rate = 0.333`
  - `mean_steps = 8.333`
  - `mean_total_tokens = 21018.0`
- 第一轮搜索优化后
  - `success_rate = 0.667`
  - `mean_steps = 9.667`
  - `mean_total_tokens = 29022.0`
- 第二轮对象消歧后
  - `success_rate = 1.000`
  - `mean_steps = 7.333`
  - `mean_total_tokens = 22390.333`

当前解释：

1. 搜索记忆与 pivot 规则，直接修复了 knife 任务从”连续开抽屉失败”到”优先去 countertop 并快速成功”的问题
2. `goal_object_guidance` 修复了 `task_goal=spoon` 但 `PDDL object_target=Ladle` 的冲突任务
3. 这说明实验组系统仍然有明显的 prompt / policy 可优化空间
4. 但这些结果目前只覆盖 `planner_llm_action full`，还没有重新跑完整的 `workflow_compare`

### 9.3.2 最新优化版完整 workflow_compare 结果

在同一批 3 个 gamefile 上，用最新代码重跑了完整三路 `workflow_compare`：

- 输出目录：`experiment/alfworld/outputs/workflow_compare_debug_real_limit3_steps10_search_guidance_v2`
- 配置：`limit=3, max_steps=10, split=debug, llm=deepseek-v3`

运行命令：

```bash
env ALFWORLD_DATA=/home/syq/.cache/alfworld \
ALFWORLD_LLM_MODEL=deepseek-v3 \
ALFWORLD_LLM_BASE_URL=https://tb.api.mkeai.com/v1 \
ALFWORLD_LLM_API_KEY=<key> \
PYTHONPATH=/home/syq/Documents/blackboard/alfworld:/home/syq/Documents/blackboard/blackboard/libs/kernel_system:/home/syq/Documents/blackboard/blackboard/libs/blackboard:/home/syq/Documents/blackboard/experiment/alfworld \
conda run -n blackboard python experiment/alfworld/examples/run_workflow_compare.py \
  --data-root /home/syq/.cache/alfworld/json_2.1.1/valid_seen \
  --gamefiles-file /home/syq/Documents/blackboard/experiment/alfworld/outputs/workflow_compare_debug_real_limit3_steps10/selected_gamefiles.json \
  --output-dir /home/syq/Documents/blackboard/experiment/alfworld/outputs/workflow_compare_debug_real_limit3_steps10_search_guidance_v2 \
  --split debug \
  --max-steps 10 \
  --modes full \
  --workflow-modes single_action,planner_action,planner_llm_action \
  --llm-backend openai_compatible
```

结果：

- `single_action`
  - `success_rate = 0.333`
  - `mean_steps = 8.333`
  - `circuit_breaker_trigger_rate = 0.333`
  - `stop_reason_breakdown = {stagnation_detected: 4, max_steps_reached: 4, environment_done: 4}`
- `planner_action`
  - `success_rate = 0.333`
  - `mean_steps = 8.333`
  - `circuit_breaker_trigger_rate = 0.333`
  - `stop_reason_breakdown = {stagnation_detected: 4, max_steps_reached: 4, environment_done: 4}`
- `planner_llm_action`
  - `success_rate = 1.000`
  - `mean_steps = 7.333`
  - `mean_total_tokens = 23329.0`
  - `circuit_breaker_trigger_rate = 0.000`
  - `stop_reason_breakdown = {environment_done: 6}`（全部正常完成，无截停）

输出文件：

- `experiment/alfworld/outputs/workflow_compare_debug_real_limit3_steps10_search_guidance_v2/workflow_compare_summary.json`
- `experiment/alfworld/outputs/workflow_compare_debug_real_limit3_steps10_search_guidance_v2/workflow_compare_summary_analysis.json`

当前结论：

1. 优化后的 `planner_llm_action` 在同一批任务上从 0.333 提升到 1.000，完整 workflow_compare 首次验证通过
2. `single_action` 与 `planner_action` 仍然完全一致，说明确定性 planner 对 deterministic action 没有增益
3. `planner_llm_action` 无任何熔断触发，动作质量稳定
4. 注意：`planner_llm_action` 只跑了 6 个 episode（3 gamefile × 2 轮），deterministic 模式跑了 12 个，样本量不完全对等，需要更大规模验证

### 9.4 当前 ALFWorld 真实 provider 对比命令

下面这组命令当前仍是 **ALFWorld** 的准确性对比命令。

后续这一节需要扩展到：

- ALFWorld compare
- WebArena compare
- ScienceWorld compare

```bash
env ALFWORLD_DATA=/home/syq/.cache/alfworld \
PYTHONPATH=/home/syq/Documents/blackboard/alfworld:/home/syq/Documents/blackboard/blackboard/libs/kernel_system:/home/syq/Documents/blackboard/blackboard/libs/blackboard:/home/syq/Documents/blackboard/experiment/alfworld \
conda run -n blackboard python experiment/alfworld/examples/run_workflow_compare.py \
  --data-root /home/syq/.cache/alfworld/json_2.1.1/valid_seen \
  --output-dir /home/syq/Documents/blackboard/experiment/alfworld/outputs/workflow_compare_debug_real \
  --split debug \
  --max-steps 20 \
  --modes full \
  --workflow-modes single_action,planner_action,planner_llm_action \
  --llm-backend openai_compatible
```

分析命令：

```bash
env PYTHONPATH=/home/syq/Documents/blackboard/blackboard/libs/kernel_system:/home/syq/Documents/blackboard/blackboard/libs/blackboard:/home/syq/Documents/blackboard/experiment/alfworld \
conda run -n blackboard python experiment/alfworld/examples/run_result_analysis.py \
  --summary-file /home/syq/Documents/blackboard/experiment/alfworld/outputs/workflow_compare_debug_real/workflow_compare_summary.json
```

## 10. 实验 6：消融实验

### 10.1 当前已完成部分

当前已经有可靠结果的消融主要是：

- `full`
- `ablate_c2`
- `ablate_c3`
- `C5` 代码路径已补齐，但还没有真实 provider 结果

已完成输出：

- debug：
  - `experiment/alfworld/outputs/ablation_debug_20_v5/ablation_summary.json`
  - `experiment/alfworld/outputs/ablation_debug_20_v5/ablation_summary_analysis.json`
- formal：
  - `experiment/alfworld/outputs/ablation_formal_20/ablation_summary.json`
  - `experiment/alfworld/outputs/ablation_formal_20/ablation_summary_analysis.json`

### 10.2 已有关键结论

debug v5：

- `full.success_rate = 0.500`
- `ablate_c2.success_rate = 0.500`
- `ablate_c3.success_rate = 0.583`

formal：

- `full.success_rate = 0.267`
- `ablate_c2.success_rate = 0.267`
- `ablate_c3.success_rate = 0.400`

结论：

1. `C3` 的影响在 debug 和 formal 上都稳定存在
2. `C2` 在 deterministic ALFWorld runner 上与 `full` 基本一致
3. `C2` 更适合通过 Experiment 2 的 schema-guard 注入来体现

### 10.3 完整消融的建议运行方式

如果要把 `experiment.md` 的 C1-C5 都纳入一轮 runner：

```bash
env ALFWORLD_DATA=/home/syq/.cache/alfworld \
PYTHONPATH=/home/syq/Documents/blackboard/alfworld:/home/syq/Documents/blackboard/blackboard/libs/kernel_system:/home/syq/Documents/blackboard/blackboard/libs/blackboard:/home/syq/Documents/blackboard/experiment/alfworld \
conda run -n blackboard python experiment/alfworld/examples/run_ablation.py \
  --data-root /home/syq/.cache/alfworld/json_2.1.1/valid_seen \
  --output-dir /home/syq/Documents/blackboard/experiment/alfworld/outputs/ablation_debug_all_components_real \
  --split debug \
  --max-steps 20 \
  --workflow-mode planner_llm_action \
  --architect-mode llm \
  --modes full,ablate_c1,ablate_c2,ablate_c3,ablate_c4,ablate_c5 \
  --llm-backend openai_compatible
```

分析：

```bash
env PYTHONPATH=/home/syq/Documents/blackboard/blackboard/libs/kernel_system:/home/syq/Documents/blackboard/blackboard/libs/blackboard:/home/syq/Documents/blackboard/experiment/alfworld \
conda run -n blackboard python experiment/alfworld/examples/run_result_analysis.py \
  --summary-file /home/syq/Documents/blackboard/experiment/alfworld/outputs/ablation_debug_all_components_real/ablation_summary.json
```

如果只想先单独验证 `C5`，建议先跑最小对照：

```bash
env ALFWORLD_DATA=/home/syq/.cache/alfworld \
PYTHONPATH=/home/syq/Documents/blackboard/alfworld:/home/syq/Documents/blackboard/blackboard/libs/kernel_system:/home/syq/Documents/blackboard/blackboard/libs/blackboard:/home/syq/Documents/blackboard/experiment/alfworld \
conda run -n blackboard python experiment/alfworld/examples/run_ablation.py \
  --data-root /home/syq/.cache/alfworld/json_2.1.1/valid_seen \
  --gamefiles-file /home/syq/Documents/blackboard/experiment/alfworld/outputs/workflow_compare_debug_real_limit3_steps10/selected_gamefiles.json \
  --output-dir /home/syq/Documents/blackboard/experiment/alfworld/outputs/planner_llm_ablate_c5_real_limit3_steps10 \
  --split debug \
  --max-steps 10 \
  --workflow-mode planner_llm_action \
  --architect-mode llm \
  --modes full,ablate_c5 \
  --llm-backend openai_compatible
```

这个对照现在可以直接比较：

- `success_rate`
- `mean_total_tokens`
- `mean_architect_total_tokens`
- `task_type_summaries`
- `steps_with_architect_decision`

### 10.4 当前必须注意的限制

- `ablate_c1` / `ablate_c4` 只有在真实 LLM 路径上才真正有研究价值
- `ablate_c5` 现在已经能形成有效对照，但仍有两个限制：
  - `LLMALFWorldArchitect` 当前是“受控编排”，不会脱离 `--workflow-mode` 自由选 worker 拓扑
  - 当 workflow 使用纯规则 worker 时，architect 的动态 instruction 增益会比 `planner_llm_action` 更弱

## 11. 当前推荐执行顺序

如果你现在继续推进，推荐严格按这个顺序：

1. 先确认真实 provider 环境变量可用
2. 先用最新代码重跑实验 5 的 `workflow_compare_debug_real_limit3_steps10`
3. 如果最新 compare 仍优于旧版，再把实验 5 的 `workflow_compare` 从 `limit=3` 扩大到更大样本
4. 然后用优化后的 `planner_llm_action` 重新跑实验 1 / 3
5. 然后先跑实验 6 的 `full vs ablate_c5` 小规模对照，确认 `LLM architect` 的真实增益
6. 在真实 `planner_llm_action + architect_mode=llm` 更稳定之后，再跑实验 6 的完整组件消融
7. 最后再决定是否扩到 formal 规模

## 12. 当前最关键的阻塞

### 阻塞 1：真实实验仍受 token 成本 / 额度约束

历史上旧 token 的最新真实运行曾出现：

- `401 AuthenticationError`
- 错误信息要点：`该令牌额度已用尽`

这意味着：

- provider 配置本身是正确的
- 网络调用本身也是通的
- 旧 token 已经不可继续使用
- 当前已通过新的可用 token 完成 `ablate_c4` 小规模真实实验
- 但后续如果继续扩大样本，仍需要持续关注额度消耗

### 阻塞 2：WebArena 正式结果与 ScienceWorld 规模化结果仍未完成

当前状态不是“完全未接入”，而是：

- `WebArena` 已经有实验代码骨架、compare runner、analysis、`script_browser` 封装和 `official_prompt` baseline
- `langgraph` / `autogen` 也已经有 WebArena 实验目录下的 runner
- 最小 `script_browser` smoke 已经跑通过一次，路径为：
  - `experiment/common/task_sets/webarena_script_browser_smoke.json`
- `experiment/webarena/examples/run_schema_guard_eval.py` 已经补齐，`reference_oracle` 下可直接产出 `schema_guard_metrics.json`
- `experiment/webarena/examples/run_context_ablation.py` 已经补齐，`reference_oracle` 下可直接产出 `context_ablation_summary.json`
- `experiment/webarena/examples/run_ablation.py` 已经补齐，`reference_oracle` 下可直接产出 `ablation_summary.json`
- 三数据集统一汇总入口也已补齐：
  - `experiment/common/run_cross_dataset_analysis.py`
  - `experiment/run/run_multidataset_experiments.sh`
- 但 **WebArena 的 `script_browser` 正式结果，以及 ScienceWorld 的正式规模化运行还没完成**
- `ScienceWorld` 已经确定为第三数据集，当前已具备任务配置、reference env scaffold、compare runner、ablation runner、analysis 和统一汇总接线

仍未完成的部分包括：

- WebArena 正式 compare 结果
- WebArena 的 `script_browser` 正式结果
- `ScienceWorld` 的正式规模化运行

### 阻塞 3：ALFWorld C5 已可执行，但还没产出真实结果

当前代码已支持 `LLMALFWorldArchitect`，下一步阻塞不在实现，而在：

- 需要真实 provider 跑出 `full vs ablate_c5`
- 需要确认新增 architect token 开销是否值得

## 13. 已有关键输出文件索引

- Experiment 2 real smoke：
  - `experiment/alfworld/outputs/exp2_real_smoke/schema_guard_metrics.json`
  - `experiment/alfworld/outputs/exp2_real_smoke/schema_guard_cases.jsonl`
- Debug ablation：
  - `experiment/alfworld/outputs/ablation_debug_20_v5/ablation_summary.json`
  - `experiment/alfworld/outputs/ablation_debug_20_v5/ablation_summary_analysis.json`
- Formal ablation：
  - `experiment/alfworld/outputs/ablation_formal_20/ablation_summary.json`
  - `experiment/alfworld/outputs/ablation_formal_20/ablation_summary_analysis.json`
- Workflow compare mock：
  - `experiment/alfworld/outputs/workflow_compare_debug_mock/workflow_compare_summary.json`
  - `experiment/alfworld/outputs/workflow_compare_debug_mock/workflow_compare_summary_analysis.json`
- Real C4 ablation small slice：
  - `experiment/alfworld/outputs/planner_llm_ablate_c4_real_limit3_steps10_rerun/ablate_c4/ablate_c4_summary.json`
  - `experiment/alfworld/outputs/planner_llm_ablate_c4_real_limit3_steps10_rerun/ablation_summary.json`
  - `experiment/alfworld/outputs/planner_llm_ablate_c4_real_limit3_steps10_rerun/ablation_summary_analysis.json`
- Optimized planner_llm_action small slice：
  - `experiment/alfworld/outputs/planner_llm_ablation_real_limit3_steps10_search_guidance/full/full_summary.json`
  - `experiment/alfworld/outputs/planner_llm_ablation_real_limit3_steps10_search_guidance_v2/full/full_summary.json`
  - `experiment/alfworld/outputs/planner_llm_ablation_real_limit3_steps10_search_guidance_v2/ablation_summary.json`
  - `experiment/alfworld/outputs/planner_llm_ablation_real_limit3_steps10_search_guidance_v2/ablation_summary_analysis.json`
- Optimized workflow_compare (search_guidance_v2, 3 gamefiles)：
  - `experiment/alfworld/outputs/workflow_compare_debug_real_limit3_steps10_search_guidance_v2/workflow_compare_summary.json`
  - `experiment/alfworld/outputs/workflow_compare_debug_real_limit3_steps10_search_guidance_v2/workflow_compare_summary_analysis.json`
