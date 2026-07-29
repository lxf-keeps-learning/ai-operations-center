# LangSmith Agent 可观测项目介绍与使用说明

## 一、项目介绍

本项目是 AI Operations Center 的 Agent 可观测性接入方案。它将 LangSmith 用作 Agent 调试、链路分析、模型调用观测和后续评估平台，同时保留本地 `ai_trace` 作为业务审计与 Trace 查询来源。

一次请求在系统中的链路如下：

```text
用户请求
  -> LangGraph Agent 根 Trace
  -> 业务节点
  -> ChatOpenAI / Tool Center / RAG
  -> 报告、回答和本地业务审计
```

当前接入三类 Agent：

| Agent | LangSmith 根 Run | 主要观测内容 |
|---|---|---|
| Operation Agent | `ioc_operation_analysis_graph` | 运营数据查询、异常识别、原因分析、建议生成、报告汇总 |
| Report Chat Agent | `ioc_report_chat_graph` | 报告上下文、问题范围、报告证据、RAG 决策、知识库检索、回答生成 |
| Runtime Agent | `ioc_runtime_chat_graph` | 会话、Prompt、模型调用、回答和流式过程 |

Tool Center 和 RAG Service 会产生独立子 Run。模型调用使用 `ChatOpenAI`，由 LangChain/LangGraph callback 关联到当前 Agent 根 Trace。

## 二、可以观测什么

- Agent 根 Trace：一次完整分析、追问或 Runtime 对话。
- LangGraph 节点：节点名称、执行状态、耗时、错误。
- LLM 调用：模型、Prompt/消息链路、输入输出、Token 和错误信息。
- Tool 调用：Tool 名称、输入摘要、结果状态、Evidence 数量和耗时。
- RAG 调用：查询摘要、场景、过滤条件、命中结果数量、失败信息和耗时。
- 业务关联：通过 `ioc_trace_id` 将 LangSmith Run 与本地 Trace、报告记录和后端日志关联。

## 三、配置方式

### 1. 生产环境

API Key 必须使用部署平台的 Secret 或密钥管理系统注入：

```env
LANGSMITH_TRACING=true
LANGSMITH_API_KEY=lsv2_你的密钥
LANGSMITH_ENDPOINT=https://api.smith.langchain.com
LANGSMITH_PROJECT=ioc-agent-prod
LANGSMITH_SAMPLING_RATE=1.0
LANGSMITH_MASK_INPUTS_OUTPUTS=true
```

`LANGSMITH_MASK_INPUTS_OUTPUTS=true` 应保持开启。系统还会对 API Key、Token、密码、手机号、邮箱和常见密钥文本做脱敏；用户、会话、租户和企业标识使用不可逆哈希引用。

### 2. 本地环境

复制配置模板：

```bash
cd backend
cp .env.example .env
```

本地没有 API Key 时不会上报。需要联调时，在本地 `.env` 中设置 Key，并重启后端服务。

## 四、启动和验证

启动后端：

```bash
cd backend
source .venv/bin/activate
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

执行一条运营分析、报告追问或 Runtime 对话后，在 LangSmith Project 中按以下 Run Name 检索：

```text
ioc_operation_analysis_graph
ioc_report_chat_graph
ioc_runtime_chat_graph
```

也可以复制返回结果中的 `trace_id`，在 LangSmith 的 metadata 中过滤 `ioc_trace_id`。

## 五、配置状态判断

后端内部会根据三个条件判断是否真正启用：

1. `LANGSMITH_TRACING=true`。
2. `LANGSMITH_API_KEY` 非空。
3. `LANGSMITH_SAMPLING_RATE` 大于 0。

任何条件不满足时，Agent 仍然正常运行，只使用本地 Trace。LangSmith 初始化或上报失败也不会阻塞业务请求。

## 六、常见问题

### LangSmith 没有数据

检查 Project、Endpoint、API Key、采样率和后端是否已重启。确认请求确实走到了对应 Agent，而不是命中本地缓存。

### 只有根 Trace，没有 Tool/RAG 子 Run

确认本次请求实际触发了对应 Tool 或 RAG 分支。RAG 未配置或规则判断不需要 RAG 时，不会产生真实检索调用。

### 看到敏感信息

立即将 `LANGSMITH_TRACING` 设为 `false`，检查脱敏配置和上报 payload，不要在生产关闭 `LANGSMITH_MASK_INPUTS_OUTPUTS`。

### 上报失败是否影响业务

不会。上报是 best-effort，业务返回、本地 Trace 和报告落库链路独立运行。

## 七、代码入口

- 根 Trace 配置：[langsmith_tracing.py](../../backend/app/observability/langsmith_tracing.py)
- 子 Run 包装器：[langsmith_runs.py](../../backend/app/observability/langsmith_runs.py)
- Tool 观测入口：[base_tool.py](../../backend/app/tool_center/base_tool.py)
- RAG 观测入口：[service.py](../../backend/app/rag/service.py)
- 线上排查手册：[langsmith-runbook.md](langsmith-runbook.md)
