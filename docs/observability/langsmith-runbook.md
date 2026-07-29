# LangSmith 线上观测运行手册

## 1. 部署配置

通过部署平台的环境变量或密钥管理系统注入，不要把 Key 写入仓库文件：

```env
LANGSMITH_TRACING=true
LANGSMITH_API_KEY=lsv2_...
LANGSMITH_ENDPOINT=https://api.smith.langchain.com
LANGSMITH_PROJECT=ioc-agent-prod
LANGSMITH_SAMPLING_RATE=1.0
LANGSMITH_MASK_INPUTS_OUTPUTS=true
```

生产建议先用 `0.1` 采样验证链路，再根据调用量调整。涉及敏感业务数据时保持 `LANGSMITH_MASK_INPUTS_OUTPUTS=true`。

服务启动后，后端会在首次构造 LangSmith client 时检查开关、Key 和采样率。缺少任一条件时只使用本地 Trace，不会尝试上报。

## 2. LangSmith 中查看什么

按 Project `ioc-agent-prod` 查看三类根 Graph Run：

- `ioc_operation_analysis_graph`
- `ioc_report_chat_graph`
- `ioc_runtime_chat_graph`

根 Run 的 metadata 包含 `ioc_trace_id`，还会按场景带上 `domain`、`report_id`、`prompt_code` 和 `streaming`。

子 Run 包括：

- LangGraph 节点：数据查询、异常识别、原因分析、建议生成、报告汇总等。
- Tool Run：`kpi_query`、`alarm_query`、`risk_query`、`work_order_query`、`ioc_summary_analysis`。
- Retriever Run：`rag_search`。
- LLM Run：由 `ChatOpenAI` 的 LangChain callback 采集。

## 3. 本地 Trace 关联

前端“Trace 查询”页面继续查询本地 `ai_trace` 表。将页面中的 `trace_id` 复制到 LangSmith metadata 的 `ioc_trace_id` 过滤条件，可以定位同一次业务请求的 LangSmith 运行树。

本地 Trace 侧保留业务审计字段，例如 Prompt 快照、Token 用量、错误码和数据库时间；LangSmith 侧用于 Agent 调试、节点耗时、模型链路和失败定位。

## 4. 排查清单

1. LangSmith 没有数据：检查 `LANGSMITH_TRACING`、Key、Endpoint、Project 和采样率。
2. 只有根 Run 没有 LLM：确认模型通过 `ChatOpenAI` 调用，并检查 LangChain callback 是否被传入 Graph。
3. Tool/RAG 没有子 Run：确认请求确实走到对应 Tool/RAG 分支，并检查根 Run 上下文是否存在。
4. 业务接口报错：LangSmith 上报异常不会改变业务结果，优先查看后端日志和本地 Trace。
5. 发现敏感内容：立即停用上报，检查脱敏配置和 payload，禁止关闭 `LANGSMITH_MASK_INPUTS_OUTPUTS` 后直接用于生产。
