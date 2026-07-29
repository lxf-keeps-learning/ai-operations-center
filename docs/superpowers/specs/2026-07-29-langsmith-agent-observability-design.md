# LangSmith Agent 可观测性设计

## 背景

项目已有 `build_langsmith_config`，可为 LangGraph 根调用挂载 LangSmith Tracer，但默认开关关闭，且 Tool/RAG/业务节点的可观测粒度不统一。目标是让线上能够稳定上报 Agent 执行链路，同时保留本地 `ai_trace` 作为业务审计链路。

## 目标

- 生产环境通过环境变量启用 LangSmith 上报，密钥不进入仓库。
- 覆盖运营分析、报告追问、Runtime 对话三类 Agent。
- 可观察 Graph、业务节点、模型调用、Tool 调用和 RAG 调用的状态、耗时、错误与关键元数据。
- 输入输出默认脱敏，用户、会话、租户和企业标识使用不可逆引用。
- LangSmith 上报异常不得阻断 Agent 主流程。

## 方案

### Trace 分层

每次 Agent 请求创建一个根 Graph Run，元数据携带 `ioc_trace_id`、`graph_name`、环境、领域、报告 ID、Prompt 编码和流式标记。LangGraph callback 负责根链路与 LangChain 模型调用的关联。

业务节点和外部调用通过统一的可观测包装器生成子 Run，统一记录名称、类型、输入摘要、输出摘要、耗时、状态和异常。包装器只接收脱敏后的 payload，并在 LangSmith 不可用时退化为普通函数调用。

### 覆盖范围

- Operation Agent：数据查询、异常识别、原因分析、建议生成、报告汇总。
- Report Chat Agent：问题分类、报告证据检索、RAG 决策、RAG 查询构建、外部 RAG 调用、回答生成。
- Runtime Agent：Graph 根链路与 Prompt/LLM 调用。

### 线上开关

生产部署环境设置 `LANGSMITH_TRACING=true`、`LANGSMITH_API_KEY`、`LANGSMITH_PROJECT` 和可选 Endpoint、采样率。默认配置仍保持本地安全关闭，避免开发机无意上报。API Key 只从环境变量或密钥管理系统读取。

### 错误与隐私

- LangSmith Client 初始化失败、网络失败或 Span 上报失败只记录后端日志，不改变业务返回。
- 凭据键、手机号、邮箱和 API Key 文本经过现有敏感数据扫描器脱敏。
- 用户/租户/公司等标识只发送哈希后的短引用。
- 不上传数据库连接串、模型 API Key 或原始鉴权头。

## 测试策略

- 配置开启/关闭、采样率和 callback 构造测试。
- 脱敏与稳定引用测试。
- 子 Run 包装器成功、异常和无 LangSmith 客户端时的行为测试。
- Graph 入口元数据测试，确认三类 Agent 传入正确的项目、Trace 和业务字段。
- 运行后端聚焦测试、完整测试，以及前端类型检查和构建。

## 成功标准

1. 生产环境配置 LangSmith 后，三类 Agent 请求均可在对应 Project 中看到根 Trace。
2. Trace 中可区分业务节点、LLM、Tool 和 RAG 调用，并携带耗时、状态和错误。
3. 脱敏测试证明敏感信息不会进入上报 payload。
4. LangSmith 不可用时，Agent 仍能正常返回业务结果。
5. 所有验证命令通过。
