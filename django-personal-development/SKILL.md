---
name: django-personal-development
description: 按个人工程规范开发、修改、重构和审查 Django 后端。适用于新项目、旧项目和渐进式迁移；涉及 Django、DRF、Ninja、API、Model、Migration、权限、任务、Admin、测试或配置时使用。
---

# 个人 Django 开发规范

以 `sugon-webwork-backend` 作为个人习惯的参考项目。该项目不可见时，不猜测其实现；把它当作待接入的规范样本。通用安全原则来自 `django-development`，本技能增加个人默认规则。

## 总原则

1. 用户当前要求优先。
2. 项目 `AGENTS.md`、`CLAUDE.md`、README、CI 和实际代码优先于本技能；安全、权限、数据一致性不能被个人偏好覆盖。
3. 新项目采用本技能的个人默认；旧项目先遵循现状，只在任务边界内渐进改善。
4. 先侦察、再设计、后修改、最后验证。禁止凭目录名或记忆推断框架和业务规则。
5. 不做无关重构，不覆盖用户未提交修改；高风险操作先停下确认。

## 项目模式

先标记一种模式：

- `NEW_PROJECT`：无历史约束，建立个人默认规范。
- `LEGACY_PROJECT`：已有稳定代码，局部兼容，禁止顺手重构。
- `MIGRATION_PROJECT`：明确进行规范迁移，按阶段、边界和回滚点推进。

旧项目新增代码规则：优先贴近邻近模块；若采用个人新规范，必须说明新旧边界和后续迁移方式。发现规范冲突时标记 `CONVENTION_GAP`；涉及权限、数据范围、迁移或不可逆操作时阻断并请求确认。

## 侦察清单

按风险缩放：微任务检查指导文件和邻近代码；普通任务检查架构和验证入口；高风险任务再做完整调用链和数据影响分析。

确认：

- Python、Django、DRF/Ninja 版本和运行方式。
- settings 分层、环境变量、数据库、缓存、任务队列和外部服务。
- App 边界、路由、View、Serializer/Schema、Service/Use Case、Selector/Query、Model、Task、Signal、Admin、Command 和测试调用链。
- 现有命名、异常、日志、事务、权限、分页、错误响应、测试和发布命令。
- Git 工作区状态与用户未提交改动。

仓库存在 `.codegraph/` 时，先用 CodeGraph 定位符号和调用路径，再用精确阅读补充。

## 个人默认架构

仅对新项目或明确迁移生效；旧项目保持其已有层次。

- View/ViewSet：接收参数、认证授权、调用业务层、返回响应；不放跨模型业务流程。
- Serializer/Schema：输入校验、字段可写性、输出转换；不承载核心业务编排。
- Model：自身状态、不变量和简单领域行为。
- QuerySet/Manager：可复用、局部查询。
- Selector：复杂读操作、查询组合和数据装载。
- Service：跨模型写操作、事务、状态流转和副作用编排。
- Task：异步边界；任务必须可重试、可观测、幂等或明确去重策略。

简单逻辑就近放置；跨模型、跨入口或需要事务的逻辑进入 Service。没有必要时不新增层，不为“看起来整齐”制造空壳文件。跨 App 访问优先通过公开 Service/Selector，避免直接依赖内部实现。

## 新项目固定目录结构

新项目默认采用以下结构；旧项目不因本技能强行搬迁，只有明确的 `MIGRATION_PROJECT` 才分阶段调整：

```text
project-root/
├── manage.py
├── pyproject.toml
├── .env.example
├── config/
│   ├── __init__.py
│   ├── urls.py
│   ├── asgi.py
│   ├── wsgi.py
│   └── settings/
│       ├── __init__.py
│       ├── base.py
│       ├── local.py
│       ├── test.py
│       └── production.py
├── apps/
│   └── <app_name>/
│       ├── __init__.py
│       ├── admin.py
│       ├── apps.py
│       ├── constants.py
│       ├── exceptions.py
│       ├── filters.py
│       ├── managers.py
│       ├── models.py
│       ├── permissions.py
│       ├── serializers.py
│       ├── selectors.py
│       ├── services.py
│       ├── tasks.py
│       ├── urls.py
│       ├── views.py
│       ├── migrations/
│       └── tests/
│           ├── __init__.py
│           ├── factories.py
│           ├── test_models.py
│           ├── test_selectors.py
│           ├── test_services.py
│           └── test_api.py
├── common/
│   ├── exceptions.py
│   ├── permissions.py
│   ├── pagination.py
│   ├── responses.py
│   └── middleware.py
└── tests/
    └── integration/
```

固定原则：

- `models.py`、`views.py`、`serializers.py`、`urls.py`、`admin.py`、`apps.py`、`migrations/` 是基础文件；即使暂时为空，也只在 Django 需要或项目约定要求时保留。
- `services.py` 处理跨模型写入、事务和业务编排；`selectors.py` 处理复杂读操作；不把业务逻辑堆到 View 或 Serializer。
- `constants.py` 放状态、枚举和跨模块常量；`exceptions.py` 放 App 业务异常；`filters.py` 放列表筛选；`managers.py` 只放 QuerySet/Manager 查询复用。
- `tasks.py` 只放异步任务；没有任务时不创建空文件。
- App 规模较大时，可将 `models.py`、`serializers.py`、`views.py`、`services.py`、`selectors.py` 拆成同名目录，但对外导入路径和边界保持稳定。
- `common/` 只收真正跨 App 的稳定基础能力；禁止把某个 App 的业务逻辑放进 `common/`。
- App 之间依赖方向优先为：API → Service/Selector → Model/Query；禁止 View 直接编排多个 App 的内部细节。

## 配置文件规范

- `config/settings/base.py`：所有环境共享配置，不写密钥、生产地址和环境专属开关。
- `config/settings/local.py`：本地开发配置，可覆盖数据库、调试、邮件和本地服务。
- `config/settings/test.py`：测试专用配置，保证测试隔离、速度和可重复。
- `config/settings/production.py`：生产安全配置，明确允许来源、HTTPS、Cookie、日志、缓存、数据库和外部服务。
- `DJANGO_SETTINGS_MODULE` 通过环境变量指定；启动命令、ASGI/WSGI 和 CI 使用同一配置约定。
- `.env.example` 只列变量名、类型/示例和是否必填，不提交真实凭据；读取环境变量集中在配置层。
- 配置按“基础默认值 → 环境覆盖 → 部署注入”处理；禁止在业务代码中直接读取环境变量。
- 新增配置必须说明默认值、适用环境、敏感性、部署来源和回滚方式。
- 修改认证、CORS、CSRF、数据库、缓存、任务队列、日志或密钥配置，按 `HIGH`/`CRITICAL` 风险门禁处理。

## API 默认规则

先采用项目已使用的 API 框架。新项目使用参考项目的稳定模式；参考项目不可用时默认选择 DRF，除非用户明确指定 Ninja 或原生 Django。

个人 API 默认：

- 路由统一挂载到 `/api/v1/`；版本升级不修改旧版本语义，破坏性变更新建版本。实际项目已有版本策略时优先遵循现状。
- 资源 URL 使用名词和复数，层级只表达真实从属关系；命名与现有项目保持一致。
- 默认采用 `ViewSet + Serializer + Router`；非 CRUD、复杂动作或特殊响应使用 `APIView`/明确的 operation，不为了形式强行套 ViewSet。
- View 只做请求编排：解析输入、认证授权、调用 Service/Selector、返回响应。
- Serializer 只做输入校验、字段映射和输出转换；跨模型写入进入 Service。
- 列表接口明确分页、筛选、排序、搜索、最大页大小和默认排序；禁止无边界返回大数据集。
- 成功响应、错误响应、分页响应保持项目统一 envelope；新增接口不得自行发明格式。
- 使用正确 HTTP 状态码；创建、更新、删除、异步受理和幂等重复请求分别定义行为。
- 每个接口明确认证、角色/对象权限和用户、组织或租户数据范围。
- 写接口评估幂等键、事务边界、并发、重试和重复副作用。
- 修改公共接口前检查前端、任务、导出、第三方和文档调用方，并保留兼容窗口。

## Model 与数据库默认规则

- 主键、软删除、时间字段和基础模型以参考项目/现有项目为准；新项目不得在未确认时强行迁移主键策略。
- 核心模型默认评估 `created_at`、`updated_at`、状态字段和审计需求。
- 状态枚举优先使用 Django `TextChoices`/`IntegerChoices` 或项目既有等价物。
- 业务不变量、唯一性和数据范围优先落到数据库约束；高频查询评估索引。
- `on_delete` 按业务语义选择，禁止无脑 `CASCADE`。
- 主动检查 N+1，合理使用 `select_related` 和 `prefetch_related`。
- Schema migration 与 data migration 分开；迁移保持单一目的、可回滚或有明确恢复方案。
- 大表变更评估锁表、分批、超时、在线发布和历史数据兼容。

## 多 App Model 依赖与循环引用

多个 App 之间允许存在数据库关系，但禁止通过 Python 顶层导入形成循环依赖。关系依赖和代码依赖分开处理。

### 默认写法

```python
# 正确：关系使用字符串引用，不在文件顶部 import peer model
class Order(models.Model):
    customer = models.ForeignKey(
        "customers.Customer",
        on_delete=models.PROTECT,
        related_name="orders",
    )

# 自定义用户模型使用配置项，不导入 Django 内置 User
class AuditLog(models.Model):
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="audit_logs",
    )
```

规则：

- `ForeignKey`、`OneToOneField`、`ManyToManyField` 的普通跨 App 关系使用 `"app_label.ModelName"`；不需要、也不应该把每个 Model 写入 settings。
- 只有可替换或项目级可配置的模型（当前主要是 User）使用 `settings.AUTH_USER_MODEL`；禁止使用 `django.contrib.auth.models.User`，也不要猜测自定义用户 App/Model 名称。
- 不为了声明字段关系而在 `models.py` 顶层导入其他 App 的 Model。
- 反向关系必须显式设置稳定、唯一的 `related_name`，避免默认名称冲突。
- Model 不直接导入 Service；跨 App 写入、状态流转和事务放到 Service。
- Model 中确需查询其他 App 时，优先移到 Selector/Service；无法移动时在方法内部延迟导入，并补充原因和测试，不把延迟导入当作默认架构。
- 类型标注只为静态检查导入时使用 `if TYPE_CHECKING:`，运行时关系仍用字符串引用。必要时配合 `from __future__ import annotations`。
- `apps.get_model()` 只用于迁移、数据修复或 App 加载阶段的动态获取；普通业务代码不得用它隐藏依赖。
- Signal 在 `AppConfig.ready()` 中加载；signal 模块只导入必要 Model，避免 Model 模块反向导入 signal、Service 或其他 App 初始化代码。
- 迁移文件显式声明跨 App `dependencies`；数据迁移中使用历史模型 `apps.get_model()`，不能导入当前 Model。

### 自定义用户模型规则

个人默认：新项目使用自定义 `User`，但优先继承 Django 的 `AbstractUser`，保留 Django Admin、权限和认证生态；只有认证字段、认证流程或权限模型确实不同，才使用 `AbstractBaseUser` 并自行实现必要协议。已有项目不因本技能替换用户模型。

当前项目使用自定义 User，不采用 Django 内置 `auth.User`。开发前先从 settings、用户 App 和迁移确认真实用户模型；不得根据 `users`、`accounts` 等目录名猜测。

- 所有 Model 外键、一对一和多对多用户关系默认使用 `settings.AUTH_USER_MODEL`。
- Model 文件不得导入 `django.contrib.auth.models.User`。
- 运行时确实需要用户 Model 时使用 `get_user_model()`；类型标注使用 `TYPE_CHECKING`，不要制造顶层运行时循环导入。
- 自定义 User 的认证字段、管理器、权限字段和登录方式以项目实现为准，不擅自补回 Django 默认字段或认证流程。
- 修改用户模型、认证后端、权限字段或登录接口时，按 `HIGH`/`CRITICAL` 风险处理，并检查迁移、现有账号、Token/Session、Admin、任务和外部调用方。
- 迁移和数据迁移使用历史模型 `apps.get_model()`；不要在迁移文件中导入当前自定义 User。

### 依赖方向

新项目优先保持单向依赖：

```text
API/View → Service/Selector → Domain Model
                         ↘ 其他 App 的公开 Service/Selector
```

如果两个 App 的 Model 互相持有业务逻辑或频繁互相调用：

1. 先判断是否存在真实数据库关系；没有关系就移除不必要导入。
2. 有关系时改用字符串关系声明，业务操作移到一个明确的拥有方 Service。
3. 共享值对象、枚举或基础模型提取到低依赖的 `common`/`core`，但禁止把业务逻辑随意塞进公共 App。
4. 仍然无法拆分时建立 Facade/Service 边界，禁止继续增加双向 Model 调用。
5. 任何跨 App 重构都记录依赖方向、迁移影响、调用方和回滚方案。

出现 `ImportError`、`AppRegistryNotReady` 或迁移加载循环时，先画出导入链并修复依赖方向；不要靠随机调整 import 顺序、复制 Model 或批量使用 `apps.get_model()` 掩盖问题。

## 内置 `stdkit` 工具包

当项目过去通过安装依赖引入 `sugon-stdkit`，现在需要直接放入项目维护时，项目内统一命名为 `stdkit`。默认采用“内置源码包 + 清晰边界 + 可追踪来源”方案，不把工具包代码散落到各个 App。

### 推荐目录

```text
project-root/
├── libs/
│   └── stdkit/
│       ├── __init__.py
│       ├── config/
│       ├── db/
│       ├── exceptions.py
│       ├── logging.py
│       ├── pagination.py
│       ├── permissions.py
│       ├── responses.py
│       ├── utils/
│       └── tests/
├── apps/
├── config/
└── pyproject.toml
```

如果项目已有 `core/`、`common/` 或 `packages/`，优先放入已有的基础包目录；不要为了形式重复创建 `libs/`。项目内包名统一为 `stdkit`；外部历史包名 `sugon-stdkit` 只作为来源、迁移记录或兼容依赖名称。

### 现有结构评估与优化

当前可见的 `stdkit` 样本位于 `openclaw/document/python/django/demo/stdkit`，包含：`db/models`、`rest`、`middleware`、`dingtalk`、`sms`、`map`、`utils`。它已经形成“数据库基础能力、Web 基础能力、外部服务、工具函数”四类能力，但现状存在职责混合风险：

- `db/models/__init__.py` 过大，同时承载字段、Manager、基础 Model、序列化、时间、软删除和动态 Model 获取；应拆成 `db/models/base.py`、`db/models/managers.py`、`db/models/fields.py`、`db/models/serializers.py`、`db/registry.py`。
- `rest/services.py` 同时包含分页、字段包装、枚举转换、客户端 IP、CRUD 数据服务；应拆为 `rest/pagination.py`、`rest/transformers.py`、`rest/request.py`，具体 CRUD Service 留在业务 App。
- `rest/views.py` 中的导出、异步任务、缓存和 View 基类耦合；应拆成 `rest/views/base.py`、`rest/export/`、`rest/tasks/`，工具包只保留可复用抽象。
- `dingtalk` 同时混合 SDK Client、旧版 API 封装、Bot、OAuth、Workflow、RabbitMQ；应按 `integrations/dingtalk/{client,oauth,workflow,bot,messaging}.py` 拆分。
- `sms/aliyun_sms.py`、`map/mapqq.py`、`map/mapbd.py` 都属于外部供应商适配器，应统一放到 `integrations/`，供应商差异隔离在 adapter 内。
- `utils/` 内容跨度过大；日期、密码、文件上传、Excel、Docx 应拆成 `utils/datetime.py`、`utils/security.py`、`storage/`、`documents/`、`spreadsheet/`。
- `error` 建议改为语义更清晰的 `errors/`，并区分异常定义、DRF handler 和 HTTP 响应。
- 删除 `.DS_Store` 等非源码文件，不把临时文件、供应商 SDK 细节和业务代码混入基础包。

推荐的优化后结构：

```text
stdkit/
├── __init__.py
├── config/                 # stdkit 配置读取、默认值、校验
├── db/
│   ├── __init__.py
│   ├── base.py             # 非 Django Model 的基础协议（如有）
│   └── models/
│       ├── __init__.py
│       ├── base.py         # BaseModel
│       ├── fields.py       # 自定义字段
│       ├── managers.py     # QuerySet/Manager
│       └── mixins.py       # 可组合能力：软删除、时间、序列化
├── rest/
│   ├── __init__.py
│   ├── responses.py
│   ├── exceptions.py
│   ├── handlers.py
│   ├── pagination.py
│   ├── permissions.py
│   ├── decorators.py
│   ├── schemas.py
│   ├── views/
│   └── export/
├── middleware/
├── integrations/
│   ├── dingtalk/
│   ├── sms/
│   │   └── aliyun.py
│   └── maps/
│       ├── baidu.py
│       └── qq.py
├── storage/
│   └── upload.py
├── documents/
│   └── docx.py
├── spreadsheet/
│   └── excel.py
├── utils/
│   ├── datetime.py
│   ├── security.py
│   ├── text.py
│   └── typing.py
└── tests/
    ├── test_db.py
    ├── test_rest.py
    ├── test_integrations.py
    └── test_utils.py
```

拆分不是一次性重写要求。内置现有代码时，先保持导入兼容，再逐步迁移；对外保留兼容 facade，例如 `stdkit.rest.response.JsonResponse` 暂时转发到新模块。

代码逻辑边界：

```text
业务 App
  ├── View / API ───────────────→ stdkit.rest
  ├── Model ────────────────────→ stdkit.db.models
  ├── 文件/文档业务 ─────────────→ stdkit.storage / documents
  └── 外部服务调用 ──────────────→ stdkit.integrations

stdkit.integrations ────────────→ 第三方 SDK
stdkit ────────────────✕────────→ 业务 App
```

`stdkit` 中的类和函数应满足：单一职责、无业务数据库查询、无具体业务 App 导入、外部服务可替换、失败可观测、配置可注入。

### 内置原则

- `stdkit` 是项目基础设施，不是业务 App；不得放入某个业务 App 内。
- `stdkit` 只提供跨 App 的稳定能力：响应、异常、日志、分页、权限基类、数据库基础设施和通用工具。
- 业务规则、具体 User、订单、组织、租户等领域逻辑留在 `apps/`，禁止反向塞回工具包。
- `stdkit` 内部禁止依赖具体业务 App；依赖方向保持 `apps → stdkit`，不能形成 `stdkit → apps`。
- Django 初始化相关代码使用显式入口；不要在包导入时读取数据库、启动任务、注册副作用或依赖 App 尚未加载的 Model。
- `stdkit` 中的 Django App（如有 Model、Signal、Admin、Migration）必须拥有独立 `apps.py`、`migrations/` 和测试，并在 settings 的 `INSTALLED_APPS` 中显式注册。纯工具模块不要伪装成 Django App。
- `stdkit` 配置通过 `config/settings` 注入，业务代码不直接修改工具包全局变量。
- `stdkit` 对外 API 通过稳定的顶层导出或 facade 暴露；内部目录可调整，调用方不应依赖深层私有路径。
- `stdkit` 每次内置变更记录来源版本/提交、变更原因、兼容性和回滚方式；可在 `libs/stdkit/VERSION` 或包元数据中记录。
- 删除原安装依赖前，先全仓搜索旧导入、旧配置、旧初始化入口和锁文件记录；确认没有运行时、脚本、Worker、Management Command 或 CI 依赖。

### 迁移步骤

1. 盘点原包版本、源码、公开导入路径、配置项和依赖。
2. 将源码复制到项目基础包目录，先保证原导入路径可用，不同时做大规模重命名。
3. 补充包边界、`__init__.py`、测试和来源记录；拆出不应内置的业务代码。
4. 将项目业务代码逐步改为项目统一入口，避免直接依赖内部深层模块。
5. 在本地、测试、Worker、命令和部署环境执行导入、启动、Django check 和相关测试。
6. 确认包内依赖已在项目依赖文件中声明；若完全不再需要外部安装包，再删除依赖和锁文件记录。
7. 保留一个可回滚提交或迁移分支；不要在一次提交中同时内置、重构、改 API 和删除旧依赖。

### 何时不应直接内置

- 多个项目需要独立升级且有正式发布流程：继续作为独立包维护。
- 工具包有复杂独立 CI、版本兼容矩阵或外部使用者：优先保留包管理方式，项目只固定版本。
- 只是少量通用函数：提取到项目 `common/` 或 `core/`，不要复制完整工具包。
- 无法确认源码许可证、来源或维护责任：先确认授权和归属，再复制进项目。

## 权限、数据范围与副作用

认证、角色权限、对象权限、租户/组织数据范围分开判断。查询、写入、导出、Admin、Task 和 Management Command 都必须检查适用边界，不能只依赖前端隐藏按钮。

跨表写入使用项目认可的事务边界；外部消息、邮件、缓存和任务注意提交顺序，必要时使用提交后触发。日志和错误不得泄露凭据、内部堆栈或其他租户数据。

## 测试与验证

新项目默认：`uv`（若可用）、`ruff`、`pytest`、`pytest-django`、类型检查和 `pre-commit`；旧项目使用其已有工具，不强行换工具链。

新增或修复行为必须补测试，至少覆盖适用项：成功路径、非法输入、权限允许/拒绝、数据范围、资源不存在、边界值、重复请求、失败回滚和回归场景。顺序：

1. 最小相关测试。
2. `python manage.py check`（涉及 Django 结构时）。
3. `makemigrations --check --dry-run`（涉及 Model 时）。
4. 更广测试、Lint、格式化、类型检查和项目 CI 命令。
5. 检查 `git diff`、迁移和测试差异，确认无无关改动。

命令必须以项目实际配置为准；没有命令就说明未执行，禁止伪造结果。Review/审计保持只读，不运行会写入数据的命令。

## 风险门禁

- `LOW`：局部代码、文案、测试；可直接处理。
- `MEDIUM`：新 API、共享逻辑、配置或普通模型改动；完成影响分析后处理。
- `HIGH`：权限、认证、数据范围、跨 App、公共契约、大迁移；先说明方案、影响和验证，再请求确认。
- `CRITICAL`：生产数据写入、删除、不可逆迁移、凭据或安全边界变化；没有明确确认不执行。

## 交付报告

简单任务可压缩；普通及以上任务固定输出：

```text
STATUS: DONE | BLOCKED | NEED_CONFIRMATION
MODE: NEW_PROJECT | LEGACY_PROJECT | MIGRATION_PROJECT
RISK: LOW | MEDIUM | HIGH | CRITICAL
CONVENTION_GAP: NONE | LOW | HIGH
MIGRATION: NONE | SCHEMA | DATA | SCHEMA_AND_DATA

## 变更范围
## 影响链
## 规范匹配
## 修改文件
## 测试与验证
## 风险
## 未解决问题
## 下一步
```

## 规范进化

新确认的个人习惯先记录为候选规则，不自动改写本技能。定期人工确认后再更新 `django-personal-development/SKILL.md`，并同步 `skills.json`、`README.md`（若公开描述变化）和验证结果。
