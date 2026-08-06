# 运营统一消息池设计

**日期：** 2026-08-06  
**状态：** 已确认，待实施

## 目标

为运营人员提供一个共享的“待处理消息”工作池，统一处理需要人工关注的 AI 深度解答任务。消息不能因为浏览器关闭、SSE 中断、服务重启或多人同时操作而丢失或被重复处理。

本阶段采用默认方案：共享池、手动领取、超时释放、后台 Worker 执行深度解答任务。

## 当前问题

当前 `report_chat_agent` 在 SSE 请求内直接执行 LangGraph。`AiSession` 虽然已有 `running/success/failed` 状态，但没有排队状态、任务领取、超时回收或 Worker 调度。前端 `sending` 只能限制单个浏览器页面，无法控制多个运营人员之间的并发。

## 方案与取舍

### 方案 A：数据库任务池 + 独立 Worker（采用）

用户请求只创建任务并返回任务标识；独立 Worker 按优先级领取任务，执行深度解答并持久化结果。运营人员从共享池原子领取待处理消息。

优点是任务可恢复、可审计、可横向扩展，当前 MySQL 和 `AiSession` 模型可以复用。缺点是需要新增任务状态和 Worker 进程。

### 方案 B：Web 进程内存队列

实现简单，但服务重启会丢任务，多实例部署时无法共享队列，不适合作为生产方案。

### 方案 C：引入 Redis/Celery 等外部队列

吞吐和调度能力更强，但会新增基础设施和运维成本。本阶段先用数据库任务池，后续吞吐达到瓶颈时保留迁移到外部队列的接口边界。

## 状态模型

### AI 执行状态

`AiSession.status` 增加或使用以下语义：

- `queued`：已创建任务，等待 Worker。
- `running`：Worker 已领取并正在执行。
- `success`：AI 深度解答成功。
- `failed`：执行失败，可重试。
- `cancelled`：人工取消。
- `expired`：超过最大执行时长或任务长期未恢复。

### 运营处理状态

新增运营消息状态：

- `awaiting_review`：等待运营人员领取。
- `claimed`：已被某名运营人员领取。
- `resolved`：运营人员处理完成。
- `reopened`：已完成消息重新打开。

AI 任务状态和运营处理状态分开，避免“AI 已生成答案”和“人工已确认”混成一个状态。

## 数据模型

新增 `operation_message` 表，关联现有 `AiSession` 和 `ReportChatMessage`：

```text
operation_message
├── id
├── runtime_session_id
├── report_chat_message_id
├── report_id
├── priority
├── status
├── assignee_id
├── claimed_at
├── lease_expires_at
├── resolved_at
├── resolution_note
├── retry_count
├── error_message
├── created_at
└── updated_at
```

关键索引：`status + priority + created_at`、`assignee_id + status`、`runtime_session_id`。同一个运行任务只允许有一条运营消息记录，使用唯一约束避免重复入池。

## 处理流程

```text
用户提问
  ↓
创建 AiSession(queued) 与 operation_message(queued)
  ↓
Worker 原子领取 queued 任务
  ↓
AiSession → running
  ↓
执行深度解答并持久化 ReportChatMessage
  ↓
成功：AiSession → success，operation_message → awaiting_review
失败：AiSession → failed，operation_message → failed
  ↓
运营人员领取：awaiting_review → claimed
  ↓
完成处理：claimed → resolved
```

前端 SSE/WebSocket 只负责推送进度和刷新数量；任务状态以数据库为准。第一阶段允许使用短轮询，避免把实时推送作为可靠性依赖。

## Worker 与并发控制

Worker 使用数据库事务和行锁领取任务，等价于：

```sql
SELECT ...
FROM operation_message
WHERE status = 'queued'
ORDER BY priority DESC, created_at ASC
FOR UPDATE SKIP LOCKED;
```

领取后立即写入 `running`、`claimed_by` 和 `claimed_at`。多个 Worker 或多个服务实例不会重复执行同一任务。

同一个报告会话默认限制一个 AI 任务同时执行；同一用户或其他报告可以并发处理。运营人员领取操作使用条件更新：只有 `awaiting_review` 且未分配的消息才能成功领取。领取租约默认 30 分钟，心跳续租；租约过期后由回收任务释放回 `awaiting_review`。

Worker 需要处理：

- 服务重启后回收超时 `running` 任务；
- LLM 超时和网络异常的有限次数重试；
- 重试次数达到上限后进入 `failed`；
- 任务执行和状态变更写入日志，保留 `trace_id` 便于追踪。

## 运营工作台

默认 tab：

- 待领取：`awaiting_review`，按优先级和创建时间排序；
- 我的处理中：当前操作员 `claimed` 的消息；
- 全部处理中：所有操作员已领取的消息；
- 已完成：`resolved`；
- 异常：AI 执行失败、超时或需要重试的消息。

每条消息展示报告、问题摘要、优先级、AI 状态、等待时长、当前处理人和 Trace。操作包括领取、释放、完成、重新打开、重试和查看完整上下文。

## API 边界

新增运营消息 API：

- `GET /operation/messages`：分页查询共享消息池，支持状态、优先级、报告和处理人过滤；
- `GET /operation/messages/{id}`：查看消息、报告上下文、AI 结果和执行链路；
- `POST /operation/messages/{id}/claim`：原子领取；
- `POST /operation/messages/{id}/release`：释放消息；
- `POST /operation/messages/{id}/resolve`：完成处理并记录备注；
- `POST /operation/messages/{id}/retry`：重试失败任务；
- `GET /operation/messages/summary`：返回各 tab 数量。

响应统一包含 `traceId`、业务 `code`、`message` 和 `data`，沿用现有 API 响应约定。

## 错误与权限

- 领取冲突返回明确的业务错误，不覆盖他人的领取结果。
- 只有具备运营处理权限的用户可以领取、释放、完成或重试。
- 普通用户只能查看自己的对话，不可查看共享运营池。
- 用户原始问题、AI 草稿和运营备注分开保存，避免覆盖审计内容。
- AI 生成失败时保留用户问题、错误信息和 Trace，允许运营人员重新触发。

## 测试策略

至少覆盖：

1. 新任务进入队列且不会重复入池。
2. 多 Worker 同时领取时只有一个成功。
3. 多运营人员同时领取时只有一个成功。
4. Worker 异常退出后任务可以回收。
5. LLM 超时、重试和最终失败状态正确。
6. 领取租约过期后消息重新回到待领取。
7. tab 汇总数量与过滤结果一致。
8. 权限隔离和原有报告聊天回归测试。

## 实施范围

本阶段包含任务表、状态机、数据库 Worker、运营消息 API、tab 列表和领取/释放/完成操作。

本阶段不引入 Redis/Celery，不改变现有报告内容结构，不重写 LangGraph 业务节点，不要求第一版使用 WebSocket。
