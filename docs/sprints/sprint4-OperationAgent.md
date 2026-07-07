# Sprint4：Operation Agent（运营分析智能体）详细实施方案

> Sprint主题：Operation Graph 的设计、实现与前端接入  
> 项目背景：IOC 智能运营中心 Agent 项目  
> 核心目标：在现有 IOC 项目中建设一个轻量 Operation Agent 能力模块，实现从运营中心页面数据到 AI 分析结论的完整闭环。

---

## 0. Sprint4 一句话目标

Sprint4 的目标不是“在页面右侧生成几句 AI 文案”，而是建设 IOC 项目中的 **Operation Agent 最小纵向闭环**：

```text
页面上下文
  ↓
Operation API
  ↓
Operation Graph
  ↓
Tool Center 获取运营数据
  ↓
规则识别异常
  ↓
LLM 分析原因与生成建议
  ↓
前端诊断区展示结果
```

最终你要完成的是一套可演示、可追踪、可扩展的运营分析智能体能力：

```text
运营数据 → 异常识别 → 原因分析 → 风险排序 → 建议生成 → Markdown 输出 → 前端展示
```

Sprint4 不做“大而全智能运营平台”，先完成一个 **本质安全分析最小闭环**，后续再扩展设备运维、经营改善、专家问答、日报/月报。

---

## 1. Sprint4 核心目标

| 目标 | 说明 | 本 Sprint 要做到什么程度 |
|---|---|---|
| Operation Graph | 编排运营分析流程 | 明确 Start、Node、Edge、End，跑通最小 Graph |
| Operation State | 管理运营分析上下文 | 保存用户、页面、指标、异常、建议、证据、最终答案 |
| Query Node | 查询运营数据 | Node 通过 Tool Center 获取 Mock 运营数据 |
| Analysis Node | 识别异常、分析原因 | 规则判断异常，LLM 辅助原因分析 |
| Advice Node | 生成建议动作 | 输出可执行建议，不输出空泛管理话术 |
| Summary Node | 生成最终分析结果 | 输出稳定 Markdown，可展示在前端诊断区 |
| Operation Prompt | 约束 LLM 输出 | system、analysis、advice、summary Prompt 分层 |
| Operation API | 对前端提供分析接口 | 提供 `/api/operation/analyze` |
| Streaming | 流式输出 | P1 实现，先普通返回，再接 SSE |

---

## 2. Sprint4 交付物清单

| 编号 | 交付物 | 文件/模块 | 优先级 | 验收标准 |
|---|---|---|---|---|
| D4-01 | Operation State | `backend/app/operation_agent/state.py` | P0 | State 字段清晰，可贯穿 Graph |
| D4-02 | Operation Graph | `backend/app/operation_agent/graph.py` | P0 | Graph 可执行，节点顺序清晰 |
| D4-03 | Init Node | `backend/app/operation_agent/nodes/init_context_node.py` | P0 | 能初始化 trace、user_context、page_context |
| D4-04 | Query Node | `backend/app/operation_agent/nodes/query_operation_data_node.py` | P0 | 能通过 Tool Center 获取 Mock 数据 |
| D4-05 | Abnormal Node | `backend/app/operation_agent/nodes/detect_abnormal_node.py` | P0 | 能基于规则识别异常指标 |
| D4-06 | Reason Node | `backend/app/operation_agent/nodes/analyze_reason_node.py` | P0 | 能调用 LLM 生成原因分析 |
| D4-07 | Advice Node | `backend/app/operation_agent/nodes/generate_advice_node.py` | P0 | 能生成结构化建议 |
| D4-08 | Summary Node | `backend/app/operation_agent/nodes/summary_node.py` | P0 | 能输出 Markdown 分析结论 |
| D4-09 | Prompt | `backend/app/operation_agent/prompts/*.md` | P0 | Prompt 模板化，不写死业务数据 |
| D4-10 | Operation API | `backend/app/api/routes/operation_api.py` | P0 | 前端可调用分析接口 |
| D4-11 | Frontend Diagnosis | `frontend/.../OperationDashboard.vue` | P1 | 右侧诊断区域可展示 AI 结果 |
| D4-12 | Streaming API | `backend/app/api/routes/operation_stream_api.py` | P1 | 支持 SSE 流式返回 |
| D4-13 | Tests | `backend/tests/operation_agent/*` | P1 | 覆盖 Graph、Node、Prompt、API 基础测试 |
| D4-14 | Sprint4 Review | `docs/sprint4_operation_agent_review.md` | P1 | 能讲清 Graph、State、Node、LLM 边界 |

---

## 3. Operation Agent 在 IOC 系统中的位置

### 3.1 总体调用链

```text
企业用户进入运营中心首页
  ↓
前端读取当前页面上下文：业务域 / 时间维度 / 企业 / 项目
  ↓
调用 Operation API
  ↓
Operation Graph 启动
  ↓
InitContextNode 初始化上下文
  ↓
QueryOperationDataNode 调用 Tool Center 获取数据
  ↓
DetectAbnormalNode 识别异常
  ↓
AnalyzeReasonNode 调用 LLM 分析原因
  ↓
GenerateAdviceNode 调用 LLM 生成建议
  ↓
SummaryNode 生成 Markdown 结果
  ↓
API 返回结构化 JSON + Markdown
  ↓
前端右侧诊断区域展示
```

### 3.2 一句话理解

```text
前端负责触发和展示；
API 负责接收请求和返回结果；
Graph 负责流程编排；
Node 负责单个步骤；
Tool Center 负责获取业务数据；
LLM 负责原因解释、建议生成和摘要表达。
```

### 3.3 Sprint4 的边界

Sprint4 只做 **Operation Agent 最小闭环**。

暂不做：

```text
复杂多轮对话
长期记忆
多 Agent 协作
自动执行工单
真实生产系统写操作
全量日报/月报
复杂权限系统
```

当前 Sprint 主线：

```text
Operation State
  ↓
Operation Graph
  ↓
Query Node 调用 Tool Center
  ↓
异常识别 Node
  ↓
LLM 分析 Node
  ↓
Summary Node
  ↓
Operation API
  ↓
前端诊断区展示
```

---

## 4. 关键架构原则

### 4.1 Graph 不等于简单函数调用

普通函数链：

```text
analyze()
  ↓
query_data()
  ↓
call_llm()
  ↓
return result
```

Operation Graph：

```text
START
  ↓
InitContextNode
  ↓
QueryOperationDataNode
  ↓
DetectAbnormalNode
  ↓
AnalyzeReasonNode
  ↓
GenerateAdviceNode
  ↓
SummaryNode
  ↓
END
```

Graph 的价值：

| 能力 | 说明 |
|---|---|
| 流程显式 | 每一步分析流程清楚可见 |
| 状态显式 | State 贯穿节点执行过程 |
| 边界清晰 | 每个 Node 只做一件事 |
| 可测试 | Node 可以单独测试 |
| 可追踪 | trace_id 贯穿 Graph、Tool、LLM |
| 可扩展 | 后续可增加设备运维、经营改善、日报、问答 |
| 可降级 | Tool 失败、LLM 失败可进入兜底分支 |

### 4.2 LLM 不负责直接查数据

错误方式：

```text
页面数据 → 拼 Prompt → LLM 自己判断
```

正确方式：

```text
页面上下文
  ↓
Tool Center 查询结构化数据
  ↓
规则节点识别异常
  ↓
LLM 基于结构化数据做解释和建议
```

原则：

```text
数据获取：Tool Center
异常识别：规则优先
原因分析：LLM 辅助
建议生成：LLM 辅助
最终输出：结构化结果 + Markdown
```

### 4.3 Node 不直接访问数据库

推荐链路：

```text
Node → Tool Center → Mock IOC Client / Real IOC Client → IOC API / DB
```

Node 只关心：

```text
我要什么业务数据？
ToolResult 是否成功？
返回的数据如何写入 State？
```

Node 不关心：

```text
数据从哪个表查
接口地址是什么
SQL 怎么写
第三方系统如何鉴权
```

### 4.4 Prompt 不写死业务数据

错误方式：

```text
当前缺陷总数为 0，请分析……
```

正确方式：

```text
当前页面上下文：
{page_context}

当前指标数据：
{metrics}

当前异常项：
{abnormal_items}

请基于以上数据分析……
```

Prompt 是模板，业务数据来自 State。

### 4.5 输出必须包含 evidence

企业项目里，AI 结论必须能解释来源。

最终结果至少包含：

```json
{
  "summary": "...",
  "abnormal_items": [],
  "risk_items": [],
  "advice_items": [],
  "evidence": []
}
```

没有 evidence 的结论只能算“模型观点”，不能算企业级运营分析结论。

---

## 5. 推荐项目目录结构

```text
backend/
  app/
    operation_agent/
      __init__.py
      state.py                         # OperationState 定义
      graph.py                         # Operation Graph 构建
      service.py                       # 对外封装 Graph 调用

      nodes/
        __init__.py
        init_context_node.py            # 初始化上下文
        query_operation_data_node.py    # 调用 Tool 获取运营数据
        normalize_metric_node.py        # 指标标准化，P1
        detect_abnormal_node.py         # 异常识别
        analyze_reason_node.py          # 原因分析，调用 LLM
        rank_risk_node.py               # 风险排序，P1
        generate_advice_node.py         # 建议生成，调用 LLM
        summary_node.py                 # 总结输出，调用 LLM
        fallback_node.py                # 失败兜底，P1

      prompts/
        system_prompt.md
        operation_analysis.md
        operation_advice.md
        operation_summary.md

      schemas/
        request.py                      # API 请求 DTO
        response.py                     # API 响应 DTO

      tests/
        test_state.py
        test_graph.py
        test_nodes.py

    api/
      routes/
        operation_api.py                # /api/operation/analyze
        operation_stream_api.py         # /api/operation/analyze/stream，P1

frontend/
  src/
    views/
      operation/
        OperationDashboard.vue
        components/
          OperationDiagnosisPanel.vue
          OperationRiskList.vue
          OperationAdviceList.vue
```

---

## 6. Operation Graph 主流程设计

### 6.1 Sprint4 第一版主流程

第一版不要做复杂分支，先打通最小闭环：

```text
START
  ↓
InitContextNode
  ↓
QueryOperationDataNode
  ↓
DetectAbnormalNode
  ↓
AnalyzeReasonNode
  ↓
GenerateAdviceNode
  ↓
SummaryNode
  ↓
END
```

### 6.2 Sprint4 完整目标流程

```text
START
  ↓
InitContextNode
  ↓
RouteIntentNode
  ↓
QueryOperationDataNode
  ↓
NormalizeMetricNode
  ↓
DetectAbnormalNode
  ↓
AnalyzeReasonNode
  ↓
RankRiskNode
  ↓
GenerateAdviceNode
  ↓
SummaryNode
  ↓
END
```

### 6.3 三种入口规划

| 入口 | trigger_type | analysis_mode | 第一版是否做 |
|---|---|---|---|
| 用户进入首页自动分析 | `page_load` | `dashboard_snapshot` | P1 |
| 用户切换 Tab 后点击分析 | `tab_analysis` | `domain_focus` | P0 |
| 用户与运营专家问答 | `expert_chat` | `qa` | P2 |

Sprint4 第一版优先做：

```text
trigger_type = tab_analysis
domain = safety
analysis_mode = domain_focus
```

也就是：

```text
用户点击“本质安全分析”
  ↓
后端分析本质安全数据
  ↓
前端诊断区展示结果
```

---

## 7. Operation State 设计

### 7.1 State 设计目标

Operation State 不是普通 dict，而是 Graph 执行过程中的业务上下文容器。

它要回答：

```text
谁在分析？
分析哪个页面？
分析哪个业务域？
查到了哪些数据？
识别了哪些异常？
生成了哪些建议？
最终输出什么？
有哪些数据依据？
```

### 7.2 第一版 State 字段

```python
from typing import TypedDict, Literal, Optional

OperationDomain = Literal["safety", "maintenance", "business", "all"]
TriggerType = Literal["page_load", "tab_analysis", "expert_chat", "scheduled_daily"]
AnalysisMode = Literal["dashboard_snapshot", "domain_focus", "qa"]


class OperationState(TypedDict, total=False):
    trace_id: str

    trigger_type: TriggerType
    analysis_mode: AnalysisMode
    user_question: Optional[str]

    user_context: dict
    page_context: dict

    raw_data: dict
    metrics: list[dict]

    abnormal_items: list[dict]
    reason_analysis: str
    risk_items: list[dict]
    advice_items: list[dict]

    evidence: list[dict]
    final_answer: str

    errors: list[dict]
```

### 7.3 State 字段说明

| 字段 | 说明 | 来源 |
|---|---|---|
| `trace_id` | 当前分析链路 ID | InitContextNode |
| `trigger_type` | 触发方式 | API 请求 |
| `analysis_mode` | 分析模式 | RouteIntentNode |
| `user_context` | 用户、组织、角色、权限 | API / 登录态 |
| `page_context` | 页面筛选条件 | 前端请求 |
| `raw_data` | Tool 返回原始数据 | Query Node |
| `metrics` | 标准化指标 | Query / Normalize Node |
| `abnormal_items` | 异常项 | DetectAbnormalNode |
| `reason_analysis` | 原因分析文本 | AnalyzeReasonNode |
| `risk_items` | 风险排序 | RankRiskNode |
| `advice_items` | 建议动作 | GenerateAdviceNode |
| `evidence` | 数据依据 | ToolResult / Node |
| `final_answer` | 最终 Markdown | SummaryNode |
| `errors` | 失败信息 | 各 Node |

---

## 8. Node 设计

### 8.1 Node 总览

| Node | 是否调用 Tool | 是否调用 LLM | 职责 |
|---|---:|---:|---|
| InitContextNode | 否 | 否 | 初始化上下文 |
| QueryOperationDataNode | 是 | 否 | 调用 Tool 获取业务数据 |
| NormalizeMetricNode | 否 | 否 | 指标标准化，P1 |
| DetectAbnormalNode | 否 | 否 | 基于规则识别异常 |
| AnalyzeReasonNode | 否 | 是 | 基于指标和异常分析原因 |
| RankRiskNode | 否 | 可选 | 对风险进行排序，P1 |
| GenerateAdviceNode | 否 | 是 | 生成建议动作 |
| SummaryNode | 否 | 是 | 生成最终 Markdown |
| FallbackNode | 否 | 可选 | 失败兜底，P1 |

### 8.2 InitContextNode

职责：

```text
将 API 请求转换成 Graph 可执行的标准 State。
```

输入：

```json
{
  "trigger_type": "tab_analysis",
  "domain": "safety",
  "time_dimension": "month",
  "date": "2026-07",
  "company_id": null,
  "project_id": null
}
```

输出到 State：

```python
{
    "trace_id": "op_xxx",
    "trigger_type": "tab_analysis",
    "analysis_mode": "domain_focus",
    "page_context": {
        "domain": "safety",
        "time_dimension": "month",
        "date": "2026-07"
    }
}
```

验收标准：

```text
- [ ] 每次分析都有 trace_id。
- [ ] page_context 字段完整。
- [ ] analysis_mode 能根据 trigger_type 得到。
- [ ] 不调用 LLM。
- [ ] 不调用数据库。
```

### 8.3 QueryOperationDataNode

职责：

```text
根据 page_context 调用 Tool Center 获取运营数据。
```

第一版只查本质安全：

```text
domain = safety
  ↓
调用 KPI / Risk / WorkOrder 相关 Tool
  ↓
获取缺陷总数、缺陷处置率、未处置数量、超期未处理数量
```

输出到 State：

```python
{
    "raw_data": {
        "safety": {...}
    },
    "metrics": [
        {
            "metric_code": "defect_total",
            "metric_name": "缺陷总数",
            "value": 0,
            "unit": "条"
        }
    ],
    "evidence": [...]
}
```

验收标准：

```text
- [ ] Node 通过 Tool Center 获取数据。
- [ ] Node 不直接访问数据库。
- [ ] ToolResult.success=false 时写入 errors。
- [ ] ToolResult.evidence 写入 State。
- [ ] Mock 数据可支撑前端演示。
```

### 8.4 DetectAbnormalNode

职责：

```text
基于规则识别异常指标。
```

第一版规则：

| 指标 | 规则 | 结果 |
|---|---|---|
| 缺陷总数 | `= 0` | 正常或无缺陷 |
| 缺陷未处置 | `> 0` | warning |
| 超期未处理 | `> 0` | high |
| 缺陷处置率 | `< 95 且缺陷总数 > 0` | warning |
| 指标为空 | `value is None / --` | data_missing |

输出到 State：

```python
{
    "abnormal_items": [
        {
            "domain": "safety",
            "metric_code": "overdue_unclosed",
            "metric_name": "超期未处理",
            "severity": "high",
            "description": "存在超期未处理缺陷",
            "evidence": [...]
        }
    ]
}
```

验收标准：

```text
- [ ] 异常识别优先用规则，不依赖 LLM。
- [ ] 0 值不默认判定异常。
- [ ] 空值单独标记为 data_missing。
- [ ] 每个异常项必须带 evidence。
```

### 8.5 AnalyzeReasonNode

职责：

```text
调用 LLM，基于指标、异常项和 evidence 分析可能原因。
```

输入：

```text
page_context
metrics
abnormal_items
evidence
```

输出到 State：

```python
{
    "reason_analysis": "当前本质安全整体平稳，缺陷总数为 0，暂无未处置缺陷。若处置率显示为 0%，需要结合缺陷总数为 0 判断，不能直接认定处置异常。"
}
```

验收标准：

```text
- [ ] LLM 只能基于 State 中的数据分析。
- [ ] Prompt 中明确禁止编造数据。
- [ ] 数据缺失不能直接判断为业务异常。
- [ ] 输出面向企业运营人员。
```

### 8.6 GenerateAdviceNode

职责：

```text
基于异常项和原因分析生成可执行建议。
```

建议结构：

```python
{
    "title": "核查缺陷处置率展示逻辑",
    "priority": "P1",
    "owner_role": "安全运营负责人",
    "action": "确认缺陷总数为 0 时，处置率是否应展示为 100% 或暂无缺陷，而不是 0%。",
    "expected_result": "避免管理人员误判本质安全处置异常。",
    "evidence": [...]
}
```

验收标准：

```text
- [ ] 建议必须可执行。
- [ ] 建议必须包含责任角色。
- [ ] 建议必须包含优先级。
- [ ] 不输出“加强管理、持续关注”这类空泛内容。
```

### 8.7 SummaryNode

职责：

```text
生成最终 Markdown 分析结果。
```

输出格式：

```markdown
## 运营分析结论

### 1. 总体判断
...

### 2. 关键发现
...

### 3. 异常与风险
...

### 4. 建议动作
...

### 5. 数据依据
...
```

验收标准：

```text
- [ ] final_answer 是稳定 Markdown。
- [ ] 前端可直接展示。
- [ ] 包含总体判断、关键发现、建议动作、数据依据。
- [ ] 不暴露后端内部字段。
```

---

## 9. Prompt 设计

### 9.1 Prompt 文件

```text
prompts/
  system_prompt.md
  operation_analysis.md
  operation_advice.md
  operation_summary.md
```

### 9.2 system_prompt.md

```markdown
你是企业级智能运营中心的运营分析专家，负责基于运营数据进行安全、设备、经营等维度的分析。

你的职责：
1. 基于数据给出结论，不编造不存在的数据。
2. 对异常指标进行解释，并给出可能原因。
3. 对风险进行优先级排序。
4. 输出可执行的运营建议。
5. 每个关键结论必须尽量附带数据依据。

你不能：
1. 把数据缺失直接判断为业务异常。
2. 在没有 evidence 的情况下给出确定性结论。
3. 输出泛泛而谈的管理建议。
4. 忽略用户当前页面筛选条件。
```

### 9.3 operation_analysis.md

```markdown
## 任务
请基于以下运营数据，分析当前运营状态、异常指标和可能原因。

## 页面上下文
{page_context}

## 指标数据
{metrics}

## 异常识别结果
{abnormal_items}

## 数据依据
{evidence}

## 分析要求
1. 先判断整体状态：正常、关注、异常、数据不足。
2. 对每个异常项说明可能原因。
3. 对数据缺失项单独说明，不要直接归因为业务异常。
4. 所有结论必须引用指标数据作为依据。
5. 输出内容面向企业运营管理人员。
```

### 9.4 operation_advice.md

```markdown
## 任务
请基于风险项和原因分析，生成可执行的运营建议。

## 异常项
{abnormal_items}

## 原因分析
{reason_analysis}

## 数据依据
{evidence}

## 输出要求
每条建议必须包含：
- 建议标题
- 优先级：P0 / P1 / P2
- 责任角色
- 建议动作
- 预期结果
- 数据依据

避免输出：
- 加强管理
- 持续关注
- 提高意识
这类空泛表达。
```

### 9.5 operation_summary.md

```markdown
## 任务
请生成运营中心首页的最终分析结果。

## 输入
- 页面上下文：{page_context}
- 指标数据：{metrics}
- 异常项：{abnormal_items}
- 原因分析：{reason_analysis}
- 建议动作：{advice_items}

## 输出格式

### 总体判断
用 2-3 句话说明当前运营状态。

### 关键发现
列出 3 条以内关键发现。

### 异常与风险
说明异常指标、风险等级和影响。

### 建议动作
输出可执行建议。

### 数据依据
列出支撑结论的关键指标。
```

---

## 10. Operation API 设计

### 10.1 第一版接口

```http
POST /api/operation/analyze
```

请求：

```json
{
  "trigger_type": "tab_analysis",
  "domain": "safety",
  "active_tab": "本质安全",
  "time_dimension": "month",
  "date": "2026-07",
  "company_id": null,
  "project_id": null
}
```

响应：

```json
{
  "trace_id": "op_xxx",
  "status": "completed",
  "summary": "## 运营分析结论\n...",
  "abnormal_items": [],
  "risk_items": [],
  "advice_items": [],
  "evidence": []
}
```

验收标准：

```text
- [ ] API 不写业务分析逻辑。
- [ ] API 只负责构造初始 State。
- [ ] API 调用 operation_graph.invoke()。
- [ ] API 返回前端需要的数据结构。
```

---

## 11. 前端接入设计

### 11.1 第一版展示位置

第一版直接展示在右侧“诊断”区域。

```text
运营中心首页
  ↓
右侧诊断区域
  ├── AI 分析结论
  ├── 关键发现
  ├── 建议动作
  └── 数据依据
```

### 11.2 前端触发方式

第一版：

```text
用户点击“本质安全分析”
  ↓
调用 /api/operation/analyze
  ↓
展示 loading
  ↓
展示 Markdown 结果
```

后续：

```text
页面加载自动分析
Tab 切换后分析
专家问答分析
SSE 流式输出
```

---

## 12. Streaming 设计

建议放在最小闭环之后实现。

### 12.1 普通返回

```text
前端点击分析
  ↓
等待后端完整执行 Graph
  ↓
一次性展示结果
```

### 12.2 Streaming 返回

```text
前端点击分析
  ↓
SSE 连接
  ↓
后端执行 Graph
  ↓
SummaryNode / LLM token 流式输出
  ↓
前端逐步追加 Markdown 内容
```

### 12.3 原则

```text
Streaming 是 API 层和前端体验层的事情。
不要让所有 Node 都关心 SSE。
Graph 负责产出结果，API 负责流式传输。
```

---

## 13. Sprint4 推荐开发顺序

### 13.1 最小闭环优先级

```text
OperationState
  ↓
InitContextNode
  ↓
QueryOperationDataNode
  ↓
DetectAbnormalNode
  ↓
SummaryNode
  ↓
OperationGraph
  ↓
OperationAPI
  ↓
前端诊断区展示
```

### 13.2 详细开发步骤

| 顺序 | 任务 | 目标 | 输出文件 | 验收 |
|---|---|---|---|---|
| 1 | 建目录 | 建 Operation Agent 基础结构 | `operation_agent/*` | 目录清晰，职责明确 |
| 2 | 写 State | 定义 Graph 上下文 | `state.py` | 字段能覆盖分析流程 |
| 3 | 写 Prompt 模板 | 定义 LLM 输出边界 | `prompts/*.md` | Prompt 不写死业务数据 |
| 4 | 写 Init Node | 初始化上下文 | `init_context_node.py` | 生成 trace_id / page_context |
| 5 | 写 Query Node | 调用 Tool 获取数据 | `query_operation_data_node.py` | 能获取 Mock 数据 |
| 6 | 写异常规则 | 识别异常指标 | `detect_abnormal_node.py` | 能输出 abnormal_items |
| 7 | 写 Summary Node | 生成 Markdown | `summary_node.py` | 能输出 final_answer |
| 8 | 写 Graph | 编排节点流程 | `graph.py` | Graph 可 invoke |
| 9 | 写 API | 前端调用入口 | `operation_api.py` | 返回 summary / evidence |
| 10 | 前端接入 | 展示诊断结果 | `DiagnosisPanel.vue` | 点击分析可展示结果 |
| 11 | 写 Reason Node | LLM 分析原因 | `analyze_reason_node.py` | 输出 reason_analysis |
| 12 | 写 Advice Node | LLM 生成建议 | `generate_advice_node.py` | 输出 advice_items |
| 13 | 补充测试 | 保证闭环稳定 | `tests/*` | 成功/失败/空数据 |
| 14 | 接 Streaming | SSE 流式输出 | `operation_stream_api.py` | 前端可逐步展示 |
| 15 | 完成 Review | 总结与面试表达 | `sprint4_operation_agent_review.md` | 能讲清架构价值 |

---

## 14. 每日推进建议

### Day 1：State + 目录 + 最小业务场景

目标：完成 Operation Agent 基础骨架。

任务：

```text
- [ ] 创建 operation_agent 目录。
- [ ] 明确第一版只做 safety / 本质安全。
- [ ] 定义 OperationState。
- [ ] 定义 page_context、user_context、metrics、abnormal_items、evidence、final_answer。
- [ ] 创建 prompts 目录。
```

产出：

```text
operation_agent/
  state.py
  prompts/
    system_prompt.md
    operation_summary.md
```

Review 重点：

```text
- State 是否过度设计。
- 字段是否能支撑 Graph 执行。
- 是否没有保存 ORM 对象。
```

### Day 2：Init Node + Query Node

目标：完成上下文初始化和数据获取。

任务：

```text
- [ ] 实现 InitContextNode。
- [ ] 实现 QueryOperationDataNode。
- [ ] 通过 Tool Center 获取 Mock 本质安全数据。
- [ ] 将 ToolResult.data 写入 State.raw_data / State.metrics。
- [ ] 将 ToolResult.evidence 写入 State.evidence。
```

产出：

```text
nodes/init_context_node.py
nodes/query_operation_data_node.py
```

Review 重点：

```text
- Node 是否只做单一职责。
- Node 是否通过 Tool Center 获取数据。
- Tool 失败时是否写入 errors。
```

### Day 3：异常识别 + 最小 Summary

目标：完成不依赖 LLM 的基础分析闭环。

任务：

```text
- [ ] 实现 DetectAbnormalNode。
- [ ] 定义本质安全异常规则。
- [ ] 实现 SummaryNode 第一版。
- [ ] 先用模板生成 Markdown，不依赖复杂 Prompt。
```

产出：

```text
nodes/detect_abnormal_node.py
nodes/summary_node.py
```

Review 重点：

```text
- 异常识别是否可解释。
- 0 值是否被误判为异常。
- 数据缺失是否单独处理。
- final_answer 是否能被前端展示。
```

### Day 4：Operation Graph + API

目标：跑通后端完整闭环。

任务：

```text
- [ ] 实现 build_operation_graph()。
- [ ] 添加节点和边。
- [ ] 编写 graph.invoke() 测试。
- [ ] 实现 /api/operation/analyze。
- [ ] API 调用 Graph 并返回结果。
```

产出：

```text
graph.py
service.py
api/routes/operation_api.py
tests/operation_agent/test_graph.py
```

Review 重点：

```text
- Graph 流程是否清晰。
- API 是否没有业务分析逻辑。
- TraceId 是否能贯穿 API、Graph、Tool。
```

### Day 5：LLM Reason + Advice + 前端展示

目标：把结果从“规则摘要”升级为“运营专家分析”。

任务：

```text
- [ ] 实现 AnalyzeReasonNode。
- [ ] 实现 GenerateAdviceNode。
- [ ] 编写 operation_analysis.md。
- [ ] 编写 operation_advice.md。
- [ ] 前端诊断区域接入 API。
- [ ] 展示 summary、advice_items、evidence。
```

产出：

```text
nodes/analyze_reason_node.py
nodes/generate_advice_node.py
prompts/operation_analysis.md
prompts/operation_advice.md
frontend/.../OperationDiagnosisPanel.vue
```

Review 重点：

```text
- LLM 是否只基于 State 数据分析。
- 建议是否可执行。
- evidence 是否展示或可追踪。
- 页面是否能体现 Graph 分析过程。
```

### Day 6：测试 + 失败兜底 + Review

目标：让 Sprint4 具备面试项目表达价值。

任务：

```text
- [ ] 补充 Graph 测试。
- [ ] 补充 Node 测试。
- [ ] 模拟 Tool 空数据。
- [ ] 模拟 Tool 失败。
- [ ] 模拟 LLM 失败。
- [ ] 编写 Sprint4 Review 文档。
- [ ] 整理面试讲法。
```

产出：

```text
tests/operation_agent/test_nodes.py
tests/operation_agent/test_api.py
docs/sprint4_operation_agent_review.md
```

Review 重点：

```text
- Tool 失败时 Graph 是否能降级。
- 空数据是否不会导致错误结论。
- 是否能讲清为什么用 Graph。
- 是否能讲清 Operation Agent 与普通 ChatBot 的区别。
```

---

## 15. Sprint4 验收标准

### 15.1 功能验收

```text
- [ ] 点击本质安全分析按钮后，后端 Graph 可执行。
- [ ] Graph 能获取 Mock 本质安全数据。
- [ ] Graph 能识别异常或正常状态。
- [ ] Graph 能生成 Markdown 分析结果。
- [ ] 前端诊断区能展示分析结果。
- [ ] 输出包含 evidence。
```

### 15.2 架构验收

```text
- [ ] API 不写分析逻辑。
- [ ] Graph 只负责编排。
- [ ] Node 单一职责。
- [ ] Tool Center 负责数据访问。
- [ ] LLM 只在 Reason / Advice / Summary 节点使用。
- [ ] Prompt 模板化。
- [ ] State 字段清晰，不保存 ORM 对象。
```

### 15.3 工程验收

```text
- [ ] Graph 有基础测试。
- [ ] Node 有基础测试。
- [ ] Tool 空数据有处理。
- [ ] Tool 失败有兜底。
- [ ] trace_id 可追踪。
- [ ] Markdown 输出格式稳定。
```

---

## 16. Sprint4 Review 输出模板

```markdown
# Sprint4 Review：Operation Agent

## 1. 本 Sprint 完成内容
- 完成 Operation State 设计。
- 完成 Operation Graph 最小闭环。
- 完成本质安全分析 Node。
- 完成 LLM 分析和建议生成。
- 完成 Operation API。
- 完成前端诊断区展示。

## 2. Graph 为什么这样拆
说明 Init、Query、Detect、Reason、Advice、Summary 的职责边界。

## 3. State 为什么这样设计
说明 user_context、page_context、metrics、abnormal_items、advice_items、evidence、final_answer 的作用。

## 4. 哪些节点调用 LLM，哪些节点不用
说明数据查询和异常识别用规则，原因分析和建议生成用 LLM。

## 5. Operation Agent 与普通 ChatBot 区别
说明它是业务数据驱动，不是闲聊。

## 6. evidence 的价值
说明每个结论都能回溯到指标和 ToolResult。

## 7. 当前不足
- 当前只做本质安全。
- 当前数据为 Mock。
- Streaming 尚未完善。
- 专家问答未接入。

## 8. 下一步计划
- 扩展设备运维。
- 扩展经营改善。
- 接入专家问答。
- 接入 Streaming。
- 生成日报/月报。
```

---

## 17. 企业面试表达

### 17.1 项目介绍

```text
我做的是一个面向企业智能运营中心的 Operation Agent。
它不是普通 ChatBot，而是基于运营中心页面上下文和业务数据进行分析的智能体。

用户在运营中心首页点击分析后，系统会通过 Operation Graph 编排数据查询、异常识别、原因分析、建议生成和摘要输出流程。
其中，数据查询通过 Tool Center 完成，异常识别优先使用规则，原因分析和建议生成由 LLM 完成。
最终结果以结构化 JSON 和 Markdown 返回前端，并展示在诊断区域。
```

### 17.2 为什么使用 Graph

```text
因为运营分析不是一次简单的大模型调用，而是一个稳定的业务流程。
我用 Graph 把流程拆成 InitContext、QueryData、DetectAbnormal、AnalyzeReason、GenerateAdvice、Summary 等节点。
这样每一步都可测试、可追踪、可扩展，也便于后续扩展设备运维、经营改善、日报和专家问答。
```

### 17.3 如何保证结果可信

```text
第一，LLM 不直接查数据，数据来自 Tool Center。
第二，异常识别优先用规则，降低模型误判。
第三，Prompt 明确要求只能基于 State 中的数据分析。
第四，最终输出包含 evidence，可以追踪数据来源。
第五，Tool 失败和空数据会进入兜底逻辑，不会让模型编造结论。
```

---

## 18. Sprint4 Checklist

```text
Business
- [ ] 明确第一版只做本质安全。
- [ ] 明确诊断结果展示位置。
- [ ] 明确页面触发方式。

Thinking
- [ ] 能讲清 Graph 编排价值。
- [ ] 能讲清 State 保存什么。
- [ ] 能讲清 Node 怎么拆。
- [ ] 能讲清 LLM 放在哪些节点。

Design
- [ ] Operation Graph 设计完成。
- [ ] Operation State 设计完成。
- [ ] Prompt 边界设计完成。
- [ ] API 入参出参设计完成。

Coding
- [ ] state.py 完成。
- [ ] graph.py 完成。
- [ ] nodes 完成。
- [ ] prompts 完成。
- [ ] operation_api.py 完成。
- [ ] 前端诊断区接入完成。

Testing
- [ ] Graph invoke 测试完成。
- [ ] Node 单测完成。
- [ ] API 测试完成。
- [ ] 空数据测试完成。
- [ ] Tool 失败测试完成。

Review
- [ ] 输出 Sprint4 Review。
- [ ] 总结 Graph 拆分原因。
- [ ] 总结 State 字段设计。
- [ ] 总结 Agent 与 ChatBot 区别。
- [ ] 总结 evidence 的企业价值。

Interview
- [ ] 准备项目介绍。
- [ ] 准备为什么用 Graph。
- [ ] 准备如何保证可信。
- [ ] 准备如何扩展日报/月报。
- [ ] 准备模型不稳定时的架构控制。
```

---

## 19. 本 Sprint 最终目标

Sprint4 完成后，你应该能够演示这条链路：

```text
用户点击“本质安全分析”
  ↓
前端调用 Operation API
  ↓
API 构造 OperationState
  ↓
Operation Graph 启动
  ↓
Query Node 通过 Tool Center 获取 Mock 数据
  ↓
Detect Node 识别异常
  ↓
LLM Node 分析原因、生成建议
  ↓
Summary Node 输出 Markdown
  ↓
前端右侧诊断区域展示
```

最终你要能讲清楚：

```text
页面只是展示入口；
Graph 是分析流程；
State 是上下文载体；
Node 是执行步骤；
Tool 是数据入口；
LLM 是分析和表达能力；
evidence 是企业可信基础。
```

这就是 Sprint4 真正要沉淀的 Agent 工程能力。
