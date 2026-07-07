# Sprint3 总结与思考：Tool Center 业务能力中心

> 当前项目状态：Sprint3 Tool Center 已形成可运行、可测试、可通过 HTTP 调用的最小闭环。  
> 核心结论：本 Sprint 已经从“AI Runtime 能对话”推进到“Agent 可以通过受控 Tool 安全访问业务能力”。

---

## 一、Sprint3 阶段定位

Sprint3 的核心目标不是“多写几个查询函数”，而是建设企业 Agent 系统中的 **Tool Center 基础设施**。

在 IOC 智能运营中心项目里，Tool Center 的定位是：

```text
Graph / Node / Agent 不直接访问数据库，也不直接调用散乱接口。

所有业务数据查询、聚合分析、动作草稿生成，
都必须通过 Tool Center 统一封装、统一校验、统一返回、统一追踪。
```

这意味着 Tool Center 是 AI 编排层和业务系统之间的安全适配层：

```text
用户问题
  -> Agent / Graph 判断任务
  -> Node 选择 Tool
  -> Tool Center 执行业务能力
  -> IOC Client / Mock IOC Client 获取业务数据
  -> ToolResult 返回结构化结果、证据、错误和 trace_id
  -> Graph State 沉淀上下文
  -> LLM 基于结构化数据生成最终表达
```

当前 Sprint3 已完成的是 **Tool Center 最小可用闭环**，还不是完整 Agent Graph 闭环。

---

## 二、当前完成内容总览

| 目标 | 当前进度 | 说明 |
|---|---|---|
| Tool SDK | 已完成 | `BaseTool.run()` 统一 trace、异常捕获、结果包装 |
| Tool DTO | 已完成 | `BaseToolInput`、`ToolContext`、`ToolResult`、`Evidence`、`ToolError` 已落地 |
| Tool Exception | 已完成 | 支持 `ToolException`、`ToolNotFoundError`、`ToolValidationError`、`ToolTimeoutError`、`ToolUpstreamError` |
| Tool Trace | 已完成基础版 | 通过 logger 输出 `TOOL_START`、`TOOL_SUCCESS`、`TOOL_FAILED`，暂未持久化到 Trace 表 |
| Tool Registry | 已完成 | 全局 registry 支持注册、查找、列出 Tool |
| Mock IOC Client | 已完成 | 使用 Mock 数据模拟 KPI、告警、隐患、工单查询 |
| Query Tool | 已完成 | 已有 KPI、Alarm、Risk、WorkOrder 四类查询 Tool |
| Analysis Tool | 已完成 | 已有 `ioc_summary_analysis`，做确定性聚合和风险评分，不调用 LLM |
| Action Tool | 已完成基础版 | 已有 `work_order_draft`，只生成工单草稿，必须人工确认 |
| HTTP API | 已完成基础版 | `/api/v1/tools`、`/api/v1/tools/call` 可列出和调用 Tool |
| 测试验收 | 已完成 | Sprint3 相关测试 146 passed，人工验收脚本 9/9 通过 |
| Graph 集成 | 部分完成 | 已通过集成测试模拟 Graph 调用链，尚未接入真实 LangGraph 节点 |

---

## 三、Sprint3 关键文件清单

### 1. Tool Center 基础设施

| 文件 | 作用 |
|---|---|
| `backend/app/tool_center/core/base_tool.py` | Tool 统一执行模板，定义 `run()` 和 `_execute()` 边界 |
| `backend/app/tool_center/core/schemas.py` | Tool 输入、输出、证据、错误结构定义 |
| `backend/app/tool_center/core/exceptions.py` | Tool 统一异常体系 |
| `backend/app/tool_center/core/trace.py` | Tool 调用日志与 trace 输出 |
| `backend/app/tool_center/core/registry.py` | Registry 类，管理 Tool 注册与查找 |
| `backend/app/tool_center/registry.py` | 进程级全局 registry 入口 |

### 2. IOC 接入与 Mock 数据

| 文件 | 作用 |
|---|---|
| `backend/app/integrations/ioc/client.py` | `IocApiClient` 抽象接口，定义 IOC 查询契约 |
| `backend/app/integrations/ioc/mock_client.py` | Mock IOC Client，实现 KPI、告警、隐患、工单查询 |
| `backend/app/integrations/ioc/mock_data.py` | Sprint3 本地 Mock 业务数据 |
| `backend/app/integrations/ioc/schema.py` | IOC API 返回结构与业务记录模型 |

### 3. Tool 实现

| 文件 | Tool | 作用 |
|---|---|---|
| `backend/app/tools/query/kpi_tool.py` | `kpi_query` | 查询 IOC KPI 指标数据 |
| `backend/app/tools/query/alarm_tool.py` | `alarm_query` | 查询 IOC 告警数据 |
| `backend/app/tools/query/risk_tool.py` | `risk_query` | 查询 IOC 隐患数据 |
| `backend/app/tools/query/work_order_tool.py` | `work_order_query` | 查询 IOC 工单数据 |
| `backend/app/tools/analysis/ioc_summary_tool.py` | `ioc_summary_analysis` | 对查询结果做规则型聚合分析 |
| `backend/app/tools/action/work_order_draft_tool.py` | `work_order_draft` | 生成工单草稿，不直接执行真实动作 |

### 4. 注册、API 与验收

| 文件 | 作用 |
|---|---|
| `backend/app/tools/register.py` | 集中注册当前 6 个 Tool，共用 `MockIocApiClient` |
| `backend/app/tools/api.py` | 暴露 `/tools` 和 `/tools/call` HTTP 接口 |
| `backend/app/main.py` | 应用启动时调用 `register_all_tools()` 并挂载 Tool API |
| `backend/scripts/verify_tool_center.py` | Sprint3 人工验收脚本 |
| `backend/tests/tools/test_tool_center_integration.py` | 模拟 registry -> Query -> Analysis -> Action 的完整调用链 |

---

## 四、核心实现理解

### 1. 为什么所有 Tool 都必须走 `BaseTool.run()`？

`BaseTool.run()` 是 Tool 的统一安全入口。子类只实现 `_execute()`，不应该绕过 `run()` 直接暴露自己的执行逻辑。

当前 `run()` 集中完成了几件事：

1. 给每次 Tool 调用生成 `trace_id`。
2. 调用 `start_trace()` 输出 `TOOL_START` 日志。
3. 执行子类 `_execute()`。
4. 把成功结果统一包装成 `ToolResult(success=True, ...)`。
5. 捕获 `ToolException`，包装成 `ToolResult(success=False, error=ToolError(...))`。
6. 捕获未知异常，统一包装为 `TOOL_INTERNAL_ERROR`。
7. 调用 `end_trace()` 输出成功或失败日志。

这保证了 Graph / Node 调用任何 Tool 时，都只需要处理一种返回协议：

```text
ToolResult.success == true  -> 继续执行后续节点
ToolResult.success == false -> 进入降级、重试、终止或人工处理分支
```

这样即使某个 Tool 执行失败，Graph 也不会因为收到裸异常而直接崩溃。

---

### 2. `ToolResult` 为什么必须结构化？

当前标准返回结构在 `backend/app/tool_center/core/schemas.py` 中定义：

```text
success: bool
data: dict | list | None
evidence: list[Evidence]
error: ToolError | None
trace_id: str | None
metadata: dict
```

每个字段都有明确作用：

| 字段 | 作用 |
|---|---|
| `success` | Graph 判断下一步分支的核心字段 |
| `data` | Tool 返回的结构化业务数据 |
| `evidence` | 支撑最终回答的证据来源 |
| `error` | 结构化错误，包含 code、message、detail、retryable |
| `trace_id` | 排查一次 Tool 调用的唯一凭证 |
| `metadata` | 保存来源、总数、是否空数据等辅助信息 |

如果 Tool 只返回自然语言字符串，Graph 无法稳定读取字段，也无法可靠测试、降级和追踪。

所以 Sprint3 的一个重要成果是把 Tool 输出从“文本结果”升级成了“结构化协议”。

---

### 3. `Evidence` 的价值是什么？

Agent 最终回答业务问题时，不能只给一个结论，还要能说明结论依据来自哪里。

当前 Query Tool 会按每条 IOC 记录生成 evidence，例如：

```text
KPI Tool -> source_type = kpi_api
Alarm Tool -> source_type = alarm_api
Risk Tool -> source_type = risk_api
WorkOrder Tool -> source_type = work_order_api
Analysis Tool -> source_type = summary
Action Tool -> source_type = work_order_draft
```

这为后续 Agent 回答提供了可解释基础：

```text
“当前风险等级为 high，因为查询到 critical 告警 2 条、高风险隐患 3 条、pending 工单若干。”
```

没有 evidence，LLM 的回答会变成黑盒文本；有 evidence，前端和用户才能追溯“结论来自哪些业务记录”。

---

### 4. 为什么需要 `IocApiClient` 抽象？

当前 IOC 接入边界在：

```text
backend/app/integrations/ioc/client.py
```

它定义了四个稳定方法：

```text
get_kpis(filters)
get_alarms(filters)
get_risks(filters)
get_work_orders(filters)
```

Query Tool 依赖的是 `IocApiClient` 抽象，而不是直接依赖 `mock_data.py`。

这样做的价值是：

```text
当前开发期：
Tool -> IocApiClient -> MockIocApiClient -> mock_data

未来生产期：
Tool -> IocApiClient -> RealIocApiClient -> 真实 IOC API
```

只要真实 IOC Client 保持 `IocApiResponse` 契约稳定，Tool 层就不需要大改。

这也是 Sprint3 的一个关键架构收获：**Mock 不是临时代码，而是真实接口契约的提前实现。**

---

### 5. Mock IOC Client 当前做了什么？

`backend/app/integrations/ioc/mock_client.py` 当前完成了：

1. KPI、告警、隐患、工单四类 Mock 查询。
2. 每类查询有明确过滤字段白名单。
3. 不支持的过滤字段会返回失败响应。
4. 查询成功时统一返回 `items + total`。
5. 空数据不是失败，而是 `success=true`、`total=0`、`metadata.empty=true`。
6. `metadata` 中保留过滤条件、支持字段和空数据状态。

这个设计避免了一个常见问题：

```text
字段拼错 -> 后端静默返回空数组 -> Agent 误以为业务没有数据
```

当前实现会让不支持字段变成失败响应，再由 Query Tool 转换为结构化 `ToolError`。

---

### 6. Query Tool 当前完成了什么？

当前已完成四个 Query Tool：

```text
kpi_query
alarm_query
risk_query
work_order_query
```

它们的共同模式是：

```text
读取 BaseToolInput.filters
  -> 调用 IocApiClient 对应方法
  -> ensure_success() 检查 Client 响应
  -> 生成 data
  -> 生成 evidence
  -> 透传 metadata
  -> 交给 BaseTool.run() 包装成 ToolResult
```

Query Tool 坚持三个边界：

1. 不直接查数据库。
2. 不调用 LLM。
3. 不执行业务写动作。

它们只负责安全、稳定、可追踪地取业务数据。

---

### 7. Analysis Tool 当前完成了什么？

当前分析 Tool 是：

```text
ioc_summary_analysis
```

对应文件：

```text
backend/app/tools/analysis/ioc_summary_tool.py
```

它做的是规则型结构化分析，不调用 LLM。

当前能力包括：

1. 统计 KPI 状态分布。
2. 统计告警等级分布。
3. 统计隐患等级分布。
4. 统计工单状态分布。
5. 按规则计算 `risk_score`。
6. 按分数输出 `risk_level`：`low`、`medium`、`high`。
7. 空数据场景安全返回 `risk_score=0`、`risk_level=low`。

这里要特别区分：

| 能力 | 当前归属 |
|---|---|
| 确定性统计、分组、评分 | Analysis Tool |
| 自然语言解释、报告表达 | 后续 Agent / Graph / LLM |

Analysis Tool 不负责写最终报告，它只负责给 Graph 和 LLM 提供稳定的结构化分析结果。

---

### 8. Action Tool 为什么只生成草稿？

当前动作 Tool 是：

```text
work_order_draft
```

对应文件：

```text
backend/app/tools/action/work_order_draft_tool.py
```

它的职责不是直接创建真实工单，而是生成工单草稿：

```text
action_type = create_work_order_draft
requires_human_confirmation = true
status = draft
```

这样设计是因为企业系统里的动作通常会触发真实流程：

```text
派单
通知
考核
资源调度
生产运维动作
安全责任流转
```

如果让 Agent 或 LLM 自动执行真实动作，Prompt 注入、幻觉、参数错误都会带来真实业务风险。

所以 Sprint3 的动作边界是：

```text
Action Tool 可以生成动作草稿。
真实执行必须进入人工确认流程。
```

当前实现已经支持基于 `alarm` 或 `risk` 查询来源详情，并把来源标题写入草稿，保证后续人工确认时可追溯。

---

### 9. Registry 和 API 当前承担什么角色？

Tool 注册入口在：

```text
backend/app/tools/register.py
```

当前启动时注册 6 个 Tool：

```text
kpi_query
alarm_query
risk_query
work_order_query
ioc_summary_analysis
work_order_draft
```

FastAPI 入口在：

```text
backend/app/tools/api.py
```

提供两个接口：

```text
GET  /api/v1/tools
POST /api/v1/tools/call
```

这使得 Tool Center 不只可以被 Python 内部调用，也可以通过 HTTP 做调试、联调和前端工具页接入。

需要注意的是，当前 API 仍是基础版：

1. 还没有做 Tool 级权限控制。
2. 还没有做租户级 Tool 可见性控制。
3. 还没有把 Tool 调用 trace 持久化到数据库。
4. `/tools/call` 适合本地联调，生产环境需要加认证、权限和审计策略。

---

## 五、当前验收结果

本次基于当前代码重新验证 Sprint3 相关能力，结果如下。

### 1. 编译检查

执行命令：

```bash
cd AIOperationsCenter/backend
.venv/bin/python -m compileall app/tool_center app/tools app/integrations/ioc
```

结果：

```text
通过
```

### 2. 人工验收脚本

执行命令：

```bash
cd AIOperationsCenter/backend
.venv/bin/python scripts/verify_tool_center.py
```

结果：

```text
通过步骤: 9/9
Tool Center 验收完成
```

验收脚本覆盖：

1. 注册所有 Tool。
2. KPI Query Tool 查询综合能耗指标。
3. Alarm Query Tool 查询 high 级别告警。
4. Risk Query Tool 查询 pending 隐患。
5. WorkOrder Query Tool 查询处理中工单。
6. IocSummaryAnalysis Tool 聚合分析。
7. WorkOrderDraft Action Tool 生成工单草稿。
8. Analysis Tool 空数据场景。
9. 不存在 Tool 的错误场景。

### 3. 自动化测试

执行命令：

```bash
cd AIOperationsCenter/backend
.venv/bin/python -m pytest tests/tool_center tests/integrations tests/tools
```

结果：

```text
146 passed
```

覆盖范围包括：

1. BaseTool 成功、失败、未知异常、metadata。
2. Tool DTO 和 schema 校验。
3. Tool Registry 注册、查找、不存在 Tool。
4. Mock IOC Client 查询、过滤、空数据、非法过滤字段。
5. Query Tool 成功和失败路径。
6. Analysis Tool 规则聚合和空数据路径。
7. Action Tool 参数校验、来源查询、草稿生成。
8. Tool Center 集成调用链。
9. Tool HTTP API。

---

## 六、Sprint3 已达成的关键价值

### 1. Agent 访问业务能力有了统一入口

Sprint3 之前，业务能力可能散落在接口、Service、数据库或 Mock 逻辑中。

Sprint3 之后，Agent 后续应该统一通过 Tool Center 访问业务能力：

```text
Graph / Node -> registry.get(tool_name) -> tool.run(input) -> ToolResult
```

这为 Sprint4 的 Operation Agent 打下了基础。

---

### 2. 业务数据访问和 LLM 推理被拆开了

当前 Query Tool 和 Analysis Tool 都不调用 LLM。

这让系统边界更清楚：

```text
Tool 负责取数和确定性分析。
LLM 负责基于结构化结果做解释和表达。
Graph 负责流程编排和状态流转。
```

这个拆分很重要，因为它让 Tool 可测试、可复现、可审计。

---

### 3. 失败路径变得可控

Tool 失败时不会直接抛异常给 Graph，而是返回：

```text
success=false
error.code
error.message
error.retryable
trace_id
```

后续 Graph 可以根据错误码做不同处理：

| 错误类型 | 建议处理 |
|---|---|
| 参数错误 | 终止当前 Tool，要求补充参数 |
| 上游失败 | 可降级或提示外部系统异常 |
| 超时 | 可重试 |
| 不存在 Tool | 进入兜底说明或开发排查 |
| 未知异常 | 记录 trace_id，返回系统异常提示 |

---

### 4. Mock 数据具备了测试和并行开发价值

当前 Mock 数据不只是“临时假数据”，它支撑了：

1. 本地开发不依赖真实 IOC 系统。
2. Tool 单元测试可重复执行。
3. 前端、后端、Agent 编排可并行推进。
4. 真实 IOC API 尚未接入时，先稳定接口契约。

未来接真实 IOC 时，应该优先保持当前 `IocApiClient` 和 `IocApiResponse` 契约稳定。

---

## 七、当前仍需注意的问题

### 1. Graph 集成还没有真正落地

当前已经有集成测试模拟：

```text
registry -> Query Tool -> ToolResult -> Analysis Tool -> Action Tool
```

但这还不是完整 LangGraph 编排。

Sprint4 需要把 Tool Center 接入 Operation Agent 的真实流程，例如：

```text
识别用户意图
  -> 选择需要的 Query Tool
  -> 汇总 ToolResult
  -> 调用 Analysis Tool
  -> 生成回答
  -> 必要时生成 Action Draft
  -> 等待人工确认
```

---

### 2. Tool Trace 目前是日志级别，尚未持久化

当前 `trace.py` 会输出 Tool 调用日志，但还没有写入数据库 Trace 表，也没有和 Sprint1/Sprint2 的请求级 trace、runtime trace 完整打通。

后续建议：

1. ToolResult.trace_id 与请求 `X-Trace-Id` 建立关联。
2. Tool 调用记录写入 runtime trace 或独立 tool_trace 表。
3. 前端 Trace Viewer 能看到一次 AI 请求下调用了哪些 Tool。
4. evidence、metadata、error_code 可以进入审计记录。

---

### 3. Tool 入参目前仍偏通用

当前 `BaseToolInput.filters` 使用 `dict`，灵活但不够强类型。

后续可以逐步演进：

```text
KpiQueryInput
AlarmQueryInput
RiskQueryInput
WorkOrderQueryInput
WorkOrderDraftInput
```

强类型入参的价值是：

1. 更早发现字段错误。
2. OpenAPI 文档更清楚。
3. Agent 选择 Tool 时更容易理解参数。
4. 前端工具调试页可以自动生成表单。

不过当前阶段保留通用 `filters` 是可以接受的，因为 Sprint3 目标优先是打通 Tool Center 主链路。

---

### 4. Action Tool 只有草稿，没有完整确认流

当前 `work_order_draft` 已经保证“不直接执行真实动作”，这是正确边界。

但后续还需要补完整动作闭环：

```text
生成草稿
  -> 前端展示草稿
  -> 人工确认
  -> 后端二次校验
  -> 调用真实业务动作接口
  -> 记录操作审计
```

这部分不建议在 Tool 内部直接做完，而应该由 Agent Graph、后端审批接口和真实业务系统共同完成。

---

### 5. Tool API 暂时适合开发联调，生产需要加权限

当前 `/api/v1/tools/call` 可以按名称调用 Tool。

这对本地开发很方便，但生产环境必须补：

1. 用户身份认证。
2. 角色和租户权限。
3. Tool 可见性控制。
4. 参数白名单。
5. 调用频率限制。
6. 敏感字段脱敏。
7. 操作审计。

否则 Tool API 可能成为绕过业务权限的入口。

---

## 八、Sprint3 到 Sprint4 的衔接建议

Sprint3 已经完成 Tool Center 的能力底座，Sprint4 可以围绕 Operation Agent 展开。

建议 Sprint4 主线：

```text
用户运营问题
  -> Operation Agent / Graph
  -> 根据意图选择 Tool
  -> 调用 KPI / Alarm / Risk / WorkOrder Query Tool
  -> 调用 IocSummaryAnalysis Tool
  -> LLM 生成运营分析结论
  -> 如需动作，生成 WorkOrderDraft
  -> 前端展示 trace、evidence、草稿和确认入口
```

优先级建议：

| 优先级 | 事项 | 原因 |
|---|---|---|
| P0 | 接入真实 Graph / Node 调用 Tool Center | 让 Sprint3 能力进入 Agent 主流程 |
| P0 | 建立 ToolResult 到最终回答的转换逻辑 | 让 LLM 基于结构化数据回答，而不是凭空回答 |
| P1 | Tool trace 与 runtime trace 打通 | 方便排查一次 AI 请求中调用了哪些 Tool |
| P1 | 前端展示 evidence 和 action draft | 让用户能看见依据和确认动作 |
| P1 | 强化 Tool API 权限与审计 | 为真实业务环境做准备 |
| P2 | 预留 RealIocApiClient 工厂 | 为后续替换真实 IOC API 降低成本 |

---

## 九、本 Sprint 的核心认知沉淀

### 1. Tool Center 不是工具函数集合

它是 Agent 访问业务系统的安全边界。

普通函数只关心“能不能拿到结果”，Tool Center 还必须关心：

```text
谁调用的
调用了什么
参数是否合规
是否有权限
数据从哪里来
失败怎么处理
结果如何解释
如何被追踪和审计
```

---

### 2. Tool 的核心价值是“可控”

企业 Agent 系统里，最怕的不是模型不会回答，而是模型绕过规则直接操作业务系统。

所以 Tool 的设计重点不是让 LLM 更自由，而是让它在清晰边界内使用业务能力：

```text
可调用
可校验
可追踪
可降级
可解释
可审计
```

---

### 3. Query、Analysis、Action 要分层

当前项目里三类 Tool 的边界是清楚的：

| 类型 | 职责 | 是否调用 LLM | 是否写业务系统 |
|---|---|---|---|
| Query Tool | 查询业务数据 | 否 | 否 |
| Analysis Tool | 确定性统计分析 | 否 | 否 |
| Action Tool | 生成动作草稿 | 否 | 否，必须人工确认 |

这个边界应该继续保持。

如果后续需要调用 LLM，也应建设单独的 AI Tool，并明确标识，不要混入业务 Query Tool。

---

### 4. `success=false` 比抛异常更适合 Graph

后端普通接口可以通过异常交给全局异常处理。

但 Graph 编排更适合拿到结构化结果：

```text
success=false
error.code=...
retryable=true/false
trace_id=...
```

因为 Graph 需要根据失败原因决定：

```text
重试
跳过
降级
请求用户补充信息
进入人工处理
终止当前流程
```

所以 Tool 层统一返回 `ToolResult` 是 Sprint3 的关键设计。

---

## 十、最终总结

Sprint3 已经把项目从“AI Runtime 可以调用模型”推进到“Agent 可以通过统一 Tool Center 安全访问业务能力”。

当前已具备：

1. Tool 统一执行模板。
2. Tool 结构化输入输出协议。
3. Tool 异常、trace、registry。
4. IOC Mock Client 和 Mock 数据。
5. KPI、告警、隐患、工单 Query Tool。
6. IOC 汇总 Analysis Tool。
7. 工单草稿 Action Tool。
8. Tool HTTP API。
9. 自动化测试和人工验收脚本。

当前还没有完成的是：

1. 真实 LangGraph 编排接入。
2. Tool trace 与 runtime trace 持久化打通。
3. Tool API 权限和审计。
4. 真实 IOC API Client。
5. Action 草稿后的人工确认与真实执行闭环。

因此，Sprint3 的结论可以概括为：

```text
Tool Center 的骨架已经搭好，Mock 业务能力已经可用，调用协议已经稳定，
下一步要把这些能力接入 Operation Agent 的真实 Graph 流程。
```
