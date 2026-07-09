# SkillOpt 集成指南

本文档说明如何为新的 Claude skill 集成 SkillOpt 训练系统。

## 前置条件

1. 已安装 SkillOpt：`pip install skillopt`
2. 配置了模型后端（Claude、OpenAI 等）
3. 准备了训练数据集

## 集成步骤

### 1. 创建环境目录

在 `SkillOpt/skillopt/envs/` 下创建新环境：

```bash
cd /path/to/SkillOpt/skillopt/envs
mkdir your_skill_name
cd your_skill_name
touch __init__.py adapter.py rollout.py dataloader.py
```

### 2. 实现 DataLoader

创建 `dataloader.py`，继承自 `SplitDataLoader`：

```python
from skillopt.datasets.base import SplitDataLoader

class YourSkillDataLoader(SplitDataLoader):
    def __init__(
        self,
        split_dir: str | None = None,
        data_path: str | None = None,
        split_mode: str = "split_dir",
        split_ratio: tuple[float, float, float] = (0.8, 0.1, 0.1),
        split_seed: int = 42,
        split_output_dir: str | None = None,
    ):
        super().__init__(
            split_dir=split_dir,
            data_path=data_path,
            split_mode=split_mode,
            split_ratio=split_ratio,
            split_seed=split_seed,
            split_output_dir=split_output_dir,
        )
```

数据格式：
- `train/items.json`: `[{"id": "train-0", "input": "...", "expected_output": "..."}]`
- `val/items.json`: 同上
- `test/items.json`: 同上

### 3. 实现 Rollout

创建 `rollout.py`，实现任务执行逻辑：

```python
from skillopt.model import chat_target

def process_one(
    item: dict,
    skill_content: str,
    exec_timeout: int = 120,
    max_completion_tokens: int = 4096,
) -> dict:
    """处理单个任务"""
    
    # 1. 构建 prompt
    system_prompt = f"{skill_content}\n\n你的任务描述..."
    user_prompt = f"输入: {item['input']}"
    
    # 2. 调用模型
    try:
        response, _ = chat_target(
            system=system_prompt,
            user=user_prompt,
            max_completion_tokens=max_completion_tokens,
            timeout=exec_timeout,
        )
        raw_output = response
        timed_out = False
    except Exception as e:
        raw_output = f"ERROR: {e}"
        timed_out = True
    
    # 3. 提取结果并评分
    predicted = extract_result(raw_output)
    expected = item.get("expected_output")
    hard_score, soft_score = score_prediction(predicted, expected)
    
    # 4. 返回结果（必须包含 hard 和 soft 字段）
    return {
        "id": item["id"],
        "input": item["input"],
        "expected_output": expected,
        "predicted_output": predicted,
        "hard": hard_score,      # 必须：0 或 1
        "soft": soft_score,      # 必须：0.0 到 1.0
        "raw_output": raw_output,
        "timed_out": timed_out,
    }
```

**关键点**：
- 必须使用 `chat_target(system=..., user=...)` 而非 `messages` 参数
- 返回结果必须包含 `hard`（0/1）和 `soft`（0.0-1.0）字段
- `hard` 表示精确匹配，`soft` 表示部分正确程度

### 4. 实现 Adapter

创建 `adapter.py`，桥接 SkillOpt 和你的环境：

```python
from skillopt.envs.base import BaseAdapter
from .dataloader import YourSkillDataLoader
from .rollout import process_one

class YourSkillAdapter(BaseAdapter):
    def __init__(self, cfg: dict):
        super().__init__(cfg)
        
        # 初始化 dataloader
        self.loader = YourSkillDataLoader(
            split_dir=cfg.get("split_dir"),
            data_path=cfg.get("data_path"),
            split_mode=cfg.get("split_mode", "split_dir"),
            split_ratio=cfg.get("split_ratio", (0.8, 0.1, 0.1)),
            split_seed=cfg.get("split_seed", 42),
            split_output_dir=cfg.get("split_output_dir"),
        )
    
    def setup(self, cfg: dict) -> None:
        """必须实现：初始化 dataloader"""
        super().setup(cfg)
        self.loader.setup(cfg)
    
    def get_dataloader(self):
        """必须实现：返回 dataloader"""
        return self.loader
    
    def build_train_env(self, batch_size: int, seed: int, **kwargs) -> list[dict]:
        """构建训练批次"""
        batch_spec = self.loader.build_train_batch(batch_size, seed)
        return batch_spec.items
    
    def build_eval_env(self, env_num: int, split: str, **kwargs) -> list[dict]:
        """构建评估批次"""
        batch_spec = self.loader.build_eval_batch(env_num, split)
        return batch_spec.items
    
    def run_envs(
        self,
        envs: list[dict],
        skill_content: str,
        exec_timeout: int = 120,
        max_completion_tokens: int = 4096,
        n_workers: int = 8,
    ) -> list[dict]:
        """并行执行任务"""
        from concurrent.futures import ThreadPoolExecutor
        
        def worker(item):
            return process_one(item, skill_content, exec_timeout, max_completion_tokens)
        
        with ThreadPoolExecutor(max_workers=n_workers) as executor:
            results = list(executor.map(worker, envs))
        
        return results
```

**关键方法**：
- `setup(cfg)`: 必须调用 `self.loader.setup(cfg)`
- `get_dataloader()`: 必须返回 dataloader 实例
- `build_train_env()`: 从训练集采样
- `build_eval_env()`: 从验证集/测试集采样
- `run_envs()`: 并行执行任务并返回结果

### 5. 注册环境

在 `SkillOpt/skillopt/envs/__init__.py` 中注册：

```python
from .your_skill_name.adapter import YourSkillAdapter

ENV_REGISTRY = {
    "searchqa": SearchQAAdapter,
    "route_effort": RouteEffortAdapter,
    "your_skill_name": YourSkillAdapter,  # 添加这行
}
```

### 6. 创建 Prompts

在环境目录下创建 `prompts/` 子目录：

```bash
mkdir prompts
touch prompts/system.md prompts/user.md
```

**system.md**（skill 指令模板）：
```markdown
{skill}

你是一个 XXX 分类器。任务是...

输出格式：
<result>...</result>
```

**user.md**（用户输入模板）：
```markdown
输入: {input}

请按照上述格式输出结果。
```

### 7. 创建训练配置

创建 `config.yaml`：

```yaml
env:
  name: your_skill_name
  skill_init: initial.md          # 初始 skill 文件
  split_mode: split_dir
  split_dir: train-data           # 数据目录
  out_root: skillopt-out
  exec_timeout: 120

train:
  rollout_batch_size: 20
  n_epochs: 3
  n_workers: 8
  
  fast_update:
    active: true
    batch_sizes: [20, 20]
  
  slow_update:
    active: true
    batch_sizes: [10, 10]

model:
  backend: claude
  target_model: claude-sonnet-4-20250514
  meta_model: claude-sonnet-4-20250514
```

### 8. 准备初始 Skill

创建 `initial.md`，包含初始版本的 skill 规则：

```markdown
# Your Skill Name

## 规则

1. 规则一
2. 规则二
3. ...

## 输出格式

<result>结果</result>
```

**注意**：不要包含 YAML frontmatter（`---` 包裹的部分），SkillOpt 需要纯文本指令。

### 9. 运行训练

```bash
cd your-skill-opt-dir
skillopt-train --config config.yaml
```

## 常见问题

### Q1: 训练时显示 `train items=0`

**原因**：Adapter 没有实现 `setup()` 或 `get_dataloader()` 方法。

**解决**：
```python
def setup(self, cfg: dict) -> None:
    super().setup(cfg)
    self.loader.setup(cfg)  # 必须调用

def get_dataloader(self):
    return self.loader  # 必须返回
```

### Q2: 所有预测都是 `predicted=None`

**原因**：
1. `chat_target()` 调用错误（使用了 `messages` 参数）
2. 结果提取函数失败

**解决**：
- 使用 `chat_target(system=..., user=...)` 格式
- 检查正则表达式或解析逻辑

### Q3: 评分始终为 0

**原因**：返回结果缺少 `hard` 和 `soft` 字段，或使用了错误的字段名（如 `correct`、`soft_score`）。

**解决**：确保返回字典包含：
```python
return {
    "hard": 1,      # 0 或 1
    "soft": 0.95,   # 0.0 到 1.0
    ...
}
```

### Q4: 模型没有输出预期格式

**原因**：system prompt 太复杂，或包含了 skill frontmatter。

**解决**：
- 使用简化版 initial skill（无 frontmatter）
- 在 system prompt 中明确输出格式要求

## 参考实现

完整参考实现：
- **SearchQA**: `/SkillOpt/skillopt/envs/searchqa/`
- **RouteEffort**: `/SkillOpt/skillopt/envs/route_effort/`

## 训练后

训练完成后，查看结果：

```bash
# 查看训练状态
cat skillopt-out/runtime_state.json | python3 -m json.tool

# 查看训练历史
cat skillopt-out/history.json | python3 -m json.tool

# 查看最佳 skill
cat skillopt-out/best_skill.md

# 测试集结果
cat skillopt-out/test_eval_final/rollout.jsonl
```

将 `best_skill.md` 部署到实际环境中使用。
