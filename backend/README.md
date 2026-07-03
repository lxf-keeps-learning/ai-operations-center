# AIOperationsCenter Backend

智能运营中心 AI Agent 后端工程，使用 Python + FastAPI 初始化，当前 Sprint0 数据库方案使用 MySQL + SQLAlchemy + pymysql。本地开发不依赖 Docker，Docker Compose 仅保留为后续标准部署方式。

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

## 目录结构

```text
backend/
├── app/
│   ├── api/                # API 路由层，只接收参数和返回 DTO
│   ├── application/        # 应用编排层，后续接入 LangGraph
│   ├── config/             # 配置管理
│   ├── core/               # Sprint1 基础设施：响应、异常、Trace、Context、配置、日志
│   ├── db/                 # 数据库连接和 Session 依赖
│   ├── models/             # SQLAlchemy 模型
│   ├── runtime/            # 运行态数据，当前为内存实现
│   ├── schemas/            # Pydantic DTO
│   ├── utils/              # 通用工具
│   └── main.py             # FastAPI 应用入口
├── alembic/                # Alembic 数据库迁移脚本
├── tests/                  # 接口测试
├── .env.example            # 环境变量样例
├── alembic.ini             # Alembic 配置
├── pyproject.toml          # 项目依赖与工具配置
└── README.md
```

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

当前 Sprint0 Demo 表为 `system_items`，迁移脚本在：

```text
backend/alembic/versions/20260702_0001_create_system_items.py
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

| 方法 | 路径 | 用途 |
|------|------|------|
| GET | `/api/v1/health` | 服务健康检查 |
| GET | `/api/v1/config/runtime` | 当前运行环境与默认模型 |
| GET | `/api/v1/config/models` | 模型配置列表，隐藏 API Key |
| GET | `/api/v1/errors/codes` | 业务错误码列表 |
| GET | `/api/v1/logs/recent` | 最近日志 |
| GET | `/api/v1/logs/llm-usage` | LLM 使用日志 |
| GET | `/api/v1/traces/{trace_id}` | Trace 示例链路 |
| GET | `/api/v1/context/current` | 当前请求上下文 |
| POST | `/api/v1/agent/chat` | 发起 AI 对话任务 |
| POST | `/api/v1/agent/analyze` | 发起 AI 分析任务 |
| GET | `/api/v1/agent/stream` | SSE 流式输出 |
| GET | `/api/v1/conversations` | 查询会话列表 |
| GET | `/api/v1/conversations/{conversation_id}` | 查询会话详情 |
| DELETE | `/api/v1/conversations/{conversation_id}` | 删除会话 |
| GET | `/api/v1/prompts/{prompt_code}` | 查询 Prompt |
| POST | `/api/v1/feedback` | 提交用户反馈 |
| GET | `/api/cache/ping` | Redis 可选健康检查 |
| GET | `/api/v1/items` | 查询 Demo Item 列表 |
| POST | `/api/v1/items` | 创建 Demo Item |
| GET | `/api/v1/items/{id}` | 查询 Demo Item 详情 |
| PUT | `/api/v1/items/{id}` | 更新 Demo Item |
| DELETE | `/api/v1/items/{id}` | 删除 Demo Item |

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

- 将 AI Runtime 的会话、Trace、Prompt 和 Feedback 逐步迁移到 MySQL 表。
- 在 `application/agent_service.py` 接入 LangGraph。
- 将内置 Prompt 迁移到 `prompt` 模块和数据库版本管理。
- 增加统一鉴权、租户上下文、Trace 入库和结构化日志。
