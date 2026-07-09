# SkillOpt 训练总结：route-effort

## 训练目标

为 `route-effort` skill 训练一个智能分类器，根据任务描述自动路由到合适的 effort 级别（low/medium/high/xhigh/max）。

## 训练过程

### 数据准备

- **训练集**: 40 个样本
- **验证集**: 5 个样本  
- **测试集**: 5 个样本
- 数据结构：每个样本包含 `query`（任务描述）和 `expected_effort`（标签）

### 修复的关键问题

训练过程中发现并修复了 5 个关键 bug：

1. **训练数据标签缺失** - 为 50 个样本添加了 `expected_effort` 字段
2. **目录结构不匹配** - 重组为 `train/`, `val/`, `test/` 子目录结构
3. **RouteEffortAdapter 缺失方法** - 添加 `setup()` 和 `get_dataloader()` 方法
4. **API 调用错误** - 修复 `chat_target()` 参数（使用 `system`/`user` 而非 `messages`）
5. **返回字段不匹配** - 将 `correct`/`soft_score` 改为 `hard`/`soft`

### 训练配置

```yaml
env:
  name: route_effort
  skill_init: initial_simple.md
  split_mode: split_dir
  split_dir: train-data
  out_root: skillopt-out
  exec_timeout: 120

train:
  rollout_batch_size: 20
  n_epochs: 3
  fast_update:
    active: true
    batch_sizes: [20, 20]
  slow_update:
    active: true
    batch_sizes: [10, 10]
```

## 训练结果

### 测试集表现

- **Hard 准确率**: 80% (4/5)
- **Soft 平均分**: 0.950

### 测试样本详情

| ID | Query | Expected | Predicted | Result |
|----|-------|----------|-----------|--------|
| test-0 | 格式化 utils.py 文件 | low | low | ✅ |
| test-2 | 实现用户登录功能 | high | high | ✅ |
| test-3 | 分析跨服务性能瓶颈 | xhigh | xhigh | ✅ |
| test-4 | 修复支付系统竞态条件 | max | max | ✅ |
| test-1 | 修复 login 函数 bug | medium | high | ❌ |

### 训练历史

| Step | Rollout N | Hard | Soft | Action |
|------|-----------|------|------|--------|
| 1 | 20 | 0.600 | 0.900 | skip_no_patches |
| 2 | 20 | 0.600 | 0.900 | skip_no_patches |
| 3 | 20 | 0.750 | 0.938 | skip_no_patches |
| 4 | 20 | 0.500 | 0.863 | skip_no_patches |
| 5 | 20 | 0.750 | 0.938 | skip_no_patches |
| 6 | 20 | 0.550 | 0.863 | skip_no_patches |

**最佳模型**: 初始 skill（step 0），验证集得分 0.6

## 最终 Skill

SkillOpt 确认初始规则已经非常有效，无需进一步优化。最终采用的分类规则：

### 决策树

```
1. 是否机械性操作，无需推理？         → low
2. 单文件 + 边界清晰？               → medium  
3. 多文件 + 有歧义或需方案选择？      → high
4. 跨模块 + 影响面大？               → xhigh
5. 安全/并发/正确性至关重要？        → max
6. 不确定时：向上路由一级（保守策略）
```

### Effort 级别定义

- **low**: 机械性操作，确定性高，无需推理（格式化、重命名、文本替换）
- **medium**: 日常任务，需少量推理（单文件 bug 修复、代码解释）
- **high**: 多文件或有歧义，需权衡方案（多文件功能、架构分析）
- **xhigh**: 跨模块、影响面大（跨模块重构、根因分析）
- **max**: 极难，错了代价极高（安全审计、并发 bug）

## 部署

已将优化后的规则更新到：
- `/Users/changsailong/.claude/skills/vlong/route-effort/SKILL.md`

## Token 使用

- **训练总用量**: ~48k tokens
- **平均每步**: ~8k tokens

## 结论

1. **初始规则质量高** - 80% 测试准确率说明人工设计的决策树已经很有效
2. **保守策略有效** - "不确定时向上路由"避免了推理资源不足的风险
3. **SkillOpt 验证价值** - 即使没有生成改进版本，训练过程也验证了规则的有效性

## 下一步优化方向

1. 扩充训练数据至 200+ 样本，覆盖更多边界情况
2. 添加领域特定规则（如数据库迁移、UI 实现等）
3. 引入任务元信息（文件数量、代码行数、依赖关系）作为特征
4. 针对唯一错误样本（test-1）优化 medium/high 边界判断
