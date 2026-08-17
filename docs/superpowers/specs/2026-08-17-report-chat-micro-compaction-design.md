# Report Chat 回答后微压缩设计

## 目标

为 Report Chat 增加回答后的增量微压缩能力。在不删除 MySQL 原始消息的前提下，将较旧的短期对话压缩为可持续更新的摘要，并仅保留最近几条原始消息进入后续 Prompt，从而控制长对话的输入 Token、延迟和成本。

第一版只覆盖 Report Chat，不改变通用 Runtime 对话链路。

## 设计原则

- 原始用户消息和助手回答始终完整写入 MySQL，满足审计、排障和摘要重建需求。
- 微压缩只改变 LangGraph Checkpointer 中供后续推理使用的短期状态。
- 回答先生成并持久化，微压缩作为同一次 Graph 执行的后置步骤运行。
- 微压缩失败不得影响本轮回答、原始消息持久化或既有摘要。
- 当前报告和证据的优先级高于微摘要，摘要不能覆盖当前业务事实。
- 使用增量摘要控制每次压缩的输入规模，不重复总结全部历史。

## Graph 架构

当前回答后的链路为：

```text
generate_report_answer
  -> persist_chat_message
  -> save_chat_memory
  -> END
```

调整为：

```text
generate_report_answer
  -> persist_chat_message      -- 完整原文写入 MySQL
  -> save_chat_memory          -- 将本轮 user/assistant 加入短期历史
  -> micro_compact             -- 检查阈值并按需增量压缩
  -> END                       -- Checkpointer 保存压缩后的状态
```

`micro_compact` 是独立 Graph 节点，只负责触发判断、摘要生成、结果校验和短期状态更新。它不负责业务消息持久化，也不修改显式长期记忆。

## 状态模型

`ReportChatState` 新增两个字段：

```python
compaction_summary: dict[str, Any]
micro_compaction: dict[str, Any]
```

`compaction_summary` 保存可供下轮 Prompt 使用的有效摘要：

```json
{
  "version": 2,
  "summary": "供下一轮模型使用的紧凑摘要",
  "covered_message_count": 8,
  "source_digest": "sha256...",
  "estimated_tokens_before": 1730,
  "estimated_tokens_after": 310,
  "updated_at": "2026-08-17T10:00:00+08:00"
}
```

字段语义：

- `version`：每次成功压缩递增，初始成功版本为 1。
- `summary`：经过校验、供回答 Prompt 使用的摘要正文。
- `covered_message_count`：累计被摘要覆盖并从 `chat_history` 移除的原始消息数。
- `source_digest`：上一版摘要和本次待压缩消息的稳定摘要，用于观测和重复执行识别。
- `estimated_tokens_before`：本次旧摘要与待压缩消息的估算 Token 总数。
- `estimated_tokens_after`：新版摘要的估算 Token 数。
- `updated_at`：成功应用新版摘要的时间。

`micro_compaction` 保存最近一次回答后的检查结果：

```json
{
  "checked": true,
  "triggered": true,
  "status": "success",
  "reason": "token_threshold",
  "messages_compacted": 4,
  "tokens_before": 1730,
  "tokens_after": 310,
  "latency_ms": 420,
  "error": null
}
```

`status` 使用 `skipped`、`success` 或 `failed`。未达到阈值时记录 `skipped`；关闭配置时 `reason` 为 `disabled`。

## 触发与增量压缩算法

每次回答保存到 `chat_history` 后执行一次轻量检查。满足以下任一条件时触发真实模型调用：

- 尚未压缩的历史估算 Token 大于等于 1200；
- `chat_history` 消息数大于 6。

触发后执行：

1. 固定保留 `chat_history` 最近 4 条消息，即最近两轮 user/assistant 原文。
2. 将更早的消息作为本次待压缩区；没有待压缩消息时跳过。
3. 以“上一版摘要 + 本次待压缩消息”构造压缩 Prompt。
4. 调用当前 Report Chat 使用的模型生成新版摘要。
5. 对输出执行非空、内容安全和压缩收益校验。
6. 校验通过后更新 `compaction_summary`，并将 `chat_history` 替换为最近 4 条原始消息。
7. 任一校验失败时保留旧摘要和完整的当前 `chat_history`。

Token 估算复用 `context_budget.estimate_tokens`，保证触发统计与回答 Prompt 预算采用同一口径。配置阈值使用“大于等于”语义，消息数使用“大于”语义，避免历史恰好为保留窗口时产生无待压缩区的调用。

## 摘要内容契约

压缩 Prompt 要求模型仅输出摘要正文，不输出 Markdown 代码块或额外解释。摘要必须优先保留：

- 用户真实意图、范围和已确认约束；
- 已确认的结论和决定；
- 对后续回答仍有影响的报告事实、数值、时间和对象；
- 使用过的证据编号、来源引用和关键依据；
- 尚未解决的问题、待办和后续方向；
- 对后续问答仍有效的用户偏好。

可以合并或删除：

- 寒暄、致谢和无信息量回复；
- 重复问题、重复结论和冗长措辞；
- 已被后续结论覆盖的中间讨论；
- 对后续推理没有影响的过程描述和展示格式。

摘要不拥有高于当前报告、当前证据或新用户问题的事实优先级。若摘要与当前报告冲突，回答必须以当前报告和证据为准。

## 回答 Prompt 集成

`build_context_budget` 新增独立的 `compaction_summary` 区段，默认分配最多 600 个估算 Token。上下文优先级调整为：

```text
当前用户问题
  -> 当前报告上下文
  -> 报告证据
  -> 报告检索与合并上下文
  -> 微压缩摘要
  -> 显式长期记忆
  -> RAG 结果
  -> 最近原始对话
```

微摘要与最近原文同时进入回答 Prompt：摘要提供较早上下文，最近 4 条原文保持短期连续性。`context_budget.contexts` 必须显式包含 `compaction_summary`，以便在 Trace 中观察其参与情况。

## 与长期记忆的边界

微摘要和长期记忆用途不同：

- `compaction_summary` 自动生成，只服务当前 Report Chat 会话的上下文连续性。
- `memory_context` 继续仅保存用户明确要求“记住”的用户级或报告级信息，可跨会话检索。
- 微压缩不得自动把摘要内容写入 LangGraph Store。
- 长期记忆不得因为微压缩而删除或改写。

## 配置

后端 Settings 增加环境变量驱动的配置：

| 配置 | 默认值 | 说明 |
|---|---:|---|
| `REPORT_CHAT_MICRO_COMPACTION_ENABLED` | `true` | 是否启用回答后检查与压缩 |
| `REPORT_CHAT_MICRO_COMPACTION_TOKEN_THRESHOLD` | `1200` | 触发压缩的未压缩历史 Token 阈值 |
| `REPORT_CHAT_MICRO_COMPACTION_MESSAGE_THRESHOLD` | `6` | 触发压缩的消息数阈值 |
| `REPORT_CHAT_MICRO_COMPACTION_KEEP_RECENT` | `4` | 成功压缩后保留的最近原始消息数 |
| `REPORT_CHAT_MICRO_COMPACTION_TARGET_TOKENS` | `600` | 新摘要允许的目标 Token 上限 |

模型调用超时复用现有 `operation_llm_timeout_seconds`。第一版复用 Report Chat 当前模型，不增加单独的模型供应商配置。

配置必须满足：Token 阈值、消息阈值和保留数均为正整数，且消息阈值大于保留数。非法配置在应用启动时按 Settings 既有校验机制报错，而不是运行时静默修正。

## 结果校验与失败处理

只有同时满足以下条件才应用新版摘要：

- 模型调用成功；
- 输出去除首尾空白后非空；
- 输出未被内容安全策略阻断；
- 新摘要估算 Token 不超过目标上限；
- 新摘要估算 Token 小于“旧摘要 + 本次待压缩消息”的估算 Token。

失败处理：

- 模型调用异常、超时、空结果或格式异常：记录失败，保留旧状态。
- 内容安全阻断：不写入摘要，不删除消息。
- 压缩后没有 Token 收益：拒绝新版摘要。
- Checkpointer 不可用：不影响已写入 MySQL 的原始消息；本地无持久化模式下摘要仅在当前进程执行状态内有效。
- `micro_compact` 不向 Graph 顶层抛出可恢复异常，避免将已完成的回答标记为失败。

失败信息写入 `micro_compaction.error`，同时追加到现有 `errors`，节点名使用 `micro_compact`。

## 可观测性

每次回答后都更新 `micro_compaction` 检查结果，记录是否触发、原因、压缩消息数、Token 前后估算、耗时和错误。

真实压缩模型调用追加到现有 `llm_usages`：

```json
{
  "action_type": "report_chat_micro_compaction",
  "model_name": "deepseek-chat",
  "input_tokens": 950,
  "output_tokens": 260,
  "total_tokens": 1210,
  "success": 1,
  "error_message": null
}
```

这样可以沿用既有用量和 Trace 体系统计：

- 检查次数与真实触发次数；
- 压缩成功率；
- 平均压缩率；
- 额外 LLM Token 和延迟；
- 失败原因分布。

## 数据恢复与幂等性

MySQL 原始消息是唯一完整审计源。Checkpointer 中的摘要丢失或质量异常时，可以在后续独立能力中按会话原始消息重建；第一版不提供自动重建接口。

`source_digest` 由上一版摘要正文和本次待压缩消息的规范化 JSON 计算。若同一节点因执行重试再次看到相同输入，可识别相同来源。第一版仍允许重新调用模型，但只有通过全部校验的结果才能替换状态；累计覆盖数只在成功应用时递增，避免失败重试造成计数漂移。

## 测试策略

### 单元测试

- 未达到阈值时不调用模型、不修改历史并记录 `skipped`。
- 消息数或 Token 任一达到触发条件即可调用压缩。
- 成功后只压缩较旧消息，最近 4 条原文逐字不变。
- 第二次压缩使用“旧摘要 + 新增旧消息”，版本和累计覆盖数正确递增。
- 模型异常、超时、空结果和内容安全阻断时不删除历史。
- 新摘要超过目标 Token 或没有压缩收益时拒绝替换。
- `source_digest` 对相同规范化输入稳定，对变化输入发生变化。
- 关闭配置后完全跳过模型调用。
- `context_budget` 正确计入微摘要并继续满足总输入预算。

### Graph 集成测试

- 节点顺序为“持久化原文 -> 保存本轮历史 -> 微压缩”。
- 回答成功后微压缩失败不会改变回答类型或使 Graph 失败。
- Checkpointer 可在下一轮恢复微摘要和最近消息。
- 下一轮回答 Prompt 同时包含微摘要与最近原文。
- MySQL 仍能返回被微压缩覆盖的完整原始消息。
- `llm_usages` 可区分回答调用和微压缩调用。

### 验收标准

- 长对话中，供回答使用的历史上下文稳定受预算控制。
- 最近两轮问答逐字保留。
- 旧消息被压缩后，关键结论、数值、证据引用和待办仍可用于下一轮回答。
- 微压缩失败不影响回答展示、原始消息持久化或后续重试。
- 只有估算 Token 明确减少时才应用新版摘要。

## 非目标

第一版不包含：

- 通用 Runtime 对话压缩；
- 后台任务队列或异步压缩 Worker；
- 单独的压缩模型路由；
- 微摘要管理页面或人工编辑；
- 自动从 MySQL 重建摘要；
- 将普通对话摘要自动提升为跨会话长期记忆。
