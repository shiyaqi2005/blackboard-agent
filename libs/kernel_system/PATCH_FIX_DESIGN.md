# JSON Patch 自动修复方案设计

## 问题分析

JSON Patch 可能出现的错误可以分为以下几类：

### 1. 路径错误 (Path Errors)
- ❌ 路径不存在（replace/remove 操作）
- ❌ 路径格式错误（缺少 `/`，多余斜杠，错误转义）
- ❌ 路径指向错误类型（对数组用对象键，对对象用数组索引）
- ❌ 父路径不存在（如 `/a/b/c` 但 `/a/b` 不存在）
- ❌ 数组索引越界

### 2. 操作错误 (Operation Errors)
- ❌ 使用 replace 但字段不存在 → 应该用 add
- ❌ 使用 add 但字段已存在 → 应该用 replace
- ❌ 使用 remove 但字段不存在
- ❌ test 操作值不匹配
- ❌ 操作类型拼写错误（如 "replce"）

### 3. 值类型错误 (Value Type Errors)
- ❌ 类型不匹配（string vs object, number vs string）
- ❌ enum 值不在允许范围内
- ❌ 数组元素类型错误
- ❌ 必需字段缺失
- ❌ 格式错误（如 email, uri, date-time）
- ❌ 数值范围错误（minimum, maximum）
- ❌ 字符串长度错误（minLength, maxLength）

### 4. 结构错误 (Structure Errors)
- ❌ patch 不是数组
- ❌ 操作缺少必需字段（op, path, value）
- ❌ 操作字段拼写错误
- ❌ 额外的未知字段

### 5. 语义错误 (Semantic Errors)
- ❌ 违反 schema 约束（additionalProperties: false）
- ❌ 违反依赖关系（dependencies, if-then-else）
- ❌ 违反唯一性约束（uniqueItems）
- ❌ 违反模式匹配（pattern）

## 修复策略

### 策略 1: 自动修复（Auto-Fix）
**适用范围**: 明确且安全的错误

**可修复的错误**:
- ✅ replace → add (路径不存在)
- ✅ add → replace (路径已存在)
- ✅ 路径格式修正（添加/移除斜杠）
- ✅ 简单类型转换（string ↔ number, boolean）
- ✅ 对象 → JSON 字符串
- ✅ 单值 → 数组包装
- ✅ 操作拼写修正（基于编辑距离）

**限制**:
- 只修复明确的、不会改变语义的错误
- 不修复可能有多种解释的错误

### 策略 2: 智能推断（Smart Inference）
**适用范围**: 需要上下文推断的错误

**可修复的错误**:
- ✅ enum 值模糊匹配（如 "planing" → "planning"）
- ✅ 缺失父路径自动创建（如 `/a/b/c` 自动创建 `/a/b`）
- ✅ 数组索引越界 → 使用 append（`/-`）
- ✅ 根据 schema 推断缺失的必需字段

**限制**:
- 需要 schema 信息
- 可能改变原始意图

### 策略 3: 降级处理（Graceful Degradation）
**适用范围**: 无法自动修复的错误

**处理方式**:
- ⚠️  跳过有问题的操作，继续执行其他操作
- ⚠️  使用默认值替代错误值
- ⚠️  记录错误但不中断流程

**限制**:
- 可能导致不完整的状态更新
- 需要明确告知用户

### 策略 4: 反馈重试（Feedback Retry）
**适用范围**: 需要 LLM 重新生成的错误

**处理方式**:
- 🔄 将错误信息反馈给 worker
- 🔄 要求 worker 重新生成 patch
- 🔄 最多重试 2-3 次

**适用错误**:
- 复杂的语义错误
- 多个相互依赖的错误
- 无法自动推断正确值的情况

## 推荐方案：分层修复架构

```
┌─────────────────────────────────────────┐
│         Worker 提交 Patch               │
└──────────────┬──────────────────────────┘
               │
               ▼
┌─────────────────────────────────────────┐
│  Layer 1: 结构验证 (Structure Check)    │
│  - 检查 patch 是否为数组                │
│  - 检查操作是否有必需字段               │
│  - 修正拼写错误                         │
└──────────────┬──────────────────────────┘
               │
               ▼
┌─────────────────────────────────────────┐
│  Layer 2: 路径修复 (Path Fixer)         │
│  - 修正路径格式                         │
│  - 检查路径是否存在                     │
│  - 自动调整 add/replace 操作            │
│  - 创建缺失的父路径（可选）             │
└──────────────┬──────────────────────────┘
               │
               ▼
┌─────────────────────────────────────────┐
│  Layer 3: 类型修复 (Type Fixer)         │
│  - 根据 schema 转换类型                 │
│  - 修正 enum 值（模糊匹配）             │
│  - 处理格式约束                         │
└──────────────┬──────────────────────────┘
               │
               ▼
┌─────────────────────────────────────────┐
│  Layer 4: 应用验证 (Apply & Validate)   │
│  - 应用 patch                           │
│  - 验证 schema                          │
└──────────────┬──────────────────────────┘
               │
         成功？ │
               ├─ Yes ──> 返回新状态
               │
               └─ No ──┐
                       │
                       ▼
         ┌─────────────────────────────┐
         │  Layer 5: 反馈重试           │
         │  - 生成详细错误报告          │
         │  - 反馈给 worker 重新生成    │
         │  - 最多重试 3 次             │
         └─────────────┬───────────────┘
                       │
                 成功？ │
                       ├─ Yes ──> 返回新状态
                       │
                       └─ No ──> 返回错误
```

## 无法覆盖的情况

### 1. 语义错误
- ❌ 违反业务逻辑（如设置负数价格）
- ❌ 数据一致性问题（如删除被引用的对象）
- ❌ 复杂的依赖关系

**原因**: 需要领域知识，无法通过通用规则修复

**解决方案**:
- 在 schema 中定义更严格的约束
- 使用自定义验证器
- 反馈给 worker 重新生成

### 2. 多义性错误
- ❌ 多个可能的修复方案（如 "planing" 可能是 "planning" 或 "planing"）
- ❌ 不确定用户意图

**原因**: 需要上下文或用户确认

**解决方案**:
- 选择最可能的修复（基于编辑距离、频率等）
- 记录修复日志供用户审查
- 反馈给 worker 重新生成

### 3. 结构性冲突
- ❌ 多个操作相互冲突（如先 add 后 remove 同一字段）
- ❌ 操作顺序错误

**原因**: 需要理解操作的整体意图

**解决方案**:
- 分析操作依赖关系
- 重新排序操作
- 反馈给 worker 重新生成

### 4. Schema 设计问题
- ❌ Schema 过于严格（如 enum 缺少合理值）
- ❌ Schema 与实际需求不匹配

**原因**: 问题在 Architect 设计阶段

**解决方案**:
- 改进 Architect prompt
- 使用更灵活的 schema（如 anyOf, oneOf）
- 允许 additionalProperties

## 实现建议

### 配置选项
```python
class PatchFixerConfig:
    # Layer 1: 结构修复
    fix_structure: bool = True
    fix_spelling: bool = True

    # Layer 2: 路径修复
    fix_path_format: bool = True
    auto_switch_add_replace: bool = True
    create_missing_parents: bool = False  # 默认关闭，可能改变语义

    # Layer 3: 类型修复
    fix_type_mismatch: bool = True
    fuzzy_match_enum: bool = True
    fuzzy_match_threshold: float = 0.8  # 相似度阈值

    # Layer 4: 降级处理
    skip_invalid_operations: bool = False  # 默认不跳过
    use_default_values: bool = False

    # Layer 5: 反馈重试
    enable_retry: bool = True
    max_retries: int = 2
```

### 修复日志
```python
class FixLog:
    level: str  # "info", "warning", "error"
    layer: str  # "structure", "path", "type", "apply", "retry"
    operation_index: int
    original_value: Any
    fixed_value: Any
    reason: str
```

## 总结

### 可以覆盖的错误（~70-80%）
- ✅ 路径格式错误
- ✅ add/replace 混淆
- ✅ 简单类型转换
- ✅ enum 模糊匹配
- ✅ 操作拼写错误

### 需要反馈重试的错误（~15-20%）
- 🔄 复杂类型不匹配
- 🔄 多个相互依赖的错误
- 🔄 语义错误

### 无法自动修复的错误（~5-10%）
- ❌ 严重的语义冲突
- ❌ Schema 设计问题
- ❌ 需要用户确认的多义性错误

**建议**: 实现 Layer 1-4 的自动修复 + Layer 5 的反馈重试，可以覆盖 85-95% 的错误情况。
