# Tool Registry 最终审查修复报告

- 分支：`codex/tool-registry-platform`
- 审查基线：`f20998e`
- 设计：`docs/superpowers/specs/2026-08-19-tool-registry-minimal-platform-design.md`

## 总体裁定

14 条反馈均经代码、设计和历史计划核对。没有驳回项；其中 3、7、9、10 按现有公开契约或数据库边界做了最小调整，其余接受。修复保持 `legacy | database` 双模式、固定 Operation Graph 流程、MCP 公共名称和标准 HTTP 响应信封，不引入远程审批服务、Redis 或 Registry 微服务。

## 逐项处置

| # | 级别 | 裁定 | 技术处置与证据 |
|---|---|---|---|
| 1 | Critical | 接受 | 删除灰度发布自动 upsert allow；`gray_percentage` 落在版本并仅控制流量。候选仍通过现有 version/tool policy 独立授权，tool deny 或无可继承策略都不会进入灰度。覆盖 `test_publish_gray_never_synthesizes_permission_allow`（无策略/tool deny）。 |
| 2 | Critical | 接受 | Operation HTTP 身份的 `roles` 按既有 API 约定取首个角色，兼容旧 `role`。真实 ASGI HTTP → Operation Graph → Gateway 集成测试证明 `operator` deny 命中并写拒绝审计，未走 internal fallback。 |
| 3 | Critical | 调整 | 设计要求确认安全，计划公开流程是 Gateway 签发挑战；不扩张为独立审批系统。挑战新增随机 nonce，成功校验后在副作用前写唯一 `confirmation_token_hash`，数据库提交即原子消费；第二个 Gateway 用同库重放不会再次执行。普通审计仍 best effort，但确认消费落库失败专门 fail closed。 |
| 4 | Critical | 接受 | seed 改为 creation-only：定义存在不更新；任一版本存在不补/恢复 1.0.0；任一策略存在不补/恢复 allow。覆盖禁用定义、退役 1.0.0、deny 与更新稳定版。 |
| 5 | Important | 接受 | `replace_policies` 改为旧启用策略软下线再插入新集合；审计 FK 保留。调用审计增加不可变 policy/tool/version snapshot，即使未来外键为空也可追溯。 |
| 6 | Important | 接受 | canonical trace 顺序为全局 trace → `context.request_id` → 新生成值，并把它显式写回 BaseTool context。覆盖无全局但有 request id，以及无全局/无 request id 两种 MCP/SSE 类场景，结果与审计 trace 一致。 |
| 7 | Important | 调整 | “无候选策略”只跳过该灰度候选，随后选择稳定版本并独立授权；若稳定版也无策略，external 仍拒绝、internal 仍按设计可信默认。避免候选配置缺口错误阻断本可用稳定版。 |
| 8 | Important | 接受 | 定义增加 `created_by/updated_by`；版本增加 `created_by/updated_by/retired_at/retired_by`，并保留 `published_by`。创建、更新、发布、自动退役和显式退役均记录操作人，管理响应同步暴露。 |
| 9 | Important | 调整 | `replace_policies` 先 `FOR UPDATE` 锁 definition。启用 scope 用标准化哈希 `active_scope_key`，数据库唯一 `(tool_id, active_scope_key)`；禁用历史 key 为空。该方案规避 MySQL 对含 NULL 组合唯一键不互斥的限制。SQLite 验证约束，spy/SQL 路径验证锁请求；真实互斥依赖生产约定的 InnoDB 事务。 |
| 10 | Important | 调整 | 通用发布服务继续只验证 JSON Schema/执行器，避免非 MCP 工具耦合 MCP；映射到 MCP 的工具在 Server 构建时校验公开字段集合及 JSON 类型兼容，移除内部 context 后用 Registry schema 替换 FastMCP schema，并在调用时严格校验嵌套约束。公共 MCP 名不变。 |
| 11 | Important | 接受 | `ToolForbiddenError` 仅在内部携带完整 resolution；Gateway 拒绝审计持久化 tool/version/implementation/policy/gray bucket/stable 标记与策略快照，公开错误 detail 保持兼容。 |
| 12 | Important | 接受 | 创建工具预检 capability；工具/版本/策略保存捕获并分类 `IntegrityError`，并发唯一冲突统一变成 `RegistryConfigurationError`，HTTP 映射现有 400050，而非 500。 |
| 13 | Minor | 接受 | 公共 `GET /tools` 统一调用双模式 `discover_tools`；database 模式只展示当前调用方可见的启用/已发布工具，响应仍只有 `name/description`。 |
| 14 | Minor | 接受 | 429 在标准 ApiResponse 信封中保留结构化 `data.retry_after_seconds`，同时设置标准 `Retry-After` header；异常直抛和 ToolResult 错误两条路径均覆盖。 |

## Schema 与迁移

- 新迁移：`20260819_0005_harden_tool_registry_governance.py`，父版本 `20260819_0004`。
- 新增定义/版本操作人字段、版本灰度和退役字段、策略 active scope、审计快照、确认令牌哈希及两个唯一索引。
- 迁移先将已有重复启用 scope 按 id 确定性软下线，再回填与 Python 相同的长度前缀 scope 哈希。
- 未连接生产数据库；Alembic 保持单 head。

## TDD 证据

- 运行时授权/角色/trace/拒绝审计：先新增 7 个失败测试，再修复为 7 passed。
- 确认重放与 seed：先新增 3 个失败测试，再修复为 3 passed。
- 策略历史/管理操作人/并发约束/冲突映射：先新增 9 个失败测试，再修复为 9 passed。
- MCP schema/工具枚举/429：先新增 5 个失败测试，再修复为 5 passed。
- MCP 属性类型兼容：新增测试先失败 1，再实现为通过。
- MCP 对无效 falsy filters 的严格校验：新增测试先失败 1，再修复为通过。
- 管理响应灰度元数据与 seed 操作人：新增测试先失败 2，再实现为通过。

## 最终验证

- 必跑专项：`331 passed, 1 warning in 18.97s`。
- MCP 启用专项：`18 passed in 2.91s`，真实 FastMCP 注册/列举/嵌套 schema/执行兼容通过。
- 全量（最终 staged tree 复验）：`693 passed, 2 failed, 1 warning in 39.74s`；失败集合与审查前基线完全相同：
  - `tests/analysis_stream/test_analysis_stream_api.py::TestAnalysisStreamApi::test_stream_uses_real_graph_node_keys`
  - `tests/analysis_stream/test_stream_service.py::test_node_order_matches_graph`
- `python -m compileall -q app alembic/versions tests/tool_registry tests/tools tests/operation_agent`：通过。
- `git diff --check`：通过。
- `alembic heads`：`20260819_0005 (head)`，单 head。
- 未连接或修改生产数据库。

## 剩余风险

- 多实例全局限流仍按原设计 deferred（进程内固定窗口），不属于本轮 14 项。
- MCP callable 兼容在 Server 构建时 fail fast，而非通用版本发布时；这是为避免 Registry 管理服务依赖 MCP 的有意边界。部署应在发布后执行 MCP 构建/启动探针。
- 策略并发依赖 MySQL InnoDB 对 definition 行的 `SELECT ... FOR UPDATE`；SQLite 测试只能验证约束与调用路径，不能模拟真实 MySQL 锁等待。
- 全量套件的两个 Analysis Stream 节点顺序失败为审查前既有基线；本轮不修改该业务流，也不跳过测试。
