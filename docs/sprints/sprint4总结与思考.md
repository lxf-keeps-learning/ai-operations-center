# Sprint4 Operation Agent 实现总结

## 1. 本次完成内容

Sprint4 完成了 Operation Agent（运营分析智能体）的最小闭环建设。实现了从"页面上下文 → 数据查询 → 异常识别 → 原因分析 → 建议生成 → Markdown 输出"的完整分析链路，优先聚焦**本质安全 safety** 领域。

第一版使用 LangGraph 编排 7 个 Node，复用 Sprint3 的 Tool Center 获取运营数据，通过 DeepSeek LLM 做原因分析和建议生成，异常识别使用纯规则。

---

## 2. 新增文件

### 后端核心 (15 个)

| 文件 | 说明 |
|------|------|
| `operation_agent/__init__.py` | 模块入口 |
| `operation_agent/state.py` | OperationState TypedDict（15 个字段） |
| `operation_agent/graph.py` | LangGraph StateGraph 编排器 |
| `operation_agent/service.py` | 供 API 调用的业务入口 |
| `operation_agent/api.py` | POST /api/v1/operation/analyze 路由 |
| `operation_agent/nodes/__init__.py` | nodes 子模块 |
| `operation_agent/nodes/init_context_node.py` | 初始化 State |
| `operation_agent/nodes/query_operation_data_node.py` | 调 Tool Center 查 KPI 数据 |
| `operation_agent/nodes/detect_abnormal_node.py` | 纯规则检测异常 |
| `operation_agent/nodes/analyze_reason_node.py` | LLM 分析原因 |
| `operation_agent/nodes/generate_advice_node.py` | LLM/兜底生成建议 |
| `operation_agent/nodes/summary_node.py` | 组装 Markdown 结论 |
| `operation_agent/schemas/__init__.py` | schemas 子模块 |
| `operation_agent/schemas/request.py` | OperationAnalyzeRequest |
| `operation_agent/schemas/response.py` | OperationAnalyzeResponse |

### Prompt 文件 (4 个)

| 文件 | 说明 |
|------|------|
| `operation_agent/prompts/system_prompt.md` | 系统角色定义 |
| `operation_agent/prompts/operation_analysis.md` | 原因分析 Prompt |
| `operation_agent/prompts/operation_advice.md` | 建议生成 Prompt |
| `operation_agent/prompts/operation_summary.md` | 汇总 Prompt（预留） |

### 测试与调试 (3 个)

| 文件 | 说明 |
|------|------|
| `tests/operation_agent/__init__.py` | 测试子模块 |
| `tests/operation_agent/test_operation_graph.py` | 10 个集成测试用例 |
| `scripts/debug_operation_agent.py` | 本地调试脚本 |

### 前端 (2 个)

| 文件 | 说明 |
|------|------|
| `frontend/src/api/operation.ts` | 前端 API 层 |
| `frontend/src/pages/operation/IndexPage.vue` | 运营分析页面 |

---

## 3. 修改文件

| 文件 | 变更 |
|------|------|
| `backend/pyproject.toml` | 新增 langgraph 依赖 |
| `backend/app/main.py` | 注册 operation_router |
| `backend/app/operation_agent/nodes/analyze_reason_node.py` | 改用 prompt 文件 + system_prompt |
| `backend/app/operation_agent/nodes/generate_advice_node.py` | 改用 prompt 文件 + 修复兜底逻辑 |
| `frontend/src/router/index.ts` | 新增 /operation 路由 |
| `frontend/src/layouts/DefaultLayout.vue` | 导航栏增加"运营分析"链接 |

---

## 4. Operation Graph 流程

```text
START
  ↓
InitContextNode        : 生成 trace_id，设置 analysis_mode，初始化空集合
  ↓
QueryOperationDataNode : 调 Tool Center kpi_query，获取 KPI 指标数据
  ↓
DetectAbnormalNode     : 纯规则检测阈值越界、数据缺失
  ↓
AnalyzeReasonNode      : 调 DeepSeek LLM 分析异常原因
  ↓
GenerateAdviceNode     : 调 DeepSeek LLM 生成建议（失败时规则兜底）
  ↓
SummaryNode            : 组装 Markdown final_answer
  ↓
END
```

---

## 5. Node 职责说明

| Node | 职责 | 调用 LLM | 调用 Tool Center | 调用 DB |
|------|------|:---------:|:----------------:|:-------:|
| InitContextNode | 初始化 trace_id、analysis_mode、清空容器 | 否 | 否 | 否 |
| QueryOperationDataNode | 通过 kpi_query Tool 获取 KPI 数据 | 否 | **是** | 否 |
| DetectAbnormalNode | 阈值规则检测异常（能耗/告警处理率/工单完成率/设备可用率） | 否 | 否 | 否 |
| AnalyzeReasonNode | 读取 operation_analysis.md Prompt，调 LLM 分析原因 | **是** | 否 | 否 |
| GenerateAdviceNode | 读取 operation_advice.md Prompt，调 LLM 生成建议 | **是** | 否 | 否 |
| SummaryNode | 将 metrics/abnormal/advice/evidence 组装为结构化 Markdown | 否 | 否 | 否 |

---

## 6. LLM 使用边界

| 步骤 | 使用 LLM | 原因 |
|------|:--------:|------|
| 异常检测 | **否** | 使用确定性规则（阈值判断），保证稳定性和可测试性 |
| 原因分析 | **是** | 需要理解上下文、关联多指标、生成自然语言解释 |
| 建议生成 | **是** | 需要基于原因推理出可执行动作，LLM 失败时规则兜底 |
| 总结输出 | **否** | 固定 Markdown 模板，规则化组装 |

LLM 只用于需要"理解"和"推理"的环节，数据获取和结构化输出用规则。

---

## 7. API 调用方式

```bash
POST /api/v1/operation/analyze
Content-Type: application/json

{
  "trigger_type": "tab_analysis",
  "domain": "safety",
  "active_tab": "本质安全",
  "time_dimension": "month",
  "date": "2026-07"
}
```

返回 (统一 ApiResponse 格式)：

```json
{
  "code": 0,
  "success": true,
  "data": {
    "trace_id": "trace_xxx",
    "status": "success",
    "summary": "## 运营分析结论\n\n### 1. 总体判断\n...",
    "abnormal_items": [...],
    "advice_items": [...],
    "evidence": [...],
    "errors": []
  }
}
```

---

## 8. 测试方式

### 后端单元测试

```bash
cd backend && source .venv/bin/activate
pytest tests/operation_agent/ -v
```

10 个测试覆盖：Graph invoke、final_answer 存在、Markdown 格式、evidence 不为空、abnormal/advice 字段存在、trace_id 生成、错误隔离。

### 后端调试脚本

```bash
python scripts/debug_operation_agent.py
```

打印完整 Markdown 分析结论、异常统计、错误详情。

### API 调用测试

```bash
curl -s -X POST http://127.0.0.1:8000/api/v1/operation/analyze \
  -H "Content-Type: application/json" \
  -d '{"trigger_type":"tab_analysis","domain":"safety"}'
```

### 前端

访问 http://localhost:5173/operation ，点击"分析"按钮。

---

## 9. 当前不足

1. **QueryOperationDataNode 只接了 KPI 数据**：告警、隐患、工单数据未接入。当前只调用了 `kpi_query` Tool，其他三个 Query Tool 可做下一步扩展。
2. **未知 domain 兜底**：`domain != "safety"` 时写入 errors，没有 Mock 数据回退。
3. **前端 Markdown 展示**：当前用 `white-space: pre-wrap` 展示原文，没有 Markdown 渲染（表格、标题等）。可后续接入 marked / markdown-it 库。
4. **LLM 调用耗时**：每次分析需要 2 次 LLM 调用（原因分析 + 建议生成），响应时间约 3-5 秒。
5. **无流式输出**：当前是同步请求，未实现 SSE 流式返回。
6. **无多轮对话**：每次都是独立分析，没有会话记忆。
7. **Analysis Tool 未接入**：Sprint3 的 `IocSummaryAnalysisTool` 可用但当前 Graph 未调用，直接在 DetectAbnormalNode 中做规则判断。

---

## 10. 下一步建议

| 优先级 | 建议 | 说明 |
|--------|------|------|
| P0 | 扩展 QueryOperationDataNode | 接入 alarm_query、risk_query、work_order_query，丰富分析维度 |
| P0 | 前端 Markdown 渲染 | 接入 marked 库，让表格、标题、列表正确显示 |
| P1 | 接入 IocSummaryAnalysisTool | 将规则检测迁移到 Analysis Tool，复用 Spring3 成果 |
| P1 | 接入告警和隐患数据到异常检测 | DetectAbnormalNode 中增加 alarm_level、risk_level 规则 |
| P2 | 流式输出 | SSE 方式逐步返回分析结果，提升体验 |
| P2 | 多领域支持 | 扩展 maintenance、business、all 领域的 Mock 数据 |
| P3 | 多轮对话 | 接入 Runtime 的 Conversation/Session 管理，支持追问 |
| P3 | 日报月报自动生成 | 基于时间维度的周期性分析 |

---

## 11. 面试表达建议

### 为什么使用 Graph？

运营分析是一个多步骤流程，每一步依赖上一步的结果。如果用单个函数实现，代码耦合度高、难以测试、难以扩展。Graph 将分析流程拆分为 6 个独立节点，每个节点只做一件事，可单独测试、可替换、可编排。LangGraph 提供了 StateGraph，天然支持 TypedDict 状态管理和节点编排。

### State 保存了什么？

OperationState 保存了分析全流程的数据：输入（user_context、page_context）、中间结果（raw_data、metrics、abnormal_items、reason_analysis）、最终输出（final_answer、evidence、advice_items）。State 不保存 ORM 对象、数据库连接或前端组件对象。

### Node 怎么拆？

按职责拆分：初始化、数据查询、异常检测、原因分析、建议生成、汇总输出。原则是每个 Node 要么做数据获取、要么做规则判断、要么调 LLM，不混合。

### Tool Center 如何接入？

QueryOperationDataNode 通过 `registry.get("kpi_query").run(BaseToolInput(...))` 调用 Tool Center。Tool 返回统一的 `ToolResult(success, data, evidence, trace_id)`。后续接入 alarm/risk/work_order 数据只需在同一个 Node 中增加 Tool 调用。

### 哪些步骤使用规则，哪些步骤使用 LLM？

- **规则**：异常检测（阈值判断、数据缺失检测）——确定性逻辑，不需要 LLM。
- **LLM**：原因分析、建议生成——需要理解上下文、推理、生成自然语言。
- **规则 + LLM 混合**：建议生成调用 LLM，解析失败时用规则兜底生成基础建议。

### 如何保证 evidence 和可信度？

每条异常和建议都携带 evidence（来源、类型、ID、描述）。Query Tool 返回的数据自带 evidence 链。SummaryNode 将 evidence 汇总到最终 Markdown 中。LLM Prompt 中要求"每个关键结论必须引用数据依据"，禁止无证据的确定性结论。

### 如何扩展设备运维、经营改善、日报、专家问答？

当前 safety 领域的模式可以完整复用到其他领域：增加对应领域的 Mock 数据 → 扩展 QueryOperationDataNode → 调整 DetectAbnormalNode 规则 → 调整 Prompt 模板。专家问答模式（qa）已在 state 中预留 `analysis_mode=qa` 和 `user_question` 字段，后续可增加对话上下文管理。
