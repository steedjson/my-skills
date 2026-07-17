---
name: django-api-change
description: 在本仓库中实现、调试或审查 Django API 与 Service 变更。涉及 apps 和 common 下的路由、视图、参数 Schema、Service、模型、迁移、权限、租户隔离、事务、软删除、导出或 API 测试时使用。
---

# Django API 变更

遵循项目的 View → Form/Schema → Service → Model 分层，保持传输层逻辑精简。

## 编辑前分析

1. 读取 `.wolf/OPENWOLF.md`，并在 OpenWolf 记忆中搜索相关业务域和已知故障；禁止整文件读取大型记忆文件。
2. 定位路由、View、Schema、Service、模型、直接调用方、下游消费者和相关测试。存在索引时优先使用 CodeGraph 导航代码，使用 `rg` 查询字符串和配置。
3. 明确请求结构、响应结构、权限、租户范围、异常行为、事务边界和验收标准。

## 遵循项目约定

- View 继承 `common.views.View`，使用 `define_params`，并返回 `JsonResponse`。
- 业务逻辑放入继承 `BaseService` 的 Service，复杂逻辑添加类型注解。
- 模型主键使用 `uuid`，不得使用 `id`。
- 遵循 `deleted_at=0` 软删除规则，并确认模型是直接拥有 `tenant_id`，还是通过关联对象访问租户。
- 多表写操作使用 `transaction.atomic`。
- 使用合适的 `stdkit.error.exceptions` 异常，不泄露内部实现细节。
- 新增管理后台模块时沿用现有 URL 结构，不创建并行路由体系。
- 保持认证中间件和异步导出约定。

## 独立验证

1. 增加目标 API/Service 回归测试，覆盖非法输入、权限或租户边界、资源不存在，以及相关写入回滚。
2. 运行 `make verify TEST=<focused target>`，统一完成变更文件的 isort、Black、错误级 Pylint、目标 pytest 和 Git diff 检查。
3. 修改模型、路由、中间件、Django 设置或 App 配置时额外运行 Django check；修改模型时再运行迁移漂移检查。
4. 修改高影响或共享逻辑时运行 `make verify-full`。
5. 从调用方和下游消费者角度审查差异；中高风险变更使用 CRG 做影响审查。
5. 报告变更文件、行为变化、实际命令及结果、跳过项、阻塞原因、剩余风险和回滚注意事项。
