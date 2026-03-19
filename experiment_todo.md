# 实验补齐 TODO

最后更新：2026-03-16

说明：

- 本文件只保留当前还没有完成、并且会影响 `experiment.md` 正式结题的事项。
- 已删除不再需要的旧 TODO：目录初始化、`experiment/common` 搭建、`langgraph/autogen` 基础接入、`ALFWorld` 基础 runner、`WebArena` smoke/compare 基础链路等已经完成的内容。

## 1. 当前状态

- `实验1`：已实现规则版语义漂移率、`comm_*` 导出和 judge 评分入口；真实 judge 实跑待验证。
- `实验2`：`ALFWorld` 已完成；`WebArena` 已实现 `reference_oracle` 版 schema-guard runner，正式实跑待验证。
- `实验3`：`ALFWorld` 可做 `C4`；`WebArena` 已实现 `reference_oracle` 版 `full vs ablate_c4`，正式实跑待验证。
- `实验4`：`ALFWorld + WebArena + ScienceWorld` 已接入统一 cross-dataset 汇总入口；正式结果仍待补齐。
- `实验5`：`ALFWorld + WebArena + ScienceWorld` 已接入统一 cross-dataset 汇总入口；正式结果仍待补齐。
- `实验6`：`ALFWorld` 已有 `C1~C5`；`WebArena` 已实现 `reference_oracle` 版 `full vs ablate_c1~c5`，`ScienceWorld` 已接入基础 ablation scaffolding；三数据集统一消融汇总入口已补齐，正式实跑待验证。

## 2. P0：先做范围对齐

- [ ] 对齐 `experiment.md`、`experiment_runbook.md` 和当前代码口径
  - 推荐把当前正式对照组明确写成 `langgraph + autogen`
  - 推荐把当前网页环境明确写成 `WebArena`
  - 推荐把新增数据集明确写成 `ScienceWorld`
  - `CrewAI` 和 `WebShop` 如果暂时不做，应明确标注为 future work，而不是继续放在当前必做范围里
- [x] 把 `ScienceWorld` 写入 `实验4/实验5/实验6` 的正式范围说明
  - 已明确为第三数据集
  - 已接到 compare / ablation / cross-dataset summary 三类链路

完成标准：

- 文档中的实验定义和当前代码能力一致，不再出现“代码能跑，但按文档仍算未完成”的情况

## 3. P0：补齐公共评估能力

- [x] 实现 `实验1` 的“语义漂移率”
  - 为 `ALFWorld` 和 `WebArena` 都补充逐步 `communication_trace`
  - 明确一次通信的统计单位
  - 统计“误解导致的无效 action / 错误 patch / fallback”占比
  - 产物：`comm_trace.jsonl`、`comm_summary.json`
- [x] 实现 `实验1` 的“LLM judge 一致性评分”数据导出与评分入口
  - 新增统一 judge runner
  - judge 输入至少包含：发送方意图、发送内容、接收方动作
  - judge 输出按 step 记录 `0/1`
  - 产物：`comm_judge.jsonl`
- [ ] 在 `openai_compatible` backend 上补一轮真实 judge 评分验证
- [x] 实现 `实验3` 的“信息检索精度”
  - 定义“相关信息片段”的判定口径
  - 记录实际送入 worker 的上下文片段
  - 支持按 episode 汇总 precision
  - 产物：`retrieval_judge.jsonl`、`context_summary.json`

建议优先改动位置：

- `experiment/alfworld/evaluators/metrics.py`
- `experiment/webarena/evaluators/metrics.py`
- `experiment/alfworld/examples/run_result_analysis.py`
- `experiment/webarena/examples/run_result_analysis.py`
- `experiment/common/` 下新增 judge 相关模块

完成标准：

- `实验1` 和 `实验3` 所需指标都能自动产出，不再只剩 token / success / patch error 这类基础指标

## 4. P1：补齐 WebArena 缺失 runner

### 4.1 实验 2：Schema 强制校验

- [x] 新增 `experiment/webarena/examples/run_schema_guard_eval.py`
- [x] 新增 `experiment/webarena/utils/injection.py`
- [x] 新增 `experiment/webarena/evaluators/schema_guard_evaluator.py`
- [x] 复用 `ALFWorld` 的思路实现 `C2 on / C2 off` 对比
  - 先捕获真实 state
  - 再生成 invalid patch case
  - 再回放并统计拦截率
- [x] 更新 `experiment/run/run_webarena_experiments.sh`
  - `exp2` 已不再是 placeholder
- [ ] 在 `script_browser` 或正式 task set 上补一轮实跑验证

完成标准：

- `WebArena` 已可单独跑出 `schema_guard_cases.jsonl` 和 `schema_guard_metrics.json`

### 4.2 实验 3：Context Slicing

- [x] 为 `WebArena` 增加 `C4` 对比入口
- [x] 支持 `full` 与 `ablate_c4` 两种模式
- [ ] 准备长上下文任务集
- [x] 接上“信息检索精度”评估
- [x] 更新 `experiment/run/run_webarena_experiments.sh`
  - `exp3` 已不再是 placeholder
- [ ] 在 `script_browser` 或正式 task set 上补一轮实跑验证

建议优先改动位置：

- `experiment/webarena/systems/blackboard_runner.py`
- `experiment/webarena/examples/run_system_compare.py`
- `experiment/webarena/utils/result_analysis.py`

完成标准：

- `WebArena` 可以正式跑 `实验3`，并输出 `success + token + retrieval precision`

### 4.3 实验 6：组件消融

- [x] 为 `WebArena` 增加 `full`、`ablate_c1`、`ablate_c2`、`ablate_c3`、`ablate_c4`、`ablate_c5`
- [x] 对齐 `ALFWorld` 侧的消融命名和输出结构
- [x] 新增 `WebArena` 消融 runner 和分析脚本
- [x] 更新 `experiment/run/run_webarena_experiments.sh`
  - `exp6` 已不再是 placeholder
- [ ] 在 `script_browser` 或正式 task set 上补一轮实跑验证

建议优先改动位置：

- `experiment/webarena/systems/blackboard_runner.py`
- `experiment/webarena/examples/`
- `experiment/webarena/utils/result_analysis.py`

完成标准：

- `WebArena` 侧可以按组件级别完成 `实验6`

## 5. P1：接入 ScienceWorld

- [x] 建立 `experiment/scienceworld/` 目录结构
  - `examples/`
  - `evaluators/`
  - `systems/`
  - `utils/`
  - `tests/`
- [x] 新增 task set
  - `experiment/common/task_sets/scienceworld_debug.json`
  - `experiment/common/task_sets/scienceworld_formal.json`
- [x] 接入 `blackboard` runner
  - 当前已支持基础 compare/reference runner
- [x] 接入 `langgraph` baseline
- [x] 接入 `autogen` baseline
- [x] 对齐统一输出
  - `episode_results.jsonl`
  - `summary.json`
  - `config_snapshot.json`
- [x] 新增结果分析入口
  - 支持准确率/成功率汇总
  - 支持后续泛化性统计
- [x] 明确 `ScienceWorld` 的运行前置
  - `blackboard` 环境需安装 `py4j`
  - 本地 `ScienceWorld` 包需要可 import
  - 最小 compare 已在真实运行时验证通过
- [x] 接入 `blackboard` 消融 runner
  - 当前已支持 `full` 与 `ablate_c1~c5` reference runner
- [x] 新增总控脚本入口
  - `experiment/run/run_scienceworld_experiments.sh` 已覆盖 smoke / exp4 / exp5 / exp6

完成标准：

- `ScienceWorld debug` 可以跑通 `blackboard / langgraph / autogen`
- `ScienceWorld` 可以进入 `实验4/实验5/实验6` 的统一汇总

## 6. P1：按实验收尾

### 实验 1

- [ ] 在公共 judge 能力补齐后，正式重跑 `ALFWorld + WebArena`
- [ ] 输出 token、语义漂移率、judge 一致性三类结果
- [ ] 确认 `blackboard / langgraph / autogen` 使用同一任务集和同一模型配置

### 实验 4

- [ ] 用统一 cross-dataset 脚本汇总三数据集正式泛化结果
- [x] 把 `ScienceWorld` 接入总汇总脚本
- [ ] 重新计算跨数据集鲁棒性统计

### 实验 5

- [ ] 在 `ScienceWorld` 接入完成后，补齐三数据集准确性对比
- [ ] 统一 `ALFWorld / WebArena / ScienceWorld` 的任务集规模与预算口径

### 实验 6

- [ ] 用统一 cross-dataset 脚本汇总三数据集正式消融结果
- [x] 确认 `ScienceWorld` 侧的 `C1~C5` 消融结果可以进入统一分析

## 7. 建议执行顺序

1. 先完成文档范围对齐。
2. 先在 `ALFWorld` 和 `WebArena` 上补一轮真实 judge 评分验证。
3. 再补齐 `ScienceWorld` 规模化运行，并把各数据集正式结果喂给统一总汇总入口。
4. 最后重跑 `实验1`、`实验4`、`实验5`、`实验6` 的正式版。

## 8. 最终完成判据

- [x] `run_webarena_experiments.sh` 中的 `exp6` 不再是 placeholder
- [x] `实验1` 能输出语义漂移率和 LLM judge 一致性评分
- [x] `实验3` 能输出信息检索精度
- [x] `ScienceWorld` 已接入 `实验4/实验5/实验6`
- [ ] 当前文档、runbook、脚本三者的实验范围一致
