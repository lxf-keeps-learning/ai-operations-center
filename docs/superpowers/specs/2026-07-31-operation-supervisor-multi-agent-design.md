# 生产报告 Supervisor 多 Agent 设计

**日期：** 2026-07-31  
**状态：** 已确认，待实施

## 目标

将现有生产报告的固定线性 Graph 升级为 Supervisor 模式的多 Agent 流程：公共报告处理由统一流程负责，Supervisor 根据业务域把领域分析与建议交给对应的业务 Agent，同时保持现有 API、SSE、报告落库和 `OperationState` 契约兼容。

## 当前上下文

生产报告入口位于 `backend/app/operation_agent/graph.py`，当前流程为：

```text
初始化上下文 → 查询运营数据 → 异常检测 → 原因分析 → 建议生成 → 报告汇总
```

现有业务域为：

- `safety`：本质安全
- `maintenance`：设备运维
- `business`：经营改善
- `capability`：能力提升
- `all`：全域分析

现有节点已经包含 LLM 失败降级、敏感内容审核、LLM 用量记录、错误记录和流式节点事件。设计以复用这些能力为前提，不重写已有业务规则。

## 方案与取舍

### 方案 A：公共骨架 + 业务域专家子图（采用）

Supervisor 只负责业务域识别、路由和执行状态记录。公共节点统一执行上下文初始化、数据查询、异常检测和最终汇总；业务 Agent 子图只负责本业务域的原因分析和建议生成。

优点是职责边界清晰、公共逻辑不重复、业务域 Prompt 可以独立演进，并且能以最小改动复用现有服务层和流式协议。

### 方案 B：单 Graph 条件切换 Prompt

保留一套原因分析和建议节点，仅根据 `domain` 选择 Prompt。实现成本较低，但业务差异会逐步集中到条件判断和 Prompt 分支中，不利于 Agent 独立扩展。

### 方案 C：每个业务域维护完整独立 Graph

每个域拥有从初始化到汇总的完整流程。隔离性最强，但会重复公共节点、错误处理和事件处理，后续容易产生行为漂移。

## 架构设计

```text
START
  ↓
Supervisor 初始化与业务域路由
  ↓
公共上下文初始化
  ↓
公共数据查询
  ↓
公共异常检测
  ↓
Supervisor 分发
  ├─ SafetyAgent       → 本质安全原因分析 → 本质安全建议
  ├─ MaintenanceAgent  → 设备运维原因分析 → 设备运维建议
  ├─ BusinessAgent     → 经营改善原因分析 → 经营改善建议
  └─ CapabilityAgent   → 能力提升原因分析 → 能力提升建议
  ↓
公共报告汇总
  ↓
END
```

### Supervisor

Supervisor 接收 `OperationState`，读取 `domain`，完成以下工作：

1. 将缺失或非法的业务域归一化为当前兼容默认值 `safety`。
2. 将 `safety`、`maintenance`、`business`、`capability` 路由到对应业务 Agent。
3. 将 `all` 路由到跨域分析 Agent，由一套 Agent 生成统一的全域结论，而不是并行生成四份彼此独立的报告。
4. 写入当前 Agent 标识和路由信息，供日志、LangSmith 和 SSE 事件使用。
5. 不直接实现业务分析规则，不持有 ORM 对象或外部连接。

### 公共流程

公共流程继续复用现有节点：

- `init_context_node`：初始化 trace、分析模式和基础状态。
- `query_operation_data_node`：通过现有 Tool Center/数据适配获取原始数据和指标。
- `detect_abnormal_node`：保留现有阈值、告警、隐患和工单规则。
- `summary_node`：继续负责最终 Markdown 报告、证据和分析依据的统一输出。

公共节点每次报告只执行一次。业务 Agent 不重新查询数据，也不改变公共异常检测结果。

### 业务 Agent

四个业务 Agent 使用统一接口，最小职责是：

```python
def run(state: OperationState) -> OperationState:
    # 读取 metrics、abnormal_items、risk_items、evidence
    # 生成业务域原因分析
    # 生成业务域建议
    # 写回 reason_analysis、advice_items、llm_usages、errors
    return state
```

内部可复用现有 `analyze_reason_node` 和 `generate_advice_node` 的调用、降级、审核与结果归一化逻辑；业务差异通过独立 Prompt 和领域配置表达，不在 Supervisor 中加入领域判断。

初始 Agent 边界如下：

- `SafetyAgent`：关注告警闭环、隐患治理、人员资质和安全阈值。
- `MaintenanceAgent`：关注设备可用率、设备在线率、维修工单和故障闭环。
- `BusinessAgent`：关注经营改善、合同履约、客户体验和经营指标。
- `CapabilityAgent`：关注人员能力、持证率、人效和物联接入能力。

## 状态与兼容性

`OperationState` 继续作为公共 Graph 与业务 Agent 之间唯一数据契约。新增字段只使用 JSON 可序列化基本类型，例如：

- `supervisor_route`：实际路由到的 Agent key。
- `active_agent`：当前执行 Agent key。
- `agent_events`：可选的 Agent 级执行摘要。

现有字段 `reason_analysis`、`advice_items`、`llm_usages`、`evidence`、`analysis_basis`、`errors` 的含义保持不变。

服务层继续使用统一的 Graph 调用方式。现有 `operation_graph` 保留为兼容导出，默认实例切换为 Supervisor Graph；请求模型、响应模型、记录服务、报告聊天和报告落库接口不改变。

## 流式事件与可观测性

保留现有 `node_started` 自定义事件，并为 Supervisor 和业务 Agent 增加稳定的 `node_key`、`node_name` 与 `agent_key` 信息。典型事件顺序为：

```text
supervisor_route → init_context → query_operation_data → detect_abnormal
→ safety_agent_reason → safety_agent_advice → summary
```

事件适配器对新增字段保持向后兼容；旧前端即使只读取 `node_key` 和展示文案，也能正常工作。LangSmith run metadata 使用同一 `trace_id`、`domain` 和 `agent_key`，便于按业务域分析耗时、Token 和失败率。

## 错误处理

- 路由失败：记录 Supervisor 错误，使用 `safety` 兼容默认 Agent，流程继续。
- 业务 Agent LLM 失败：复用现有规则兜底，不阻断公共汇总。
- 单个建议生成失败：保留原因分析和证据，`advice_items` 使用安全的空列表或规则兜底结果。
- 业务 Agent 未写入结果：公共 `summary_node` 根据现有状态生成明确的“数据不足/无法完成该部分”说明。
- 敏感内容：继续由现有内容审核组件处理，Agent 不绕过审核。

## 测试策略

新增或调整测试覆盖：

1. Supervisor 对五种业务域输入的路由结果，包括四个业务域和 `all`。
2. 公共节点执行一次且业务 Agent 收到完整的公共分析上下文。
3. 每个业务 Agent 写回原有状态字段，且不改变 `OperationState` 的 JSON 可序列化特性。
4. LLM 失败、空结果、审核拦截和非法业务域的兜底行为。
5. 现有 operation graph、API、SSE、记录落库和报告聊天回归测试。
6. 流式事件包含 Supervisor/Agent 信息，同时兼容旧事件消费者。

验证命令：

```bash
cd backend
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest tests/operation_agent -q
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest tests/analysis_stream -q
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q
```

## 非目标

- 本阶段不改前端页面布局，只扩展可选的 Agent 状态展示数据。
- 本阶段不引入新的外部 Agent 框架或新的模型供应商。
- 本阶段不把报告问答 `report_chat_agent` 改造为多 Agent；它继续消费生产报告结果。
- 本阶段不改变数据库表结构，除非现有可观测性或记录契约验证后证明确有必要。
