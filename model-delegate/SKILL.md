---
name: model-delegate
description: 为 Codex 建立轻量双任务分工。适用于先用 grill-me 确认方案，再把边界清楚的实现任务委派给指定模型执行，并由主任务统一审查验收。
---

# 模型委派

使用 Codex App 原生顶层任务协调。当前任务作为规划与审查任务，另建一个可见执行任务。不要使用子智能体协议、独立 `codex exec`、脚本、插件、MCP 编排、共享状态文件或高频轮询。

## 与 grill-me 联动

`grill-me` 只负责提问、质疑和收敛方案，不负责写代码或创建执行任务。完成 grilling 后，用户显式调用 `$model-delegate`，或明确说“按已确认方案委派执行”，本技能才开始创建执行任务。

承接 grilling 结果时：

1. 把最终确认的方案当作 `DECISION` 和 `INPUTS`，不要重新进行架构争论；
2. 若方案仍有未决选择、范围或验收条件，先回到规划任务补齐，不创建执行任务；
3. 只把已确认的边界、文件范围、验收条件和约束发送给执行任务；
4. 主任务不直接落地实现，只负责拆解、委派、等待、审查和验收。

推荐交接格式：

```text
GRILLING_STATUS: COMPLETE
DECISION: 已确认的实现方案
SCOPE: 本次只执行的范围
ACCEPTANCE: 可验证的完成条件
FILE_BOUNDARIES: 允许读取或修改的文件
CONSTRAINTS: 用户已确认的限制
OPEN_RISKS: 仍需主任务审查的风险
```

先搜索或加载当前运行面提供的任务协调工具。若没有 `create_thread`、`send_message_to_thread`、`wait_threads` 和 `read_thread`，停止并报告不兼容。恢复已有委派任务时优先使用 `list_threads`；若该工具不可用，只能使用已验证的正式 `threadId`，不得猜测候选会话。不得静默改用默认 Agent 或其他执行路径。

## 职责

规划任务负责：

- 理解需求、拆解边界、决定架构和风险；
- 选择可独立验收的执行任务；
- 创建执行任务并保存 `DELEGATION_KEY`、`clientThreadId` 和正式 `threadId` 的可验证绑定；
- 任务恢复后主动盘点、校验并推进已有执行任务；
- 处理阻塞、审查结果、检查差异和完成最终验收；
- 向用户提供最终答复。

执行任务负责：

- 只完成收到的任务包；
- 不改变整体目标或架构，不创建其他任务；
- 不修改无关文件，不执行未授权的破坏性操作；
- 运行约定检查并返回证据；
- 遇到阻塞时停止在安全位置，返回结构化阻塞报告。

## 执行模型确认

每个顶层用户任务首次准备委派时，只确认一次执行模型：

1. 若用户已明确给出 `create_thread` 接受的规范模型名和 reasoning effort，直接使用。
2. 用户未指定时，先检查当前运行面 `create_thread` 明确接受的模型和 effort；若同时支持规范模型 `gpt-5.6-luna` 与 `max`，默认使用 `model=gpt-5.6-luna`、`thinking=max`，不再询问模型选择。
3. 若 `gpt-5.6-luna + max` 不可用，再查看当前推荐组合，列出最多 3 个可传给 `create_thread` 的替代方案，并请求用户明确确认。
4. 默认组合或推荐组合只对当前顶层任务有效；不修改主任务模型、全局默认模型或用户配置。
5. 创建执行任务时显式传入已选定的模型和 effort。模型或 effort 被拒绝时返回原始错误；若拒绝的是默认组合，回到推荐方案确认，不自动换成未经确认的模型。

只有用户明确确认委派后才调用 `create_thread`。确认模型和 effort 即视为允许为本次委派创建执行任务。

只使用 `create_thread` 接受的规范模型名。不得展示或传入带 provider 路由后缀的别名，例如 `-csap-tokenplan`、`-csap-oai1` 或 `-csap-codexbuy-oai`。若运行时元数据使用 `route-alias (canonical-name)` 格式，创建任务时使用括号内的规范模型名，例如 `deepseek-v4-flash-0731`，不得使用括号外的路由别名。

不要从 `send_message_to_thread` 的模型元数据推断 `create_thread` 支持的模型或 effort，也不要根据显示名称猜测。只有 `create_thread` 明确接受过的组合才能作为已确认示例，例如 `model=deepseek-v4-flash-0731 effort=xhigh`。工具只证明请求值时，报告“请求模型/effort”；只有任务元数据明确返回实际值时，才报告“实际模型/effort”。

## 项目工具与技能基线

委派任务应尽量复现主任务的项目工作方式，但不假定执行任务会继承主任务的历史消息、实时 MCP 连接、工具调用结果或已加载上下文。主任务在创建执行任务前，必须记录本次项目基线：

- `PROJECT_BASE_ROOT`：原项目主检出目录；worktree 缺少未跟踪工具目录时，只读获取基线的来源；
- `EXECUTION_ROOT`：执行任务实际写入、测试和 Git 操作的 worktree 或 `local` 项目目录；
- `PROJECT_RULES`：仓库根目录及相关路径下的 `AGENTS.md`、`.wolf/anatomy.md`、`.wolf/cerebrum.md`、`.wolf/buglog.json` 等适用规则；
- `CODEGRAPH`：项目是否存在 `.codegraph/`，以及是否要求优先使用 CodeGraph；
- `OPENWOLF`：OpenWolf 是否生效，以及本次任务需要遵守的 OpenWolf 入口规则；
- `PROJECT_SKILLS`：本任务相关、主任务已使用或项目明确要求的技能；
- `CHECKS`：项目已有的测试、类型检查、构建、格式化或校验命令；
- `TOOL_LIMITS`：工具只读范围、禁止操作和执行环境限制。
- `POST_MERGE_SYNC`：主任务合并后应完成的 CodeGraph 刷新确认和 OpenWolf 记录入口。

任务包必须增加：

```text
TOOLING_BASELINE:
  PROJECT_BASE_ROOT: 原项目主检出目录，只读提供未跟踪的工具和规则基线
  EXECUTION_ROOT: 本次实际写入、测试和 Git 操作目录
  PROJECT_RULES: 适用项目规则及读取顺序
  CODEGRAPH: required/available/not-applicable，以及使用条件
  OPENWOLF: required/available/not-applicable，以及使用条件
  PROJECT_SKILLS: 本任务必须使用的相关技能
  CHECKS: 主任务要求执行的检查
  TOOL_LIMITS: 工具、权限和环境限制
  POST_MERGE_SYNC: 主任务在合并后执行的 CodeGraph 和 OpenWolf 收尾规则
```

执行任务开始时必须：

1. 先读取 `EXECUTION_ROOT` 中的项目规则；若 worktree 缺少未跟踪的 `.codegraph/`、`.wolf/` 或项目技能目录，改从 `PROJECT_BASE_ROOT` 只读获取相同基线；
2. `PROJECT_BASE_ROOT` 存在 `.codegraph/` 且 `CODEGRAPH` 为 required 或 available 时，使用 `PROJECT_BASE_ROOT` 作为 CodeGraph 的项目路径进行架构和影响分析；不得因为 worktree 未复制索引而报告 `TOOLING_GAP`；
3. `PROJECT_BASE_ROOT` 存在 `.wolf/` 且 OpenWolf 生效或任务包标记为 required 时，读取并遵守其适用规则。不得向 `PROJECT_BASE_ROOT` 写入文件、运行会修改其状态的钩子，或把它作为 Git 操作目录；
4. 任何将修改的源码、测试结果、Git 状态和提交必须以 `EXECUTION_ROOT` 为准。来自 `PROJECT_BASE_ROOT` 的 CodeGraph 或规则内容只用于理解项目约定，不能替代对 worktree 当前文件的检查；
5. 使用 `PROJECT_SKILLS` 中与任务相关的技能，并按 `CHECKS` 在 `EXECUTION_ROOT` 执行验证；
6. 只使用与本任务相关的工具，不要求无关的全局工具全部参与。

主任务和执行任务不能使用同一实时工具连接时，执行任务必须在报告中说明实际可用性。仅当 `PROJECT_BASE_ROOT` 与 `EXECUTION_ROOT` 都无法提供必需工具、技能或项目规则时，才返回 `TOOLING_GAP`；不得因 worktree 缺少未跟踪目录而静默降级或误报缺失。可选工具缺失但不影响验收时，必须记录缺失和替代依据。

## 主任务合并后同步

执行任务不得把 worktree 工具状态写回主项目。执行分支合并并通过关键检查后，由主任务在 `PROJECT_BASE_ROOT` 完成收尾：

1. 使用 `PROJECT_BASE_ROOT` 重新执行 CodeGraph 架构或影响分析，确认查询针对已合并的主项目内容；工具提示索引尚未同步时，等待其自动更新后重试。不得复制 worktree 的 `.codegraph/`、自行初始化索引或将未合并内容写入主项目索引。
2. 按 `POST_MERGE_SYNC` 和项目规则运行 OpenWolf 的受支持记录流程。只有项目明确提供的钩子、命令或 `.wolf` 记录约定可以写入；不得猜测格式、伪造记录或把 worktree 的会话状态直接复制到主项目。
3. OpenWolf 产生记录文件时，主任务必须检查其内容只描述已合并、已验收的变更；按项目规则运行必要检查，并确保记录成为主项目可审查状态的一部分后才报告完成。
4. 没有受支持的 OpenWolf 记录入口时，主任务在最终报告中写 `OPENWOLF_RECORD: NOT-AVAILABLE` 和实际原因。项目规则要求记录但记录失败时，标记 `STATUS: BLOCKED`；未要求记录时可继续完成，但不得声称已记录。

## 创建执行任务

默认只创建一个执行任务。仅当子任务互相独立且写入范围隔离时才并行创建多个。

调用 `create_thread` 时：

- 使用用户指定或按上述优先级确定的模型和 effort；
- 设置清晰标题；
- 关联当前项目；
- Git 项目默认使用独立 worktree；只有用户明确要求直接使用当前项目目录时，才使用 `local` 环境；
- 使用独立 worktree 时，任务包必须要求执行任务提交全部预期变更，并返回实际 worktree 路径、分支名和提交 ID；
- 不使用 worktree 时，必须确保写入范围不重叠；无法隔离时串行执行；
- 将完整任务包放入首条消息。

主任务必须为每个执行任务生成唯一、不可复用的 `DELEGATION_KEY`，并在当前规划任务的消息记录中保存以下绑定：`DELEGATION_KEY`、创建响应中的 `clientThreadId`、正式 `threadId`、项目、`EXECUTION_ROOT`、worktree 分支和任务标题。不得用任务标题、模型、创建时间、项目名、最近活动会话或用户可见短 ID 推断正式 `threadId`。

若创建时只返回 `clientThreadId`，等待与该 `clientThreadId` 对应的任务初始化完成后，才记录正式 `threadId`。只有创建响应、任务列表元数据或运行面明确返回的映射，才能确认 `clientThreadId -> threadId`。后续通信只使用已验证的正式 `threadId`；不得把 `clientThreadId` 当成正式 `threadId` 传入执行工具。

任务包必须包含：

```text
ROLE: Bounded execution task reporting to the planning task
DELEGATION_KEY: 主任务生成的本次委派唯一标识，所有状态报告必须原样回显
SCOPE: 明确目标和允许处理的范围
INPUTS: 必要上下文、文件和已知事实
TOOLING_BASELINE: 包含 PROJECT_BASE_ROOT、EXECUTION_ROOT、POST_MERGE_SYNC 和主任务记录的项目规则、工具、技能、检查基线
OUTPUT: 预期交付物和报告格式
ACCEPTANCE: 可执行的验收条件
FILE_BOUNDARIES: 允许读取或修改的文件范围
CONSTRAINTS: 权限、安全、兼容性和禁止事项
```

使用 worktree 时，任务包的 `CONSTRAINTS` 还必须写明：执行任务不得把未提交修改作为最终交付；完成前必须提交变更、保持 worktree 状态可审查，并返回 `WORKTREE_PATH`、`WORKTREE_BRANCH` 和 `COMMIT_ID`。执行任务不得自行合并到主分支或删除 worktree。

不要把整体架构判断、跨任务协调、权限决策或最终验收交给执行任务。

## 等待与阻塞反馈

使用一次有界 `wait_threads` 等待状态变化；不要循环读取任务或发送心跳。等待返回完成、需要关注或超时后，再按需使用 `read_thread` 查看结果。

## 暂停后恢复

规划任务在重新启动、恢复上下文或用户要求继续时，必须先恢复已有委派，再开始新委派、重新拆解或向用户报告完成：

1. 从当前规划任务记录读取每个已知 `DELEGATION_KEY`、`clientThreadId` 和正式 `threadId`；可用时使用 `list_threads` 交叉检查任务元数据。
2. 只有同时满足以下条件，才视为身份已验证：正式 `threadId` 有运行面返回的创建映射；任务属于同一项目；任务首条消息或状态报告回显相同 `DELEGATION_KEY`；其 `EXECUTION_ROOT`、任务范围与保存的绑定一致。
3. 不得因标题、分支名、模型、最近活动时间、相同项目或显示顺序相似而选择会话。任何一项无法验证时，记录 `THREAD_IDENTITY_GAP`，不得向候选任务发送继续、修改、合并或清理指令。
4. 身份已验证且任务未完成时，主任务必须向原正式 `threadId` 发送一次恢复消息，要求先检查当前状态，再从原任务包的安全位置继续。每次恢复周期对同一任务至多发送一次；随后使用一次有界 `wait_threads` 等待新状态，避免重复催促。
5. 身份已验证且任务返回 `STATUS: BLOCKED` 时，主任务能根据已确认方案自行决定的，立即用同一 `threadId` 发送决定并要求继续；需要用户新决定的，向用户报告该阻塞，不创建替代任务。
6. 身份已验证且任务已完成时，直接进入审查、合并、验证和主任务收尾，不发送恢复消息。

恢复消息格式：

```text
DELEGATION_KEY: 原样回显已验证标识
ACTION: RESUME_ORIGINAL_TASK
INSTRUCTION: 先检查当前 worktree、分支、未完成步骤和已有检查结果；仅在原任务包范围内继续。
REPORT: 回显 DELEGATION_KEY、当前状态、已完成项、下一步、阻塞项和实际检查。
```

执行任务遇到无法自行安全解决的问题时，结束当前回合并返回：

```text
DELEGATION_KEY: 原样回显主任务标识
STATUS: BLOCKED
BLOCKER: 阻塞事实
EVIDENCE: 已检查内容和实际错误
DECISION_NEEDED: 需要规划任务决定的问题
SAFE_NEXT_STEP: 获得决定后可执行的最小下一步
```

规划任务读取身份已验证的阻塞报告，完成必要判断，再用 `send_message_to_thread` 向同一 `threadId` 发送决定或修正任务。续派默认不传 model 或 thinking，保持原执行任务设置不变。不要新建替代执行任务，除非原任务已不可恢复或需要隔离的新范围。

等待本身不需要高频主模型推理；只有工具返回新状态或任务消息后，规划任务才继续处理。超时不等于失败，先读取任务状态再判断。

## 审查与完成

执行任务完成时必须返回：

```text
STATUS: COMPLETE
DELEGATION_KEY: 原样回显主任务标识
RESULT: 完成内容
FILES: 检查或修改的文件
CHECKS: 实际运行的检查及结果
TOOLS_USED: 实际使用的项目工具和关键工具调用
SKILLS_USED: 实际使用的相关技能
TOOLING_GAPS: 未获得的工具、技能或规则，以及影响
BASELINE_MATCH: MATCH/PARTIAL/MISMATCH，并说明依据
RISKS: 未验证项和剩余风险
```

若执行任务使用了临时 worktree，返回中必须额外包含：

```text
WORKTREE_PATH: 实际使用的 worktree 路径
WORKTREE_BRANCH: 对应分支名
COMMIT_ID: 执行任务提交的变更提交 ID
WORKTREE_STATE: 变更是否已提交、合并或保留，以及是否可安全清理
```

规划任务必须：

1. 等待所有执行任务结束；
2. 读取每个结果并检查实际文件差异；
3. 验证关键检查，不能把执行任务声明当作最终证据；
4. 对照 `TOOLING_BASELINE` 审查 `TOOLS_USED`、`SKILLS_USED`、`TOOLING_GAPS` 和 `BASELINE_MATCH`；必需基线不匹配时不得声明完成；
5. 确认 worktree 分支、提交 ID 和主仓库路径属于本次委派，且主仓库没有会被覆盖的未提交修改；
6. 从主仓库当前主分支手动合并执行分支，优先使用 `git merge --no-ff <WORKTREE_BRANCH>`；只有确需单独应用提交时才使用 `git cherry-pick <COMMIT_ID>`；
7. 解决合并冲突并重新运行关键检查；合并失败或无法验证时不得声明完成；
8. 按“主任务合并后同步”完成 CodeGraph 刷新确认和 OpenWolf 记录；必需记录失败时不得清理 worktree 或声明完成；
9. 只有合并、验收和必需同步成功后，才清理本次委派创建的 worktree；只有 `git branch -d <WORKTREE_BRANCH>` 能安全确认分支已合并时才删除分支，使用 cherry-pick 后不得强制删除源分支；
10. 需要修正时继续向原 `threadId` 派发；
11. 统一整合、验收并回复用户。

若执行任务未提交变更、提交 ID 不存在、worktree 仍有未保存修改，或主仓库存在无法安全处理的未提交修改，规划任务必须先续派要求执行任务整理并提交，或报告 `STATUS: BLOCKED`；不得直接复制文件、强制重置、覆盖主仓库或跳过合并。

## Worktree 清理

临时 worktree 只用于隔离执行任务。主任务必须完成“审查 -> 合并 -> 验收 -> 清理”完整闭环，不能只报告执行任务完成：

1. 清理前确认变更已合并到主分支，关键检查已通过，且 `WORKTREE_STATE` 为可安全清理；仍有未保存、未应用或需要用户保留的变更时不得清理。
2. 只删除本次 `model-delegate` 委派创建的 worktree 路径，不得使用 `git clean -fdx`、强制重置或删除主仓库工作区。
3. 清理命令按已验证路径执行，例如：

```bash
git worktree remove <worktree-path>
git branch -d <worktree-branch>
```

4. 分支仅在 `git branch -d <worktree-branch>` 成功确认变更已合并后删除；否则保留分支并只报告位置。禁止用 `git branch -D` 绕过未合并保护。
5. 清理后运行 `git worktree list` 验证；无法清理时在最终报告中列出路径、分支和原因。

最终报告必须包含执行任务 ID、`DELEGATION_KEY`、已验证的 `clientThreadId -> threadId` 绑定、请求模型/effort、恢复动作、合并方式、合并提交或结果、完成状态、验证结果、`CODEGRAPH_POST_MERGE`、`OPENWOLF_RECORD` 和无法确认的事项。
若使用过 worktree，最终报告必须包含 `WORKTREE_PATH`、`WORKTREE_BRANCH`、合并结果和清理结果；未能合并或清理时必须列出路径、分支和原因，并将状态标记为 `BLOCKED` 或未完成。
