# AIOperationsCenter Backend

智能运营中心 AI Agent 后端工程，使用 Python + FastAPI 构建。当前后端已包含基础 API、AI Runtime、Tool Center、IOC Mock 适配层、MySQL 持久化、Trace/Context/异常处理等基础设施。本地开发不依赖 Docker，Docker Compose 仅保留为后续标准部署方式。

## 技术栈

- Python 3.11+
- FastAPI
- Pydantic v2
- Uvicorn
- MySQL
- SQLAlchemy 2
- pymysql
- Alembic
- Redis（当前本地开发默认不启用，后续部署预留）
- REST + SSE

## 基础设施快速索引

项目规模变大后，先按下面这张表找基础设施入口：

| 想找什么                               | 优先看哪里                                                                        | 说明                                                                                        |
| -------------------------------------- | --------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------- |
| FastAPI 应用创建、路由挂载、中间件注册 | `app/main.py`                                                                     | 后端总入口，集中注册 CORS、Trace Middleware、异常处理器、业务路由、Runtime 路由、Cache 路由 |
| 普通业务 API 路由聚合                  | `app/api/router.py`                                                               | 挂载健康检查、Agent、会话、Prompt、Feedback 等早期 `/api/v1` 路由                           |
| 基础设施 API 路由聚合                  | `app/api/v1/router.py`                                                            | 挂载配置、错误码、日志、Trace、Context 等基础设施接口                                       |
| Runtime API 路由聚合                   | `app/runtime/api/router.py`                                                       | 挂载 Runtime 会话、Prompt、Trace、Feedback、Chat 等持久化运行态接口                         |
| 环境变量与应用配置                     | `app/config/settings.py`                                                          | 应用名、端口前缀、数据库、Redis、CORS、日志级别等配置                                       |
| LLM Provider 配置                      | `app/core/config/llm_settings.py`                                                 | DeepSeek / OpenAI 类模型配置读取和默认模型管理                                              |
| 统一响应结构                           | `app/schemas/common.py`、`app/core/schema/response_schema.py`                     | `ApiResponse`、业务响应包装、基础响应契约                                                   |
| 统一异常与业务错误码                   | `app/core/exception/`                                                             | `AppException`、错误码定义、FastAPI 异常处理器                                              |
| Trace / Request Context                | `app/core/middleware/trace_middleware.py`、`app/core/context/`、`app/core/trace/` | 请求链路 ID、上下文持有、Trace 透传                                                         |
| 日志初始化                             | `app/core/logging/logger.py`                                                      | 后端日志格式和日志级别初始化                                                                |
| MySQL 连接和 Session 依赖              | `app/db/session.py`、`app/db/base.py`                                             | SQLAlchemy Engine、SessionLocal、FastAPI `get_db` 依赖                                      |
| Redis 可选健康检查                     | `app/db/redis.py`、`app/api/routes/cache.py`                                      | Redis 本地默认非强依赖，仅用于 ping/预留缓存能力                                            |
| Alembic 迁移                           | `alembic/`、`alembic.ini`                                                         | 数据库版本迁移入口和迁移脚本                                                                |
| AI Runtime 主流程                      | `app/runtime/runtime_service.py`                                                  | Runtime Chat 的会话、Prompt、LLM 调用、Trace 记录编排                                       |
| LLM 调用适配                           | `app/runtime/llm/client.py`                                                       | Provider 选择、消息组装、模型调用、token/错误信息封装                                       |
| Runtime 数据访问                       | `app/runtime/models/`、`app/runtime/repositories/`、`app/runtime/services/`       | 会话、Prompt、Trace、Feedback 等运行态数据的模型、仓储、服务                                |
| Tool Center 基础设施                   | `app/tool_center/core/`                                                           | BaseTool、ToolResult、Evidence、ToolError、Trace、Registry                                  |
| IOC Mock/Client 适配                   | `app/integrations/ioc/`                                                           | IOC Client 抽象、Mock Client、Mock 数据和业务数据 DTO                                       |
| 业务 Query Tool                        | `app/tools/query/`                                                                | KPI、Alarm、Risk、WorkOrder 查询 Tool                                                       |
| Tool 注册入口                          | `app/tools/register.py`、`app/tool_center/registry.py`                            | 全局 Tool Registry 和批量注册函数                                                           |
| 测试入口                               | `tests/`                                                                          | API、Runtime、Tool Center、Mock IOC Client、Query Tool 测试                                 |

## 目录结构

```text
backend/
├── app/
│   ├── api/
│   │   ├── routes/             # 早期业务 API：health、agent、conversation、prompt、feedback、cache、items
│   │   ├── v1/                 # 基础设施 API：config、context、error_code、log、trace
│   │   └── router.py           # 普通业务 API 聚合路由
│   ├── application/
│   │   └── agent_service.py    # 早期 Agent/SSE 编排服务，保留给前端联调和 Sprint1 流程
│   ├── config/
│   │   └── settings.py         # 应用级配置：DATABASE_URL、Redis、CORS、日志、API 前缀
│   ├── core/
│   │   ├── config/             # 核心配置，包含 LLM Provider 配置
│   │   ├── context/            # Request/User/Page Context，上下文隔离与透传
│   │   ├── exception/          # 统一异常、业务错误码、异常处理器
│   │   ├── logging/            # 日志初始化
│   │   ├── middleware/         # Trace Middleware 等 FastAPI 中间件
│   │   ├── schema/             # 核心响应 Schema
│   │   └── trace/              # Trace Context 工具
│   ├── db/
│   │   ├── base.py             # SQLAlchemy Declarative Base
│   │   ├── redis.py            # Redis ping 工具，当前本地开发默认可关闭
│   │   └── session.py          # SQLAlchemy Engine / SessionLocal / get_db
│   ├── integrations/
│   │   └── ioc/                # IOC 外部系统适配层：Client 抽象、Mock Client、Mock 数据
│   ├── models/
│   │   └── item.py             # Sprint0 Demo Item 模型
│   ├── runtime/
│   │   ├── api/                # Runtime REST API：sessions、prompts、traces、feedback、chat
│   │   ├── llm/                # LLM Client 适配
│   │   ├── models/             # Runtime SQLAlchemy 模型
│   │   ├── repositories/       # Runtime 数据访问层
│   │   ├── schemas/            # Runtime Pydantic DTO
│   │   ├── services/           # Runtime 业务服务
│   │   ├── in_memory_store.py  # 早期内存 Store，兼容旧接口
│   │   └── runtime_service.py  # Runtime Chat 主编排服务
│   ├── schemas/                # 早期业务 API DTO：agent、cache、conversation、feedback、health、item、prompt
│   ├── tool_center/
│   │   ├── core/               # Tool SDK：BaseTool、DTO、异常、Trace、Registry
│   │   └── registry.py         # 全局 Tool Registry 包装
│   ├── tools/
│   │   ├── query/              # KPI / Alarm / Risk / WorkOrder 查询 Tool
│   │   └── register.py         # Query Tool 批量注册入口
│   ├── utils/                  # ID、SSE、时区等通用工具
│   └── main.py                 # FastAPI 应用入口
├── alembic/
│   ├── versions/               # 数据库迁移脚本
│   ├── env.py                  # Alembic 运行环境
│   └── script.py.mako          # Alembic 迁移模板
├── tests/
│   ├── integrations/           # Mock IOC Client 等外部适配层测试
│   ├── tool_center/            # Tool SDK 基础设施测试
│   ├── tools/                  # Query Tool 注册和执行测试
│   └── test_api.py             # FastAPI 基础接口测试
├── .env.example                # 本地环境变量样例
├── .env.dev / .env.test / .env.prod
├── alembic.ini                 # Alembic 配置
├── pyproject.toml              # 项目依赖、pytest、ruff、打包配置
├── verify_sprint1.py           # Sprint1 接口契约验证脚本
└── README.md
```

## 关键文件说明

### 应用入口与路由

| 文件                        | 作用                                                                                                                             |
| --------------------------- | -------------------------------------------------------------------------------------------------------------------------------- |
| `app/main.py`               | 创建 FastAPI App，注册 CORS、Trace Middleware、异常处理器，并挂载 `api_router`、`v1_router`、`runtime_router`、cache、items 路由 |
| `app/api/router.py`         | 早期业务接口聚合，统一挂到 `/api/v1` 下                                                                                          |
| `app/api/v1/router.py`      | 基础设施接口聚合，主要服务前端调试页、错误码页、日志页、上下文页                                                                 |
| `app/runtime/api/router.py` | Runtime 模块接口聚合，主要用于会话、Prompt、Trace、Feedback 和 Chat 的持久化运行态接口                                           |

### 配置、上下文、异常、响应

| 文件/目录                                 | 作用                                                                       |
| ----------------------------------------- | -------------------------------------------------------------------------- |
| `app/config/settings.py`                  | 应用级 settings，读取 `.env` 中的数据库、Redis、CORS、日志、API 前缀等配置 |
| `app/core/config/llm_settings.py`         | LLM Provider 配置读取，管理默认 Provider、模型名、Base URL、API Key        |
| `app/core/middleware/trace_middleware.py` | 每个请求生成/透传 Trace ID，初始化请求上下文，响应时写回 Trace Header      |
| `app/core/context/`                       | 保存请求、用户、页面上下文，避免跨请求污染                                 |
| `app/core/exception/error_code.py`        | 统一业务错误码定义                                                         |
| `app/core/exception/exception_handler.py` | FastAPI 异常处理器，把异常统一包装成业务响应                               |
| `app/schemas/common.py`                   | 早期 API 的通用 `ApiResponse` 结构                                         |
| `app/core/schema/response_schema.py`      | 核心层响应 Schema，后续基础设施响应可优先往这里收敛                        |

### 数据库与迁移

| 文件/目录                                                           | 作用                                                        |
| ------------------------------------------------------------------- | ----------------------------------------------------------- |
| `app/db/base.py`                                                    | SQLAlchemy 模型基类                                         |
| `app/db/session.py`                                                 | 数据库 Engine、SessionLocal、`get_db` 依赖                  |
| `app/db/redis.py`                                                   | Redis ping 能力，当前用于可选健康检查，不作为本地启动强依赖 |
| `alembic/versions/20260702_0001_create_system_items.py`             | Sprint0 Demo `system_items` 表迁移                          |
| `alembic/versions/907e5e77381a_create_runtime_tables.py`            | Runtime 会话、Prompt、Trace、Feedback 等核心表迁移          |
| `alembic/versions/20260703_0002_add_prompt_snapshot_to_ai_trace.py` | Trace 表增加 Prompt 快照字段                                |

### AI Runtime

| 文件/目录                        | 作用                                                                                     |
| -------------------------------- | ---------------------------------------------------------------------------------------- |
| `app/runtime/runtime_service.py` | Runtime Chat 主流程：创建 Session、加载 Prompt、组装历史、调用 LLM、记录 Trace、更新状态 |
| `app/runtime/llm/client.py`      | LLM 调用适配层，封装 Provider 配置、请求消息、响应文本、token 使用和错误信息             |
| `app/runtime/models/`            | Runtime SQLAlchemy 模型：conversation、session、prompt、trace、feedback                  |
| `app/runtime/repositories/`      | Runtime 数据访问层，只处理数据库读写                                                     |
| `app/runtime/services/`          | Runtime 业务服务层，封装仓储调用和领域状态更新                                           |
| `app/runtime/schemas/`           | Runtime API 输入输出 DTO                                                                 |
| `app/runtime/in_memory_store.py` | 早期内存态数据源，保留给旧 Agent 接口兼容和轻量演示                                      |

### Tool Center 与 IOC 适配

| 文件/目录                             | 作用                                                                               |
| ------------------------------------- | ---------------------------------------------------------------------------------- |
| `app/tool_center/core/base_tool.py`   | Tool 统一执行入口，负责 trace_id、异常捕获、ToolResult 包装                        |
| `app/tool_center/core/schemas.py`     | Tool 输入输出 DTO：ToolContext、BaseToolInput、Evidence、ToolError、ToolResult     |
| `app/tool_center/core/exceptions.py`  | Tool 层异常类型和错误码                                                            |
| `app/tool_center/core/trace.py`       | Tool 调用日志记录，记录耗时、状态、错误、证据数量                                  |
| `app/tool_center/core/registry.py`    | Tool 注册中心，支持注册、获取、列出 Tool                                           |
| `app/tool_center/registry.py`         | 全局 registry 实例，供 Graph/Node/API 统一获取 Tool                                |
| `app/integrations/ioc/client.py`      | IOC API Client 抽象接口，后续真实 IOC Client 应按这里的签名实现                    |
| `app/integrations/ioc/mock_client.py` | Mock IOC Client，支持 KPI、告警、隐患、工单查询和过滤                              |
| `app/integrations/ioc/mock_data.py`   | 脱敏 Mock 业务数据                                                                 |
| `app/integrations/ioc/schema.py`      | IOC Mock/API 返回 DTO 和业务记录 DTO                                               |
| `app/tools/query/`                    | 查询类 Tool，当前包含 `kpi_query`、`alarm_query`、`risk_query`、`work_order_query` |
| `app/tools/register.py`               | 批量注册当前查询类 Tool                                                            |

### 测试目录

| 目录/文件                                       | 作用                                              |
| ----------------------------------------------- | ------------------------------------------------- |
| `tests/test_api.py`                             | 基础 API 和统一响应契约测试                       |
| `tests/integrations/test_mock_ioc_client.py`    | Mock IOC Client 数据与过滤测试                    |
| `tests/tool_center/`                            | BaseTool、Tool Schema、Tool Registry 基础设施测试 |
| `tests/tools/query/`                            | KPI、Alarm、Risk、WorkOrder Query Tool 单元测试   |
| `tests/tools/test_tool_registry_integration.py` | Tool Registry 集成注册测试                        |

## Navicat 创建数据库

1. 打开 Navicat，连接本机 MySQL。
2. 新建数据库，数据库名填写 `ioc_ai`。
3. 字符集选择 `utf8mb4`。
4. 排序规则选择 `utf8mb4_unicode_ci`。
5. 创建本地用户 `ioc_user`，密码 `ioc_password`。
6. 给 `ioc_user` 授权 `ioc_ai` 数据库的常用读写和 DDL 权限。

也可以在 Navicat 查询窗口执行：

```sql
CREATE DATABASE IF NOT EXISTS ioc_ai
  DEFAULT CHARACTER SET utf8mb4
  DEFAULT COLLATE utf8mb4_unicode_ci;

CREATE USER IF NOT EXISTS 'ioc_user'@'localhost' IDENTIFIED BY 'ioc_password';
GRANT SELECT, INSERT, UPDATE, DELETE, CREATE, ALTER, DROP, INDEX
  ON ioc_ai.* TO 'ioc_user'@'localhost';
FLUSH PRIVILEGES;
```

## 配置 DATABASE_URL

复制环境变量文件：

```bash
cp .env.example .env
```

确认 `backend/.env` 中包含：

```text
DATABASE_URL=mysql+pymysql://ioc_user:ioc_password@localhost:3306/ioc_ai
```

后端只从 `DATABASE_URL` 读取数据库连接。若你的 MySQL 用户、密码、端口不同，只需要改这一项。

MySQL 是当前 Sprint0 必须跑通的主数据库，Demo CRUD 会直接读写 `system_items` 表。

## 配置 Redis 预留项

当前本地开发模式 Redis 可不启用，`backend/.env` 保持默认配置即可：

```text
REDIS_ENABLED=false
REDIS_URL=redis://localhost:6379/0
```

当 `REDIS_ENABLED=false` 时，后端启动不会连接 Redis，Redis 未启动也不会影响其他接口。后续标准部署模式需要启用 Redis 时，将 `REDIS_ENABLED` 改为 `true`，并按部署环境调整 `REDIS_URL`。

Redis 是后续缓存、会话、任务状态、限流能力的预留组件，Sprint0 不引入复杂缓存业务，只提供健康检查接口。

## 安装依赖

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

## 初始化表

当前迁移脚本包括 Demo 表和 Runtime 核心表：

```text
backend/alembic/versions/20260702_0001_create_system_items.py
backend/alembic/versions/907e5e77381a_create_runtime_tables.py
backend/alembic/versions/20260703_0002_add_prompt_snapshot_to_ai_trace.py
```

执行迁移：

```bash
alembic upgrade head
```

## 启动后端

默认按 `8000` 端口启动：

```bash
fastapi dev app/main.py --host 127.0.0.1 --port 8000
```

也可以使用 uvicorn：

```bash
uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

如果本机 `8000` 已被其他服务占用，可以临时改用 `8001`：

```bash
uvicorn app.main:app --host 127.0.0.1 --port 8001 --reload
```

## 接口文档

启动后访问：

```text
http://localhost:8000/docs
http://localhost:8000/redoc
http://localhost:8000/api/v1/openapi.json
```

如果使用 `8001`，将地址中的端口替换为 `8001`。

## 已实现接口

| 方法   | 路径                                      | 用途                       |
| ------ | ----------------------------------------- | -------------------------- |
| GET    | `/api/v1/health`                          | 服务健康检查               |
| GET    | `/api/v1/config/runtime`                  | 当前运行环境与默认模型     |
| GET    | `/api/v1/config/models`                   | 模型配置列表，隐藏 API Key |
| GET    | `/api/v1/errors/codes`                    | 业务错误码列表             |
| GET    | `/api/v1/logs/recent`                     | 最近日志                   |
| GET    | `/api/v1/logs/llm-usage`                  | LLM 使用日志               |
| GET    | `/api/v1/traces/{trace_id}`               | Trace 示例链路             |
| GET    | `/api/v1/context/current`                 | 当前请求上下文             |
| POST   | `/api/v1/agent/chat`                      | 发起 AI 对话任务           |
| POST   | `/api/v1/agent/analyze`                   | 发起 AI 分析任务           |
| GET    | `/api/v1/agent/stream`                    | SSE 流式输出               |
| GET    | `/api/v1/conversations`                   | 查询会话列表               |
| GET    | `/api/v1/conversations/{conversation_id}` | 查询会话详情               |
| DELETE | `/api/v1/conversations/{conversation_id}` | 删除会话                   |
| GET    | `/api/v1/prompts/{prompt_code}`           | 查询 Prompt                |
| POST   | `/api/v1/feedback`                        | 提交用户反馈               |
| GET    | `/api/cache/ping`                         | Redis 可选健康检查         |
| GET    | `/api/v1/items`                           | 查询 Demo Item 列表        |
| POST   | `/api/v1/items`                           | 创建 Demo Item             |
| GET    | `/api/v1/items/{id}`                      | 查询 Demo Item 详情        |
| PUT    | `/api/v1/items/{id}`                      | 更新 Demo Item             |
| DELETE | `/api/v1/items/{id}`                      | 删除 Demo Item             |

Runtime 持久化接口：

| 方法  | 路径                                                     | 用途                                         |
| ----- | -------------------------------------------------------- | -------------------------------------------- |
| POST  | `/api/v1/ai/chat`                                        | Runtime AI Chat 入口                         |
| POST  | `/api/v1/runtime/chat`                                   | Runtime Chat 入口，创建 Session 并记录 Trace |
| POST  | `/api/v1/runtime/conversations`                          | 创建 Runtime Conversation                    |
| GET   | `/api/v1/runtime/conversations/{conversation_id}`        | 查询 Runtime Conversation                    |
| PATCH | `/api/v1/runtime/conversations/{conversation_id}/status` | 更新 Conversation 状态                       |
| POST  | `/api/v1/runtime/sessions`                               | 创建 Runtime Session                         |
| GET   | `/api/v1/runtime/sessions/{session_id}`                  | 查询 Runtime Session                         |
| PATCH | `/api/v1/runtime/sessions/{session_id}/status`           | 更新 Session 状态                            |
| PATCH | `/api/v1/runtime/sessions/{session_id}/output`           | 更新 Session 输出                            |
| POST  | `/api/v1/runtime/prompts`                                | 创建 Prompt 版本                             |
| GET   | `/api/v1/runtime/prompts/{code}/active`                  | 查询启用中的 Prompt                          |
| GET   | `/api/v1/runtime/prompts/{code}/versions`                | 查询 Prompt 版本列表                         |
| PATCH | `/api/v1/runtime/prompts/{prompt_id}/status`             | 更新 Prompt 状态                             |
| POST  | `/api/v1/runtime/traces`                                 | 创建 Runtime Trace                           |
| GET   | `/api/v1/runtime/traces/{trace_id}`                      | 按 trace_id 查询 Runtime Trace               |
| GET   | `/api/v1/runtime/sessions/{session_id}/traces`           | 按 session_id 查询 Runtime Trace             |
| POST  | `/api/v1/runtime/feedback`                               | 提交 Runtime Feedback                        |
| GET   | `/api/v1/runtime/sessions/{session_id}/feedback`         | 查询 Session Feedback                        |

## Demo CRUD 测试

```bash
curl -X POST http://localhost:8000/api/v1/items \
  -H "Content-Type: application/json" \
  -d '{"name":"Sprint0 Demo","description":"MySQL CRUD demo","is_active":true}'

curl http://localhost:8000/api/v1/items
```

## Redis 健康检查

默认本地开发不启用 Redis：

```bash
curl http://localhost:8000/api/cache/ping
```

返回 `Redis disabled` 表示当前配置符合 Sprint0 本地开发模式。启用 Redis 后，该接口会尝试连接 `REDIS_URL` 并返回 `pong`；如果连接失败，会返回清晰错误信息，但不会影响 MySQL 和其他业务接口。

## Docker Compose

项目根目录 `docker-compose.yml` 保留为后续标准部署方式，当前本地开发不依赖 Docker。若后续需要容器部署 MySQL，可在项目根目录执行：

```bash
docker compose up -d mysql
```

真实数据会保存在 Docker volume `mysql_data` 中，不提交到 Git。

## 验证命令

```bash
source .venv/bin/activate
pytest
curl http://localhost:8000/api/v1/health
```

SSE 联调示例：

```bash
curl -N "http://localhost:8000/api/v1/agent/stream?traceId=<trace_id>"
```

## 后续扩展建议

- 逐步收敛旧的 `application/agent_service.py` 和 `runtime/in_memory_store.py`，让新流程优先走 Runtime 持久化链路。
- 在 Graph/Node 层接入 `tool_center`，让业务数据访问统一通过 Tool Center。
- 为 Tool Center 增加 Analysis Tool、Action Draft Tool 和 Graph Node 示例。
- 增加统一鉴权、租户权限、Tool Trace 入库和更完整的结构化日志。
