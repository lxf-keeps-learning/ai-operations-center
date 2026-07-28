# Prompt Center 一期最小闭环设计

## 1. 决策状态

本设计已确认以下产品决策：

- Prompt 配置融合到现有 `/infra/config` 配置中心，不新增一级导航。
- 采用两角色模型：运营人员、管理员。
- IOC 数据库是 Prompt 版本主数据源，现有 Markdown 是运行时安全回退。
- LangSmith 用于 Prompt 镜像、Trace 聚合和效果观测，不作为生产运行依赖。
- 一期仅覆盖 5 个真实运行 Prompt，不建设复杂实验、自动优化或独立失败案例中心。

## 2. 目标与非目标

### 2.1 目标

一期形成以下可验证闭环：

1. 配置中心展示 5 个真实 Prompt。
2. 运营人员创建草稿、编辑业务内容、预览和执行单条测试。
3. 运营人员提交审核，管理员审核、发布和回滚。
4. 草稿不影响运行；Graph 只读取指定环境的已发布版本。
5. Prompt Center 异常时回退现有 Markdown。
6. 发布版本同步到 LangSmith，并在运行 Trace 中记录 Prompt 版本信息。
7. IOC 本地 `ai_trace` 保留 Prompt 快照、调用指标和审计能力。

### 2.2 非目标

一期不包含：

- A/B 流量分配和复杂实验中心。
- 自动 Prompt 优化或强化学习。
- 完整 Dataset 管理。
- 多模型批量比较。
- 独立质量评估和失败案例一级页面。
- 让前端直接调用 LangSmith。
- 将未被运行时代码引用的 Markdown 暴露为“可调优 Prompt”。

## 3. 当前代码基线

仓库已存在一组未提交的 Prompt Center、评估、实验和失败案例草稿代码，但当前状态
不能作为完成基线：

- 前端正式构建存在 TypeScript 错误。
- Alembic 新迁移引用了不存在的 `down_revision`。
- 当前 LangSmith Prompt 客户端调用不符合已安装的 `langsmith 0.9.8` API。
- 新的 Prompt Resolver 尚未被真实 Graph 节点调用。
- 当前 seed 脚本只创建代码中不存在的 `ioc.safety.analysis` 示例。
- Prompt Center API 缺少针对性测试；现有全量测试未覆盖新模块。

实现阶段应保留用户已有改动，按本设计收敛可复用代码，并停止注册一期范围外的页面和
Router。不得把现有草稿代码直接视为已完成能力。

## 4. 内置 Prompt 清单

一期仅注册真实调用点：

| Prompt Key | 页面名称 | Graph / Node | 现有回退文件 |
| --- | --- | --- | --- |
| `operation.analyze_reason` | 运营分析—原因分析 | `ioc_operation_analysis_graph / analyze_reason` | `operation_agent/prompts/system_prompt.md` + `operation_analysis.md` |
| `operation.generate_advice` | 运营分析—建议生成 | `ioc_operation_analysis_graph / generate_advice` | `operation_agent/prompts/system_prompt.md` + `operation_advice.md` |
| `report_chat.rag_decision` | 报告问答—RAG 决策 | `ioc_report_chat_graph / should_use_rag` | `report_chat_agent/prompts/rag_decision.md` |
| `report_chat.query_rewrite` | 报告问答—Query Rewrite | `ioc_report_chat_graph / build_rag_query` | `report_chat_agent/prompts/rag_query_rewrite.md` |
| `report_chat.generate_answer` | 报告问答—答案生成 | `ioc_report_chat_graph / generate_report_answer` | `report_chat_agent/prompts/system_prompt.md` + `report_answer.md` / `rag_answer.md` |

`operation_summary.md` 和 `boundary_response.md` 当前没有对应的 LLM 运行时消费点，一期
不展示。答案生成 Prompt 使用一个定义和两个内容变体，运行时由 `used_rag` 选择
`report_answer` 或 `rag_answer`，版本作为一个整体发布，避免两个分支版本失配。

## 5. 总体架构

```text
现有 Markdown
    │ 首次幂等导入，之后只作回退
    ▼
IOC Prompt DB ── 配置中心编辑/测试/审核/发布
    │                         │
    │ 已发布固定版本          └── 发布时 push_prompt
    ▼                                      │
Graph Prompt Resolver                      ▼
    │                              LangSmith Prompt Commit
    ├── 成功：统一渲染结果                  │
    └── 失败：Markdown 回退                 │ commit hash/tag
             │                              │
             ▼                              ▼
        真实 Graph 节点 ─────────── LangSmith Trace Metadata
             │
             └──────────────────── IOC ai_trace + Prompt 快照
```

依赖方向固定为：

- Graph 节点依赖轻量 `PromptResolver` 接口。
- `PromptResolver` 依赖 Prompt Repository、Renderer 和内置回退注册表。
- 发布服务依赖 LangSmith Adapter，但运行时 Resolver 不依赖 LangSmith。
- 前端只依赖 IOC Prompt API。

## 6. 初始化与主数据规则

新增集中式内置 Prompt 注册表，注册表保存 Prompt Key、展示名称、Graph/Node、变量定义、
内容变体和 Markdown 回退加载器。

初始化必须幂等：

- 本地开发启动时可调用 `ensure_builtin_prompts()`，确保首次打开页面即可看到 5 条数据。
- 正式环境通过同一函数的 CLI/部署步骤执行，避免应用启动时发生不可控数据写入。
- 仅当 Prompt Key 不存在时创建 `v1.0.0` 和 production 发布记录。
- Prompt Key 已存在时绝不覆盖数据库内容或移动 production 指针。
- 内置源内容哈希写入初始版本元数据，用于审计，不自动覆盖线上版本。
- 当前虚构 seed 数据不再作为默认初始化内容。

## 7. 数据模型

一期使用以下表：

- `prompt_definition`
- `prompt_version`
- `prompt_variable`
- `prompt_release`
- `prompt_test_run`
- `prompt_evaluation`（仅基础确定性评估）
- `prompt_audit_log`

`prompt_test_case` 可保留接口和表结构，但一期页面只要求单条即时测试。

`prompt_version` 增加或明确以下同步字段：

- `langsmith_commit_hash`
- `langsmith_tag`
- `langsmith_sync_status`: `not_required | pending | synced | failed`
- `langsmith_sync_error`
- `langsmith_synced_at`

`ai_trace` 继续使用现有字段：

- `prompt_id`: Prompt Version ID 的字符串形式。
- `prompt_code`: Prompt Key。
- `prompt_version`: Prompt Version ID。
- `prompt_snapshot`: 实际发送给模型的完整 Prompt 快照。
- `graph_name`、`node_name`、Token、耗时和状态字段。

以下补充信息写入 `input_data.prompt_metadata`，避免一期继续扩展 Trace 表：

```json
{
  "version_label": "1.2.0",
  "langsmith_commit_hash": "abc123",
  "environment": "production",
  "fallback": false,
  "variant": "rag_answer"
}
```

## 8. 生命周期与状态

一期版本状态：

```text
draft → reviewing → approved → published
  ▲         │           │
  └─ rejected           └─ 可发布
```

规则：

- 每次编辑保存到草稿版本；已发布版本不可修改。
- 运营人员可创建草稿、更新业务字段、测试和提交审核。
- 管理员可审核、驳回、发布和回滚。
- 发布通过事务切换 production 指针并锁定版本。
- 回滚创建新的 release 记录并将 production 指针指回上一版本。
- LangSmith 同步失败不回滚 IOC 发布，版本标记为 `failed` 并提供重试。
- 草稿、审核中和驳回版本不会被生产 Resolver 读取。

## 9. 权限模型

复用现有 `UserContext` 中的 `roles` 和 `permissions`，在 Prompt API 层新增统一依赖检查。

### 9.1 角色映射

运营人员 `prompt_operator`：

- `prompt:read`
- `prompt:draft:create`
- `prompt:draft:update`
- `prompt:preview`
- `prompt:test`
- `prompt:submit`

管理员 `prompt_admin`：

- 包含运营人员全部权限。
- `prompt:system:update`
- `prompt:review`
- `prompt:publish`
- `prompt:rollback`
- `prompt:langsmith:read`
- `prompt:langsmith:retry`

### 9.2 字段级保护

运营人员可编辑：

- 业务角色
- 业务目标
- 业务规则
- 输出要求
- 正例和反例
- 变更原因

仅管理员可编辑：

- System Prompt
- 模型配置
- 输出 Schema
- 变量定义和敏感标记
- LangSmith 配置

前端按权限隐藏或禁用操作，后端必须再次校验。运营人员提交受保护字段时返回 `403`，
不能静默丢弃。

当前请求头由浏览器直接提供，不能视为完整生产认证。正式部署时网关必须移除客户端
自带的 `X-User-*`、`X-Roles`、`X-Permissions`，并用已认证身份重新写入。开发环境
允许使用固定的本地角色配置验证两种界面，但该配置不得用于生产。

## 10. 前端信息架构

移除当前新增的一级入口：

- Prompt 管理
- 质量评估
- 实验中心
- 失败案例

配置中心路由：

```text
/infra/config                         配置中心，默认运行环境页签
/infra/config/prompts                 Prompt 列表页签
/infra/config/prompts/:id             Prompt 详情
/infra/config/prompts/:id/edit        草稿编辑与最终 Prompt 预览
/infra/config/prompts/:id/test        单条测试与基础评估
/infra/config/prompts/:id/compare     版本对比
/infra/config/prompts/:id/release     管理员审核、发布与回滚
/infra/config/prompts/:id/metrics     使用情况与同步状态
```

列表页展示：

- 5 个真实 Prompt。
- Prompt Key、场景、Graph/Node、production 版本、草稿状态。
- LangSmith 同步状态。
- 真实调用量、错误数、平均 Token 和平均耗时；无数据时显示“暂无数据”。
- 基于当前角色的可执行操作。

一期不新建 Prompt 定义。内置 Prompt 的 Key、Graph 和 Node 映射由代码注册表管理，
避免运营人员创建无法被运行时消费的孤立配置。

## 11. API 边界

后端保持 `/api/v1/prompt-center` 模块前缀，主要接口为：

```text
GET    /prompts
GET    /prompts/{prompt_id}
POST   /prompts/{prompt_id}/versions
PUT    /prompts/{prompt_id}/versions/{version_id}
POST   /prompts/{prompt_id}/versions/{version_id}/preview
POST   /prompts/{prompt_id}/versions/{version_id}/test
POST   /prompts/{prompt_id}/versions/{version_id}/submit
POST   /prompts/{prompt_id}/versions/{version_id}/approve
POST   /prompts/{prompt_id}/versions/{version_id}/reject
POST   /prompts/{prompt_id}/versions/{version_id}/publish
POST   /prompts/{prompt_id}/rollback
POST   /prompts/{prompt_id}/versions/{version_id}/langsmith/retry
GET    /prompts/{prompt_id}/metrics
```

删除一期不需要的通用“新建 Prompt 定义”入口。所有写接口从 `UserContext` 获取操作者，
不接受请求体伪造 `operator_id`、`approved_by` 或 `released_by`。

## 12. 运行时 Resolver

统一返回：

```python
class ResolvedPrompt:
    prompt_id: int | None
    prompt_key: str
    version_id: int | None
    version_label: str
    environment: str
    messages: list[dict[str, str]]
    rendered_text: str
    langsmith_commit_hash: str | None
    fallback: bool
    variant: str | None
```

Resolver 行为：

1. 按 Prompt Key 和 `production` 环境查询 active release。
2. 加载不可变版本，校验变量并完成渲染。
3. 返回消息和元数据。
4. Prompt 不存在、数据库不可用、版本损坏或变量校验失败时加载内置 Markdown。
5. 回退必须记录告警、`fallback=true` 和原因，不得悄悄降级。

5 个节点只负责准备业务变量、调用 Resolver、调用 LLM 和写 Trace。节点不得直接访问
Prompt Center Repository。

## 13. LangSmith 集成

### 13.1 发布同步

- 使用已安装 SDK 的 `Client.push_prompt(prompt_identifier, object=..., commit_tags=...)`。
- Prompt 对象使用 `ChatPromptTemplate` 或等价 LangChain Prompt 对象。
- IOC 版本号使用普通 commit tag；生产环境使用 `production` commit tag。
- 保存返回 URL 中解析/查询得到的 commit hash；不拼接错误的 API Endpoint URL 作为 UI URL。
- 同步异常写入同步状态，不暴露 API Key 或完整异常凭据。

### 13.2 运行 Trace

为每个使用 Prompt 的 Graph/Node Run 注入：

```json
{
  "prompt_key": "operation.generate_advice",
  "prompt_version": "1.2.0",
  "prompt_version_id": 42,
  "prompt_commit_hash": "abc123",
  "prompt_environment": "production",
  "prompt_variant": null,
  "prompt_fallback": false,
  "ioc_trace_id": "trace_xxx",
  "graph_name": "ioc_operation_analysis_graph",
  "node_name": "generate_advice"
}
```

IOC `ai_trace` 继续承担业务审计和本地可追溯性。LangSmith 关闭或不可达时不影响
Graph、Prompt 发布或 IOC Trace。

## 14. 异常处理

| 场景 | 行为 |
| --- | --- |
| Prompt DB 不可用 | 使用内置 Markdown，Trace 标记回退 |
| production release 缺失 | 使用内置 Markdown并产生告警 |
| 模板变量缺失 | 测试接口返回明确 400；真实 Graph 回退 Markdown |
| 草稿测试 LLM 失败 | 保存失败的 Test Run 和 Trace，不改变版本状态 |
| LangSmith push 失败 | IOC 发布成功，状态为 `failed`，管理员可重试 |
| 越权字段更新或发布 | 后端返回 403 并写审计日志 |
| 回滚没有上一版本 | 返回明确 400，不改变 production 指针 |
| Trace 聚合无数据 | 页面显示“暂无数据”，不显示模拟值 |

## 15. 测试与验收

实施必须采用测试先行，至少覆盖：

### 15.1 初始化与数据

- 空数据库初始化后严格得到 5 个 Prompt。
- 重复初始化不新增版本、不覆盖草稿、不移动 production。
- 未引用 Markdown 不进入列表。
- Alembic revision 链可解析并升级到唯一 head。

### 15.2 权限

- 运营人员能创建/编辑业务草稿、预览、测试和提交。
- 运营人员修改 System Prompt、模型配置或调用发布/回滚接口返回 403。
- 管理员能审核、发布、回滚和重试 LangSmith 同步。
- 操作者来自请求上下文而非请求体。

### 15.3 生命周期与运行时

- 草稿不会改变 Resolver 返回的 production 版本。
- 发布后对应节点使用新版本并写入 Prompt 元数据。
- 回滚后 Resolver 恢复上一 production 版本。
- 数据库异常和渲染异常触发 Markdown 回退。
- 5 个真实节点均有 Resolver 接入与回退测试。

### 15.4 LangSmith 与本地观测

- `push_prompt` 参数符合 `langsmith 0.9.8` 契约。
- 同步成功保存 commit 信息，同步失败不阻断发布。
- Trace metadata 包含 Prompt Key、版本、Node 和 IOC Trace ID。
- LangSmith 关闭时不创建远程回调，IOC `ai_trace` 仍保留 Prompt 快照。
- 测试默认设置 `LANGSMITH_TRACING=false`，不得上传测试或真实业务数据。

### 15.5 前端

- Prompt 页面只出现在配置中心。
- 列表展示 5 个真实 Prompt 和真实/空指标状态。
- 两种角色的按钮和受保护字段符合权限矩阵。
- 编辑、预览、测试、提交审核、发布和回滚路径可完成。
- `npm run type-check` 与 `npm run build` 均通过。

### 15.6 最终验证命令

```bash
cd backend
LANGSMITH_TRACING=false PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q
.venv/bin/alembic heads

cd ../frontend
npm run type-check
npm run build
```

需要远程 LangSmith 验证时，只允许先上传不含 IOC 业务数据的合成 Trace。真实业务链路
上传必须单独获得明确授权。

## 16. 最小交付顺序

1. 修复迁移链并收敛一期模型。
2. 建立 5 个 Prompt 的内置注册表和幂等初始化。
3. 完成后端 RBAC、版本、测试、发布和回滚闭环。
4. 建立 Resolver，逐个接入 5 个真实节点并保留 Markdown 回退。
5. 修正 LangSmith `push_prompt` 与 Trace metadata。
6. 将前端页面收敛到配置中心并修复构建。
7. 完成后端、迁移、前端和合成 LangSmith 验证。

