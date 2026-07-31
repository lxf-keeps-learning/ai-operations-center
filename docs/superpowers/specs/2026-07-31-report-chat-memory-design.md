# Report Chat：LangGraph 官方记忆设计

## 目标

Report Chat 使用 LangGraph 官方的两层持久化能力：

- Checkpointer 保存同一 `thread_id` 的短期对话状态，恢复 `chat_history`。
- Store 保存跨会话的长期记忆，并拆分为两个命名空间：
  - 用户级：`(user_id, "user_memory")`
  - 报告级：`(user_id, "report_memory", report_id)`

现有 MySQL 继续负责报告、业务会话和消息审计；PostgreSQL 只负责 LangGraph 状态与 Store，避免把框架状态混入业务表。

## Graph 接入

报告对话图通过 `build_report_chat_graph(checkpointer=..., store=...)` 编译。生产环境由 `LANGGRAPH_POSTGRES_URL` 启用官方 `PostgresSaver` 和 `PostgresStore`；未配置时保留无持久化的本地开发模式。

每次报告追问使用报告会话 ID 作为 `configurable.thread_id`。因此，同一报告会话的下一轮调用会自动恢复上轮 Graph State；服务层不再把空的 `chat_history` 作为每轮输入覆盖已恢复状态。

流程为：

```text
load_report_context
  -> load_chat_memory  -- Checkpointer 恢复历史 + Store 检索用户/报告记忆
  -> classify_question_scope
  -> retrieve_report_evidence
  -> should_use_rag
  -> ...
  -> generate_report_answer
  -> persist_chat_message
  -> save_chat_memory  -- 更新 Checkpointer 历史 + 保存用户明确要求记住的内容
```

长期记忆只接受用户明确包含“记住”“以后都”“我的偏好是”等表达的内容；普通问答不会自动写入 Store。记忆仅作为辅助 Prompt 上下文，不能覆盖当前报告证据。

记忆是非阻断能力：Store 检索失败时返回空记忆并将错误写入 Graph State；Store 写入失败时保留本轮对话历史和回答，只记录写入错误，不将整次报告问答标记为失败。

长期记忆值统一使用结构化 JSON，包含记忆类型、作用域、内容、报告 ID、来源 trace/session、置信度、重要性、状态和创建/更新时间。写入 key 按作用域、报告 ID 和内容生成，重复内容会更新同一 Store 记录；匿名用户不写入长期记忆，敏感内容拦截后不落库。

回答生成前使用输入预算进行上下文裁剪，默认输入预算为 8000 tokens、输出预算为 2000 tokens。裁剪优先级为：用户问题、当前报告上下文、报告证据、报告检索片段、报告/用户记忆、RAG 结果、历史对话。实际估算值和是否发生裁剪会写入 `state["context_budget"]`，同时仍以模型返回的真实 `prompt_tokens` 为准。

## 本地启动

```bash
docker compose up -d mysql postgres
cd backend
LANGGRAPH_POSTGRES_URL=postgresql://langgraph:langgraph_password@localhost:5432/langgraph \
  .venv/bin/uvicorn app.main:app --reload
```

首次启动时应用调用官方 `setup()` 创建 Checkpointer 和 Store 所需表。PostgreSQL 连接失败会让持久化初始化失败，应在部署中通过健康检查确保数据库先就绪。

## 生产配置

配置 `LANGGRAPH_POSTGRES_URL` 后，应用会使用：

- `langgraph.checkpoint.postgres.PostgresSaver`
- `langgraph.store.postgres.PostgresStore`
- `langgraph-checkpoint-postgres` 与 `psycopg[binary,pool]`

不配置该变量时，应用只使用进程内实现，重启后记忆丢失，仅适用于本地开发和测试。

## 测试边界

- `InMemorySaver` / `InMemoryStore` 验证图的 Checkpointer、Store 注入契约。
- 测试用户命名空间隔离和显式记忆写入规则。
- 既有报告 RAG、同步问答和 SSE 流式测试保持通过。
