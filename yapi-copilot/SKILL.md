---
name: yapi-copilot
description: Manage and sync YApi interface documents (categories, APIs, JSON-Schema request/response contracts) directly via YApi REST APIs with zero UI clicking and automated local Chrome cookie or token authentication. Use when the user asks to create, update, query, diff, or document API interfaces on YApi, sync backend code (Django, FastAPI, Spring, etc.) to YApi, or manage YApi projects and categories.
---

# YApi Copilot

通过 YApi 后台原生 REST API 自动化维护接口文档，替代脆弱易错的浏览器网页点选。支持自动解密本地 Chrome 已登录凭证，实现零配置免手动抓包鉴权。

## 核心工作流

### 1. 鉴权与连通性验证

优先使用本地 Chrome 解密凭证，亦支持环境变量 `YAPI_COOKIE`：

```bash
python3 scripts/yapi_client.py auth-check [--url <YAPI_BASE_URL>]
```

如未提供 `--url`，默认使用当前企业 YApi 域名。

### 2. 检索现有项目与分类

在创建或修改前，先拉取项目树避免重复建类或接口冲突：

```bash
# 查询项目分类及接口列表
python3 scripts/yapi_client.py list-menu --project-id <PROJECT_ID>
```

### 3. 创建分类与接口

当目标分类不存在时先建分类，再创建接口骨架：

```bash
# 1. 创建分类（如分类不存在）
python3 scripts/yapi_client.py add-cat --project-id <PROJECT_ID> --name "分类名称" --desc "分类描述"

# 2. 调用 Python 客户端进行增量更新或新增接口
```

### 4. 增量更新原则（严禁覆盖破坏历史契约）

在调用 `POST /api/interface/up` 更新接口时，必须遵循以下契约保护规则：
1. **先读后改**：通过 `GET /api/interface/get?id=<ID>` 获取线上现有完整数据对象；
2. **只增不删**：保留线上已有字段与备注，仅在 `properties`、`req_query` 或 `req_body_other` 中增量合入新字段；
3. **Draft-04 规范**：返回 JSON 体必须设为 `res_body_type="json"`、`res_body_is_json_schema=true`，根节点使用 `$schema: "http://json-schema.org/draft-04/schema#"`；
4. **准确标注**：明确标注字段类型（`string`, `integer`, `array`, `object`）、格式（如 `date`）、是否必填（`required` 数组）以及中文 `description`。

### 5. 校验与验证

更新完成后，必须再次请求 `GET /api/interface/get?id=<ID>` 回查确认 `errcode == 0` 且字段已成功生效。

## 资源索引

- `scripts/yapi_client.py`: 核心客户端 CLI 与 Python 类库。
- `references/yapi-api-routes.md`: YApi 官方原生 REST API 路由速查字典。
