# 1. Sprint2 的核心：
**AI Runtime 不是普通 CRUD，而是 Agent 系统的运行时底座**。

当前内容中已经正确理解了以下关键点：

| 模块 | 当前理解 | 审核结论 |
|---|---|---|
| Conversation | 用户和 AI 的一段对话容器 | 正确 |
| Session | 一次 AI 任务执行上下文 | 正确 |
| Prompt | AI 系统配置资产，需要版本化 | 正确，但需要补充“执行时如何记录版本” |
| Trace | AI 执行链路记录 | 正确，但需要补充“trace_id 与 step/span 的关系” |
| Feedback | 用户反馈，用于优化闭环 | 正确 |
| Runtime DB | 存储 AI 运行时数据 | 正确，但要明确不存 IOC 业务主数据 |
| ai_logs | 是否需要单独日志表 | 当前 Sprint2 暂不建议新增 |

本次需要重点补强 3 个地方：

1. **Prompt 表怎么设计，以及某次执行如何记录用了哪个 Prompt 版本。**
2. **Trace 的记录粒度：不是只记录最终结果，而是记录 Graph / Node / Tool / LLM 的执行步骤。**
3. **ai_logs 暂时不单独建表，避免和 Trace 重复。系统日志先交给应用日志体系，AI 执行过程由 Trace 负责。**

---


# 2. 核心概念补充

## 2-1 Conversation 是什么？

Conversation 是用户和 AI 的一段对话容器。

它不是一次具体任务，而是一个较大的对话范围。例如用户进入智能运营中心 AI 助手，围绕“今日运营异常”连续问了多个问题，这一整段可以属于一个 Conversation。

### 关注点

Conversation 主要关注：

1. 谁发起的？
2. 属于哪个业务场景？
3. 什么时候开始？
4. 当前是什么状态？
5. 这个对话下面有哪些 Session？

### 生命周期

```text
created → active → closed / archived
```

### 简单理解

```text
Conversation = 一段对话容器
```
---

## 2-2 Session 是什么？

Session 是一次 AI 任务执行的上下文。

同一个 Conversation 中可以有多个 Session。用户每发起一次明确的 AI 任务，就可以创建一个 Session。

例如：

```text
Conversation：用户正在和 AI 助手讨论今日运营问题
  ├── Session 1：分析今日高风险告警
  ├── Session 2：总结异常区域分布
  └── Session 3：生成运营日报建议
```

### Session 保存什么

Session 主要保存本次任务的：

1. 用户输入是什么？
2. 用了哪些上下文？
3. 执行结果是什么？
4. 当前是否完成？
5. 是否失败？
6. 失败原因是什么？

### 生命周期

```text
created → running → success / failed / cancelled / expired
```

### 简单理解

```text
Session = 一次 AI 任务执行上下文
```
---

## 2-3 Conversation 和 Session 的区别

| 对比项 | Conversation | Session |
|---|---|---|
| 粒度 | 一段对话 | 一次 AI 任务 |
| 生命周期 | 更长 | 更短 |
| 关注点 | 用户、场景、对话状态 | 输入、上下文、输出、执行状态 |
| 数量关系 | 一个 Conversation 可以包含多个 Session | 一个 Session 只属于一个 Conversation |
| 类比 | 一个聊天窗口 | 聊天窗口里的一次任务请求 |

一句话总结：

```text
Conversation 是一段对话；Session 是这段对话中的一次 AI 任务。
```
---

## 2-4 Prompt 为什么要单独建表？

Prompt 不是普通字符串，而是 AI 系统的配置资产。

在企业级 AI 系统里，Prompt 需要独立管理，因为它会直接影响模型输出质量、稳定性和可追溯性。

### 实际会遇到的问题

1. Prompt 改坏了，需要回滚。
2. 不同业务场景需要不同 Prompt。
3. 同一个 Prompt 需要多个版本。
4. 线上结果异常时，需要知道当时用了哪个 Prompt 版本。
5. 后续需要评测不同 Prompt 版本的效果。

### Prompt 表不是只为了“存 Prompt”

真正目的不是把 Prompt 字符串存起来，而是要解决：

```text
某一次 AI 执行，到底用了哪个 Prompt、哪个版本、什么状态、什么内容。
```

---

## 2-5 Prompt 版本应该怎么记录？

Prompt 版本记录分两层：

### 第一层：Prompt 配置表

`ai_prompt` 保存 Prompt 的不同版本。

例如：

| code | version | status | content |
|---|---:|---|---|
| ioc_alarm_analysis | 1 | inactive | 第一版告警分析 Prompt |
| ioc_alarm_analysis | 2 | active | 第二版告警分析 Prompt |
| ioc_daily_report | 1 | active | 运营日报生成 Prompt |

### 第二层：执行时留痕

每次 AI 执行时，需要在 `ai_trace` 中记录：

```text
prompt_id
prompt_code
prompt_version
```

为了增强可追溯性，也可以记录：

```text
prompt_snapshot
```

也就是当时实际发送给模型的 Prompt 内容快照。

### 推荐规则

1. `ai_prompt` 中的 `code + version` 必须唯一。
2. Prompt 发布后，原则上不修改历史版本内容。
3. 如果 Prompt 内容要变更，新增 version。
4. 执行时在 Trace 中记录 prompt_id、prompt_code、prompt_version。
5. 对关键链路，可以额外保存 prompt_snapshot。

---

## 2-6 Trace 是什么？

Trace 是 AI 执行链路记录。

它要记录一次 AI 请求从进入 Runtime 到完成输出的关键过程。

### Trace 主要记录什么

1. 这次请求进了哪个 Graph？
2. 执行了哪个 Node？
3. 调用了哪个 Tool？
4. 使用了哪个模型？
5. 使用了哪个 Prompt 版本？
6. 输入是什么？
7. 输出是什么？
8. 耗时多少？
9. 使用了多少 Token？
10. 成功还是失败？
11. 如果失败，错误是什么？

### 为什么需要 Trace

没有 Trace，线上 AI 出错时只能粗略判断：

```text
大模型回答错了。
```

有了 Trace，可以进一步定位：

1. 是 Prompt 写错了？
2. 是 Tool 返回错了？
3. 是 Graph 路由错了？
4. 是模型幻觉？
5. 是上下文丢失？
6. 是数据源接口返回异常？
7. 是 Token 超限导致截断？

---

## 2-7 Trace 的推荐粒度

Trace 不建议只记录一条最终结果，而是建议记录为“一次请求多条执行步骤”。

### 推荐模型

```text
trace_id：一次完整 AI 请求的链路 ID
span_id：链路中的某一个执行步骤 ID
parent_span_id：父步骤 ID
```

示例：

```text
trace_id = T001
  ├── span_1：graph_start
  ├── span_2：node_analyze_alarm
  ├── span_3：tool_query_alarm_data
  ├── span_4：llm_summarize_result
  └── span_5：graph_end
```

这样后续排查问题会更清晰。

---

## 2-8 Feedback 是什么？

Feedback 是用户对 AI 输出结果的反馈。

它的价值不是单纯记录“满意 / 不满意”，而是为后续优化 Prompt、评测 Agent、改进工具调用和优化业务流程提供依据。

### Feedback 记录内容

1. 用户是否满意？
2. 反馈类型是什么？
3. 用户具体意见是什么？
4. 反馈关联哪个 Conversation？
5. 反馈关联哪个 Session？
6. 反馈关联哪次 AI 输出？

### Feedback 的价值

```text
用户反馈 → 问题归类 → Prompt优化 / Tool优化 / Graph优化 → 新版本验证 → 质量提升
```

---

## 2-9 Runtime DB 是什么？

Runtime DB 是 AI 运行时数据库。

它用于保存 AI 系统运行过程中产生的数据，包括：

1. 会话数据。
2. 任务上下文。
3. Prompt 配置与版本。
4. 执行链路 Trace。
5. 用户反馈 Feedback。

### Runtime DB 不保存什么

Runtime DB 不保存 IOC 业务主数据。

例如：

| 数据 | 是否进入 Runtime DB | 原因 |
|---|---:|---|
| 告警 | 否 | IOC 业务系统是唯一数据源 |
| 隐患 | 否 | IOC 业务系统是唯一数据源 |
| 工单 | 否 | IOC 业务系统是唯一数据源 |
| 用户会话 | 是 | 属于 AI 运行态数据 |
| AI 任务上下文 | 是 | 属于 AI 运行态数据 |
| Prompt 版本 | 是 | 属于 AI 配置资产 |
| Trace | 是 | 属于 AI 执行链路 |
| Feedback | 是 | 属于 AI 优化闭环 |

---

  
# 3. 流程规划
1. 这一章节，主要是跑通AI runtime的流程
不是追求 Agent 多智能，也不是马上接入复杂业务，而是先让 AI 系统具备：
  1. 有会话。
  2. 有任务上下文。
  3. 有 Prompt 版本管理。
  4. 有执行链路记录。
  5. 有用户反馈闭环。
  6. 有 MySQL 持久化能力。

### 最小闭环

```text
POST /ai/chat
  ↓
创建 Conversation
  ↓
创建 Session
  ↓
读取 active Prompt
  ↓
执行 Mock Agent / Graph
  ↓
写入 Trace
  ↓
更新 Session 输出
  ↓
返回 AI 结果
  ↓
POST /runtime/feedback
```

2. 那首要任务是创建数据库去存储上述的内容
   1. ai_conversation,包含哪些字段？
   2. ai_session 
   3. ai_prompt,这个表怎么设计呢，有N个prompt，不同的prompt 又要有不同的版本
   4. ai_trace
   5. ai_feedback
   6. ai_logs 日志表格是否需要呢？因为trace有记录了呢
3. 要求
   1. 使用mysql + SQLAlchemy JSON
   2. Session上下文直接持久化到Mysql的JSON字段
   3. Runtime 表不保存IOC业务主数据
   4. Prompt必须支持code、version、status
   5. Trace 必须记录 trace_id、graph、node、tool、model、cost、token、error
   6. Feedback 必须关联 conversation_id 和 session_id
   7. 代码结构按 models / schemas / repositories / services / api 分层


# 4. 表设计
## 4-1 ai_conversation：会话表

### 表职责

管理用户和 AI 的一段对话容器。

### 字段设计

| 字段 | 类型 | 是否必填 | 说明 |
|---|---|---:|---|
| id | varchar(64) | 是 | 主键 ID |
| user_id | varchar(64) | 是 | 用户 ID |
| title | varchar(255) | 否 | 会话标题 |
| biz_type | varchar(64) | 否 | 业务场景，例如 alarm、report、risk |
| source | varchar(64) | 否 | 来源，例如 web、api、system |
| status | varchar(32) | 是 | created、active、closed、archived |
| metadata | json | 否 | 扩展信息 |
| created_at | datetime | 是 | 创建时间 |
| updated_at | datetime | 是 | 更新时间 |

### 建议索引

```sql
idx_conversation_user_id(user_id)
idx_conversation_biz_type(biz_type)
idx_conversation_status(status)
```

---

## 4-2 ai_session：任务上下文表

### 表职责

管理一次 AI 任务执行上下文。

### 字段设计

| 字段 | 类型 | 是否必填 | 说明 |
|---|---|---:|---|
| id | varchar(64) | 是 | 主键 ID |
| conversation_id | varchar(64) | 是 | 所属 Conversation |
| user_id | varchar(64) | 是 | 用户 ID |
| task_type | varchar(64) | 否 | 任务类型，例如 chat、analysis、report |
| input_text | longtext | 是 | 用户输入 |
| context | json | 否 | 本次任务上下文，使用 MySQL JSON |
| output_text | longtext | 否 | AI 输出结果 |
| status | varchar(32) | 是 | created、running、success、failed、cancelled、expired |
| error_message | text | 否 | 失败原因 |
| started_at | datetime | 否 | 开始执行时间 |
| finished_at | datetime | 否 | 结束执行时间 |
| expire_at | datetime | 否 | 上下文过期时间，暂不依赖 Redis |
| created_at | datetime | 是 | 创建时间 |
| updated_at | datetime | 是 | 更新时间 |

### 建议索引

```sql
idx_session_conversation_id(conversation_id)
idx_session_user_id(user_id)
idx_session_status(status)
idx_session_created_at(created_at)
```

### 说明

当前不使用 Redis，所以 Session 上下文直接持久化到 MySQL 的 `context` JSON 字段。

`expire_at` 字段建议保留，虽然当前不做 Redis 过期，但后续可以用于：

1. 清理历史上下文。
2. 控制 Session 生命周期。
3. 接入 Redis 后设置 TTL。

---

## 4-3 ai_prompt：Prompt 配置与版本表

### 表职责

管理 Prompt 模板、版本、状态和发布记录。

### 字段设计

| 字段 | 类型 | 是否必填 | 说明 |
|---|---|---:|---|
| id | varchar(64) | 是 | 主键 ID |
| code | varchar(128) | 是 | Prompt 编码，例如 ioc_alarm_analysis |
| name | varchar(255) | 是 | Prompt 名称 |
| version | int | 是 | 版本号，从 1 递增 |
| content | longtext | 是 | Prompt 模板内容 |
| variables | json | 否 | 模板变量定义，例如 {"date":"日期","city":"城市"} |
| scene_code | varchar(64) | 否 | 业务场景编码 |
| status | varchar(32) | 是 | draft、active、inactive、archived |
| description | varchar(500) | 否 | 描述 |
| created_by | varchar(64) | 否 | 创建人 |
| published_at | datetime | 否 | 发布时间 |
| created_at | datetime | 是 | 创建时间 |
| updated_at | datetime | 是 | 更新时间 |

### 建议唯一约束

```sql
uk_prompt_code_version(code, version)
```

### 建议索引

```sql
idx_prompt_code(code)
idx_prompt_status(status)
idx_prompt_scene_code(scene_code)
```

### Prompt 获取规则

根据 `code` 获取当前可用 Prompt：

```text
where code = :code and status = 'active'
order by version desc
limit 1
```

### Prompt 版本规则

1. 同一个 `code` 可以有多个 `version`。
2. `code + version` 唯一。
3. 线上执行只使用 `status = active` 的版本。
4. Prompt 内容变更时新增版本，不直接修改已发布版本。
5. 执行时在 Trace 中记录 prompt_id、prompt_code、prompt_version。

---

## 4-4 ai_trace：执行链路表

### 表职责

记录 AI 请求在 Runtime、Graph、Node、Tool、LLM 中的执行链路。

### 字段设计

| 字段 | 类型 | 是否必填 | 说明 |
|---|---|---:|---|
| id | varchar(64) | 是 | 主键 ID |
| trace_id | varchar(64) | 是 | 一次完整 AI 请求的链路 ID |
| span_id | varchar(64) | 否 | 当前执行步骤 ID |
| parent_span_id | varchar(64) | 否 | 父步骤 ID |
| conversation_id | varchar(64) | 否 | 关联 Conversation |
| session_id | varchar(64) | 是 | 关联 Session |
| span_type | varchar(32) | 是 | graph、node、tool、llm、runtime |
| graph_name | varchar(128) | 否 | Graph 名称 |
| node_name | varchar(128) | 否 | Node 名称 |
| tool_name | varchar(128) | 否 | Tool 名称 |
| model_name | varchar(128) | 否 | 模型名称 |
| prompt_id | varchar(64) | 否 | 使用的 Prompt ID |
| prompt_code | varchar(128) | 否 | 使用的 Prompt code |
| prompt_version | int | 否 | 使用的 Prompt version |
| input_data | json | 否 | 输入数据 |
| output_data | json | 否 | 输出数据 |
| cost_ms | int | 否 | 耗时，毫秒 |
| prompt_tokens | int | 否 | Prompt token 数 |
| completion_tokens | int | 否 | 输出 token 数 |
| total_tokens | int | 否 | 总 token 数 |
| status | varchar(32) | 是 | success、failed、running |
| error_code | varchar(128) | 否 | 错误编码 |
| error_message | text | 否 | 错误信息 |
| created_at | datetime | 是 | 创建时间 |

### 可选字段

如果对审计要求高，可以增加：

| 字段 | 类型 | 说明 |
|---|---|---|
| prompt_snapshot | longtext | 当次实际使用的 Prompt 内容快照 |
| request_id | varchar(64) | 外部请求 ID |
| metadata | json | 扩展信息 |

### 建议索引

```sql
idx_trace_trace_id(trace_id)
idx_trace_session_id(session_id)
idx_trace_conversation_id(conversation_id)
idx_trace_span_type(span_type)
idx_trace_status(status)
idx_trace_created_at(created_at)
```

### Trace 记录示例

```text
trace_id = T001
  ├── span_type=runtime, event=session_created
  ├── span_type=graph, graph_name=ioc_analysis_graph
  ├── span_type=node, node_name=alarm_analyze_node
  ├── span_type=tool, tool_name=query_alarm_tool
  ├── span_type=llm, model_name=deepseek-chat, prompt_code=ioc_alarm_analysis, prompt_version=2
  └── span_type=runtime, event=session_finished
```

---

## 4-5 ai_feedback：用户反馈表

### 表职责

记录用户对 AI 输出结果的反馈，用于后续优化闭环。

### 字段设计

| 字段 | 类型 | 是否必填 | 说明 |
|---|---|---:|---|
| id | varchar(64) | 是 | 主键 ID |
| conversation_id | varchar(64) | 是 | 关联 Conversation |
| session_id | varchar(64) | 是 | 关联 Session |
| user_id | varchar(64) | 是 | 用户 ID |
| rating | int | 否 | 评分，例如 1-5 |
| feedback_type | varchar(64) | 否 | inaccurate、incomplete、useful、unsafe、other |
| content | text | 否 | 用户反馈内容 |
| created_at | datetime | 是 | 创建时间 |

### 建议索引

```sql
idx_feedback_conversation_id(conversation_id)
idx_feedback_session_id(session_id)
idx_feedback_user_id(user_id)
idx_feedback_type(feedback_type)
```

---

# 5.代码结构规划

当前要求代码结构按以下分层：

```text
backend/
  app/
    runtime/
      models/
        conversation_model.py
        session_model.py
        prompt_model.py
        trace_model.py
        feedback_model.py
      schemas/
        conversation_schema.py
        session_schema.py
        prompt_schema.py
        trace_schema.py
        feedback_schema.py
      repositories/
        conversation_repository.py
        session_repository.py
        prompt_repository.py
        trace_repository.py
        feedback_repository.py
      services/
        conversation_service.py
        session_service.py
        prompt_service.py
        trace_service.py
        feedback_service.py
      api/
        conversation_api.py
        session_api.py
        prompt_api.py
        trace_api.py
        feedback_api.py
      runtime_service.py
```

### 分层职责

| 层级 | 职责 |
|---|---|
| models | SQLAlchemy ORM 表模型 |
| schemas | Pydantic 请求和响应模型 |
| repositories | 数据库访问，封装 CRUD |
| services | 业务逻辑，编排 repository |
| api | FastAPI 路由入口 |
| runtime_service.py | 串联 Conversation、Session、Prompt、Trace 的最小 AI Runtime 流程 |

---
## 6. API 规划

## 6.1 Conversation API

| 方法 | 路径 | 说明 |
|---|---|---|
| POST | /runtime/conversations | 创建会话 |
| GET | /runtime/conversations/{conversation_id} | 查询会话详情 |
| PATCH | /runtime/conversations/{conversation_id}/status | 更新会话状态 |

---

## 6.2 Session API

| 方法 | 路径 | 说明 |
|---|---|---|
| POST | /runtime/sessions | 创建任务 Session |
| GET | /runtime/sessions/{session_id} | 查询 Session 详情 |
| PATCH | /runtime/sessions/{session_id}/status | 更新 Session 状态 |
| PATCH | /runtime/sessions/{session_id}/output | 更新 Session 输出 |

---

## 6.3 Prompt API

| 方法 | 路径 | 说明 |
|---|---|---|
| POST | /runtime/prompts | 创建 Prompt 版本 |
| GET | /runtime/prompts/{code}/active | 获取当前 active Prompt |
| GET | /runtime/prompts/{code}/versions | 查询 Prompt 历史版本 |
| PATCH | /runtime/prompts/{prompt_id}/status | 更新 Prompt 状态 |

---

## 6.4 Trace API

| 方法 | 路径 | 说明 |
|---|---|---|
| POST | /runtime/traces | 写入 Trace 记录 |
| GET | /runtime/traces/{trace_id} | 查询一次请求完整链路 |
| GET | /runtime/sessions/{session_id}/traces | 查询某个 Session 的执行链路 |

---

## 6.5 Feedback API

| 方法 | 路径 | 说明 |
|---|---|---|
| POST | /runtime/feedback | 提交用户反馈 |
| GET | /runtime/sessions/{session_id}/feedback | 查询某次任务反馈 |

---

## 6.6 最小 AI Chat API

建议新增一个最小入口，用于串联 Runtime 流程：

| 方法 | 路径 | 说明 |
|---|---|---|
| POST | /ai/chat | 发起一次 AI 请求，跑通 Runtime 最小闭环 |

内部流程：

```text
1. 如果没有 conversation_id，则创建 Conversation
2. 创建 Session
3. 根据 prompt_code 获取 active Prompt
4. 执行 Mock Agent / Graph
5. 写入 Trace
6. 更新 Session 输出
7. 返回 AI 结果
```
---

# 7. 状态枚举建议

### ConversationStatus

```text
created
active
closed
archived
```

### SessionStatus

```text
created
running
success
failed
cancelled
expired
```

### PromptStatus

```text
draft
active
inactive
archived
```

### TraceStatus

```text
running
success
failed
```

### TraceSpanType

```text
runtime
graph
node
tool
llm
```

### FeedbackType

```text
useful
inaccurate
incomplete
unsafe
other
```

---

# 8. Sprint2 评审重点

评审时重点看以下内容：

1. Runtime 表是否没有保存 IOC 业务主数据。
2. Conversation 和 Session 边界是否清晰。
3. Prompt 是否支持 code、version、status。
4. Prompt 执行时是否能记录使用版本。
5. Trace 是否包含 trace_id、graph、node、tool、model、cost、token、error。
6. Feedback 是否关联 conversation_id 和 session_id。
7. 是否没有使用 PostgreSQL 专属能力。
8. 是否没有使用 JSONB。
9. 是否没有引入 Redis 依赖。
10. 是否按照 models / schemas / repositories / services / api 分层。

---

# 9. 测试用例规划

### 9-1 Conversation 测试

| 用例 | 预期 |
|---|---|
| 创建 Conversation | 返回 conversation_id |
| 查询 Conversation | 能查到用户、状态、业务场景 |
| 更新状态为 closed | 状态更新成功 |

---

### 9-2 Session 测试

| 用例 | 预期 |
|---|---|
| 创建 Session | 返回 session_id |
| 保存 context JSON | MySQL JSON 字段正常保存 |
| 更新 output_text | 输出结果更新成功 |
| 更新 status=success | 状态更新成功 |

---

### 9-3 Prompt 测试

| 用例 | 预期 |
|---|---|
| 创建 prompt v1 | 成功 |
| 创建 prompt v2 | 成功 |
| 查询 active prompt | 返回当前 active 版本 |
| code + version 重复 | 创建失败 |

---

### 9-4 Trace 测试

| 用例 | 预期 |
|---|---|
| 写入 graph trace | 成功 |
| 写入 node trace | 成功 |
| 写入 tool trace | 成功 |
| 写入 llm trace | 成功 |
| 查询 trace_id 全链路 | 返回多条 span 记录 |

---

### 9-5 Feedback 测试

| 用例 | 预期 |
|---|---|
| 提交满意反馈 | 成功 |
| 提交不准确反馈 | 成功 |
| 根据 session 查询反馈 | 能查到对应反馈 |

---

### 9-6 Runtime 最小闭环测试

| 步骤 | 预期 |
|---|---|
| 调用 POST /ai/chat | 返回 AI 结果 |
| 自动创建 Conversation | 成功 |
| 自动创建 Session | 成功 |
| 能读取 active Prompt | 成功 |
| 能写入 Trace | 成功 |
| 能更新 Session 输出 | 成功 |
| 能提交 Feedback | 成功 |

---
##  一句话总结

Sprint2 的本质不是写几个 CRUD 接口，而是搭建企业级 Agent 系统的运行时底座。

当前最重要的不是追求复杂能力，而是先跑通：

```text
Conversation → Session → Prompt → Graph / Agent → Trace → Feedback → MySQL Runtime DB
```

跑通这个闭环后，后续 Sprint 才能继续扩展真实 Agent、业务工具调用、评测优化、流式输出、缓存、限流和长期 Memory。

### 总结和反思
1. Prompt为什么需要版本管理？
   1. 每次的prompt 都需要记录？那怎么区分是同一个prompt的不同版本呢 ？依据含义？
2. Session 和 Memory 是一回事还有Conversation？
   1. session 是一次AI任务会话
   2. Memory存储的记忆，不是一回事
3. Trace 在AI Agent中记录哪些问题？有什么价值
   1. 价值：便于查找和定位问题
   2. 用户的prompt是什么？
   3. 任务失败与否？
   4. ... 待补充
4. 用户反馈如何用于优化Agent？
5. Runtime 与 IOC 业务系统的边界
6. Feedback 如何形成AI优化闭环
