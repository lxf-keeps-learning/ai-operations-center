# Sprint2 总结与反思：AI Runtime 最小闭环

## 1. Sprint2 阶段定位

Sprint2 的核心目标不是单纯完成几张表或几个 CRUD 接口，而是建设一个 **AI Runtime 最小运行闭环**。
AI Runtime 的职责是统一管理会话、上下文、Prompt、Trace、反馈等运行时能力，为后续 Agent 系统提供基础支撑。Sprint2 原始目标中也明确包含 Conversation、Session、Prompt、Runtime Trace、Feedback、Runtime DB 等能力。

当前 Sprint2 已经完成的关键进展是：

```text
用户输入
→ 创建 Conversation
→ 创建 Session
→ 读取 Prompt
→ 调用 LLM
→ 生成回答
→ 写入 Trace
→ 保存 Session 输出
→ 支持 Feedback 扩展
```

这说明项目已经从“后端基础工程”进入了“AI 应用运行时”阶段。

---

## 2. Prompt 为什么需要版本管理？

### 2.1 Prompt 不是普通字符串

Prompt 在 AI 系统中不是一段临时文本，而是影响模型输出质量的核心配置资产。

它决定了：

```text
模型扮演什么角色
模型按照什么规则回答
模型如何理解业务场景
模型输出什么格式
模型如何处理异常情况
```

所以 Prompt 一旦变化，AI 的输出行为就可能发生变化。

---

### 2.2 是否每次执行都要创建一个 Prompt 版本？

**不是。**

需要区分两个概念：

```text
Prompt 版本创建：只有 Prompt 内容或参数发生正式变更时才创建新版本
Prompt 执行记录：每次 AI 调用都要记录当时使用了哪个 Prompt 版本
```

也就是说：

```text
不是每次调用都新增一条 Prompt 版本
而是每次调用都要在 Trace 或 Session 中记录使用的 prompt_code、prompt_version、prompt_id
```

例如：

```text
用户今天问了 100 次问题
如果都使用 ioc_operation_assistant v1.0.0
那么 ai_prompt 表中不需要新增 100 条 Prompt
但 ai_trace 中应该记录每次请求使用的是 ioc_operation_assistant v1.0.0
```

---

### 2.3 如何区分同一个 Prompt 的不同版本？

不能只靠“含义”判断，必须靠结构化字段。

建议使用：

```text
code：表示同一个 Prompt 的业务身份
version：表示该 Prompt 的版本
status：表示版本状态
```

例如：

| code                    | version | status   | 含义     |
| ----------------------- | ------- | -------- | ------ |
| ioc_operation_assistant | v1.0.0  | inactive | 初始版本   |
| ioc_operation_assistant | v1.1.0  | active   | 当前线上版本 |
| ioc_operation_assistant | v1.2.0  | draft    | 待测试版本  |

其中：

```text
code 相同，说明是同一个 Prompt 模板
version 不同，说明是不同版本
status=active，说明当前线上使用版本
```

所以同一个 Prompt 的不同版本不是靠自然语言含义判断，而是靠：

```text
code + version
```

建议数据库增加唯一约束：

```text
unique(code, version)
```

---

### 2.4 为什么必须记录 Prompt 版本？

因为线上问题排查时，经常需要回答：

```text
这次 AI 回答为什么变差了？
当时使用的是哪个 Prompt？
是不是刚刚改过 Prompt？
能不能回滚到上一个版本？
A/B 测试中哪个 Prompt 效果更好？
```

如果没有 Prompt 版本，出现问题时只能猜测；有了版本，就可以定位、回滚和评估。

---

## 3. Conversation、Session、Memory 的区别

### 3.1 Conversation 是什么？

Conversation 是用户与 AI 的一段对话容器。

它关注的是：

```text
谁发起的？
属于哪个业务场景？
什么时候开始？
当前是什么状态？
这段对话下有哪些任务？
```

例如：

```text
用户打开智能运营助手，开始咨询今天的运营异常。
这就是一个 Conversation。
```

Conversation 更偏向“用户交互层”的概念。

---

### 3.2 Session 是什么？

Session 是一次 AI 任务执行上下文。

在同一个 Conversation 中，用户可能连续问多个问题，每一个问题都可能触发一次 AI 任务。

例如：

```text
Conversation：用户今天与智能运营助手的一整段对话

Session 1：分析今日高风险告警
Session 2：解释某个异常设备原因
Session 3：生成一份运营日报
```

Session 关注的是：

```text
本次任务输入是什么？
用了哪些上下文？
调用了哪个 Prompt？
调用了哪个模型？
执行结果是什么？
是否成功？
失败原因是什么？
```

所以可以简单记：

```text
Conversation = 一段对话
Session = 一次 AI 任务
```

---

### 3.3 Memory 是什么？

Memory 是 AI 系统的记忆能力，不等同于 Session。

Memory 通常用于保存：

```text
用户长期偏好
历史交互经验
业务规则沉淀
跨会话可复用的信息
```

例如：

```text
用户偏好日报输出成表格
某个企业固定关注高风险隐患
某些业务术语的解释方式
```

它可以跨 Conversation、跨 Session 使用。

所以三者关系是：

```text
Conversation：当前一段对话
Session：当前一次任务
Memory：可跨任务、跨会话复用的记忆
```

Sprint2 当前重点是 Conversation 和 Session，Memory 可以后续再做，避免过早复杂化。

---

## 4. Trace 在 AI Agent 中记录什么？有什么价值？

### 4.1 Trace 的本质

Trace 是 AI 执行链路记录。

它不是普通日志，而是记录一次 AI 请求从输入到输出的关键路径。

如果没有 Trace，线上问题只能笼统归因：

```text
大模型回答错了
```

但有了 Trace，可以继续判断：

```text
是 Prompt 写错了？
是 Prompt 版本不对？
是上下文丢失了？
是 Tool 返回错了？
是 Graph 路由错了？
是模型本身幻觉？
是接口调用失败？
是模型超时？
```

---

### 4.2 Trace 应该记录哪些内容？

建议 Sprint2 阶段至少记录以下内容：

| 类型        | 字段                                                   |
| --------- | ---------------------------------------------------- |
| 请求标识      | trace_id、conversation_id、session_id                  |
| Prompt 信息 | prompt_id、prompt_code、prompt_version                 |
| 模型信息      | provider、model_name                                  |
| 执行链路      | graph_name、node_name、tool_name                       |
| 输入输出      | input_data、output_data                               |
| 成本性能      | cost_ms、prompt_tokens、completion_tokens、total_tokens |
| 状态信息      | status、error_message                                 |
| 时间信息      | created_at                                           |

如果当前 Sprint2 还没有复杂 Graph 和 Tool，也可以先这样处理：

```text
graph_name = runtime_chat_graph
node_name = llm_chat_node
tool_name = null
```

这样后续接入 LangGraph 或 Tool 时，字段不用大改。

---

### 4.3 Trace 的价值

Trace 至少有 5 个价值：

```text
1. 问题定位：定位 Prompt、上下文、模型、Tool、Graph 哪一层出了问题
2. 链路审计：知道一次 AI 请求具体发生了什么
3. 成本分析：统计 token、耗时、模型调用成本
4. 效果评估：结合 Feedback 判断哪些 Prompt 或模型效果更好
5. 系统演进：为后续 Agent 调优、Prompt 优化、模型切换提供数据依据
```

Sprint2 原始 Code Review 中也要求 Trace 包含 traceId、graph、node、tool、cost 等核心信息。

---

## 5. 用户反馈如何用于优化 Agent？

Feedback 不是简单的点赞点踩，它是 AI 系统持续优化的入口。

### 5.1 Feedback 需要记录什么？

建议记录：

```text
feedback_id
conversation_id
session_id
trace_id
user_id
rating
feedback_type
content
created_at
```

其中：

```text
rating：评分，例如 1-5
feedback_type：反馈类型，例如 helpful / wrong_answer / incomplete / hallucination / bad_format
content：用户补充说明
```

---

### 5.2 Feedback 如何形成优化闭环？

推荐闭环如下：

```text
用户反馈
→ 关联 Session 和 Trace
→ 定位当时的 Prompt、模型、上下文和输出
→ 分类问题类型
→ 判断是 Prompt 问题、上下文问题、模型问题还是业务数据问题
→ 优化 Prompt / Tool / Graph / 模型配置
→ 创建新 Prompt 版本
→ 回归测试
→ 上线 active 版本
→ 继续收集 Feedback
```

例如：

```text
用户反馈：回答不完整
排查 Trace：发现 Prompt 没要求输出处理建议
优化方式：新增 Prompt v1.1.0，要求必须输出风险原因、影响范围、处理建议
上线后：继续观察 Feedback 是否改善
```

这就是：

```text
Feedback → Trace → Prompt优化 → 新版本 → 再评估
```

---

## 6. Runtime 与 IOC 业务系统的边界

### 6.1 Runtime 不保存 IOC 业务主数据

AI Runtime 的职责是管理 AI 运行过程，不是替代 IOC 业务系统。

IOC 业务系统保存：

```text
告警
隐患
工单
设备
组织
人员
业务指标
```

AI Runtime 保存：

```text
Conversation
Session
Prompt版本
Trace
Feedback
模型调用信息
```

原 Sprint2 文档中也明确了数据边界：告警、隐患、工单不落 AI 库，IOC 是唯一业务数据源；会话、Session、Prompt版本、Trace、用户反馈才落 AI 库。

---

### 6.2 Runtime 可以保存业务数据 ID，但不保存业务主数据

可以保存：

```text
alarm_id
work_order_id
risk_id
business_ref_id
```

不建议保存：

```text
完整告警详情
完整工单详情
完整设备主数据
完整业务报表数据
```

原因是：

```text
避免数据重复
避免主数据不一致
避免 AI Runtime 变成第二套业务库
保持 IOC 系统作为业务事实源
```

---

## 7. ai_logs 是否需要？

Sprint2 阶段暂不建议单独设计 ai_logs 表。

原因是：

```text
Trace 已经记录 AI 执行链路
应用日志可以由 logging / logback / ELK / 文件日志等系统处理
如果再建 ai_logs，容易和 ai_trace 职责重复
```

建议边界：

```text
ai_trace：记录 AI 请求执行链路
系统日志：记录程序运行日志、异常堆栈、接口日志
ai_logs：暂不建设，后续如有审计或运营分析需求再评估
```

也就是说：

```text
Sprint2 先做 Trace，不急着做 ai_logs
```

---

## 8. Sprint2 当前成果总结

当前 Sprint2 已经具备以下能力：

```text
1. 明确了 AI Runtime 与 IOC 业务系统的边界
2. 明确了 Conversation、Session、Prompt、Trace、Feedback 的职责
3. 使用 MySQL 存储 Runtime 运行态数据
4. 暂不使用 Redis，降低当前阶段复杂度
5. 引入 LLM，已经可以实现简单问答
6. 具备了从用户输入到模型回答的最小链路
7. 为后续 Agent、Graph、Tool、Memory、Feedback 优化预留了基础结构
```

这说明 Sprint2 已经不是简单“建表阶段”，而是完成了 AI Runtime 的第一版运行闭环。

---

## 9. Sprint2 当前仍需补强的点

### 9.1 Prompt 版本留痕

每次 LLM 调用时，Trace 中必须记录：

```text
prompt_id
prompt_code
prompt_version
```

否则未来无法定位某次回答用了哪个 Prompt。

---

### 9.2 Trace 记录粒度

当前即使只是简单问答，也建议记录：

```text
provider
model_name
input_data
output_data
cost_ms
token
status
error_message
```

后续接入 Agent 后，再扩展：

```text
graph_name
node_name
tool_name
tool_input
tool_output
```

---

### 9.3 Feedback 闭环

Feedback 不能只停留在“用户点了赞或踩”。

需要能关联：

```text
Feedback → Session → Trace → Prompt版本 → 模型输出
```

这样反馈才有优化价值。

---

### 9.4 前端入口

既然已经引入 LLM 并能问答，前端首页应提供最小对话入口：

```text
输入框
发送按钮
回答展示区
loading 状态
错误提示
session_id / trace_id 调试信息
```

这样才能从产品层验证 Sprint2 的最小闭环。

---

## 10. 面试表达版本

如果被问到 Sprint2 做了什么，可以这样回答：

```text
Sprint2 我主要完成了 AI Runtime 的最小闭环设计与实现。这个 Runtime 不保存 IOC 的业务主数据，而是专门管理 AI 运行时数据，包括 Conversation、Session、Prompt版本、Trace 和 Feedback。

Conversation 用来表示用户与 AI 的一段对话，Session 用来表示一次 AI 任务执行，Prompt 通过 code 和 version 管理不同版本，Trace 记录一次 AI 调用的执行链路，Feedback 用于后续优化闭环。

当前阶段我们使用 MySQL 存储 Runtime 数据，暂不引入 Redis，降低系统复杂度。同时已经接入 LLM，实现了简单问答链路。一次用户请求会创建 Session，读取 active Prompt，调用模型，记录 Trace，保存输出，并返回给前端。

这个 Sprint 的价值是让项目从普通后端 CRUD 进入了真正的企业级 AI Runtime 阶段，为后续接入 Agent、Graph、Tool 和业务数据分析打下基础。
```

---

## 11. 下一阶段建议

Sprint2 后续可以继续打磨：

```text
1. 补齐前端首页 AI 对话入口
2.
```
