# AIOperationsCenter

面向智能运营中心（IOC）的企业级 AI Agent 示例项目。系统以运营分析报告为主流程：从页面上下文出发，经 Tool Center 获取 KPI、告警、隐患和工单数据，由 LangGraph 完成异常识别、原因分析、建议生成和报告汇总；报告生成后可继续进行绑定 `report_id` 的追问，并在需要制度、标准或案例依据时调用 RAG。

## 当前能力

- FastAPI 统一响应、错误码、Trace/Context、日志和环境配置。
- AI Runtime 会话、Prompt、LLM 调用与 Trace 持久化。
- Tool Center 统一工具注册、调用、错误和 evidence 契约。
- Operation Agent 六节点分析闭环与 30 分钟报告复用。
- Report Chat Graph：报告内追问、范围判断、证据检索和消息持久化。
- RAG Decision、Query Rewrite、外部 RAG 调用与真实依据展示。
- Graph 节点级 SSE Streaming、失败状态展示和事件审计。

```text
Vue 3 工作台
  -> FastAPI / Trace Context
  -> Operation Graph
  -> Tool Center -> IOC Mock / IOC API
  -> 规则识别 + LLM 分析与降级
  -> operation_analysis_record + analysis_events
  -> Report Chat Graph -> Report Evidence / RAG
```

## 技术栈

- 前端：Vue 3、TypeScript、Vite、Pinia、Vue Router
- 后端：Python 3.11+、FastAPI、LangGraph、SQLAlchemy、Alembic
- 数据库：MySQL；Redis 为可选预留能力
- 模型：OpenAI-compatible LLM 接口，当前配置以 DeepSeek 为主
- 通信：REST + SSE

## 目录

```text
AIOperationsCenter/
├── backend/               # FastAPI、Runtime、Tool Center、Operation/Report Chat Graph
├── frontend/              # Vue 运营分析、报告记录、报告追问和基础设施控制台
├── docs/sprints/          # Sprint0-Sprint10 方案、Review、复盘和面试材料
├── docker-compose.yml     # 本地 MySQL
└── .env.example           # Compose/MySQL 示例配置
```

## 本地启动

### 1. 启动 MySQL

```bash
cp .env.example .env
docker compose up -d mysql
```

也可以复用本机 MySQL，数据库初始化细节见 [数据库初始化说明](docs/数据库初始化说明.md)。

### 2. 启动后端

```bash
cd backend
cp .env.example .env
python3 -m venv .venv
source .venv/bin/activate
pip install -e '.[dev]'
alembic upgrade head
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

后端接口文档：`http://127.0.0.1:8000/docs`

### 3. 启动前端

```bash
cd frontend
cp .env.example .env.local
npm install
npm run dev
```

前端地址：`http://127.0.0.1:5173`

## 验证

```bash
cd backend
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python scripts/debug_operation_agent.py

cd ../frontend
npm run type-check
npm run build
```

## 关键入口

| 目标 | 文件 |
|---|---|
| FastAPI 应用与路由注册 | `backend/app/main.py` |
| Operation Graph 节点注册 | `backend/app/operation_agent/graph.py` |
| 同步分析与缓存/持久化 | `backend/app/operation_agent/service.py` |
| SSE 节点事件流 | `backend/app/operation_agent/stream_service.py` |
| Tool Center | `backend/app/tool_center/`、`backend/app/tools/` |
| Report Chat Graph | `backend/app/report_chat_agent/graph.py` |
| RAG 调用 | `backend/app/rag/` |
| 运营分析工作台 | `frontend/src/pages/operation/IndexPage.vue` |
| 报告追问面板 | `frontend/src/components/ReportChatPanel.vue` |
| Sprint 方案与复盘 | `docs/sprints/` |

## 当前边界

- IOC 业务数据默认使用脱敏 Mock，真实 IOC 接口通过 Client 适配层接入。
- RAG 服务可使用 Mock 或外部检索服务；真实知识库召回质量仍需独立评估。
- Redis 默认关闭，不影响本地核心链路。
- SSE 当前是 Graph 节点级进度，不是 LLM token 级输出。
- 当前身份上下文用于 Trace、数据过滤和审计基础，生产级认证授权仍应由网关和权限系统补齐。

更详细的后端、前端说明分别见 [backend/README.md](backend/README.md) 和 [frontend/README.md](frontend/README.md)。
