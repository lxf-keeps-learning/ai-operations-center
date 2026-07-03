# Sprint1：基础设施底座建设任务文档

> 项目角色：AIOperationsCenter / 智能运营中心 AI Agent 项目  
> 当前阶段：Sprint1 实际启动  
> 目标定位：先建设企业级基础设施底座，为后续 AI Runtime、Tool Center、Agent Graph 提供统一公共能力。

---

## 1. Sprint1 总目标

Sprint1 的目标不是直接实现完整 AI 问答、Agent Graph 或复杂运营业务，而是优先完成后端和前端的基础设施能力。

本期重点建设以下能力：

| 模块 | 目标 |
|---|---|
| Config Center | 配置统一管理，支持多环境、多模型配置 |
| Logger Center | 日志统一记录，支持问题排查、操作审计、模型调用统计 |
| Trace Center | 每次请求有唯一 TraceId，贯穿 API、Service、Graph、Tool、LLM |
| Exception Center | 异常统一处理，避免接口返回格式混乱 |
| Response DTO | 所有接口成功和失败格式统一 |
| Context Center | 请求上下文、用户上下文、页面上下文、Graph 状态边界清晰 |
| Health API | 提供服务健康检查能力 |
| Infrastructure Console | 前端提供基础设施控制台入口 |

---

## 2. Sprint1 范围边界

### 2.1 本期应该做

- 建设后端 `core` 基础设施模块。
- 定义统一接口响应规范。
- 定义 HTTP 状态码与业务错误码规范。
- 实现全局异常处理。
- 实现 TraceId 中间件。
- 实现统一 Logger。
- 实现配置中心基础能力。
- 实现大模型配置展示能力。
- 实现基础 Context 分层。
- 实现健康检查接口。
- 实现前端基础设施控制台。
- 实现配置中心、模型配置、日志中心、错误码说明、健康检查等基础页面。

### 2.2 本期不建议做

- 不做完整 AI 问答业务。
- 不做复杂 Agent Graph。
- 不做复杂 Tool Center。
- 不做复杂日志检索平台。
- 不做复杂计费系统。
- 不做复杂权限系统。
- 不做完整运营大屏。
- 不在前端保存任何模型 API Key。
- 不让前端直接调用千问、DeepSeek、豆包等模型厂商接口。

---

## 3. 统一响应规范

### 3.1 设计原则

后端所有接口必须返回统一结构。

需要区分两层状态：

```text
HTTP 状态码：协议层状态，比如 200、400、401、403、404、500
业务错误码：系统内部业务状态，比如 0、400001、500001、504101
```

不要把 HTTP 状态码直接当作业务 `code` 使用。

### 3.2 成功响应格式

```json
{
  "code": 0,
  "message": "success",
  "traceId": "trace_xxx",
  "success": true,
  "data": {}
}
```

### 3.3 失败响应格式

```json
{
  "code": 400001,
  "message": "参数错误",
  "traceId": "trace_xxx",
  "success": false,
  "data": null
}
```

### 3.4 字段规范

| 字段 | 说明 |
|---|---|
| code | 业务状态码，成功为 0 |
| message | 响应信息，成功为 success，失败为错误说明 |
| traceId | 一次请求的全链路追踪 ID |
| success | 是否成功 |
| data | 业务数据，失败时通常为 null |

### 3.5 命名规范

推荐使用：

```text
message
traceId
```

不推荐使用：

```text
msg
requestId
```

原因：

- `message` 比 `msg` 更语义化。
- `traceId` 比 `requestId` 更适合后续 AI Agent 全链路追踪。
- 后续链路会从 Browser → API → Service → Graph → Tool → LLM → Response，不只是一次 HTTP 请求。

---

## 4. HTTP 状态码与业务错误码规范

### 4.1 状态码分层

| 层级 | 作用 | 示例 |
|---|---|---|
| HTTP 状态码 | 表示协议层请求状态 | 200、400、401、403、404、500 |
| 业务错误码 | 表示业务层具体错误 | 400001、500101、504101 |

### 4.2 常见 HTTP 状态码

#### 2xx：成功

| 状态码 | 含义 |
|---:|---|
| 200 | 请求成功 |
| 201 | 创建成功 |
| 204 | 请求成功但无返回内容 |

#### 3xx：重定向

| 状态码 | 含义 |
|---:|---|
| 301 | 永久重定向 |
| 302 | 临时重定向 |
| 304 | 缓存未变化 |

说明：Sprint1 中 3xx 不需要重点处理，理解即可。

#### 4xx：客户端错误

| 状态码 | 含义 |
|---:|---|
| 400 | 请求参数错误 |
| 401 | 未认证 |
| 403 | 无权限 |
| 404 | 资源不存在 |
| 409 | 资源冲突 |
| 422 | 参数校验失败 |
| 429 | 请求过于频繁 |

#### 5xx：服务端错误

| 状态码 | 含义 |
|---:|---|
| 500 | 服务内部错误 |
| 502 | 网关或下游服务错误 |
| 503 | 服务不可用 |
| 504 | 网关或下游调用超时 |

### 4.3 业务错误码建议

| code | message | HTTP status | 说明 |
|---:|---|---:|---|
| 0 | success | 200 | 成功 |
| 400001 | 参数错误 | 400 | 请求参数错误 |
| 401001 | 未登录 | 401 | 用户未认证 |
| 403001 | 无权限 | 403 | 用户无权限 |
| 404001 | 资源不存在 | 404 | 请求资源不存在 |
| 422001 | 参数校验失败 | 422 | Pydantic 参数校验失败 |
| 429001 | 请求过于频繁 | 429 | 请求被限流 |
| 500001 | 系统内部错误 | 500 | 未知系统异常 |
| 500101 | 大模型调用失败 | 502 | LLM Provider 调用失败 |
| 504101 | 大模型调用超时 | 504 | LLM Provider 调用超时 |

### 4.4 文档交付物

创建文档：

```text
AIAgent/AIOperationsCenter/docs/HTTP状态码与业务错误码说明.md
```

文档内容包括：

1. HTTP 状态码是什么。
2. 业务错误码是什么。
3. 为什么 HTTP 状态码和业务错误码不能混用。
4. 本项目错误码分段规则。
5. 常见 HTTP 状态码说明。
6. 常见业务错误码说明。
7. 前端如何处理错误。
8. 后端如何抛出业务异常。

---

## 5. TraceId 设计

### 5.1 Trace 是什么

Trace 可以理解为：

```text
一次请求从进入系统到返回结果的全过程链路标识。
```

每次用户请求进来，系统生成一个唯一 `traceId`。

### 5.2 请求链路

```text
Browser
  ↓
API
  ↓
Service
  ↓
Graph
  ↓
Tool
  ↓
LLM
  ↓
Response
```

### 5.3 TraceId 规则

- 如果前端请求头携带 `X-Trace-Id`，后端复用该值。
- 如果前端没有携带，后端自动生成 UUID。
- TraceId 写入当前请求上下文。
- TraceId 写入日志。
- TraceId 写入响应头 `X-Trace-Id`。
- TraceId 写入响应体 `traceId` 字段。

### 5.4 Logger 和 Trace 区别

| 对比项 | Logger | Trace |
|---|---|---|
| 解决什么 | 记录发生了什么 | 串起一次请求全过程 |
| 核心字段 | level、message、time | traceId、spanId |
| 关注点 | 单条日志 | 整条链路 |
| 示例 | LLM 调用失败 | 这次请求在哪一步失败 |

一句话：

```text
Logger 是点，Trace 是线。
```

---

## 6. 日志中心设计

### 6.1 设计原则

日志主要由后端统一记录，前端负责展示、查询和上报部分浏览器行为日志。

前端不是日志中心的核心存储方。

### 6.2 日志类型

Sprint1 建议规划以下日志类型：

| 日志类型 | 说明 | 示例 |
|---|---|---|
| 系统日志 | 服务启动、关闭、配置加载 | 应用启动成功 |
| API 访问日志 | 请求路径、耗时、状态码 | `/api/v1/health 200 15ms` |
| 业务操作日志 | 用户点击、提交、修改配置 | 用户切换默认模型 |
| LLM 调用日志 | 模型、Token、耗时、费用 | qwen 输入 500 token |
| Tool 调用日志 | 工具名称、入参摘要、结果状态 | 查询运营指标 |
| 异常日志 | 错误码、堆栈摘要、TraceId | LLM 调用超时 |

### 6.3 LLM 使用日志字段

```json
{
  "traceId": "trace_xxx",
  "provider": "qwen",
  "model": "qwen-plus",
  "inputTokens": 1200,
  "outputTokens": 800,
  "totalTokens": 2000,
  "cost": 0.012,
  "durationMs": 2300,
  "success": true
}
```

### 6.4 Sprint1 日志页面展示

| 日志类型 | 展示字段 |
|---|---|
| API 日志 | path、method、status、durationMs、traceId |
| 操作日志 | userId、action、target、time、traceId |
| LLM 日志 | provider、model、inputTokens、outputTokens、durationMs、traceId |
| 异常日志 | errorCode、message、stack摘要、traceId |

Sprint1 可以先使用 mock 数据或内存日志。

---

## 7. 配置中心设计

### 7.1 配置分层原则

不是所有配置都区分前后端，而是要区分：

```text
敏感配置：后端管理
非敏感展示配置：前端可以展示
```

### 7.2 后端配置

| 配置 | 是否放后端 | 原因 |
|---|---:|---|
| 大模型 API Key | 是 | 不能暴露给前端 |
| 数据库连接 | 是 | 敏感信息 |
| Redis 地址 | 是 | 基础设施配置 |
| LangGraph 配置 | 是 | 后端运行配置 |
| 环境变量 dev/test/prod | 是 | 决定后端运行模式 |
| 模型供应商启用状态 | 是 | 后端控制可用模型 |
| 单次最大 Token | 是 | 防止前端绕过限制 |
| 超时时间 | 是 | 服务稳定性控制 |

### 7.3 前端配置

| 配置 | 是否放前端 | 原因 |
|---|---:|---|
| 页面标题 | 是 | 展示配置 |
| API Base URL | 是 | 前端请求后端 |
| 可选择模型列表 | 可以展示 | 应从后端接口获取 |
| 默认主题 | 是 | UI 配置 |
| 页面菜单 | 是 | UI 配置 |

### 7.4 大模型配置

本期支持三个 provider：

- 千问 Qwen
- DeepSeek
- 豆包 Doubao

后端配置示例：

```yaml
llm:
  default_provider: qwen
  providers:
    qwen:
      enabled: true
      model: qwen-plus
      api_key: ${QWEN_API_KEY}
      max_input_tokens: 8000
      max_output_tokens: 2000
      rpm_limit: 60
    deepseek:
      enabled: true
      model: deepseek-chat
      api_key: ${DEEPSEEK_API_KEY}
      max_input_tokens: 8000
      max_output_tokens: 2000
      rpm_limit: 60
    doubao:
      enabled: true
      model: doubao-pro
      api_key: ${DOUBAO_API_KEY}
      max_input_tokens: 8000
      max_output_tokens: 2000
      rpm_limit: 60
```

前端只展示非敏感字段：

```json
{
  "provider": "qwen",
  "displayName": "千问",
  "enabled": true,
  "default": true,
  "model": "qwen-plus",
  "maxInputTokens": 8000,
  "maxOutputTokens": 2000,
  "rpmLimit": 60
}
```

---

## 8. DTO 设计

### 8.1 DTO 是什么

DTO 是 Data Transfer Object，意思是数据传输对象。

在项目中用于统一前后端接口数据结构。

### 8.2 DTO 解决的问题

- 前后端接口结构统一。
- 成功返回格式统一。
- 失败返回格式统一。
- 避免直接暴露数据库对象。
- 避免每个接口自己随便定义返回格式。

### 8.3 Sprint1 DTO 交付物

| 文件 | 作用 |
|---|---|
| `response_schema.py` | 统一响应模型 |
| `base_dto.py` | DTO 基类 |
| `error_response.py` | 错误返回模型 |
| `pagination.py` | 分页响应模型，可选 |

---

## 9. Context 分层设计

### 9.1 Context 是什么

Context 可以理解为：

```text
一次请求或一次任务执行过程中需要携带的上下文信息。
```

它不是业务数据本身，而是帮助系统理解：

- 谁在请求？
- 从哪里请求？
- 当前页面是什么？
- 当前选择对象是什么？
- 当前任务执行环境是什么？

### 9.2 Context 分层

| 类型 | 生命周期 | 保存什么 | 不保存什么 |
|---|---|---|---|
| RequestContext | 一次 HTTP 请求 | traceId、requestTime、clientIp、userAgent | 不保存业务对象 |
| UserContext | 一次请求或会话 | userId、username、orgId、roles、permissions | 不保存密码、敏感身份信息 |
| PageContext | 一次页面 AI 任务 | pageCode、filters、selectedObjectId | 不保存完整页面数据 |
| GraphState | 一次 Graph 执行 | intent、messages、toolResult、aiResult | 不保存 ORM 对象、数据库连接 |

### 9.3 Context 和 GraphState 区别

| 对比项 | Context | GraphState |
|---|---|---|
| 关注点 | 请求是谁发起的、从哪里来 | Agent 当前执行到了哪一步 |
| 生命周期 | 请求级、会话级 | Graph 执行级 |
| 数据类型 | 用户、页面、Trace、权限 | 意图、工具结果、模型结果 |
| 是否属于业务流转 | 不直接属于 | 属于 Agent 执行流转 |
| 示例 | userId、traceId、pageCode | intent、tool_result、ai_result |

一句话：

```text
Context 是执行环境，GraphState 是执行过程。
```

---

## 10. 后端目录设计

### 10.1 后端设计原则

后端基础设施能力统一放在 `core` 模块中。

建议原则：

- 配置统一放 `core/config`。
- 日志统一放 `core/logging`。
- Trace 统一放 `core/trace`。
- 异常统一放 `core/exception`。
- DTO 统一放 `core/schema`。
- Context 统一放 `core/context`。
- 中间件统一放 `core/middleware`。
- API 路由放 `api`。
- 业务服务放 `application`。
- Agent 能力后续放 `agent`。

### 10.2 推荐目录

```text
backend/
├── app/
│   ├── main.py
│   ├── api/
│   │   ├── router.py
│   │   └── v1/
│   │       ├── health_api.py
│   │       ├── config_api.py
│   │       ├── log_api.py
│   │       ├── error_code_api.py
│   │       ├── trace_api.py
│   │       └── context_api.py
│   ├── core/
│   │   ├── config/
│   │   │   ├── settings.py
│   │   │   ├── llm_settings.py
│   │   │   └── env.py
│   │   ├── logging/
│   │   │   ├── logger.py
│   │   │   ├── log_schema.py
│   │   │   ├── operation_logger.py
│   │   │   └── llm_usage_logger.py
│   │   ├── trace/
│   │   │   ├── trace_context.py
│   │   │   └── trace_middleware.py
│   │   ├── exception/
│   │   │   ├── error_code.py
│   │   │   ├── base_exception.py
│   │   │   └── exception_handler.py
│   │   ├── schema/
│   │   │   ├── response_schema.py
│   │   │   ├── base_dto.py
│   │   │   └── pagination.py
│   │   ├── context/
│   │   │   ├── request_context.py
│   │   │   ├── user_context.py
│   │   │   ├── page_context.py
│   │   │   └── context_holder.py
│   │   └── middleware/
│   │       └── request_log_middleware.py
│   ├── application/
│   │   └── infra_service.py
│   ├── agent/
│   │   ├── runtime/
│   │   ├── graph/
│   │   ├── tool/
│   │   └── prompt/
│   └── tests/
│       ├── test_response.py
│       ├── test_error_code.py
│       ├── test_exception.py
│       ├── test_trace.py
│       └── test_health.py
├── docs/
│   └── HTTP状态码与业务错误码说明.md
├── .env.dev
├── .env.test
├── .env.example
└── README.md
```

---

## 11. 后端 API 设计

统一挂载到：

```text
/api/v1
```

### 11.1 健康检查

```http
GET /api/v1/health
```

返回：

```json
{
  "code": 0,
  "message": "success",
  "traceId": "trace_xxx",
  "success": true,
  "data": {
    "status": "UP",
    "env": "dev",
    "version": "1.0.0"
  }
}
```

### 11.2 模型配置

```http
GET /api/v1/config/models
```

返回千问、DeepSeek、豆包三种模型的非敏感配置。

### 11.3 当前运行环境

```http
GET /api/v1/config/runtime
```

返回：

- env
- appName
- version
- defaultModel

### 11.4 错误码列表

```http
GET /api/v1/errors/codes
```

返回所有业务错误码说明。

### 11.5 最近日志

```http
GET /api/v1/logs/recent
```

Sprint1 可以先返回 mock 数据或内存日志。

### 11.6 LLM 使用日志

```http
GET /api/v1/logs/llm-usage
```

字段包括：

- provider
- model
- inputTokens
- outputTokens
- totalTokens
- durationMs
- traceId

### 11.7 Trace 查询

```http
GET /api/v1/traces/{traceId}
```

Sprint1 可以先返回 mock 链路数据。

### 11.8 当前 Context

```http
GET /api/v1/context/current
```

返回当前 RequestContext、UserContext、PageContext 示例。

---

## 12. 前端页面设计

### 12.1 前端首页定位

Sprint1 前端首页不做复杂业务运营首页，而是做：

```text
基础设施控制台 Infrastructure Console
```

### 12.2 页面结构

```text
基础设施控制台
├── 配置中心
├── 模型配置
├── 日志中心
├── Trace 查询
├── 错误码说明
├── 健康检查
└── Context 示例
```

### 12.3 页面功能

| 页面 | 本期功能 | 复杂度 |
|---|---|---|
| Dashboard | 展示系统环境、服务状态、当前模型 | 低 |
| Config Center | 展示当前环境、配置项摘要 | 中 |
| Model Config | 展示可选模型，支持选择默认模型 | 中 |
| Log Center | 展示最近日志，不做复杂检索 | 中 |
| Trace Viewer | 输入 traceId，查看链路日志 | 中 |
| Error Code | 展示错误码说明 | 低 |
| Health Check | 展示后端健康状态 | 低 |
| Context Demo | 展示当前请求上下文 | 低 |

### 12.4 前端目录建议

```text
frontend/
├── src/
│   ├── api/
│   │   ├── config.ts
│   │   ├── health.ts
│   │   ├── logs.ts
│   │   ├── errors.ts
│   │   ├── trace.ts
│   │   └── context.ts
│   ├── pages/
│   │   ├── dashboard/
│   │   ├── config-center/
│   │   ├── model-config/
│   │   ├── log-center/
│   │   ├── trace-viewer/
│   │   ├── error-code/
│   │   ├── health-check/
│   │   └── context-demo/
│   ├── components/
│   │   ├── layout/
│   │   ├── status-card/
│   │   └── data-table/
│   ├── types/
│   │   ├── response.ts
│   │   ├── config.ts
│   │   ├── log.ts
│   │   └── error-code.ts
│   └── utils/
│       ├── request.ts
│       └── trace.ts
```

---

## 13. 前端请求封装

### 13.1 是否需要封装 request.ts

需要。

前端页面不要直接重复处理每个接口的 `code`、`message`、`traceId`。

推荐结构：

```text
页面组件
  ↓
api/config.ts、api/logs.ts
  ↓
utils/request.ts
  ↓
后端接口
```

### 13.2 request.ts 负责什么

- 统一 baseURL。
- 自动加入 `X-Trace-Id`。
- 统一处理 HTTP 错误。
- 统一处理业务 code。
- 成功时返回 `data`。
- 失败时展示 `message`。
- 保留 `traceId`，方便页面复制排查。
- 避免每个页面重复写接口异常处理逻辑。

---

## 14. Sprint1 推荐执行顺序

建议按以下顺序推进：

```text
1. response_schema.py
2. error_code.py
3. docs/HTTP状态码与业务错误码说明.md
4. base_exception.py
5. exception_handler.py
6. trace_context.py
7. trace_middleware.py
8. logger.py
9. settings.py
10. llm_settings.py
11. request_context.py
12. user_context.py
13. page_context.py
14. context_holder.py
15. health_api.py
16. config_api.py
17. error_code_api.py
18. log_api.py
19. trace_api.py
20. context_api.py
21. 前端基础设施控制台
22. 前端配置中心页面
23. 前端模型配置页面
24. 前端日志中心页面
25. 前端错误码说明页面
26. 前端健康检查页面
27. 前端 Trace 查询页面
28. 前端 Context 示例页面
```

原因：

- Response 是所有接口基础。
- ErrorCode 和 Exception 依赖 Response。
- Trace 和 Logger 依赖统一上下文。
- Health API 用来验证基础设施。
- Config API 和 Log API 用来支撑前端基础设施页面。
- 前端页面最后接 API。

---

## 15. Sprint1 验收标准

### 15.1 接口验收

- 所有接口返回结构一致。
- 成功返回 `success=true`。
- 失败返回 `success=false`。
- 所有响应都包含 `code`、`message`、`traceId`、`data`。
- HTTP 状态码和业务 code 分开。

### 15.2 Trace 验收

- 每个请求都有 traceId。
- traceId 出现在响应体中。
- traceId 出现在响应头中。
- traceId 出现在日志中。
- 异常时也能返回 traceId。

### 15.3 异常验收

- 参数错误返回统一格式。
- 未登录返回统一格式。
- 无权限返回统一格式。
- 系统异常返回统一格式。
- LLM 超时返回统一格式。
- 不允许每个接口自己随便写 try-except。
- 未知异常不直接把堆栈返回前端。

### 15.4 配置验收

- 可以通过 `.env.dev`、`.env.test` 切换环境。
- 后端可以读取当前环境配置。
- 前端可以展示当前环境。
- 模型列表由后端返回。
- API Key 不出现在前端代码中。

### 15.5 日志验收

- 后端所有 API 请求都有日志。
- 日志中包含 traceId。
- LLM 调用日志可以记录 provider、model、token、耗时。
- 异常日志可以记录错误码和 traceId。
- 代码中不允许随意使用 `print`。

### 15.6 Context 验收

- 可以获取当前 traceId。
- 可以获取当前用户信息。
- 可以获取当前页面上下文。
- Context 不保存完整业务对象。
- GraphState 和 Context 不混用。

### 15.7 前端验收

- 有基础设施控制台首页。
- 可以进入配置中心。
- 可以进入模型配置页面。
- 可以进入日志中心页面。
- 可以进入错误码说明页面。
- 可以进入健康检查页面。
- 可以查询 Trace 示例链路。
- 前端不展示任何 API Key。

---

## 16. 给 Codex / OpenCode 的完整任务 Prompt

```md
你是资深全栈工程师，现在请在当前项目中完成 Sprint1：基础设施底座建设。

## 一、项目背景

当前项目是 AIOperationsCenter / 智能运营中心 AI Agent 项目。Sprint1 目标是建设基础设施能力，为后续 AI Runtime、Tool Center、Agent Graph 提供统一公共能力。

本次不要实现完整 AI 问答业务，不要实现复杂 Agent Graph，只做基础设施底座。

## 二、Sprint1 目标

请完成以下能力：

1. 配置统一 Config Center
2. 日志统一 Logger Center
3. TraceId 全链路追踪
4. 业务错误码 ErrorCode
5. 全局异常处理 Exception Handler
6. 统一响应 DTO
7. Context 分层
8. Health API
9. 前端基础设施控制台页面

## 三、统一响应规范

后端所有接口必须返回统一结构：

```json
{
  "code": 0,
  "message": "success",
  "traceId": "trace_xxx",
  "success": true,
  "data": {}
}
```

失败返回：

```json
{
  "code": 400001,
  "message": "参数错误",
  "traceId": "trace_xxx",
  "success": false,
  "data": null
}
```

注意：

- HTTP 状态码和业务 code 必须分开。
- HTTP 200 表示协议请求成功。
- 业务 code=0 表示业务成功。
- 业务错误码使用 400001、401001、403001、404001、500001、500101、504101 等。
- 不要把 HTTP 状态码直接当业务 code 使用。
- 字段统一使用 message，不要使用 msg。
- 字段统一使用 traceId，不要使用 requestId。

## 四、HTTP 状态码和业务错误码文档

请创建文档：

```text
AIAgent/AIOperationsCenter/docs/HTTP状态码与业务错误码说明.md
```

文档内容包括：

1. HTTP 状态码是什么
2. 业务错误码是什么
3. 为什么 HTTP 状态码和业务错误码不能混用
4. 本项目错误码分段规则
5. 常见 HTTP 状态码说明
6. 常见业务错误码说明
7. 前端如何处理错误
8. 后端如何抛出业务异常

业务错误码建议：

| code | message | HTTP status | 说明 |
|---:|---|---:|---|
| 0 | success | 200 | 成功 |
| 400001 | 参数错误 | 400 | 请求参数错误 |
| 401001 | 未登录 | 401 | 用户未认证 |
| 403001 | 无权限 | 403 | 用户无权限 |
| 404001 | 资源不存在 | 404 | 资源不存在 |
| 422001 | 参数校验失败 | 422 | Pydantic 参数校验失败 |
| 429001 | 请求过于频繁 | 429 | 限流 |
| 500001 | 系统内部错误 | 500 | 未知系统异常 |
| 500101 | 大模型调用失败 | 502 | LLM Provider 调用失败 |
| 504101 | 大模型调用超时 | 504 | LLM Provider 调用超时 |

## 五、后端目录设计

请按照以下结构建设后端基础设施模块。如果项目已有目录，请在不破坏现有结构的前提下合并。

```text
backend/
├── app/
│   ├── main.py
│   ├── api/
│   │   ├── router.py
│   │   └── v1/
│   │       ├── health_api.py
│   │       ├── config_api.py
│   │       ├── log_api.py
│   │       ├── error_code_api.py
│   │       ├── trace_api.py
│   │       └── context_api.py
│   ├── core/
│   │   ├── config/
│   │   │   ├── settings.py
│   │   │   ├── llm_settings.py
│   │   │   └── env.py
│   │   ├── logging/
│   │   │   ├── logger.py
│   │   │   ├── log_schema.py
│   │   │   ├── operation_logger.py
│   │   │   └── llm_usage_logger.py
│   │   ├── trace/
│   │   │   ├── trace_context.py
│   │   │   └── trace_middleware.py
│   │   ├── exception/
│   │   │   ├── error_code.py
│   │   │   ├── base_exception.py
│   │   │   └── exception_handler.py
│   │   ├── schema/
│   │   │   ├── response_schema.py
│   │   │   ├── base_dto.py
│   │   │   └── pagination.py
│   │   ├── context/
│   │   │   ├── request_context.py
│   │   │   ├── user_context.py
│   │   │   ├── page_context.py
│   │   │   └── context_holder.py
│   │   └── middleware/
│   │       └── request_log_middleware.py
│   └── tests/
│       ├── test_response.py
│       ├── test_error_code.py
│       ├── test_exception.py
│       ├── test_trace.py
│       └── test_health.py
├── docs/
│   └── HTTP状态码与业务错误码说明.md
├── .env.dev
├── .env.test
├── .env.example
└── README.md
```

## 六、后端具体实现要求

### 1. response_schema.py

实现统一响应模型：

- ApiResponse
- success_response
- error_response

要求：

- 支持泛型 data
- 所有返回包含 code、message、traceId、success、data
- traceId 默认从当前 TraceContext 获取

### 2. error_code.py

实现业务错误码枚举或常量类。

至少包含：

- SUCCESS = 0
- PARAM_ERROR = 400001
- UNAUTHORIZED = 401001
- FORBIDDEN = 403001
- NOT_FOUND = 404001
- VALIDATION_ERROR = 422001
- RATE_LIMIT = 429001
- INTERNAL_ERROR = 500001
- LLM_PROVIDER_ERROR = 500101
- LLM_TIMEOUT = 504101

每个错误码需要包含：

- code
- message
- http_status
- description

### 3. base_exception.py

实现 AppException。

字段包括：

- code
- message
- http_status
- data

### 4. exception_handler.py

实现全局异常处理。

需要处理：

- AppException
- FastAPI HTTPException
- RequestValidationError
- 未知 Exception

要求：

- 所有异常都返回统一 ApiResponse
- 异常日志中必须包含 traceId
- 未知异常不要把堆栈直接返回给前端
- 堆栈只写入日志

### 5. trace_context.py

使用 contextvars 保存当前请求 traceId。

提供方法：

- set_trace_id
- get_trace_id
- clear_trace_id

### 6. trace_middleware.py

实现 TraceId 中间件。

要求：

- 如果请求头有 X-Trace-Id，则使用请求头中的 traceId
- 如果没有，则后端生成 uuid
- 将 traceId 写入 contextvar
- 将 traceId 写入响应头 X-Trace-Id
- 所有响应体中也包含 traceId

### 7. logger.py

实现统一日志入口。

要求：

- 禁止业务代码直接 print
- 日志中自动包含 traceId
- 日志格式至少包含 time、level、module、message、traceId
- 支持 info、warning、error、exception

### 8. settings.py

实现配置中心。

要求：

- 支持 dev、test、prod 环境
- 从 .env 或环境变量读取配置
- 不允许硬编码 API Key
- 提供 get_settings 方法

### 9. llm_settings.py

实现模型配置。

本期支持三个 provider：

- qwen
- deepseek
- doubao

字段包括：

- provider
- display_name
- enabled
- default
- model
- max_input_tokens
- max_output_tokens
- rpm_limit

注意：

- 前端只能看到非敏感字段
- API Key 只能存在后端配置中
- 前端不能直接调用大模型厂商接口

### 10. Context 分层

实现以下基础模型：

RequestContext：

- traceId
- requestTime
- clientIp
- userAgent

UserContext：

- userId
- username
- orgId
- roles
- permissions

PageContext：

- pageCode
- filters
- selectedObjectId

ContextHolder：

- 获取当前 RequestContext
- 获取当前 UserContext
- 获取当前 PageContext

注意：

- Context 保存执行环境信息
- 不要在 Context 中保存 ORM 对象、数据库连接、大型业务对象
- GraphState 暂时不实现，只预留说明

## 七、后端 API

请实现以下接口，统一挂载到 `/api/v1`。

### 1. 健康检查

```http
GET /api/v1/health
```

返回服务状态、环境、版本。

### 2. 模型配置

```http
GET /api/v1/config/models
```

返回可选模型列表，只返回非敏感字段。

### 3. 当前运行环境

```http
GET /api/v1/config/runtime
```

返回 env、appName、version、defaultModel。

### 4. 错误码列表

```http
GET /api/v1/errors/codes
```

返回所有业务错误码说明。

### 5. 最近日志

```http
GET /api/v1/logs/recent
```

Sprint1 可以先返回 mock 数据或内存日志。

### 6. LLM 使用日志

```http
GET /api/v1/logs/llm-usage
```

Sprint1 可以先返回 mock 数据，字段包括 provider、model、inputTokens、outputTokens、durationMs、traceId。

### 7. Trace 查询

```http
GET /api/v1/traces/{traceId}
```

Sprint1 可以先返回 mock 链路数据。

### 8. 当前 Context

```http
GET /api/v1/context/current
```

返回当前 RequestContext、UserContext、PageContext 示例。

## 八、前端目录设计

请建设前端基础设施控制台。如果已有前端项目，请按现有技术栈实现。

推荐目录：

```text
frontend/
├── src/
│   ├── api/
│   │   ├── config.ts
│   │   ├── health.ts
│   │   ├── logs.ts
│   │   ├── errors.ts
│   │   ├── trace.ts
│   │   └── context.ts
│   ├── pages/
│   │   ├── dashboard/
│   │   ├── config-center/
│   │   ├── model-config/
│   │   ├── log-center/
│   │   ├── trace-viewer/
│   │   ├── error-code/
│   │   ├── health-check/
│   │   └── context-demo/
│   ├── components/
│   │   ├── layout/
│   │   ├── status-card/
│   │   └── data-table/
│   ├── types/
│   │   ├── response.ts
│   │   ├── config.ts
│   │   ├── log.ts
│   │   └── error-code.ts
│   └── utils/
│       ├── request.ts
│       └── trace.ts
```

## 九、前端页面要求

### 1. 基础设施控制台 Dashboard

展示入口：

- 配置中心
- 模型配置
- 日志中心
- Trace 查询
- 错误码说明
- 健康检查
- Context 示例

### 2. 配置中心

展示：

- 当前环境
- 应用名称
- 版本
- 当前默认模型

### 3. 模型配置

展示：

- 千问
- DeepSeek
- 豆包
- enabled
- default
- model
- max_input_tokens
- max_output_tokens
- rpm_limit

注意：

- 不展示 API Key
- 不允许前端直接请求模型厂商

### 4. 日志中心

展示：

- API 日志
- 操作日志
- LLM 调用日志
- 异常日志

Sprint1 可以使用后端 mock 数据。

### 5. Trace 查询

输入 traceId，查询链路。

展示：

- traceId
- request received
- api handled
- service handled
- llm called
- response returned

Sprint1 可以使用 mock 数据。

### 6. 错误码说明

展示 `/api/v1/errors/codes` 返回的错误码表。

### 7. 健康检查

展示 `/api/v1/health` 返回结果。

### 8. Context 示例

展示 `/api/v1/context/current` 返回结果。

## 十、前端请求封装要求

请实现 `utils/request.ts`。

要求：

- 统一 baseURL
- 自动加入 X-Trace-Id
- 统一处理 ApiResponse
- 成功时返回 data
- 失败时展示 message
- 保留 traceId，方便页面复制
- 不要在每个页面重复写 code 判断逻辑

## 十一、开发约束

1. 不要提交真实 API Key。
2. 不要在前端保存模型密钥。
3. 不要让前端直接调用千问、DeepSeek、豆包。
4. 不要实现复杂 Agent Graph。
5. 不要实现复杂计费系统。
6. 不要实现复杂日志平台。
7. 不要破坏已有项目结构。
8. 所有新增接口必须使用统一响应格式。
9. 所有异常必须走全局异常处理。
10. 所有日志必须带 traceId。

## 十二、验收标准

完成后需要满足：

1. 启动后端成功。
2. `/api/v1/health` 正常返回统一格式。
3. 所有接口返回都有 code、message、traceId、success、data。
4. 异常接口也返回统一格式。
5. traceId 同时出现在响应体和响应头。
6. 日志中包含 traceId。
7. `/api/v1/config/models` 能返回千问、DeepSeek、豆包三种模型配置。
8. 前端基础设施控制台可以进入配置中心、模型配置、日志中心、错误码说明、健康检查页面。
9. 前端不展示任何 API Key。
10. docs 下生成 HTTP 状态码与业务错误码说明文档。
11. 后端 core 目录形成统一基础设施分层。
12. 代码中不要出现随意 print。

## 十三、最终输出

请完成代码实现，并输出：

1. 修改了哪些文件
2. 新增了哪些文件
3. 如何启动后端
4. 如何启动前端
5. 如何验证接口
6. 哪些地方是 Sprint1 mock，后续需要 Sprint2 替换
```

---

## 17. 给 Codex / OpenCode 的第一小步 Prompt

建议你先用这个小步 Prompt 跑第一轮，避免一次任务过大。

```md
请先完成 Sprint1 后端基础设施第一阶段，只做以下内容：

1. 统一响应 DTO
2. 业务错误码
3. HTTP 状态码与业务错误码说明文档
4. 全局异常处理
5. TraceId 中间件
6. Health API

要求：

- 所有接口返回统一结构：code、message、traceId、success、data。
- HTTP 状态码和业务 code 分开。
- 成功时业务 code=0。
- 失败时使用业务错误码。
- traceId 同时出现在响应体和响应头。
- 异常不能直接返回堆栈给前端。
- docs 下新增 `HTTP状态码与业务错误码说明.md`。
- 不要做前端。
- 不要做模型配置。
- 不要做 Agent Graph。
- 不要做复杂日志平台。

完成后输出新增和修改文件清单，以及如何运行和验证。
```

---

## 18. Sprint1 一句话目标

Sprint1 最终要达到：

```text
任意一个前端请求进入后端后，都能读取配置、生成 TraceId、记录日志、统一处理异常、统一返回 DTO，并且能在前端基础设施控制台看到配置、健康状态、错误码和基础日志。
```
