# Sprint1 总结与思考：基础设施底座建设

## 一、Sprint1 总体回顾

Sprint1 的核心目标是建设项目基础设施底座，为后续 AI Runtime、Tool Center、Agent Graph 提供统一公共能力。

本期重点不是做完整 AI Agent 业务，而是先完成企业项目必须具备的基础能力：

- 统一接口响应
- 统一错误码
- 统一异常处理
- 统一 TraceId 链路追踪
- 统一日志能力
- 统一配置管理
- 统一前端请求封装
- 建设基础设施控制台入口

这些能力对应 Sprint1 原始目标中的配置统一、日志统一、Trace 统一、异常统一、DTO 统一、Context 统一等基础设施能力。

---

## 二、完成内容总结

## 1. 完成统一 DTO 与接口响应规范

### 1.1 后端封装统一接口格式

后端完成统一响应 DTO 封装，所有接口统一返回以下结构：

```json
{
  "code": 0,
  "message": "success",
  "traceId": "xxx",
  "success": true,
  "data": {}
}
```

失败时统一返回：

```json
{
  "code": 400001,
  "message": "参数错误",
  "traceId": "xxx",
  "success": false,
  "data": null
}
```

### 1.2 明确 HTTP 状态码与业务错误码的区别

本期输出了《HTTP 状态码与业务错误码说明》文档，明确区分：

| 类型 | 作用 | 示例 |
|---|---|---|
| HTTP 状态码 | 表示协议层请求状态 | 200、400、401、500 |
| 业务错误码 | 表示系统内部业务错误 | 0、400001、500001、504101 |

核心认知：

> HTTP 状态码解决“请求在协议层是否成功”，业务错误码解决“业务处理是否成功”。

例如：

- HTTP 200 + code 0：请求成功，业务成功。
- HTTP 400 + code 400001：请求参数错误。
- HTTP 500 + code 500001：服务端内部异常。
- HTTP 504 + code 504101：大模型调用超时。

### 1.3 前端完成统一请求封装

前端完成 `request.ts` 请求封装，主要能力包括：

1. 统一 `baseURL`。
2. 自动加入 `X-Trace-Id`。
3. 统一处理 `ApiResponse`。
4. 成功时返回 `data`。
5. 错误时统一处理 `message`。
6. 保留 `traceId`，方便排查问题。
7. 页面组件不用重复写 `code` 判断逻辑。

### 1.4 为什么使用 X-Trace-Id，而不是 requestId

`requestId` 更偏向一次 HTTP 请求编号，而 `traceId` 更偏向全链路追踪编号。

在本项目中，一次用户请求后续可能经过：

```text
Browser → API → Service → Graph → Tool → LLM → Response
```

所以本项目统一使用 `traceId` 更合适。

核心认知：

> requestId 关注一次请求，traceId 关注一次完整链路。

---

## 2. 后端基础能力建设

本期后端围绕 `core` 模块建设基础设施能力，形成统一管理。

### 2.1 统一响应模型

文件：

```text
core/schema/response_schema.py
```

完成内容：

- 定义统一响应结构。
- 封装成功响应。
- 封装失败响应。
- 所有响应自动带上 `traceId`。
- 避免每个接口自己拼接返回格式。

### 2.2 业务错误码

文件：

```text
core/exception/error_code.py
```

完成内容：

- 定义业务错误码枚举或常量。
- 统一维护错误码、错误信息、HTTP 状态码。
- 支持前端错误码说明页面展示。
- 避免错误码散落在业务代码中。

示例错误码：

| code | 含义 |
|---:|---|
| 0 | 成功 |
| 400001 | 参数错误 |
| 401001 | 未登录 |
| 403001 | 无权限 |
| 404001 | 资源不存在 |
| 422001 | 参数校验失败 |
| 500001 | 系统内部错误 |
| 500101 | 大模型调用失败 |
| 504101 | 大模型调用超时 |

### 2.3 全局异常处理

文件：

```text
core/exception/exception_handler.py
```

完成内容：

- 统一处理业务异常。
- 统一处理参数校验异常。
- 统一处理系统未知异常。
- 异常返回统一 DTO。
- 异常日志中记录 `traceId`。
- 不把后端堆栈直接暴露给前端。

核心认知：

> 全局异常处理是系统的兜底机制，保证接口出错时也能稳定返回统一结构。

### 2.4 TraceId 链路追踪

相关文件：

```text
core/trace/trace_context.py
core/trace/trace_middleware.py
```

完成内容：

- 每次请求自动生成 `traceId`。
- 如果前端请求头中带 `X-Trace-Id`，后端复用该值。
- 如果前端没有传，后端自动生成。
- 响应头返回 `X-Trace-Id`。
- 响应体中返回 `traceId`。
- 日志中自动带上 `traceId`。

核心认知：

> TraceId 是线上排查问题的关键入口。

### 2.5 Logger 日志能力

相关文件：

```text
core/logging/logger.py
```

完成内容：

- 建设统一日志入口。
- 禁止业务代码随意使用 `print`。
- 日志中统一包含时间、级别、模块、消息、traceId。
- 后续可扩展 API 日志、操作日志、LLM 调用日志、异常日志。

日志与 Trace 的关系：

> Logger 负责记录发生了什么，Trace 负责把一次请求中的多条日志串起来。

### 2.6 Config 配置中心

相关文件：

```text
core/config/settings.py
core/config/llm_settings.py
```

完成内容：

- 支持不同环境配置，例如 dev、test、prod。
- 支持从环境变量或配置文件读取配置。
- 大模型配置统一由后端管理。
- 前端只能获取非敏感配置。
- API Key 不暴露给前端。

本期模型配置支持：

- 千问 Qwen
- DeepSeek
- 豆包 Doubao

### 2.7 Context 基础结构

相关文件：

```text
core/context/request_context.py
core/context/user_context.py
core/context/page_context.py
core/context/context_holder.py
```

完成内容：

- 定义请求上下文。
- 定义用户上下文。
- 定义页面上下文。
- 明确 Context 与 GraphState 的边界。

Context 分层建议如下：

| 类型 | 生命周期 | 职责 |
|---|---|---|
| RequestContext | 一次请求 | traceId、requestTime、clientIp、userAgent |
| UserContext | 一次请求或会话 | userId、username、orgId、roles、permissions |
| PageContext | 一次 AI 任务 | pageCode、filters、selectedObjectId |
| GraphState | Graph 执行期 | intent、messages、toolResult、aiResult |

---

## 3. 前端基础能力建设

### 3.1 增加基础设施控制台入口

前端新增基础设施控制台，用于验证和展示 Sprint1 的基础设施能力。

页面入口包括：

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

### 3.2 配置中心

完成内容：

- 展示当前运行环境。
- 展示应用名称。
- 展示版本信息。
- 展示后端返回的基础配置。
- 不展示敏感信息。

### 3.3 模型配置

完成内容：

- 展示千问、DeepSeek、豆包三类模型。
- 展示模型是否启用。
- 展示默认模型。
- 展示 token 限制配置。
- 不展示 API Key。
- 不允许前端直接请求模型厂商接口。

### 3.4 日志中心

完成内容：

- 展示基础日志数据。
- 支持查看 API 日志。
- 支持查看操作日志。
- 支持查看 LLM 调用日志。
- 支持查看异常日志。

本期日志中心偏基础展示，后续可以扩展为完整日志检索平台。

### 3.5 Trace 查询

完成内容：

- 支持输入 `traceId` 查询链路。
- 展示一次请求的链路过程。
- 用于模拟线上排查问题。

### 3.6 错误码说明

完成内容：

- 展示后端统一错误码。
- 方便前后端开发统一理解错误含义。
- 减少接口联调中的沟通成本。

### 3.7 健康检查

完成内容：

- 展示后端服务状态。
- 展示当前环境。
- 展示服务版本。
- 为后续部署检查提供基础能力。

### 3.8 Context 示例

完成内容：

- 展示当前请求上下文。
- 展示用户上下文。
- 展示页面上下文。
- 帮助理解 Context 的边界。

---

# 三、核心思考与完善

## 1. Trace 和 Logger 的区别是什么？

### 原始理解

Log 是日志，可以记录操作记录和用户行为。

Trace 是通过 ID 把一条完整链路记录下来。

### 完善后的理解

Logger 和 Trace 都属于可观测性能力，但解决的问题不同。

| 对比项 | Logger | Trace |
|---|---|---|
| 关注点 | 单个事件 | 一次完整请求链路 |
| 解决问题 | 发生了什么 | 这次请求经过了哪些环节 |
| 核心内容 | time、level、message、module | traceId、span、调用链路 |
| 使用场景 | 查看错误、操作、模型调用 | 串联 API、Service、Graph、Tool、LLM |
| 类比 | 一个个点 | 一条线 |

一句话总结：

> Logger 是点状记录，Trace 是链路追踪。Logger 告诉你发生了什么，Trace 告诉你这件事从哪里开始、经过哪里、在哪里失败。

---

## 2. 为什么企业项目必须统一异常？

### 原始理解

1. 便于排查问题。
2. 遇到问题时有托底措施。
3. 不会因为突发异常导致页面崩掉。

### 完善后的理解

企业项目必须统一异常，主要原因有 5 个：

### 2.1 保证接口返回稳定

如果不做统一异常，不同接口可能返回不同格式：

```json
{"error": "xxx"}
```

```json
{"msg": "失败"}
```

```json
{"detail": "参数错误"}
```

前端就需要为每个接口单独写判断逻辑，维护成本很高。

统一异常后，所有错误都返回：

```json
{
  "code": 500001,
  "message": "系统内部错误",
  "traceId": "xxx",
  "success": false,
  "data": null
}
```

### 2.2 避免系统异常直接暴露给用户

后端堆栈不能直接返回给前端，否则会有安全风险。

统一异常后：

- 前端看到的是友好的错误提示。
- 后端日志记录完整堆栈。
- 排查问题通过 `traceId` 定位。

### 2.3 降低业务代码复杂度

如果没有统一异常，每个接口都可能写大量 `try-except`。

统一异常后，业务代码只需要抛出业务异常：

```python
raise AppException(ErrorCode.PARAM_ERROR)
```

异常处理交给全局异常处理器。

### 2.4 提升前后端协作效率

前端只需要按照统一错误码和统一响应格式处理错误，不需要理解后端每个接口的异常细节。

### 2.5 提升线上问题排查效率

异常日志中统一带上 `traceId`、错误码、错误信息，可以快速定位问题。

一句话总结：

> 统一异常不是为了让代码更好看，而是为了让系统在出错时仍然可控、可查、可恢复。

---

## 3. 为什么不能把 UserContext 直接放进数据库？

### 原始理解

1. 用户上下文信息过多时，数据存储量过大。
2. 需要区分 State、记忆。

### 完善后的理解

UserContext 是运行时上下文，不是持久化数据模型。

它通常包含：

```text
userId
username
orgId
roles
permissions
requestTime
traceId
```

这些信息用于当前请求处理，不代表都需要直接入库。

### 3.1 UserContext 生命周期很短

UserContext 通常只在一次请求或一次会话中有效。

例如用户角色、权限、组织信息可能来自：

- 登录态
- Token
- 权限系统
- 用户中心
- 当前页面上下文

它是运行时组合出来的，不一定是一个需要整体存储的数据库对象。

### 3.2 UserContext 中可能包含临时信息

例如：

- traceId
- 当前请求时间
- 当前页面
- 当前筛选条件
- 当前用户选择的对象

这些信息没有必要直接进入用户表。

### 3.3 UserContext 和用户数据不是一回事

用户数据是可持久化的，例如：

```text
用户ID
用户名
手机号
组织ID
角色ID
```

UserContext 是运行时使用的上下文，例如：

```text
当前请求用户是谁
当前用户有哪些权限
当前用户正在访问哪个页面
当前请求 traceId 是什么
```

### 3.4 需要区分 Context、State、Memory

| 类型 | 含义 | 是否持久化 |
|---|---|---|
| Context | 当前请求的执行环境 | 通常不整体持久化 |
| State | 当前 Graph 执行过程中的状态 | 可按需 checkpoint |
| Memory | 长期记忆或历史经验 | 可以持久化 |
| Database Entity | 数据库业务实体 | 持久化 |

一句话总结：

> UserContext 是运行时视角，不是数据库建模对象。可以持久化其中必要字段，但不应该把整个 UserContext 直接存进数据库。

---

## 4. 为什么 GraphState 不应该保存 ORM 对象？

### 原始理解

1. GraphState 是当前 Graph 流程的数据。
2. ORM 是记忆？需要完善。

### 完善后的理解

ORM 不是记忆。

ORM 是 Object Relational Mapping，也就是数据库表和 Python/Java 对象之间的映射对象。

例如：

```python
user = UserModel(id=1, name="Tom")
```

这个 `UserModel` 就是 ORM 对象。

GraphState 不应该保存 ORM 对象，原因如下：

### 4.1 GraphState 应该是可序列化的数据

GraphState 后续可能用于：

- 节点之间传递
- checkpoint 保存
- 中断恢复
- 调试回放
- 日志记录
- 分布式执行

因此 GraphState 中最好保存简单、可序列化的数据，例如：

```json
{
  "userId": "u001",
  "intent": "analyze_energy",
  "selectedStationId": "s001",
  "toolResult": {}
}
```

而不是保存 ORM 对象。

### 4.2 ORM 对象依赖数据库 Session

ORM 对象通常依赖数据库连接和 Session。

如果把 ORM 对象放进 GraphState，会带来问题：

- Session 关闭后对象可能失效。
- 跨线程、跨进程传递可能失败。
- checkpoint 时无法序列化。
- 数据状态可能过期。
- Graph 执行和数据库实现强耦合。

### 4.3 GraphState 应该保存业务快照，而不是数据库连接对象

正确做法：

```json
{
  "userId": "u001",
  "orgId": "org001",
  "stationId": "station001"
}
```

需要数据库数据时，在 Tool 或 Service 中重新查询。

错误做法：

```python
{
  "user": user_orm_object,
  "station": station_orm_object,
  "db_session": session
}
```

### 4.4 这样可以降低 Agent 与数据库的耦合

GraphState 应该关注 Agent 执行过程，而不是数据库访问细节。

一句话总结：

> GraphState 保存的是 Agent 执行状态，不应该保存 ORM 对象。ORM 是数据库映射对象，不是记忆，也不是 Graph 状态。

---

## 5. 统一 Response 如何提升前后端协作效率？

### 原始理解

1. 统一规范后减少不必要沟通。
2. 前后端按规范统一开发即可。

### 完善后的理解

统一 Response 可以从 5 个方面提升协作效率。

### 5.1 前端请求封装更简单

所有接口返回结构一致：

```json
{
  "code": 0,
  "message": "success",
  "traceId": "xxx",
  "success": true,
  "data": {}
}
```

前端可以统一写在 `request.ts` 中，不需要每个页面重复判断。

### 5.2 错误处理更统一

前端可以根据统一规则处理错误：

```text
success = true  → 返回 data
success = false → 展示 message，保留 traceId
```

### 5.3 接口文档更清晰

所有接口只需要关注 `data` 里面的业务字段，外层结构保持一致。

### 5.4 联调成本更低

前端不用反复问后端：

- 这个接口成功字段叫什么？
- 失败字段叫什么？
- 错误信息在哪里？
- 错误码在哪里？
- traceId 在哪里？

### 5.5 后续 SDK 封装更容易

如果后续做前端 SDK、Python SDK、Java SDK，统一 Response 是基础。

一句话总结：

> 统一 Response 的本质是统一前后端契约，让双方只关注业务 data，而不是反复处理接口格式差异。

---

## 6. 如果线上 AI 调用失败，如何通过 Trace 定位？

### 原始理解

TraceId 是唯一的，通过 ID 可以将一整条链路串联起来，用于排查问题。

### 完善后的排查流程

假设用户反馈：

```text
刚才分析能耗异常失败了，页面提示大模型调用超时。
traceId = abc-123
```

排查步骤如下：

### 6.1 通过 traceId 查询 API 日志

先确认请求是否进入后端：

```text
traceId=abc-123
path=/api/v1/ai/analyze
status=504
duration=30000ms
```

判断：

- 请求是否到达后端。
- HTTP 状态码是什么。
- 总耗时是多少。

### 6.2 查询业务日志

查看 Service 或 Graph 是否正常执行：

```text
traceId=abc-123
step=intent_recognition
status=success
```

```text
traceId=abc-123
step=tool_call
status=success
```

判断：

- 意图识别是否成功。
- Tool 是否调用成功。
- 是否在进入 LLM 前已经失败。

### 6.3 查询 LLM 调用日志

查看模型调用是否失败：

```text
traceId=abc-123
provider=qwen
model=qwen-plus
inputTokens=5000
outputTokens=0
durationMs=30000
status=timeout
```

判断：

- 哪个模型失败。
- 是否超时。
- 输入 token 是否过大。
- 是否 provider 异常。
- 是否触发限流。

### 6.4 查询异常日志

查看具体异常原因：

```text
traceId=abc-123
errorCode=504101
message=大模型调用超时
```

### 6.5 最终定位

可能结论：

```text
本次请求成功进入 API，Graph 前置步骤正常，Tool 调用正常。
失败点发生在 LLM Provider 调用阶段。
模型 qwen-plus 响应超时，耗时 30 秒，触发系统超时异常。
```

### 6.6 后续处理方式

根据定位结果可以采取：

- 降低输入 token。
- 增加模型超时时间。
- 切换备用模型。
- 增加重试机制。
- 增加模型调用降级策略。
- 检查供应商服务状态。

一句话总结：

> TraceId 是线上问题的入口，通过它可以把 API、Service、Graph、Tool、LLM、Exception 多类日志串起来，定位失败发生在哪一层。

---

# 四、本次 Sprint1 的关键认知升级

## 1. DTO 不是简单封装，而是接口契约

DTO 的价值不是少写几个字段，而是让前后端形成稳定契约。

## 2. TraceId 是企业级系统的问题定位入口

没有 TraceId，线上问题只能靠猜。

有了 TraceId，就可以按链路排查。

## 3. Logger 和 Trace 要一起设计

只做 Logger，日志是散的。

只做 Trace，没有日志内容。

两者结合，才能真正排查问题。

## 4. 统一异常是系统稳定性的底线

异常不可避免，但必须可控。

统一异常就是让系统在出错时也保持稳定。

## 5. Context 是运行时环境，GraphState 是执行过程

Context 回答：

```text
谁在请求？
从哪里请求？
当前页面是什么？
有什么权限？
```

GraphState 回答：

```text
Agent 执行到哪一步？
识别了什么意图？
调用了什么工具？
模型输出了什么？
```

## 6. ORM 不是记忆

ORM 是数据库映射对象。

Memory 是长期记忆。

State 是执行状态。

Context 是运行时上下文。

这几个概念必须分清。

---

# 五、Sprint1 遗留问题与后续优化

## 1. 日志中心还可以继续增强

Sprint1 只完成基础日志展示，后续可以增强：

- 日志筛选
- TraceId 查询
- 日志等级过滤
- 时间范围查询
- LLM 调用统计
- Token 使用趋势
- 用户操作审计

## 2. Trace 目前还可以继续增强

后续可以增加：

- spanId
- parentSpanId
- Graph 节点级 Trace
- Tool 调用级 Trace
- LLM 调用级 Trace
- Trace 可视化链路

## 3. 模型配置还可以继续增强

后续可以增加：

- 默认模型切换
- 模型启停
- 模型降级策略
- 模型调用限流
- Token 预算控制
- 多模型路由策略

## 4. Context 还可以继续增强

后续可以结合真实业务补充：

- 当前组织
- 当前站点
- 当前页面筛选条件
- 当前用户权限
- 当前业务对象
- 当前 Agent 任务上下文

## 5. ErrorCode 需要持续维护

随着业务增长，需要继续补充：

- 业务模块错误码
- Tool 错误码
- Agent 错误码
- LLM 错误码
- 权限错误码
- 数据错误码

---

# 六、Sprint1 总结一句话

Sprint1 完成了企业级 AI Agent 项目的基础设施底座建设。

本期最重要的成果不是页面功能，而是建立了一套统一的工程规范：

```text
统一配置
统一响应
统一错误码
统一异常
统一日志
统一 Trace
统一 Context
```

这些能力会成为后续 Sprint2、Sprint3 开发 AI Runtime、Tool Center、Agent Graph、智能分析能力的基础。
