# SkillOpt route_effort 环境代码

这个目录包含修复后的 SkillOpt `route_effort` 环境代码，用于训练 route-effort skill。

## 文件说明

- `__init__.py` - 环境初始化，导出 RouteEffortAdapter
- `adapter.py` - 环境适配器，桥接 SkillOpt 和 route-effort 环境
- `dataloader.py` - 数据加载器，处理训练/验证/测试数据
- `rollout.py` - 任务执行器，运行单个任务并评分

## 修复的关键 Bug

训练过程中发现并修复了 5 个关键问题：

### 1. Adapter 缺失方法 (`adapter.py`)

**问题**: `RouteEffortAdapter` 没有实现 `setup()` 和 `get_dataloader()` 方法，导致训练时显示 `train items=0`。

**修复**:
```python
def setup(self, cfg: dict) -> None:
    """初始化 dataloader"""
    super().setup(cfg)
    self.loader.setup(cfg)  # 必须调用

def get_dataloader(self):
    """返回 dataloader 实例"""
    return self.loader
```

### 2. API 调用错误 (`rollout.py`)

**问题**: 使用了错误的 `chat_target()` 参数格式，传入 `messages` 而非 `system`/`user`。

**修复前**:
```python
response, _ = chat_target(
    messages=[{"role": "system", "content": system_prompt}, ...],
    ...
)
```

**修复后**:
```python
response, _ = chat_target(
    system=system_prompt,
    user=user_prompt,
    max_completion_tokens=max_completion_tokens,
    timeout=exec_timeout,
)
```

### 3. 返回字段不匹配 (`rollout.py`)

**问题**: `process_one()` 返回的字段名是 `correct` 和 `soft_score`，但 SkillOpt 期望 `hard` 和 `soft`。

**修复前**:
```python
return {
    "correct": correct,
    "soft_score": soft_score,
    ...
}
```

**修复后**:
```python
return {
    "hard": hard_score,      # 0 或 1
    "soft": soft_score,      # 0.0 到 1.0
    ...
}
```

### 4. 数据标签缺失 (`../train-data/`)

**问题**: 训练数据样本缺少 `expected_effort` 字段，导致无法评分。

**修复**: 为所有 50 个样本（40 train + 5 val + 5 test）添加了 `expected_effort` 标签。

### 5. 目录结构不匹配 (`../train-data/`)

**问题**: 数据文件直接放在 `train-data/` 根目录，不符合 SkillOpt 的 `split_dir` 模式。

**修复**: 重组为标准结构：
```
train-data/
├── train/items.json
├── val/items.json
└── test/items.json
```

## 使用方法

### 安装到 SkillOpt

将这些文件复制到 SkillOpt 安装目录：

```bash
# 找到 SkillOpt 安装位置
SKILLOPT_PATH=$(python3 -c "import skillopt; import os; print(os.path.dirname(skillopt.__file__))")

# 复制修复后的代码
cp -r skillopt-env/* "$SKILLOPT_PATH/envs/route_effort/"

# 验证安装
python3 -c "from skillopt.envs.route_effort import RouteEffortAdapter; print('✓ 安装成功')"
```

### 验证修复

运行训练前检查：

```bash
cd ../  # 回到 skill-opt 目录
skillopt-train --config config.yaml
```

应该看到：
- ✅ 训练集加载成功（不再显示 `train items=0`）
- ✅ 模型正确输出 `<effort>level</effort>` 格式
- ✅ 评分系统正常工作（hard/soft 分数不为 0）
- ✅ 训练历史显示准确率提升

## 代码详解

### adapter.py

核心职责：
- 初始化 dataloader
- 构建训练/评估批次
- 并行执行任务（使用 ThreadPoolExecutor）

关键方法：
- `setup()` - 初始化 dataloader（必须实现）
- `get_dataloader()` - 返回 dataloader 实例（必须实现）
- `build_train_env()` - 从训练集采样批次
- `build_eval_env()` - 从验证集/测试集采样批次
- `run_envs()` - 并行执行任务列表

### rollout.py

核心职责：
- 执行单个 route-effort 任务
- 调用 Claude API 获取预测
- 提取 `<effort>` 标签并评分

关键函数：
- `process_one()` - 主入口，处理单个任务
- `_extract_effort()` - 从输出中提取 effort 级别
- `_score_effort()` - 计算 hard 和 soft 分数

评分逻辑：
```python
def _score_effort(predicted, expected):
    if predicted == expected:
        return 1, 1.0  # 完全正确
    
    # 距离评分：最大距离为 4（low vs max）
    distance = abs(EFFORT_SCORE[predicted] - EFFORT_SCORE[expected])
    soft_score = max(0.0, 1.0 - (distance / 4.0))
    return 0, soft_score
```

### dataloader.py

核心职责：
- 加载训练/验证/测试数据
- 支持 `split_dir` 和 `split_ratio` 两种模式
- 构建批次规格

继承自 `SplitDataLoader`，无需自定义逻辑。

## 训练结果

使用这些修复后的代码，训练结果：

- **测试集准确率**: 80% (4/5)
- **Soft 评分**: 0.950/1.0
- **训练稳定性**: 6/6 步成功完成
- **Token 效率**: ~48k tokens 完成完整训练

## 集成到其他项目

如果要为其他 skill 创建 SkillOpt 环境，参考这个实现：

1. 继承 `BaseAdapter` 和 `SplitDataLoader`
2. 实现必需方法：`setup()`, `get_dataloader()`
3. 实现 `process_one()` 函数，返回包含 `hard`/`soft` 字段的字典
4. 使用 `chat_target(system=..., user=...)` 调用模型
5. 准备符合 `split_dir` 格式的训练数据

详细集成指南见项目根目录的 `skillopt-integration-guide.md`。

## 参考资料

- [SkillOpt 训练报告](../../skillopt-training-summary.md)
- [SkillOpt 集成指南](../../skillopt-integration-guide.md)
- [SkillOpt 官方仓库](https://github.com/anthropics/skillopt)
