# route-effort SkillOpt 训练配置

这个目录包含 route-effort skill 的 SkillOpt 训练配置和数据。

## 训练结果

- **测试集准确率**: 80% (4/5)
- **Soft 评分**: 0.950/1.0
- **训练时间**: ~4 分钟
- **Token 消耗**: ~48k tokens

## 目录结构

```
skill-opt/
├── config.yaml           # SkillOpt 训练配置
├── initial_simple.md     # 初始 skill 规则（简化版）
├── train-data/           # 训练数据集
│   ├── train/            # 训练集 (40 samples)
│   │   └── items.json
│   ├── val/              # 验证集 (5 samples)
│   │   └── items.json
│   └── test/             # 测试集 (5 samples)
│       └── items.json
└── README.md             # 本文件
```

## 训练配置

**配置文件**: `config.yaml`

关键参数：
- 环境: `route_effort`
- 训练轮数: 3 epochs
- 批次大小: 20 samples
- 超时: 120 秒
- 并行: 8 workers

## 数据集

### 数据格式

每个样本包含：
```json
{
  "id": "train-0",
  "query": "格式化 utils.py 文件",
  "expected_effort": "low"
}
```

### 数据分布

| Split | 样本数 | 说明 |
|-------|--------|------|
| train | 40 | 训练集，用于规则优化 |
| val   | 5  | 验证集，用于选择最佳规则 |
| test  | 5  | 测试集，用于最终评估 |

### Effort 级别分布

训练数据覆盖所有 5 个 effort 级别：
- `low`: 机械操作（格式化、重命名等）
- `medium`: 单文件任务（bug 修复、解释等）
- `high`: 多文件任务（功能开发、架构分析等）
- `xhigh`: 跨模块任务（重构、根因分析等）
- `max`: 高风险任务（安全审计、并发 bug 等）

## 如何运行训练

### 前置条件

1. 安装 SkillOpt:
```bash
pip install skillopt
```

2. 配置 Claude API（或其他模型后端）:
```bash
export ANTHROPIC_API_KEY="your-api-key"
```

3. 确保 SkillOpt 环境已安装 route_effort adapter（见下文）

### 运行训练

```bash
cd route-effort/skill-opt
skillopt-train --config config.yaml
```

### 查看结果

训练完成后，结果保存在 `skillopt-out/` 目录：

```bash
# 查看最终状态
cat skillopt-out/runtime_state.json | python3 -m json.tool

# 查看训练历史
cat skillopt-out/history.json | python3 -m json.tool

# 查看最佳 skill
cat skillopt-out/best_skill.md

# 查看测试集结果
cat skillopt-out/test_eval_final/rollout.jsonl
```

## SkillOpt 环境集成

训练过程中修复了 5 个关键 bug，这些修复已集成到 SkillOpt 的 `route_effort` 环境中：

### 修复的问题

1. **数据标签缺失** - 为训练数据添加 `expected_effort` 字段
2. **目录结构** - 重组为 `train/val/test` 子目录结构
3. **Adapter 方法缺失** - 添加 `setup()` 和 `get_dataloader()` 方法
4. **API 调用错误** - 修复 `chat_target()` 参数（使用 `system`/`user`）
5. **返回字段不匹配** - 将 `correct`/`soft_score` 改为 `hard`/`soft`

### SkillOpt 环境位置

修复后的代码位于：
```
/path/to/SkillOpt/skillopt/envs/route_effort/
├── __init__.py
├── adapter.py      # 修复: 添加 setup() 和 get_dataloader()
├── rollout.py      # 修复: chat_target() 调用和返回字段
└── dataloader.py
```

完整的修复细节和集成指南见项目根目录的 `skillopt-integration-guide.md`。

## 初始 Skill 规则

**文件**: `initial_simple.md`

这是训练的起点 skill，包含：
- 5 个 effort 级别的定义
- 6 步决策树
- 输出格式规范

**重要**：不包含 YAML frontmatter，因为 SkillOpt 需要纯文本指令。

训练结果显示初始规则已经非常有效（80% 准确率），SkillOpt 没有生成改进版本。

## 测试集样本

测试集结果详情：

| ID | Query | Expected | Predicted | Result |
|----|-------|----------|-----------|--------|
| test-0 | 格式化 utils.py 文件 | low | low | ✅ |
| test-2 | 实现用户登录功能 | high | high | ✅ |
| test-3 | 分析跨服务性能瓶颈 | xhigh | xhigh | ✅ |
| test-4 | 修复支付系统竞态条件 | max | max | ✅ |
| test-1 | 修复 login 函数 bug | medium | high | ❌ |

唯一错误是 medium/high 边界判断，这是未来优化的方向。

## 重新训练

如果要基于新数据重新训练：

1. 更新 `train-data/` 中的样本
2. 调整 `config.yaml` 参数（如需要）
3. 运行 `skillopt-train --config config.yaml`
4. 比较新旧结果，选择最佳版本

建议扩展数据集至 200+ 样本以提高准确率。

## 参考资料

- [SkillOpt 训练报告](../../skillopt-training-summary.md)
- [SkillOpt 集成指南](../../skillopt-integration-guide.md)
- [route-effort CHANGELOG](../CHANGELOG.md)
- [SkillOpt 官方文档](https://github.com/anthropics/skillopt)
