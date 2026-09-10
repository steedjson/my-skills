# YApi 核心 REST API 路由速查

YApi 提供了一组内置的 Web 控制台接口（`/api/...`），本 Skill 优先使用这些接口完成自动化文档维护。

## 1. 认证与会话

- 请求头：`Cookie: _yapi_token=<JWT_TOKEN>; _yapi_uid=<UID>`
- 凭证获取：
  - 自动解密：`scripts/yapi_client.py` 会自动扫描并解密 macOS Chrome 的 SQLite Cookie（`Profile */Cookies`）。
  - 手动传入：通过环境变量 `YAPI_COOKIE` 或 CLI 参数 `--cookie` 显式指定。

## 2. 核心读接口

| 动作 | 方法 | 路径 | 关键入参 | 说明 |
| :--- | :--- | :--- | :--- | :--- |
| 获取项目详情 | `GET` | `/api/project/get` | `id=<project_id>` | 返回项目基本信息及配置 |
| 获取分类及接口菜单 | `GET` | `/api/interface/list_menu` | `project_id=<project_id>` | 返回完整分类树及各分类下的接口简要列表 |
| 获取单个接口详情 | `GET` | `/api/interface/get` | `id=<interface_id>` | 返回接口完整定义（包括 Query/Body/Headers/JSON-Schema） |
| 获取分类下接口列表 | `GET` | `/api/interface/list_cat` | `catid=<cat_id>&page=1&limit=20` | 分页拉取分类下的接口 |

## 3. 核心写接口

| 动作 | 方法 | 路径 | 请求体格式 | 说明 |
| :--- | :--- | :--- | :--- | :--- |
| 创建分类 | `POST` | `/api/interface/add_cat` | JSON: `{project_id, name, desc}` | 在指定项目中新建左侧菜单分类 |
| 创建接口 | `POST` | `/api/interface/add` | JSON: `{project_id, catid, title, path, method}` | 新建接口基本骨架（创建成功后返回 `_id`） |
| 更新接口定义 | `POST` | `/api/interface/up` | JSON: 接口完整对象 (含 `id`) | 保存请求参数、返回 JSON-Schema、状态及备注 |

## 4. JSON-Schema 最佳实践

在 YApi 中配置返回体或请求体为 JSON-Schema 时：
1. `res_body_type` 设为 `"json"`；
2. `res_body_is_json_schema` 设为 `true`；
3. `res_body` 必须为合法的 JSON-Schema 字符串，根对象遵循 draft-04 规范：
   ```json
   {
     "$schema": "http://json-schema.org/draft-04/schema#",
     "type": "object",
     "properties": {
       "code": {"type": "integer", "description": "状态码"},
       "msg": {"type": "string", "description": "消息"},
       "data": {"type": "object", "properties": {...}}
     },
     "required": ["code", "msg", "data"]
   }
   ```
