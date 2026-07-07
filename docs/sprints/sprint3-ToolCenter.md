# Sprint3：Tool Center（业务能力中心）详细实施方案

> 角色定位：AI 架构师 + 项目导师视角  
> Sprint主题：Tool 的统一封装与 Agent 安全访问业务能力  
> 项目背景：IOC 智能运营中心 Agent 项目  
> 核心目标：建设 Tool Center，统一封装 IOC 业务能力，让 Agent 通过 Tool 安全访问业务数据和业务动作。

---

## 0. Sprint3 一句话目标

Sprint3 的目标不是“多写几个函数”，而是建设企业 Agent 系统中的 **Tool Center 基础设施**：

```text
Graph / Node / Agent 不直接访问数据库，也不直接调用散乱接口。
所有业务数据查询、聚合分析、动作草稿生成，都必须通过 Tool Center 统一封装、统一校验、统一返回、统一追踪。
```

最终你要完成的是一层可扩展、可测试、可替换 Mock/真实接口、可被 Graph 稳定调用的 Tool 能力中心。

---

## 1. Sprint3 核心目标

| 目标 | 说明 | 本 Sprint 要做到什么程度 |
|---|---|---|
| Tool SDK | 统一 Tool 基类与调用规范 | 所有 Tool 继承 BaseTool，统一 run / validate / trace / error handling |
| Query Tool | 查询 IOC 业务数据 | KPI、Alarm、Risk、WorkOrder 等业务查询 Tool 可被 Graph 调用 |
| Analysis Tool | 聚合分析业务数据 | 对 Tool 查询结果做确定性统计、排行、分组，不调用 LLM |
| Action Tool | 生成人工确认后的业务动作 | 只生成动作草稿，不直接执行高风险动作 |
| Mock IOC API | 模拟 IOC 业务接口 | 早期不依赖真实系统，使用 Mock Client / Mock Data 支撑开发 |
| Tool Trace | 记录 Tool 调用日志 | 每次 Tool 调用记录入参摘要、耗时、状态、错误、证据来源 |
| Graph 集成 | 让 Node 通过 Tool Center 调用业务能力 | Graph 不直接写业务查询逻辑，只调用 Tool |
| 测试验收 | Tool 可单元测试、集成测试、异常测试 | 每个 Tool 至少有成功、失败、空数据三类测试 |

---

## 2. Sprint3 交付物清单

| 编号 | 交付物 | 文件/模块 | 优先级 | 验收标准 |
|---|---|---|---|---|
| D3-01 | BaseTool | `backend/app/tool_center/core/base_tool.py` | P0 | 子类可继承；统一执行流程；异常不外抛 |
| D3-02 | Tool DTO | `backend/app/tool_center/core/schemas.py` | P0 | 输入输出结构化；Pydantic 可校验 |
| D3-03 | Tool Exception | `backend/app/tool_center/core/exceptions.py` | P0 | 统一错误码、错误类型、错误消息 |
| D3-04 | Tool Trace | `backend/app/tool_center/core/trace.py` | P0 | 记录调用开始、结束、耗时、状态 |
| D3-05 | Tool Registry | `backend/app/tool_center/core/registry.py` | P1 | 可注册、查找、列出 Tool |
| D3-06 | Mock IOC Client | `backend/app/tool_center/clients/mock_ioc_client.py` | P0 | 可返回 Mock KPI / Alarm / Risk / WorkOrder 数据 |
| D3-07 | KPI Query Tool | `backend/app/tool_center/tools/query/kpi_tool.py` | P0 | 可查询指标数据，返回 evidence |
| D3-08 | Alarm Query Tool | `backend/app/tool_center/tools/query/alarm_tool.py` | P0 | 可查询告警列表，支持级别过滤 |
| D3-09 | Risk Query Tool | `backend/app/tool_center/tools/query/risk_tool.py` | P0 | 可查询隐患数据，支持状态过滤 |
| D3-10 | WorkOrder Query Tool | `backend/app/tool_center/tools/query/work_order_tool.py` | P1 | 可查询工单数据，支持状态/工厂过滤 |
| D3-11 | Analysis Tool | `backend/app/tool_center/tools/analysis/*.py` | P1 | 可做确定性聚合统计，不做 LLM 推理 |
| D3-12 | Action Tool | `backend/app/tool_center/tools/action/*.py` | P1 | 生成动作草稿，必须带人工确认标识 |
| D3-13 | Tool Tests | `backend/tests/tool_center/*` | P0 | 覆盖成功、失败、空数据、参数错误 |
| D3-14 | Sprint Review 文档 | `docs/sprint3_tool_center_review.md` | P1 | 能讲清设计边界、价值、扩展方式 |

---

## 3. Tool Center 在 Agent 系统中的位置

### 3.1 总体调用链

```text
User Question
   ↓
Agent / Graph
   ↓
Node：识别当前业务意图
   ↓
Tool Center：统一封装业务能力
   ↓
IOC API / Mock API / Future EMS / ERP / CRM API
   ↓
ToolResult：结构化结果 + evidence + error
   ↓
Graph State：沉淀当前轮上下文
   ↓
LLM：基于结构化数据生成分析结论
   ↓
User / Dashboard / Action Confirmation
```

### 3.2 一句话理解

```text
Graph 负责流程，Node 负责步骤，Tool 负责安全拿业务能力，Service 负责系统内部业务实现，LLM 负责推理和表达。
```

### 3.3 Sprint3 的边界

本 Sprint 只建设 Tool Center，不做完整 Agent 闭环。可以预留 Graph Node 调用入口，但不要把全部精力放在复杂 Graph 上。

当前 Sprint 的主线：

```text
Tool DTO → BaseTool → Mock IOC Client → Query Tool → Tool Trace → Tests → Graph Node 示例调用
```

---

## 4. 关键架构原则

### 4.1 Agent 不能直接访问业务数据库

企业 AI 系统中，Agent / LLM 不应该直接访问数据库，原因包括：

| 风险 | 说明 |
|---|---|
| 权限风险 | Agent 如果直接查库，容易绕过企业已有的账号、角色、数据权限体系 |
| 安全风险 | Prompt 注入、越权查询、敏感字段泄露等风险会被放大 |
| SQL 风险 | LLM 生成 SQL 不稳定，可能产生错误查询、慢查询、全表扫描甚至误操作 |
| 审计风险 | 直接查库难以追踪“谁在什么场景下查询了什么业务数据” |
| 解耦风险 | Agent 与数据库表结构强绑定，后续数据库变化会影响 Agent 稳定性 |
| 业务风险 | Agent 不理解真实业务边界，可能把中间表、脏数据、未授权数据直接用于结论 |

正确方式：

```text
Agent / Graph → Tool Center → Service / API → Database
```

Tool Center 对外暴露的是业务能力，不暴露数据库细节。

---

### 4.2 Tool 和 Service 的区别

| 对比项 | Tool | Service |
|---|---|---|
| 所属层级 | Agent 能力层 / AI 业务能力入口 | 后端业务服务层 |
| 主要使用者 | Agent、Graph、Node、LLM 编排层 | Controller、API、定时任务、内部模块 |
| 核心职责 | 把业务能力封装成 Agent 可安全调用的工具 | 承载业务规则、数据读写、事务处理 |
| 返回格式 | 必须结构化，统一 ToolResult | 可以返回领域对象、DTO、数据库模型等 |
| 是否面向 LLM | 是，输出要稳定、可解释、可追踪 | 不一定，通常面向后端业务逻辑 |
| 是否直接查库 | 不建议，优先调用 Service / API | 可以在合规架构下访问 Repository / DAO |
| 是否执行动作 | 只生成动作草稿或调用受控动作 | 可以执行真实业务操作 |
| 是否需要 evidence | 需要，方便 Agent 解释结论来源 | 不一定需要 |
| 是否需要 Trace | 必须需要，便于审计和排错 | 通常也需要日志，但粒度不同 |

一句话：

```text
Service 是后端系统的业务实现层；Tool 是 Agent 系统访问业务能力的安全适配层。
```

---

### 4.3 Tool、Graph、Node、Service 的区别

| 概念 | 职责 | IOC 项目中的例子 |
|---|---|---|
| Graph | 定义业务分析流程和状态流转 | “运营日报分析流程”：查 KPI → 查告警 → 查隐患 → 生成总结 |
| Node | Graph 中的一个执行步骤 | `fetch_kpi_node`、`analyze_risk_node`、`generate_report_node` |
| Tool | Agent 调用业务能力的统一入口 | `KpiQueryTool`、`AlarmQueryTool`、`RiskQueryTool` |
| Service | 后端业务服务层，封装真实业务逻辑 | `KpiService`、`AlarmService`、`WorkOrderService` |
| Client | 调用外部系统或 Mock API 的适配器 | `MockIocClient`、`RealIocClient` |
| DTO | 输入输出数据结构 | `ToolInput`、`ToolResult`、`Evidence` |
| Trace | 调用审计与调试信息 | Tool 名称、参数摘要、耗时、错误码 |

推荐边界：

```text
Graph：不要写接口调用细节
Node：不要写复杂业务查询
Tool：不要写 LLM Prompt
Service：不要感知 Agent 编排
Client：只负责连接外部系统
```

---

### 4.4 Tool 能不能调用 LLM？

本项目 Sprint3 的原则：**Tool 默认不调用 LLM。**

原因：

1. Tool 的职责是“安全访问业务能力”，不是“推理”。
2. LLM 推理应放在 Agent / Graph 的分析节点中，方便统一管理 Prompt、上下文和输出。
3. 如果 Tool 内部又调用 LLM，会导致调用链不透明，难以测试、难以追踪、难以定位问题。
4. Tool 返回应尽量稳定，LLM 输出天然存在不确定性，不适合作为基础数据层。

允许的例外：

```text
未来如果建设专门的 LLM Tool，例如 TextSummaryTool、IntentClassifyTool，可以调用 LLM。
但这类 Tool 必须明确标记为 AI Tool，不能和业务 Query Tool 混在一起。
```

本 Sprint 结论：

```text
Query Tool：不调用 LLM，只取数。
Analysis Tool：不调用 LLM，只做确定性聚合统计。
Action Tool：不调用 LLM 或只生成结构化动作草稿，最终执行必须人工确认。
LLM 推理：放在 Graph 的分析 Node 或 Response Node 中。
```

---

### 4.5 为什么需要 Mock IOC API？

Mock IOC API 的价值不是“临时代码”，而是企业项目早期研发的关键基础设施。

| 价值 | 说明 |
|---|---|
| 解耦真实系统 | 真实 IOC 接口未准备好时，Agent 工程仍可推进 |
| 稳定开发环境 | 不依赖测试库、专线、权限、外部接口稳定性 |
| 支持并行研发 | 前端、Agent、Tool、测试可并行推进 |
| 支持脱敏数据 | 使用脱敏后的业务样例，避免真实数据泄露 |
| 支持测试 | Mock 数据固定，单元测试和集成测试可重复 |
| 支持契约设计 | 先设计接口契约，后续真实接口按契约替换 |

Mock 的正确定位：

```text
Mock API 不是假业务，而是真实业务接口契约的提前实现。
```

---

### 4.6 Tool 结果为什么要结构化？

Agent 系统不能只依赖自然语言字符串，因为字符串难以解析、难以测试、难以稳定传递状态。

统一返回结构：

```json
{
  "success": true,
  "data": {},
  "evidence": [],
  "error": null,
  "trace_id": "trace_xxx",
  "metadata": {}
}
```

结构化的价值：

| 价值 | 说明 |
|---|---|
| 稳定解析 | Graph 可以稳定读取 `success`、`data`、`error` |
| 可测试 | 单元测试可以断言字段，而不是比对自然语言 |
| 可降级 | 失败时也能返回 `error`，Graph 可判断下一步 |
| 可解释 | evidence 支撑最终结论，避免“黑盒分析” |
| 可扩展 | metadata 可扩展耗时、来源、版本、分页等信息 |
| 可审计 | trace_id 可关联日志，定位一次完整调用链 |

---

## 5. 推荐项目目录结构

以下以 FastAPI + LangGraph 后端项目为假设，目录可以按你当前项目实际名称微调。

```text
backend/
  app/
    tool_center/
      __init__.py
      core/
        __init__.py
        base_tool.py              # Tool 统一基类
        schemas.py                # Tool 输入输出 DTO
        exceptions.py             # Tool 异常与错误码
        trace.py                  # Tool 调用追踪
        registry.py               # Tool 注册中心
      clients/
        __init__.py
        ioc_client_base.py         # IOC Client 抽象接口
        mock_ioc_client.py         # Mock IOC Client
        real_ioc_client.py         # 真实 IOC Client 预留
      tools/
        __init__.py
        query/
          __init__.py
          kpi_tool.py              # KPI 查询 Tool
          alarm_tool.py            # 告警查询 Tool
          risk_tool.py             # 隐患查询 Tool
          work_order_tool.py       # 工单查询 Tool
        analysis/
          __init__.py
          kpi_analysis_tool.py     # KPI 聚合统计 Tool
          alarm_analysis_tool.py   # 告警聚合统计 Tool
          risk_analysis_tool.py    # 风险排行 Tool
        action/
          __init__.py
          work_order_action_tool.py # 工单动作草稿 Tool
      mock_data/
        kpi_mock.json
        alarm_mock.json
        risk_mock.json
        work_order_mock.json
    graph/
      nodes/
        fetch_kpi_node.py
        fetch_alarm_node.py
        fetch_risk_node.py
        generate_report_node.py
      states/
        operation_state.py
    api/
      routes/
        mock_ioc_routes.py          # 可选：Mock API HTTP 路由
  tests/
    tool_center/
      test_base_tool.py
      test_kpi_tool.py
      test_alarm_tool.py
      test_risk_tool.py
      test_tool_trace.py
      test_tool_error.py
```

### 5.1 目录职责说明

| 目录 | 作用 | 注意事项 |
|---|---|---|
| `core/` | Tool 基础设施 | 放通用逻辑，不放具体业务 |
| `clients/` | 对接 IOC / Mock API | 后续从 Mock 切真实接口主要改这里 |
| `tools/query/` | 查询类 Tool | 只查询，不推理，不执行业务动作 |
| `tools/analysis/` | 聚合分析类 Tool | 只做确定性统计，如 count、group、rank、trend |
| `tools/action/` | 动作类 Tool | 只生成草稿，涉及执行必须人工确认 |
| `mock_data/` | Mock 业务数据 | 尽量贴近真实字段，但必须脱敏 |
| `graph/nodes/` | Graph 调用 Tool 的节点 | Node 只编排 Tool，不写接口细节 |
| `tests/tool_center/` | Tool 测试 | 每个 Tool 都要能独立测试 |

---

## 6. Sprint3 实施路线图

### 阶段一：明确边界与契约设计

目标：先把 Tool Center 的输入输出契约定下来，避免后续各个 Tool 返回格式混乱。

#### Step 1：定义 ToolResult 统一返回模型

建议字段：

```python
class Evidence(BaseModel):
    source: str
    source_type: str
    record_id: str | None = None
    timestamp: str | None = None
    description: str | None = None

class ToolError(BaseModel):
    code: str
    message: str
    detail: dict | None = None
    retryable: bool = False

class ToolResult(BaseModel):
    success: bool
    data: dict | list | None = None
    evidence: list[Evidence] = []
    error: ToolError | None = None
    trace_id: str | None = None
    metadata: dict = {}
```

验收标准：

- [ ] 成功时：`success=true`，`data` 有业务数据，`error=null`。
- [ ] 失败时：`success=false`，`data=null` 或空对象，`error` 有错误码。
- [ ] 每次返回都必须带 `trace_id`。
- [ ] 业务数据来源必须尽量带 `evidence`。

---

#### Step 2：定义 ToolInput 基础模型

建议基础字段：

```python
class ToolContext(BaseModel):
    user_id: str | None = None
    tenant_id: str | None = None
    role: str | None = None
    request_id: str | None = None
    locale: str = "zh-CN"

class BaseToolInput(BaseModel):
    context: ToolContext
```

不同业务 Tool 再扩展自己的入参：

```python
class KpiQueryInput(BaseToolInput):
    factory_id: str
    metric_codes: list[str]
    start_time: str
    end_time: str
```

验收标准：

- [ ] 每个 Tool 的入参都用 Pydantic 定义。
- [ ] 不允许直接传散乱 dict 后不校验就调用。
- [ ] 时间、工厂、指标编码等核心参数必须显式定义。
- [ ] context 中保留用户、租户、请求 ID，方便后续权限和审计。

---

### 阶段二：实现 BaseTool 基类

目标：所有 Tool 都走统一执行流程。

推荐执行流程：

```text
run(input)
  ↓
validate_input(input)
  ↓
before_call(trace start)
  ↓
_execute(input)
  ↓
wrap_success_result(data, evidence)
  ↓
after_call(trace end)
  ↓
return ToolResult
```

失败流程：

```text
run(input)
  ↓
validate_input(input)
  ↓
_execute(input) throws exception
  ↓
catch exception
  ↓
wrap_error_result(error_code, retryable)
  ↓
trace failed
  ↓
return ToolResult(success=false)
```

#### Step 3：实现 BaseTool

建议职责：

| 方法 | 作用 |
|---|---|
| `name` | Tool 唯一名称 |
| `description` | Tool 能力描述 |
| `input_schema` | 入参模型 |
| `run()` | 对外唯一调用入口 |
| `_execute()` | 子类实现的核心业务逻辑 |
| `_build_success()` | 构造成功 ToolResult |
| `_build_error()` | 构造失败 ToolResult |
| `_trace_start()` | 记录开始调用 |
| `_trace_end()` | 记录结束调用 |

伪代码：

```python
class BaseTool(ABC):
    name: str
    description: str

    def run(self, tool_input: BaseModel) -> ToolResult:
        trace_id = create_trace_id()
        start_time = time.time()
        try:
            self._trace_start(trace_id, tool_input)
            data, evidence, metadata = self._execute(tool_input)
            result = self._build_success(data, evidence, trace_id, metadata)
            self._trace_end(trace_id, success=True, start_time=start_time)
            return result
        except ToolException as e:
            result = self._build_error(e, trace_id)
            self._trace_end(trace_id, success=False, start_time=start_time, error=e)
            return result
        except Exception as e:
            wrapped = ToolException(code="TOOL_INTERNAL_ERROR", message=str(e), retryable=False)
            result = self._build_error(wrapped, trace_id)
            self._trace_end(trace_id, success=False, start_time=start_time, error=wrapped)
            return result

    @abstractmethod
    def _execute(self, tool_input: BaseModel):
        pass
```

验收标准：

- [ ] Tool 子类不需要重复写 try/except。
- [ ] 所有异常都被包装成 `ToolResult.error`。
- [ ] Tool 不直接抛异常给 Graph。
- [ ] Tool 调用成功/失败都能记录 Trace。
- [ ] 所有 Tool 的调用入口都是 `run()`。

---

### 阶段三：实现 Tool 异常体系

目标：让 Graph 能判断 Tool 调用失败后怎么处理。

#### Step 4：定义错误类型

建议错误码：

| 错误码 | 含义 | 是否可重试 | Graph 处理方式 |
|---|---|---|---|
| `TOOL_VALIDATION_ERROR` | 参数校验失败 | 否 | 让上层补充参数或终止当前分支 |
| `TOOL_PERMISSION_DENIED` | 无权限访问 | 否 | 终止并返回权限提示 |
| `TOOL_TIMEOUT` | 接口超时 | 是 | 可重试 1-2 次，失败后降级 |
| `TOOL_NETWORK_ERROR` | 网络异常 | 是 | 可重试，或使用缓存/Mock |
| `TOOL_DATA_EMPTY` | 查询结果为空 | 否 | 进入空数据处理分支 |
| `TOOL_UPSTREAM_ERROR` | 上游 IOC API 错误 | 视情况 | 根据错误码判断是否重试 |
| `TOOL_INTERNAL_ERROR` | Tool 内部错误 | 否 | 记录错误，进入失败兜底 |

验收标准：

- [ ] 错误码不能只写 `Exception`。
- [ ] `retryable` 必须明确。
- [ ] Graph 不靠字符串猜测错误类型。
- [ ] 空数据不是系统异常，要单独处理。

---

### 阶段四：实现 Mock IOC API / Mock Client

目标：通过 Mock 数据模拟 IOC 系统接口，支撑 Tool 开发。

#### Step 5：设计 Mock 数据

建议 Mock 数据文件：

```text
mock_data/
  kpi_mock.json
  alarm_mock.json
  risk_mock.json
  work_order_mock.json
```

KPI Mock 示例：

```json
[
  {
    "factory_id": "factory_001",
    "factory_name": "华北能源站A",
    "metric_code": "energy_consumption",
    "metric_name": "综合能耗",
    "value": 1280.5,
    "unit": "tce",
    "timestamp": "2026-07-06T08:00:00+09:00",
    "source_system": "IOC_MOCK"
  }
]
```

Alarm Mock 示例：

```json
[
  {
    "alarm_id": "alarm_001",
    "factory_id": "factory_001",
    "level": "high",
    "title": "冷站出水温度异常",
    "status": "open",
    "occurred_at": "2026-07-06T08:20:00+09:00",
    "source_system": "IOC_MOCK"
  }
]
```

Risk Mock 示例：

```json
[
  {
    "risk_id": "risk_001",
    "factory_id": "factory_001",
    "risk_type": "equipment",
    "level": "medium",
    "description": "2号泵运行振动偏高，存在设备劣化风险",
    "status": "pending",
    "discovered_at": "2026-07-06T09:00:00+09:00",
    "source_system": "IOC_MOCK"
  }
]
```

#### Step 6：设计 IOC Client 抽象接口

```python
class IocClientBase(ABC):
    @abstractmethod
    def query_kpi(self, params: dict) -> list[dict]:
        pass

    @abstractmethod
    def query_alarms(self, params: dict) -> list[dict]:
        pass

    @abstractmethod
    def query_risks(self, params: dict) -> list[dict]:
        pass

    @abstractmethod
    def query_work_orders(self, params: dict) -> list[dict]:
        pass
```

Mock 实现：

```python
class MockIocClient(IocClientBase):
    def query_kpi(self, params: dict) -> list[dict]:
        data = load_json("kpi_mock.json")
        return filter_by_params(data, params)
```

验收标准：

- [ ] Tool 调用的是 `IocClientBase` 抽象能力，而不是直接读 json。
- [ ] Mock Client 和未来 Real Client 方法签名一致。
- [ ] 从 Mock 切真实接口时，尽量不改 Tool 代码。
- [ ] Mock 数据必须脱敏，不使用真实敏感信息。

---

### 阶段五：实现 Query Tool

目标：完成 IOC 核心业务数据查询 Tool。

#### Step 7：实现 KPI Query Tool

职责：查询工厂/区域/系统的指标数据。

输入：

```python
class KpiQueryInput(BaseToolInput):
    factory_id: str
    metric_codes: list[str]
    start_time: str
    end_time: str
```

输出 data 建议：

```json
{
  "factory_id": "factory_001",
  "metrics": [
    {
      "metric_code": "energy_consumption",
      "metric_name": "综合能耗",
      "value": 1280.5,
      "unit": "tce",
      "timestamp": "2026-07-06T08:00:00+09:00"
    }
  ]
}
```

Evidence 建议：

```json
[
  {
    "source": "IOC_MOCK",
    "source_type": "kpi_api",
    "record_id": "factory_001:energy_consumption:202607060800",
    "timestamp": "2026-07-06T08:00:00+09:00",
    "description": "综合能耗指标来自 Mock IOC KPI 接口"
  }
]
```

验收标准：

- [ ] 支持按 `factory_id` 查询。
- [ ] 支持按 `metric_codes` 过滤。
- [ ] 返回数据包含单位、时间、来源。
- [ ] 无数据时返回 `TOOL_DATA_EMPTY` 或 success=true + 空 data，二者需统一约定。

建议本项目约定：

```text
查询成功但无数据：success=true，data=[]，metadata.empty=true。
接口失败或参数错误：success=false，error 不为空。
```

---

#### Step 8：实现 Alarm Query Tool

职责：查询告警数据。

输入：

```python
class AlarmQueryInput(BaseToolInput):
    factory_id: str | None = None
    levels: list[str] | None = None
    status: str | None = None
    start_time: str
    end_time: str
```

输出 data 建议：

```json
{
  "alarms": [
    {
      "alarm_id": "alarm_001",
      "factory_id": "factory_001",
      "level": "high",
      "title": "冷站出水温度异常",
      "status": "open",
      "occurred_at": "2026-07-06T08:20:00+09:00"
    }
  ],
  "summary": {
    "total": 1,
    "high": 1,
    "medium": 0,
    "low": 0
  }
}
```

验收标准：

- [ ] 支持按工厂过滤。
- [ ] 支持按告警等级过滤。
- [ ] 支持按状态过滤。
- [ ] 输出 summary，方便上层 Graph 使用。
- [ ] 每条告警有 evidence。

---

#### Step 9：实现 Risk Query Tool

职责：查询隐患/风险数据。

输入：

```python
class RiskQueryInput(BaseToolInput):
    factory_id: str | None = None
    risk_level: str | None = None
    status: str | None = None
    start_time: str
    end_time: str
```

输出 data 建议：

```json
{
  "risks": [
    {
      "risk_id": "risk_001",
      "factory_id": "factory_001",
      "risk_type": "equipment",
      "level": "medium",
      "description": "2号泵运行振动偏高，存在设备劣化风险",
      "status": "pending",
      "discovered_at": "2026-07-06T09:00:00+09:00"
    }
  ],
  "summary": {
    "total": 1,
    "pending": 1,
    "closed": 0
  }
}
```

验收标准：

- [ ] 支持按风险等级过滤。
- [ ] 支持按状态过滤。
- [ ] 输出风险数量统计。
- [ ] 风险数据不能被 LLM 自行编造，必须来自 ToolResult。

---

#### Step 10：实现 WorkOrder Query Tool

职责：查询工单数据。

输入：

```python
class WorkOrderQueryInput(BaseToolInput):
    factory_id: str | None = None
    status: str | None = None
    start_time: str
    end_time: str
```

验收标准：

- [ ] 支持查询待处理、处理中、已关闭工单。
- [ ] 支持按工厂过滤。
- [ ] 返回工单编号、标题、状态、负责人、创建时间。
- [ ] 作为 Action Tool 的上下文数据来源。

---

### 阶段六：实现 Analysis Tool

目标：把常见确定性聚合逻辑沉淀为 Tool，减少 Graph Node 中重复写统计代码。

注意：Analysis Tool 不是 LLM 推理，它只做确定性数据加工。

#### Step 11：实现 KPI Analysis Tool

可支持能力：

| 能力 | 说明 |
|---|---|
| `calc_metric_avg` | 指标平均值 |
| `calc_metric_max` | 指标最大值 |
| `calc_metric_min` | 指标最小值 |
| `calc_metric_trend` | 简单趋势：上升、下降、持平 |
| `compare_threshold` | 与阈值对比 |

验收标准：

- [ ] 输入来自 KPI Query Tool 的结构化 data。
- [ ] 输出统计结果，不输出自然语言结论。
- [ ] 不调用 LLM。
- [ ] 保留 evidence 传递链。

---

#### Step 12：实现 Alarm Analysis Tool

可支持能力：

| 能力 | 说明 |
|---|---|
| `count_by_level` | 按告警等级统计 |
| `count_by_factory` | 按工厂统计 |
| `top_alarm_factories` | 告警最多工厂排行 |
| `open_alarm_ratio` | 未关闭告警占比 |

验收标准：

- [ ] 输入为 Alarm Query Tool 返回数据。
- [ ] 输出排行、分组、数量。
- [ ] 不生成“原因判断”，原因判断交给 Graph 的 LLM 节点。

---

#### Step 13：实现 Risk Analysis Tool

可支持能力：

| 能力 | 说明 |
|---|---|
| `count_by_level` | 按风险等级统计 |
| `count_by_type` | 按风险类型统计 |
| `pending_risk_rank` | 待处理风险排行 |
| `risk_heatmap_data` | 风险热力图数据结构 |

验收标准：

- [ ] 支持风险数量、等级、类型、状态统计。
- [ ] 不做主观推理，不生成最终建议。
- [ ] 输出可以直接进入 Graph State。

---

### 阶段七：实现 Action Tool

目标：让 Agent 能生成“业务动作草稿”，但不能直接越权执行业务动作。

#### Step 14：实现 WorkOrder Action Tool

职责：根据告警/风险结果生成工单草稿。

输入：

```python
class WorkOrderDraftInput(BaseToolInput):
    source_type: str        # alarm / risk / manual
    source_id: str
    title: str
    description: str
    priority: str
    suggested_assignee: str | None = None
```

输出 data：

```json
{
  "action_type": "create_work_order_draft",
  "requires_human_confirmation": true,
  "draft": {
    "title": "处理冷站出水温度异常",
    "description": "基于告警 alarm_001 生成工单草稿，请运维人员确认后创建。",
    "priority": "high",
    "source_type": "alarm",
    "source_id": "alarm_001"
  }
}
```

关键原则：

```text
Sprint3 Action Tool 只生成动作草稿，不直接创建真实工单，不直接下发控制指令。
```

验收标准：

- [ ] 所有 Action Tool 输出必须包含 `requires_human_confirmation=true`。
- [ ] 动作草稿必须可追溯到原始 evidence。
- [ ] 不允许 Tool 在无确认情况下直接修改生产系统。
- [ ] Graph 后续应进入“等待人工确认”状态。

---

### 阶段八：实现 Tool Trace

目标：让每一次 Tool 调用都可追踪、可审计、可排错。

#### Step 15：设计 Trace 记录字段

建议字段：

```python
class ToolTraceRecord(BaseModel):
    trace_id: str
    request_id: str | None = None
    tool_name: str
    input_summary: dict
    success: bool
    error_code: str | None = None
    start_time: str
    end_time: str
    duration_ms: int
    evidence_count: int = 0
```

Trace 输出方式：

Sprint3 阶段可以先用日志文件或控制台日志：

```text
logs/tool_trace.log
```

后续可升级为：

```text
数据库 trace 表 / OpenTelemetry / LangSmith / 企业日志平台
```

验收标准：

- [ ] 每次 Tool 调用都有 trace_id。
- [ ] 成功和失败都记录日志。
- [ ] 入参日志要做摘要，不记录敏感字段明文。
- [ ] 错误日志必须包含 error_code。
- [ ] duration_ms 可用于排查慢 Tool。

---

### 阶段九：Tool Registry 注册中心

目标：让 Graph / Node 可以通过统一入口找到 Tool。

#### Step 16：实现 Tool Registry

```python
class ToolRegistry:
    def __init__(self):
        self._tools = {}

    def register(self, tool: BaseTool):
        self._tools[tool.name] = tool

    def get(self, name: str) -> BaseTool:
        if name not in self._tools:
            raise ToolException(code="TOOL_NOT_FOUND", message=f"Tool not found: {name}")
        return self._tools[name]

    def list_tools(self) -> list[str]:
        return list(self._tools.keys())
```

初始化示例：

```python
def build_tool_registry(ioc_client: IocClientBase) -> ToolRegistry:
    registry = ToolRegistry()
    registry.register(KpiQueryTool(ioc_client=ioc_client))
    registry.register(AlarmQueryTool(ioc_client=ioc_client))
    registry.register(RiskQueryTool(ioc_client=ioc_client))
    registry.register(WorkOrderQueryTool(ioc_client=ioc_client))
    return registry
```

验收标准：

- [ ] Tool 有唯一 name。
- [ ] Node 不直接 new 一堆 Tool，优先从 registry 获取。
- [ ] 后续增加 Tool 不影响已有 Tool。
- [ ] 可通过配置加载 Mock Client 或 Real Client。

---

## 7. Graph 如何处理 Tool 调用失败

这是 Sprint3 必须想清楚的问题。Graph 不应该因为一个 Tool 失败就无脑崩溃，也不应该无限重试。

### 7.1 基本原则

```text
Tool 不把异常抛给 Graph，而是返回 ToolResult。
Graph 根据 success / error.code / retryable 决定下一步。
```

### 7.2 推荐处理流程

```text
Node 调用 Tool
   ↓
ToolResult.success == true?
   ├─ 是：写入 State，进入下一个 Node
   └─ 否：读取 error.code / retryable
          ↓
          retryable == true 且 retry_count < max_retry?
             ├─ 是：重试当前 Tool
             └─ 否：进入失败兜底分支
```

### 7.3 错误分类与 Graph 策略

| 错误类型 | Graph 处理方式 |
|---|---|
| 参数错误 | 不重试，返回“缺少必要查询条件”或进入补参 Node |
| 权限错误 | 不重试，返回权限不足说明 |
| 网络错误 | 可重试 1-2 次 |
| 超时错误 | 可重试 1 次，仍失败则降级 |
| 上游错误 | 根据 retryable 判断 |
| 空数据 | 不算失败，进入“无数据分析”分支 |
| 内部错误 | 不重试，记录日志，返回兜底说明 |

### 7.4 轮询还是回调？

当前 Sprint3 推荐：**同步调用 + 有限重试**。

原因：

1. Query Tool 查询类操作通常是同步短请求。
2. Tool 返回结果后 Graph 决定下一个节点即可，不需要复杂回调。
3. 轮询适用于长任务，例如报表生成、批处理任务、外部审批流，本 Sprint 暂不需要。
4. 回调适用于外部系统异步通知，例如工单审批完成、巡检任务完成，后续 Action 闭环阶段再引入。

建议约定：

```text
Sprint3：同步 Tool 调用 + max_retry=1 或 2。
后续 Sprint：对于长耗时动作，引入 async job_id + status query tool + callback/event。
```

### 7.5 State 中建议保存的失败信息

```python
class OperationState(TypedDict):
    question: str
    tool_results: dict
    tool_errors: list[dict]
    retry_count: dict
    evidence: list[dict]
    final_answer: str | None
```

失败时写入：

```json
{
  "tool_name": "alarm_query_tool",
  "trace_id": "trace_xxx",
  "error_code": "TOOL_TIMEOUT",
  "message": "IOC alarm api timeout",
  "retryable": true
}
```

---

## 8. Tool 返回数据为什么要带 evidence

### 8.1 evidence 的作用

| 作用 | 说明 |
|---|---|
| 支撑结论 | Agent 最终说“高风险告警增加”，必须知道依据哪几条数据 |
| 防止幻觉 | LLM 只能基于 Tool 提供的数据解释，不能凭空编造 |
| 支持审计 | 出现争议时，可以回溯数据来源 |
| 支持调试 | 方便定位是数据问题、Tool 问题还是 Prompt 问题 |
| 支持前端展示 | 前端可以展示“结论依据”或“数据来源” |

### 8.2 evidence 建议结构

```json
{
  "source": "IOC_MOCK",
  "source_type": "alarm_api",
  "record_id": "alarm_001",
  "timestamp": "2026-07-06T08:20:00+09:00",
  "description": "冷站出水温度异常告警记录"
}
```

### 8.3 evidence 与 data 的关系

```text
Data：给 Graph / LLM 用来分析的结构化业务数据。
Evidence：说明这些数据从哪里来、对应哪些业务记录。
```

一句话：

```text
没有 evidence 的 Agent 结论，在企业系统里很难被信任。
```

---

## 9. 从 Mock 平滑替换为真实 IOC API

### 9.1 核心策略

```text
Tool 不感知 Mock 还是真实接口。
Tool 只依赖 IocClientBase。
MockIocClient 和 RealIocClient 实现相同方法签名。
```

### 9.2 切换方式

通过配置切换：

```env
IOC_CLIENT_TYPE=mock
# IOC_CLIENT_TYPE=real
```

工厂方法：

```python
def build_ioc_client() -> IocClientBase:
    client_type = settings.IOC_CLIENT_TYPE
    if client_type == "mock":
        return MockIocClient()
    if client_type == "real":
        return RealIocClient(base_url=settings.IOC_API_BASE_URL)
    raise ValueError(f"Unsupported IOC_CLIENT_TYPE: {client_type}")
```

### 9.3 替换步骤

| 阶段 | 动作 |
|---|---|
| 第一步 | 固定 ToolInput / ToolResult 契约 |
| 第二步 | Mock 数据字段尽量对齐真实 IOC API |
| 第三步 | 编写 IocClientBase 抽象接口 |
| 第四步 | Tool 只依赖 IocClientBase，不依赖具体实现 |
| 第五步 | 增加 RealIocClient，实现真实 HTTP 调用 |
| 第六步 | 用环境变量切换 mock / real |
| 第七步 | 做契约测试，保证 Mock 和 Real 返回结构一致 |
| 第八步 | 灰度切换，先查询类 Tool 切真实，再考虑动作类 Tool |

### 9.4 验收标准

- [ ] 切真实接口时不改 Graph。
- [ ] 尽量不改 Tool，只改 Client 实现。
- [ ] Mock 与 Real 返回字段通过 adapter 统一成 ToolResult。
- [ ] 真实接口异常仍然转成统一 ToolError。

---

## 10. Tool Center 如何扩展到 MES、ERP、CRM

Tool Center 的价值在于它不是只为 IOC 写死，而是一套企业 AI 访问业务系统的通用模式。

### 10.1 扩展方式

```text
tool_center/
  clients/
    ioc_client_base.py
    mes_client_base.py
    erp_client_base.py
    crm_client_base.py
  tools/
    ioc/
      query/
      analysis/
      action/
    mes/
      query/
      analysis/
      action/
    erp/
      query/
      analysis/
      action/
    crm/
      query/
      analysis/
      action/
```

### 10.2 命名规范

```text
{ioc|mes|erp|crm}_{domain}_{action}_tool
```

示例：

| 系统 | Tool 名称 | 能力 |
|---|---|---|
| IOC | `ioc_alarm_query_tool` | 查询 IOC 告警 |
| IOC | `ioc_risk_query_tool` | 查询 IOC 隐患 |
| MES | `mes_production_plan_query_tool` | 查询生产计划 |
| ERP | `erp_inventory_query_tool` | 查询库存 |
| CRM | `crm_customer_profile_query_tool` | 查询客户信息 |

### 10.3 扩展原则

| 原则 | 说明 |
|---|---|
| 系统隔离 | IOC、MES、ERP、CRM 的 Client 分开 |
| 契约统一 | 所有 Tool 都返回 ToolResult |
| 权限前置 | 不同系统的数据权限必须在 Tool / Client 层校验 |
| Evidence 一致 | 不同系统都要返回来源证据 |
| Action 谨慎 | 涉及业务修改必须人工确认 |

一句话：

```text
Tool Center 是企业 AI 的业务能力网关；IOC 是第一个接入场景，MES、ERP、CRM 是后续扩展系统。
```

---

## 11. Sprint3 推荐开发顺序

### 11.1 最小闭环优先级

建议你不要一开始写太多 Tool，而是先打通最小闭环：

```text
BaseTool → ToolResult → MockIocClient → KpiQueryTool → Test → Graph Node 示例
```

打通后再复制扩展到 Alarm、Risk、WorkOrder。

### 11.2 详细开发步骤

| 顺序 | 任务 | 目标 | 输出文件 | 验收 |
|---|---|---|---|---|
| 1 | 建目录 | 建 Tool Center 基础结构 | `tool_center/*` | 目录清晰，职责明确 |
| 2 | 写 DTO | 统一输入输出模型 | `schemas.py` | Pydantic 校验通过 |
| 3 | 写异常 | 统一 ToolError | `exceptions.py` | 错误码清晰 |
| 4 | 写 Trace | 统一调用日志 | `trace.py` | 成功/失败可记录 |
| 5 | 写 BaseTool | 统一执行模板 | `base_tool.py` | 子类只实现 `_execute` |
| 6 | 写 Mock Data | 模拟业务数据 | `mock_data/*.json` | 数据可读、可过滤、已脱敏 |
| 7 | 写 Mock Client | 统一数据访问接口 | `mock_ioc_client.py` | Tool 不直接读文件 |
| 8 | 写 KPI Tool | 第一个 Query Tool | `kpi_tool.py` | 成功返回 ToolResult |
| 9 | 写 KPI 测试 | 保证最小闭环稳定 | `test_kpi_tool.py` | 成功/失败/空数据 |
| 10 | 写 Alarm Tool | 扩展告警查询 | `alarm_tool.py` | 可按等级/状态过滤 |
| 11 | 写 Risk Tool | 扩展隐患查询 | `risk_tool.py` | 可按等级/状态过滤 |
| 12 | 写 WorkOrder Tool | 扩展工单查询 | `work_order_tool.py` | 可按状态过滤 |
| 13 | 写 Analysis Tool | 做确定性统计 | `analysis/*.py` | 不调用 LLM |
| 14 | 写 Action Draft Tool | 生成工单草稿 | `action/*.py` | 必须人工确认 |
| 15 | 写 Registry | 统一管理 Tool | `registry.py` | 可注册和获取 Tool |
| 16 | 接入 Graph Node 示例 | Node 调用 Tool | `fetch_kpi_node.py` | ToolResult 写入 State |
| 17 | 完成 Review | 输出总结与面试答案 | `docs/*` | 能讲清架构价值 |

---

## 12. 每日推进建议

如果 Sprint3 规划为 5 天，可以这样推进。

### Day 1：基础契约与目录

目标：完成 Tool Center 的基础骨架。

任务：

- [ ] 创建 `tool_center` 目录。
- [ ] 定义 `ToolContext`、`BaseToolInput`、`ToolResult`、`Evidence`、`ToolError`。
- [ ] 定义 `ToolException` 和错误码。
- [ ] 初步实现 `ToolTraceRecord`。
- [ ] 写 `test_tool_schema.py` 验证 DTO。

产出：

```text
schemas.py
exceptions.py
trace.py
test_tool_schema.py
```

Review 重点：

- DTO 是否统一。
- 错误码是否清晰。
- 是否为后续权限、审计、trace 预留字段。

---

### Day 2：BaseTool + Mock Client

目标：完成 Tool 统一执行流程和 Mock 数据访问。

任务：

- [ ] 实现 `BaseTool.run()`。
- [ ] 实现成功/失败结果包装。
- [ ] 实现 trace start/end。
- [ ] 创建 Mock 数据文件。
- [ ] 实现 `IocClientBase` 和 `MockIocClient`。
- [ ] 写 BaseTool 测试。

产出：

```text
base_tool.py
ioc_client_base.py
mock_ioc_client.py
mock_data/*.json
test_base_tool.py
test_mock_ioc_client.py
```

Review 重点：

- 子类是否只需要实现 `_execute()`。
- 异常是否都被 ToolResult 包装。
- Mock Client 是否和 Tool 解耦。

---

### Day 3：Query Tool 最小闭环

目标：完成 KPI、Alarm、Risk 查询 Tool。

任务：

- [ ] 实现 `KpiQueryTool`。
- [ ] 实现 `AlarmQueryTool`。
- [ ] 实现 `RiskQueryTool`。
- [ ] 每个 Tool 返回 data + evidence。
- [ ] 写成功/空数据/参数错误测试。

产出：

```text
kpi_tool.py
alarm_tool.py
risk_tool.py
test_kpi_tool.py
test_alarm_tool.py
test_risk_tool.py
```

Review 重点：

- Tool 是否只查数据，不做 LLM 推理。
- 返回是否统一 ToolResult。
- evidence 是否能支撑数据来源。

---

### Day 4：Analysis Tool + Action Draft Tool

目标：完成聚合分析和动作草稿能力。

任务：

- [ ] 实现 `KpiAnalysisTool`。
- [ ] 实现 `AlarmAnalysisTool`。
- [ ] 实现 `RiskAnalysisTool`。
- [ ] 实现 `WorkOrderDraftTool`。
- [ ] Action Tool 输出必须带 `requires_human_confirmation=true`。

产出：

```text
kpi_analysis_tool.py
alarm_analysis_tool.py
risk_analysis_tool.py
work_order_action_tool.py
```

Review 重点：

- Analysis Tool 是否只做确定性统计。
- Action Tool 是否没有直接执行真实动作。
- 是否能被 Graph 后续接入。

---

### Day 5：Registry + Graph Node 示例 + Review

目标：完成 Sprint3 可演示闭环。

任务：

- [ ] 实现 `ToolRegistry`。
- [ ] 编写 `build_tool_registry()`。
- [ ] 编写一个 Graph Node 调用示例。
- [ ] 完成工具调用失败处理示例。
- [ ] 完成 Sprint3 Review 文档。
- [ ] 整理面试问题答案。

产出：

```text
registry.py
fetch_kpi_node.py
operation_state.py
sprint3_tool_center_review.md
```

Review 重点：

- Graph 是否通过 Tool Center 访问业务能力。
- Tool 失败时 Graph 是否有兜底策略。
- 是否能讲清 Tool Center 的企业价值。

---

## 13. Graph Node 调用示例

### 13.1 Node 示例

```python
def fetch_kpi_node(state: OperationState) -> OperationState:
    registry = state["tool_registry"]
    tool = registry.get("ioc_kpi_query_tool")

    tool_input = KpiQueryInput(
        context=ToolContext(
            user_id=state.get("user_id"),
            tenant_id=state.get("tenant_id"),
            request_id=state.get("request_id"),
        ),
        factory_id=state["factory_id"],
        metric_codes=state.get("metric_codes", []),
        start_time=state["start_time"],
        end_time=state["end_time"],
    )

    result = tool.run(tool_input)

    state.setdefault("tool_results", {})["kpi"] = result.model_dump()

    if result.success:
        state.setdefault("evidence", []).extend([e.model_dump() for e in result.evidence])
        state["next_step"] = "fetch_alarm"
    else:
        state.setdefault("tool_errors", []).append(result.error.model_dump())
        state["next_step"] = "handle_tool_error"

    return state
```

### 13.2 你需要理解的重点

```text
Node 不关心 KPI 数据从 Mock 还是 Real API 来。
Node 只关心 ToolResult 是否成功，以及如何把结果写入 State。
```

---

## 14. 测试方案

### 14.1 单元测试

| 测试对象 | 测试内容 |
|---|---|
| DTO | 必填字段、类型校验、默认值 |
| BaseTool | 成功包装、异常包装、trace_id 生成 |
| MockClient | 参数过滤、空数据、文件不存在 |
| QueryTool | 成功查询、空结果、参数错误 |
| AnalysisTool | 聚合统计是否正确 |
| ActionTool | 是否必须人工确认 |
| Registry | 注册、查找、Tool 不存在 |

### 14.2 集成测试

测试完整链路：

```text
Graph Node → ToolRegistry → KpiQueryTool → MockIocClient → ToolResult → State
```

验收标准：

- [ ] ToolResult 能写入 State。
- [ ] evidence 能向后传递。
- [ ] Tool 失败不会导致程序崩溃。
- [ ] Graph 能进入错误处理分支。

### 14.3 异常测试

必须覆盖：

- [ ] 参数缺失。
- [ ] 参数类型错误。
- [ ] Mock 数据为空。
- [ ] Mock 数据文件不存在。
- [ ] Client 抛出超时异常。
- [ ] Tool 内部未知异常。
- [ ] Registry 找不到 Tool。

---

## 15. Code Review Checklist

### 15.1 Tool 设计

- [ ] Tool 命名是否清晰，例如 `ioc_kpi_query_tool`。
- [ ] Tool 是否单一职责。
- [ ] Tool 是否没有写 Prompt。
- [ ] Tool 是否没有调用 LLM。
- [ ] Tool 是否没有直接访问数据库。
- [ ] Tool 是否没有返回 ORM 对象。
- [ ] Tool 是否返回统一 ToolResult。

### 15.2 DTO 与结构化

- [ ] 入参是否用 Pydantic 定义。
- [ ] 输出是否包含 `success/data/evidence/error/trace_id/metadata`。
- [ ] 错误结构是否稳定。
- [ ] 空数据处理是否统一。

### 15.3 Trace 与审计

- [ ] 每次调用是否有 trace_id。
- [ ] 成功和失败是否都记录。
- [ ] 是否记录耗时。
- [ ] 是否避免记录敏感字段明文。

### 15.4 Mock 与真实接口切换

- [ ] Tool 是否只依赖 Client 抽象接口。
- [ ] Mock Client 与未来 Real Client 方法是否一致。
- [ ] 是否可通过配置切换。

### 15.5 Graph 集成

- [ ] Graph Node 是否通过 ToolRegistry 获取 Tool。
- [ ] Node 是否没有写接口调用细节。
- [ ] Tool 失败是否有明确处理。
- [ ] Evidence 是否写入 State。

---

## 16. Sprint3 验收标准

### 16.1 功能验收

- [ ] 可以通过 KPI Tool 查询 Mock KPI 数据。
- [ ] 可以通过 Alarm Tool 查询 Mock 告警数据。
- [ ] 可以通过 Risk Tool 查询 Mock 隐患数据。
- [ ] 可以通过 WorkOrder Tool 查询 Mock 工单数据。
- [ ] 可以通过 Analysis Tool 对查询结果做聚合统计。
- [ ] 可以通过 Action Tool 生成工单草稿。
- [ ] 所有 Tool 返回统一 ToolResult。
- [ ] 每个 Tool 调用都有 trace_id。

### 16.2 架构验收

- [ ] Agent 不直接访问数据库。
- [ ] Graph 不直接调用 IOC API。
- [ ] Tool 不调用 LLM。
- [ ] Query Tool 不执行业务动作。
- [ ] Action Tool 不越过人工确认。
- [ ] Mock 与真实 IOC API 边界清晰。
- [ ] Tool Center 可扩展到其他业务系统。

### 16.3 工程验收

- [ ] 每个核心 Tool 有单元测试。
- [ ] 失败场景有测试。
- [ ] 目录结构清晰。
- [ ] 命名规范一致。
- [ ] 代码可读、可复用。
- [ ] Review 文档能解释设计价值。

---

## 17. Sprint3 总结模板

Sprint3 完成后，你需要能用下面的结构复盘。

### 17.1 我完成了什么

```text
本 Sprint 我完成了 Tool Center 的基础建设，包括统一 Tool SDK、Tool 输入输出 DTO、Mock IOC Client、KPI/Alarm/Risk/WorkOrder Query Tool、Analysis Tool、Action Draft Tool、Tool Trace 和 Graph Node 调用示例。
```

### 17.2 我解决了什么问题

```text
解决了 Agent 直接访问业务系统不安全、不稳定、不可审计的问题。通过 Tool Center 将业务能力统一封装，让 Agent 只通过结构化 ToolResult 获取数据，并通过 evidence 追溯数据来源。
```

### 17.3 我对架构的理解

```text
Graph 负责流程编排，Node 负责流程步骤，Tool 负责封装 Agent 可调用的业务能力，Service 负责后端业务实现，Client 负责连接具体外部系统。Tool Center 是 Agent 和业务系统之间的安全边界。
```

### 17.4 我还需要继续加强什么

```text
后续需要加强真实 IOC API 接入、权限校验、动作确认流、异步任务、Tool 性能监控，以及更多业务系统如 MES、ERP、CRM 的 Tool 扩展。
```

---

## 18. 企业面试口径

### Q1：为什么企业 Agent 必须通过 Tool 访问数据？

企业 Agent 不能直接访问数据库，因为直接访问会带来权限绕过、敏感数据泄露、SQL 风险、审计困难和系统强耦合问题。Tool Center 作为安全边界，把底层数据库或业务 API 封装成受控的业务能力，并统一做参数校验、权限控制、异常封装、结构化返回和调用追踪。这样 Agent 只拿到被允许、被过滤、可解释的数据。

### Q2：Tool Center 如何解决系统扩展问题？

Tool Center 把不同业务系统的能力统一封装成标准 Tool。每个 Tool 都遵守统一的输入输出契约和 Trace 规范。后续接入 MES、ERP、CRM 时，只需要新增对应系统的 Client 和 Tool，不需要改 Graph 的核心编排逻辑。Graph 面向的是 Tool 能力，而不是某一个具体系统的接口。

### Q3：Tool 和普通后端 Service 有什么区别？

Service 是后端系统内部的业务实现层，通常承载业务规则、数据读写和事务处理；Tool 是 Agent 系统访问业务能力的安全适配层，它面向 Agent/Graph，强调结构化输出、证据来源、异常封装和审计追踪。Tool 可以调用 Service 或 API，但不应该把 Service 的复杂实现暴露给 Agent。

### Q4：如果 Tool 调用失败，Graph 应该怎么处理？

Tool 失败时不应该直接抛异常让 Graph 崩溃，而是返回统一的 ToolResult，其中包含 error.code 和 retryable。Graph 根据错误类型决定下一步：参数错误进入补参分支，权限错误直接终止，网络或超时错误可以有限重试，空数据进入无数据分支，内部错误进入兜底分支。重试必须有次数限制，不能无限循环。

### Q5：Tool 返回数据为什么要带 evidence？

Evidence 用来说明数据来源和结论依据。企业 AI 系统的输出必须可解释、可审计、可追溯。如果 Agent 最终说“某工厂高风险告警增加”，就必须能追溯到具体告警记录、来源系统和时间。Evidence 可以减少幻觉，提高用户对 Agent 结论的信任。

### Q6：如何把 Tool Center 扩展到 MES、ERP、CRM？

扩展方式是保持 ToolResult、ToolError、Evidence、Trace 这些基础契约不变，然后为不同系统增加独立 Client 和 Tool。例如 `MesProductionPlanQueryTool`、`ErpInventoryQueryTool`、`CrmCustomerProfileQueryTool`。Graph 不直接依赖某个系统接口，而是依赖 Tool 能力，因此系统扩展时主要新增 Tool，不破坏已有流程。

### Q7：Tool 能不能调用 LLM？

一般不建议 Query Tool 和 Analysis Tool 调用 LLM。Query Tool 负责取数，Analysis Tool 负责确定性聚合，LLM 推理应该放在 Graph 的分析节点中。这样职责清晰，便于测试和追踪。未来如果确实需要 LLM Tool，应该单独归类为 AI Tool，不和业务数据 Tool 混在一起。

### Q8：为什么 Action Tool 不能直接执行业务动作？

企业系统中的动作可能影响生产、工单、审批、设备和人员安排。如果 Agent 直接执行，风险很高。Sprint3 阶段 Action Tool 只生成动作草稿，并标记 `requires_human_confirmation=true`，后续由人工确认后再执行。这样既能发挥 Agent 的辅助决策能力，又能控制业务风险。

---

## 19. Sprint3 最终完成定义 Definition of Done

当下面条件全部满足时，Sprint3 可以认为完成：

- [ ] Tool Center 目录已建立。
- [ ] BaseTool 可被所有 Tool 继承。
- [ ] ToolResult / ToolError / Evidence / ToolContext 已统一。
- [ ] Mock IOC Client 可返回 KPI、Alarm、Risk、WorkOrder 数据。
- [ ] KPI、Alarm、Risk 至少三个 Query Tool 已完成。
- [ ] 至少一个 Analysis Tool 已完成。
- [ ] 至少一个 Action Draft Tool 已完成。
- [ ] Tool Trace 可记录调用日志。
- [ ] ToolRegistry 可统一注册和获取 Tool。
- [ ] 至少一个 Graph Node 示例能调用 Tool。
- [ ] 单元测试覆盖核心成功与失败场景。
- [ ] 你能讲清 Tool、Graph、Node、Service 的区别。
- [ ] 你能讲清为什么 Tool Center 是企业 AI 的安全边界。
- [ ] 你能讲清如何从 Mock 平滑替换到真实 IOC API。

---

## 20. 本 Sprint 最重要的架构认知

```text
Sprint0：确定项目方向和业务价值。
Sprint1：建立业务分析和产品需求框架。
Sprint2：建立 Agent / Graph 的流程意识。
Sprint3：建立 Tool Center，让 Agent 安全、稳定、可审计地访问业务能力。
```

Tool Center 是你从“会调 LangGraph API”走向“能设计企业 Agent 系统”的关键一步。

这一步做扎实后，你的项目不再只是 Prompt Demo，而是具备了企业级 AI 应用的基础架构：

```text
有边界、有契约、有追踪、有测试、有 Mock、有扩展。
```

