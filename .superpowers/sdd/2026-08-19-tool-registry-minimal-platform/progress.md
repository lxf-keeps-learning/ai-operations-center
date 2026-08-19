# SDD ledger — plan: docs/superpowers/plans/2026-08-19-tool-registry-minimal-platform.md

## Baseline

- Worktree: `/Users/liuxiaofei/Documents/study/IOC/ai-operations-center/.worktrees/tool-registry-platform`
- Branch: `codex/tool-registry-platform`
- Start commit: `9435375`
- Default test collection is blocked by pre-existing missing `mcp` package (10 collection errors).
- Comparable baseline with `MCP_ENABLED=false`: 513 passed, 2 failed.
- Baseline failures: `tests/analysis_stream/test_analysis_stream_api.py::TestAnalysisStreamApi::test_stream_uses_real_graph_node_keys`; `tests/analysis_stream/test_stream_service.py::test_node_order_matches_graph`.
- Ruling: Continue with the two Analysis Stream failures as the explicit baseline and require no new failures — the plan already isolates Graph compatibility tests and final verification compares against baseline — cost if wrong: a Registry regression in those exact assertions could be misclassified, so Task 9 and final review must inspect their diffs directly.
- Ruling: Run non-MCP suites with `MCP_ENABLED=false`, then verify MCP separately in Task 10 — the current project imports an undeclared dependency — cost if wrong: integration differences caused only when MCP is enabled may be found later than other failures.

## Preflight consistency scan

| Scope | Producer / requirement | Consumer / test | Finding and ruling |
|---|---|---|---|
| Task 1 internal | Contracts, settings, executor catalog | Contract/catalog tests | Consistent; `ToolContext` default external is security-safe and later internal callers set it explicitly. |
| Task 2 internal | Four ORM models and migration | SQLite model tests and Alembic head test | Consistent; migration starts from current sole head `20260806_0003`. |
| Task 3 internal | Repository, seed, dual executor registration | Idempotency and legacy integration tests | Consistent; seed is explicit and never runs at import/startup. |
| Task 4 internal | Pure policy, rollout, limiter, confirmation | Deterministic unit tests | Consistent; no database dependency is introduced. |
| Task 5 internal | Cache and database Registry | Cache/fallback/resolve tests | Consistent; stale fallback rejects all action types as the spec requires. |
| Task 6 internal | Gateway and audit | Decision, confirmation, audit tests | Consistent; fake commit tools are permitted for unit tests although no built-in commit executor exists. |
| Task 7 internal | Transactional service and admin API | Service/API authorization tests | Consistent; middleware trusts gateway-provided identity headers, matching existing project security boundaries. |
| Task 8 internal | Legacy/database adapter and Tool API | Both-mode compatibility tests | Consistent; external identity comes only from middleware context. |
| Task 9 internal | Fixed capability mapping in Operation Graph | Graph node/state tests | Consistent; business flow remains fixed while version discovery becomes dynamic. |
| Task 10 internal | MCP descriptors and execution from Registry | MCP adapter/server tests | Conflict: project imports `mcp` but does not declare it and the baseline environment lacks it. Ruling: Task 10 must add `mcp>=1.0.0,<2.0.0` to `backend/pyproject.toml` and report enabled-MCP test evidence — cost if wrong: the selected range may need adjustment to the FastMCP API available at install time. |
| Task 11 internal | End-to-end/failure tests and docs | Full verification | Consistent; final suite explicitly permits only proven baseline failures. |
| Task 12 internal | Diff/security/final review | Branch handoff | Consistent; review base `0c949c1` intentionally includes the implementation-plan commit in the branch diff but does not hide implementation changes. |
| Tasks 1 → 2 | Task 1 immutable records/enums | Task 2 persistence values | Consistent; ORM stores enum values as strings and converts at repository boundary. |
| Tasks 1 → 3 | Executor catalog and contracts | Dual registration and repository snapshots | Consistent; the same `BaseTool` instance is bound to legacy name and implementation ref. |
| Tasks 1 → 7 | `jsonschema` dependency | Publish schema validation | Consistent; Task 7 must use `validator_for(...).check_schema(...)` exactly. |
| Tasks 2 → 3 | ORM models | Repository and seed | Consistent; Task 3 owns commits and immutable conversion, not Task 2. |
| Tasks 3 → 5 | `load_snapshot()` | Registry cache/resolution | Consistent; no live ORM object crosses the repository boundary. |
| Tasks 3 → 6 | Audit repository methods | Gateway best-effort audit | Consistent after plan added `update_audit`; reviewer must verify audit failure never masks a successful result. |
| Tasks 4 → 5 | Policy and rollout functions | Database Registry | Consistent; Registry selects the version before Gateway rate limiting. |
| Tasks 4 → 6 | Limiter and confirmation service | Gateway execution order | Consistent; challenge binds trace, version, arguments, and user. |
| Tasks 5 → 7 | Registry invalidation | Management publish/update | Consistent; invalidation occurs only after a successful database commit. |
| Tasks 5 → 8 | Discovery/resolve APIs | Mode adapter | Consistent; adapter constructs database services lazily. |
| Tasks 6 → 8 | `ToolGateway.execute` | Existing Tool API | Consistent; compatibility adapter owns legacy-name translation and HTTP status mapping. |
| Tasks 6 → 9 | Governance metadata | Operation evidence labels | Consistent; result metadata supplies selected tool identity while content stays stable. |
| Tasks 7 → 8 | Both modify `app/main.py` | Router mount then runtime construction | Sequential overlap is intentional; Task 8 must preserve Task 7's router mount. |
| Tasks 8 → 9 | `execute_tool` | Operation Graph | Consistent; internal caller context is explicit. |
| Tasks 8 → 10 | `discover_tools` / `execute_tool` | MCP server and callables | Consistent; public MCP names remain compatibility data while descriptions and versions come from Registry. |
| Tasks 9 → 11 | Graph migration | End-to-end regression | Consistent; Task 11 reruns the fixed Graph contract suite. |
| Tasks 10 → 11 | MCP dependency and enabled-mode tests | Final full verification | Consistent with the Task 10 dependency ruling above. |

## Task status

- Task 1: complete (commits 9435375..637cc89, review clean)
- Task 2: Ruling: `gray_percentage` belongs only to `ToolPolicyRecord` / `tool_policies`; remove it from `ToolVersionRecord`, `ToolVersion`, migration, and tests — Spec section 4.3 is authoritative and a duplicate source would make rollout resolution ambiguous — cost if wrong: version-specific rollout would need a future schema migration instead of being directly stored on versions.
- Task 2: fix round 1/5 (2 addressed, 1 open — missing test for action with unsupported non-null phase; commits d4ad4d2..886867c)
- Task 2: fix round 2/5 (1 addressed, 0 open — unsupported action phase now covered; commits 886867c..873d6a0)
- Task 2: complete (commits 637cc89..873d6a0, review clean)
- Task 3: fix round 1/5 (1 addressed, 0 review findings open — deep freeze added; commits 0dde815..51f2a78)
- Task 3: Ruling: the frozen schema representation must pass `jsonschema.validators.validator_for(schema).check_schema(schema)` directly; `MappingProxyType`/tuple fails under jsonschema 4.26 — use deeply read-only `dict`/`list` subclasses or an equally direct-compatible representation — cost if wrong: custom containers add maintenance surface and must override every ordinary mutation method.
- Task 3: fix round 2/5 (1 addressed, 0 open — frozen schemas directly pass jsonschema 4.26; commits 51f2a78..7657fa2)
- Task 3: complete (commits 873d6a0..7657fa2, review clean)
- Task 4: fix round 1/5 (2 addressed, 0 open — policy ranks and retry timing corrected; commits 9b779ef..6e458f1)
- Task 4: complete (commits 7657fa2..6e458f1, review clean)

## Final review hardening (OpenCode findings 1-14)

- 状态：实现与专项回归完成；最终报告见 `final-review-fix-report.md`。
- Ruling（FR-1，替代 Task 2/7 的 gray_percentage 裁定）：灰度比例是版本发布元数据，授权是策略决策。`tool_versions.gray_percentage` 是运行时唯一流量来源；`tool_policies.gray_percentage` 仅为管理/存量兼容保留且运行时忽略。发布灰度版本不得创建或恢复 allow 策略。候选无匹配策略或 deny 时跳过候选，稳定版本再独立授权。
- Ruling（FR-2，替代 Task 5-3）：候选无匹配策略不使整个 external 请求立即 forbidden；它只使该候选不可选。只有稳定版本最终也无匹配策略时，external 才拒绝；internal 仍按设计使用可信默认。
- Ruling（FR-3，替代 Task 6 疑虑）：Gateway 的 canonical trace 顺序固定为全局 trace、`ToolContext.request_id`、新生成值，并显式写回 BaseTool context；无全局上下文的 Graph/MCP/SSE 不再产生双 trace。
- Ruling（FR-4，确认边界）：保留计划既有的 Gateway 签名挑战公开流程，不扩张为独立审批/人工签发系统；新增 nonce 与 `tool_call_audits.confirmation_token_hash` 唯一索引，在副作用前数据库原子消费。重复令牌或消费落库失败均 fail closed。
- Ruling（FR-5，替代 Task 7-3）：策略替换是“启用集合全量替换”，不是物理删除历史。先 `FOR UPDATE` 锁工具定义，旧启用策略软下线，再插入新集合；审计外键与策略快照保持可追溯。
- Ruling（FR-6，MySQL scope 唯一性）：MySQL 唯一索引允许多个含 `NULL` 的组合，不能直接约束 `(version_id, tenant_id, role)`。启用策略使用长度前缀 scope 的 SHA-256 `active_scope_key`，唯一约束 `(tool_id, active_scope_key)`；禁用历史 key 为 `NULL`。SQLite 覆盖约束行为，SQL/调用 spy 覆盖行锁路径，真实 MySQL 的锁强度仍依赖 InnoDB 事务。
- Ruling（FR-7，替代 Task 10-1）：MCP 映射工具在 FastMCP Server 构建时校验 Registry 公开字段和 JSON 类型与 callable 兼容，移除内部 `context` 后以 Registry schema 暴露并严格运行时验证。通用发布服务只验证 JSON Schema 与执行器绑定，避免把非 MCP 工具耦合到 MCP callable；不兼容的 MCP 配置在构建时 fail fast。
- Ruling（FR-8，seed）：seed 是 creation-only bootstrap；只在该层级完全为空时创建初始定义、版本或策略，不更新任何已有治理行。
- Ruling（FR-9，审计）：拒绝决策携带完整内部 resolution 并持久化工具/能力/版本/实现/策略/灰度快照；公开错误 detail 不泄漏新增内部字段。
- Ruling（FR-10，管理审计）：定义和版本持久化 `created_by/updated_by`，版本另持久化 `published_by/retired_by` 与退役时间；API 响应暴露这些治理元数据。
- Ruling（FR-11，兼容 API）：`GET /tools` 统一走双模式 `discover_tools`，保持 `name/description` 形状；429 保持标准信封并新增 `data.retry_after_seconds` 和 `Retry-After`。
- Deferred：本轮 14 项无功能性 deferred/驳回。既有全量基线的两个 Analysis Stream 节点顺序失败继续按 Baseline 记录，未弱化或跳过。
- Final verification：专项 `331 passed, 1 warning`；MCP 启用 `18 passed`；全量 `693 passed, 2 failed, 1 warning`，失败集合与 Baseline 完全相同；`compileall`、`git diff --check` 通过；Alembic `20260819_0005 (head)` 单 head。

## Scope re-review blockers

- Ruling（SR-1，confirmation canonicalization）：消费唯一键继续使用 canonical token 文本的 SHA-256，但 verify 只接受 `issue()` 输出的无 padding URL-safe Base64；解码后重新编码必须逐字相等。这样保留现有数据库/公开流程，同时拒绝 Python decoder 容忍的 payload/signature `=` 等价变体。HMAC、过期与 trace/tool/version/arguments/user 绑定顺序不变；确认消费事务失败仍 rollback，因此原 token 可再成功一次。
- Ruling（SR-2，MCP required/null）：query MCP callable 根据 Registry public schema 的 `required` 动态选择必填或可选签名。required `filters` 的 missing 由 FastMCP 参数模型拒绝、null 由非空 dict 类型拒绝，二者都不进入 Gateway；optional missing/null 才兼容归一为 `{}`。公共工具名、字段名和 analysis callable 不变。
- Scope re-review verification：confirmation/Gateway/Audit `35 passed`；MCP 启用 `20 passed`；完整专项 `340 passed, 1 warning`；全量 `702 passed, 2 failed, 1 warning`，失败集合仍与 Baseline 完全相同；`compileall`、`git diff --check` 通过，Alembic `20260819_0005 (head)` 单 head。
