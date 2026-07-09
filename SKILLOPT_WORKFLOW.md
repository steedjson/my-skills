# SkillOpt 训练工作流完整指南

本指南说明如何使用 SkillOpt 在本项目中训练 skills，提交到 git，然后安装运行最新版本。

## 前置条件

### 1. 安装 SkillOpt

```bash
pip install skillopt
```

### 2. 配置模型后端

SkillOpt 支持多种模型后端。推荐使用 Claude：

```bash
export ANTHROPIC_API_KEY="your-api-key"
```

### 3. 安装 SkillOpt 环境代码

将修复后的环境代码复制到 SkillOpt 安装目录：

```bash
# 找到 SkillOpt 安装位置
SKILLOPT_PATH=$(python3 -c "import skillopt; import os; print(os.path.dirname(skillopt.__file__))")

# 对于 route-effort skill
cp -r route-effort/skill-opt/skillopt-env/* "$SKILLOPT_PATH/envs/route_effort/"

# 验证安装
python3 -c "from skillopt.envs.route_effort import RouteEffortAdapter; print('✓ route_effort 环境安装成功')"
```

## 工作流步骤

### 步骤 1: 准备训练数据

训练数据应该来自真实使用场景。两种数据来源：

#### 选项 A: 从现有 skill 使用日志提取

如果 skill 已经在使用，可以从历史数据中提取真实样本：

```bash
# 示例：从 route-effort 使用日志提取
cd route-effort/skill-opt

# 创建数据目录
mkdir -p train-data/{train,val,test}

# 从日志提取样本（需要自定义脚本）
# 格式示例：
cat > train-data/train/items.json << 'EOF'
[
  {
    "id": "train-0",
    "query": "格式化 utils.py 文件",
    "expected_effort": "low"
  },
  {
    "id": "train-1", 
    "query": "修复 login 函数的空指针 bug",
    "expected_effort": "medium"
  }
]
EOF
```

#### 选项 B: 手动标注真实任务

收集真实项目中的任务描述并手动标注：

```bash
# 1. 收集最近的 git commit 消息
git log --oneline -100 > /tmp/recent-commits.txt

# 2. 收集 issue/PR 标题
# (根据你的代码托管平台使用 gh/glab)

# 3. 手动标注并创建训练数据
# 推荐数据分布：
# - 训练集: 40-100 样本
# - 验证集: 5-10 样本
# - 测试集: 5-10 样本
```

**数据质量检查清单：**
- ✅ 每个样本都有唯一的 `id`
- ✅ 每个样本都有 `expected_output` 标签（字段名取决于你的 skill）
- ✅ 覆盖所有可能的输出类别
- ✅ 包含边界情况和易混淆的样本
- ✅ 数据分布符合真实使用场景

### 步骤 2: 创建初始 Skill 规则

创建 `initial_skill.md`，包含你的初始规则（**不要包含 YAML frontmatter**）：

```bash
cd your-skill/skill-opt

cat > initial_skill.md << 'EOF'
# Your Skill Name

## 规则

1. 规则一的描述
2. 规则二的描述
3. ...

## 决策逻辑

[描述决策树或分类逻辑]

## 输出格式

<result>输出内容</result>
EOF
```

### 步骤 3: 配置训练参数

创建或修改 `config.yaml`：

```yaml
env:
  name: your_skill_name          # 环境名称，需要在 SkillOpt 中注册
  skill_init: initial_skill.md   # 初始 skill 文件
  split_mode: split_dir          # 数据加载模式
  split_dir: train-data          # 数据目录
  out_root: skillopt-out         # 输出目录
  exec_timeout: 120              # 超时时间（秒）

train:
  rollout_batch_size: 20         # 每批次样本数
  n_epochs: 3                    # 训练轮数
  n_workers: 8                   # 并行线程数
  
  fast_update:
    active: true
    batch_sizes: [20, 20]        # 快速更新批次大小
  
  slow_update:
    active: true
    batch_sizes: [10, 10]        # 慢速更新批次大小

model:
  backend: claude                # 模型后端
  target_model: claude-sonnet-4-20250514
  meta_model: claude-sonnet-4-20250514
```

### 步骤 4: 运行训练

```bash
cd your-skill/skill-opt

# 清理旧的输出（可选）
rm -rf skillopt-out

# 运行训练
skillopt-train --config config.yaml

# 训练过程会显示：
# - 加载的数据集大小
# - 每一步的准确率
# - 最佳 skill 的选择
```

**训练监控提示：**
- 每步显示的 `acc=0.000` 可能是显示 bug，查看 `hard` 和 `soft` 分数才是真实准确率
- 训练日志保存在 `skillopt-out/` 目录

### 步骤 5: 查看训练结果

```bash
cd your-skill/skill-opt

# 查看最终状态
cat skillopt-out/runtime_state.json | python3 -m json.tool

# 查看训练历史
cat skillopt-out/history.json | python3 -c "
import json, sys
h = json.load(sys.stdin)
print(f'总训练步数: {len(h)}')
for step in h:
    print(f'Step {step[\"step\"]}: hard={step[\"rollout_hard\"]:.3f}, soft={step[\"rollout_soft\"]:.3f}')
"

# 查看最佳 skill
cat skillopt-out/best_skill.md

# 查看测试集结果
cat skillopt-out/test_eval_final/rollout.jsonl | python3 -c "
import json, sys
results = [json.loads(line) for line in sys.stdin if line.strip()]
hard = sum(r.get('hard', 0) for r in results)
soft = sum(r.get('soft', 0.0) for r in results)
print(f'测试集: {len(results)} 样本')
print(f'Hard 准确率: {hard}/{len(results)} = {hard/len(results):.2%}')
print(f'Soft 平均分: {soft/len(results):.3f}')
"
```

### 步骤 6: 评估和迭代

**评估标准：**
- Hard 准确率 ≥ 70% 为可接受
- Hard 准确率 ≥ 80% 为良好
- Soft 评分 ≥ 0.85 表示即使错误也接近正确

**如果结果不理想：**

1. **分析错误样本**
```bash
# 查看所有预测结果
cat skillopt-out/test_eval_final/rollout.jsonl | python3 -c "
import json, sys
for line in sys.stdin:
    if line.strip():
        r = json.loads(line)
        if r.get('hard') == 0:  # 只显示错误样本
            print(f\"错误: {r['id']}\"
            print(f\"  输入: {r.get('query') or r.get('input')}\"
            print(f\"  预期: {r.get('expected')}\"
            print(f\"  预测: {r.get('predicted')}\"
            print()
"
```

2. **改进策略**
   - 增加类似的训练样本
   - 调整初始规则的边界判断
   - 增加更多特征描述
   - 扩大训练数据集（推荐 100+ 样本）

3. **重新训练**
```bash
# 修改 train-data/ 或 initial_skill.md
# 然后重新运行
skillopt-train --config config.yaml
```

### 步骤 7: 部署到实际 Skill

训练满意后，将最佳规则应用到实际 skill：

```bash
# 1. 备份当前 SKILL.md
cp ../SKILL.md ../SKILL.md.backup

# 2. 对比训练前后的差异
diff initial_skill.md skillopt-out/best_skill.md

# 3. 手动合并改进到 SKILL.md
# (SkillOpt 的输出是简化版，需要手动整合到完整的 SKILL.md 中)

# 4. 更新 CHANGELOG
cat >> ../CHANGELOG.md << EOF

## vX.X.X ($(date +%Y-%m-%d))

### SkillOpt 训练优化
- 训练数据: N 样本
- 测试准确率: XX%
- 主要改进: [描述规则改进]
EOF
```

### 步骤 8: 提交到 Git

```bash
cd ../..  # 回到项目根目录

# 1. 查看修改
git status
git diff

# 2. 添加训练相关文件
git add your-skill/skill-opt/
git add your-skill/SKILL.md
git add your-skill/CHANGELOG.md

# 3. 提交
git commit -m "feat(your-skill): apply SkillOpt training optimizations

Training results:
- Test accuracy: XX%
- Soft score: X.XXX
- Training samples: N train + M val + K test

Key improvements:
- [改进点 1]
- [改进点 2]
"

# 4. 推送到远程
git push origin main
```

### 步骤 9: 安装最新版本的 Skill

有两种方式安装更新后的 skill：

#### 选项 A: 本地安装（开发测试）

```bash
# 直接从本地仓库链接到 Claude skills 目录
ln -sf "$(pwd)/your-skill" ~/.claude/skills/vlong/your-skill

# 验证
ls -la ~/.claude/skills/vlong/your-skill
```

#### 选项 B: 从 GitHub 安装（生产部署）

```bash
# 1. 确保代码已推送到 GitHub
git push origin main

# 2. 使用安装脚本（如果有）
curl -fsSL https://raw.githubusercontent.com/your-username/my-skills/main/your-skill/install.sh | bash

# 或手动安装
cd ~/.claude/skills/vlong
rm -rf your-skill
git clone https://github.com/your-username/my-skills.git temp
mv temp/your-skill ./
rm -rf temp
```

### 步骤 10: 验证新 Skill

```bash
# 1. 重启 Claude Code（如果需要）

# 2. 测试 skill
# 在 Claude Code 中运行：
# /your-skill [测试输入]

# 3. 检查输出是否符合预期
```

## 完整示例：route-effort

参考 `route-effort/skill-opt/` 目录查看完整的工作示例：

```bash
# 查看训练配置
cat route-effort/skill-opt/config.yaml

# 查看训练数据
cat route-effort/skill-opt/train-data/train/items.json | python3 -m json.tool | head -50

# 查看初始规则
cat route-effort/skill-opt/initial_simple.md

# 查看环境代码
ls -la route-effort/skill-opt/skillopt-env/

# 查看训练结果文档
cat skillopt-training-summary.md
```

## 持续改进工作流

建议建立持续改进循环：

```
收集真实使用数据
    ↓
标注新样本
    ↓
添加到训练集
    ↓
重新训练
    ↓
评估改进效果
    ↓
部署新版本
    ↓
(循环)
```

**自动化脚本示例：**

```bash
#!/bin/bash
# train-and-deploy.sh

set -e

SKILL_NAME="your-skill"
SKILL_DIR="$SKILL_NAME/skill-opt"

cd "$SKILL_DIR"

echo "=== 清理旧输出 ==="
rm -rf skillopt-out

echo "=== 运行训练 ==="
skillopt-train --config config.yaml

echo "=== 评估结果 ==="
ACCURACY=$(cat skillopt-out/test_eval_final/rollout.jsonl | python3 -c "
import json, sys
results = [json.loads(line) for line in sys.stdin if line.strip()]
hard = sum(r.get('hard', 0) for r in results)
print(hard / len(results))
")

echo "测试准确率: $ACCURACY"

if (( $(echo "$ACCURACY >= 0.80" | bc -l) )); then
    echo "=== 准确率达标，准备部署 ==="
    
    # 备份当前版本
    cp ../SKILL.md ../SKILL.md.backup
    
    # 提示手动合并
    echo "请手动合并训练结果到 SKILL.md"
    echo "训练后的最佳规则: skillopt-out/best_skill.md"
    
else
    echo "=== 准确率未达标 ($ACCURACY < 0.80)，不部署 ==="
    exit 1
fi
```

## 常见问题

### Q1: 训练显示 `train items=0`

**原因**: Adapter 没有正确初始化 dataloader。

**解决**: 确认 `skillopt-env/adapter.py` 包含：
```python
def setup(self, cfg: dict) -> None:
    super().setup(cfg)
    self.loader.setup(cfg)

def get_dataloader(self):
    return self.loader
```

### Q2: 所有预测都是 `None`

**原因**: 模型输出解析失败或 API 调用错误。

**解决**: 
1. 检查 `rollout.py` 是否使用 `chat_target(system=..., user=...)`
2. 检查输出格式提取的正则表达式

### Q3: 评分始终为 0

**原因**: 返回字段名不匹配。

**解决**: 确保 `rollout.py` 返回：
```python
return {
    "hard": 1,      # 0 或 1
    "soft": 0.95,   # 0.0 到 1.0
    ...
}
```

### Q4: 如何扩展训练数据

**推荐流程**:
1. 每周收集真实使用案例
2. 月度标注和训练
3. 季度大规模扩展（目标 200+ 样本）

## 参考资料

- [SkillOpt 训练报告](./skillopt-training-summary.md)
- [SkillOpt 集成指南](./skillopt-integration-guide.md)
- [route-effort 训练示例](./route-effort/skill-opt/)
- [SkillOpt 官方文档](https://github.com/anthropics/skillopt)

## 总结

完整工作流：

1. ✅ 准备真实训练数据（40+ train, 5+ val, 5+ test）
2. ✅ 创建初始 skill 规则
3. ✅ 配置训练参数
4. ✅ 运行 SkillOpt 训练
5. ✅ 评估结果（目标：hard ≥ 80%, soft ≥ 0.85）
6. ✅ 迭代改进（如需要）
7. ✅ 部署到实际 SKILL.md
8. ✅ 提交到 git
9. ✅ 安装最新版本
10. ✅ 验证运行

**关键成功因素**:
- 使用真实数据，不是编造的样本
- 覆盖所有输出类别和边界情况
- 建立持续改进循环
- 记录每次训练的结果和改进

现在你可以为任何 skill 应用这个工作流！
