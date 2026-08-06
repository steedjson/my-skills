---
name: cc-switch-reasoning-tier-repair
description: 检查并修复 Codex 与 cc-switch 模型 reasoning 档位配置。用户提到 max、ultra 档位消失，Codex 或 cc-switch 重启重装后档位被恢复，模型目录与 config.toml 不一致，或要求补全模型档位时使用。
---

# CC-Switch Reasoning Tier Repair

## 工作边界

只处理当前配置中已经存在的模型。使用 `references/expected-tier-map.json` 作为已核实模型的修复基准；未知模型不猜测档位、不删除现有字段，保留原值并报告为 unresolved。

每次执行都读取实时状态：

- `CODEX_HOME/config.toml`，未设置 `CODEX_HOME` 时使用 `~/.codex/config.toml`；
- `config.toml` 的 `model_catalog_json` 指向的 JSON 模型目录；
- `models_cache.json` 运行时模型缓存；
- 当前 `[model_providers.*]` 中包含已核实模型的内嵌 `models` 数组。CCSwitchMulti
  会生成动态 Provider 名，不能假定固定名称。

## 执行流程

1. 先运行检查，不写入文件：

   ```bash
   python3 /path/to/cc-switch-reasoning-tier-repair/scripts/repair.py --check --effort max
   ```

2. 用户明确要求修复时，先预览：

   ```bash
   python3 /path/to/cc-switch-reasoning-tier-repair/scripts/repair.py --dry-run --effort max
   ```

3. 预览结果符合预期后，去掉 `--dry-run` 执行修复。脚本会在写入前备份
   `config.toml`、当前 catalog 和 `models_cache.json`，并在写入后重新解析
   TOML 与 JSON。

4. 使用 `--effort max` 同时修复顶层 `model_reasoning_effort`。使用 `--config`
   指定配置文件，使用 `--backup-dir` 指定备份目录；需要其他已核实模型映射时，
   用 `--tier-map` 指定 JSON 映射文件。

5. 报告实际修改的模型、备份路径、未解析模型和验证结果。不要输出 API key、userToken 或完整 provider 配置。

## 重要限制

- catalog 中声明的档位只代表客户端可选项，不等于路由后端一定接受。修复后仍需用一次真实请求或新 Codex 任务验证目标档位。
- `OK` 只表示配置文件、当前 catalog 和运行时缓存一致；不表示真实出站请求已经
  使用该档位。
- 重启或重新安装后如果配置再次被覆盖，重新运行本 Skill；不要把一次成功修复当作永久持久化。
- 不要删除未知档位、未知模型或用户的其他配置。发现 JSON/TOML 无法解析时停止并先报告，不要覆盖损坏文件。

## 资源

- `scripts/repair.py`：读取实时配置、检查漂移、备份并修复。
- `references/expected-tier-map.json`：已核实模型与档位映射；修改前应确认它仍符合当前模型目录。
