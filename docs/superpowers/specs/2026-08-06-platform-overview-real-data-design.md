# Agent 平台概览真实数据与消息池设计

**日期：** 2026-08-06  
**状态：** 已确认，待实施

## 目标

将 `/platform` 概览页从静态演示数据改为真实接口驱动，并把指标卡变成可跳转的工作入口。概览需要展示今日请求数、运行中任务、待处理消息、失败任务、Token 用量、Agent 成功率、平均响应时长和最近 Session。

“待处理消息”沿用项目既有共享运营消息池设计，不用 Session 状态临时替代。

## 方案

采用后端聚合接口方案。新增一个概览查询服务，统一查询 `AiSession`、`AiTrace` 和 `operation_message`，由单个接口返回指标与最近 Session；前端只负责加载、展示、刷新和路由跳转。

不采用前端多接口自行聚合，避免统计口径分散、多个请求之间数据不一致；不引入汇总表或缓存，避免当前数据规模下增加额外一致性维护。

## 数据口径

新增 `GET /api/v1/platform/overview`，返回以下字段：

```text
metrics:
  today_requests: int
  running_tasks: int
  pending_messages: int
  failed_tasks: int
  total_tokens: int
  agent_success_rate: float
  average_response_ms: float
recent_sessions: PlatformOverviewSession[]
```

- `today_requests`：按应用本地时区当天 `AiSession.created_at` 统计。
- `running_tasks`：`AiSession.status` 为 `queued` 或 `running` 的数量。
- `pending_messages`：`operation_message.status` 为 `awaiting_review` 或 `reopened` 的数量。
- `failed_tasks`：按应用本地时区当天创建且状态为 `failed` 的 Session 数量。
- `total_tokens`：当天 `AiTrace.span_type = "llm"` 记录的 `total_tokens` 之和；空值按 0 处理。
- `agent_success_rate`：已结束 Session 中 `success` 数量除以 `success + failed` 数量；没有已结束记录时返回 0。
- `average_response_ms`：有 `started_at` 和 `finished_at` 的已完成 Session 的平均耗时；没有有效样本时返回 0。
- `recent_sessions`：按 `created_at` 倒序返回最近 10 条真实 Session。每条包含 Session ID、标题/输入摘要、Agent/任务类型、渠道、运行次数、Token、状态和更新时间。运行次数按 Conversation 下 Session 数量统计，Token 按关联 LLM Trace 汇总。

所有数量和耗时均由后端计算，接口没有数据时返回 0 或空数组，不返回前端静态占位数字。

## 共享运营消息池

概览依赖的 `operation_message` 需要补齐项目既有设计的最小可用闭环：

- 表字段包含消息 ID、Runtime Session ID、报告聊天消息 ID、报告 ID、优先级、运营状态、处理人、领取时间、租约、完成时间、处理备注、重试次数、错误信息和时间字段。
- 运营状态至少支持 `awaiting_review`、`claimed`、`resolved`、`reopened` 和失败状态。
- 为 Runtime Session 建立唯一关联，避免同一个运行任务重复入池。
- 提供消息列表和汇总查询，支持按状态、处理人、优先级和报告过滤。
- 概览只读消息池汇总；消息处理动作继续遵循既有设计的领取、释放、完成、重开、重试状态边界。
- 为现有会产生人工关注任务的入口接入消息入池，确保接口不是只有空表读取。入池失败不能覆盖原始 AI 任务结果，并保留错误信息和 Trace 关联。

## 前端行为

修改 `/platform` 概览页：

- 删除当前指标卡和最近 Session 的静态数组与硬编码数值。
- 页面加载时请求概览接口，显示加载、空数据、错误和重试状态。
- 指标卡采用链接或按钮语义，点击后跳转：
  - 今日请求数 → `/platform/sessions`，按当天范围筛选；
  - 运行中任务 → `/platform/sessions?status=running`，同时覆盖 queued 的展示口径；
  - 待处理消息 → `/platform/messages?status=awaiting_review`；
  - 失败任务 → `/platform/sessions?status=failed`；
  - Token 用量 → `/platform/traces?span_type=llm` 或用量视图；
  - Agent 成功率 → `/platform/agents`；
  - 平均响应时长 → `/platform/sessions`，按已完成运行查看。
- 最近 Session 使用真实返回值，保留当前的状态筛选交互；行或详情入口跳转到 Session 列表/详情。
- 侧边栏启用“待处理消息”导航项，移除“功能待开发”状态。

如果目标列表页尚不支持某个查询参数，本次同时补齐该页的参数解析和服务端过滤，保证点击后确实落到对应数据集，而不是只改变 URL。

## 后端结构

建议新增或修改以下边界：

- `backend/app/platform/`：概览 schema、查询服务、消息池模型/仓储/服务。
- `backend/app/platform/api/overview_api.py`：概览 HTTP 接口。
- `backend/app/platform/api/message_api.py`：消息池列表、汇总和状态操作接口。
- `backend/alembic/versions/20260806_0003_create_operation_messages.py`：消息池表迁移；版本号按仓库当前 Alembic head 调整。
- `backend/app/runtime/`：为概览所需的状态、耗时和 LLM Trace 查询提供兼容过滤，不改变既有 Runtime API 响应结构。
- `backend/app/main.py`：注册 Platform 路由。

查询服务保持纯聚合职责，不在 HTTP 层拼 SQL。时间边界使用现有 `app.utils.timezone`，避免 UTC 与应用本地时间混用。

## 错误处理

- 概览查询失败返回统一 API 错误响应，前端保留页面结构并显示可重试错误。
- 某类统计没有数据时按定义返回 0，不把缺失数据伪装成固定演示值。
- 消息池入池失败记录日志并保留原始任务状态，不能因为运营扩展功能导致主 AI 请求失败。
- 领取冲突、租约过期和非法状态转换沿用共享消息池设计中的明确业务错误。

## 测试策略

后端测试覆盖：

1. 概览接口返回当天请求数、运行中任务、失败任务和最近 Session。
2. LLM Trace Token 汇总不会把非 LLM Span 计入总量。
3. 成功率和平均响应耗时的分母、空数据和缺失时间字段口径正确。
4. 消息池唯一入池、状态过滤、汇总数量和待处理状态统计正确。
5. 概览查询不改变既有 Runtime Session/Trace API 响应。

前端测试覆盖：

1. 概览页调用真实 API 并渲染返回指标和 Session。
2. 加载、空数据、失败重试状态可见。
3. 七类指标跳转到对应列表或详情入口，并携带筛选参数。
4. 待处理消息导航项可用，Session 列表不再读取静态数组。

验证命令按项目现有脚本执行，至少包括后端新增聚合/消息池测试、前端相关 Vitest 测试、TypeScript 构建和现有回归测试。

## 范围约束

- 不引入 Redis、Celery 或新的统计缓存基础设施。
- 不重写现有 Agent 图和报告内容结构。
- 不删除或改变现有 Runtime、Trace、Graph 页面已有接口字段。
- 不把静态模拟数据保留为生产回退值；仅允许在测试中使用 fixture。
