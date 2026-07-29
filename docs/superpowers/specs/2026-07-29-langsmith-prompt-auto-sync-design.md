# LangSmith Prompt 自动同步设计

## 1. 背景与目标

AIOperationsCenter V2 已将 `ioc.safety.analysis` 建模为可编辑、可审核、可发布和可回滚的 Prompt 资产，并在 Operation Graph Trace metadata 中记录：

- `prompt_key`
- `prompt_version`
- `prompt_commit_hash`
- `prompt_environment`

当前仍存在一个断点：

1. `LangSmithPromptClient.push_prompt` 使用的参数不符合当前已安装的 `langsmith 0.9.8` SDK。
2. 灰度发布和正式发布没有调用 Prompt 同步客户端。
3. `prompt_version.langsmith_commit_hash` 和 `langsmith_tag` 没有自动写入。
4. Trace 虽具备 Commit 字段，但通常只能记录空值。

本次目标是在不改变 IOC 作为发布控制面的前提下，完成以下严格闭环：

```text
Prompt 版本审核通过
→ 发布前自动同步 LangSmith Prompt Hub
→ 保存 Commit Hash 和版本 Tag
→ 创建 IOC 发布记录
→ LangGraph Trace 自动携带 Commit 信息
```

## 2. 范围

### 2.1 本次实现

- 新增独立的 LangSmith Prompt 同步开关。
- 修正 Prompt Client，使其兼容 `langsmith 0.9.8`。
- 将 Prompt Version 转换为 LangSmith `ChatPromptTemplate`。
- 在灰度发布和正式发布前执行同步。
- 同步失败时阻止发布，并保留原生产版本。
- 同一 Prompt Version 重复发布时复用已有 Commit。
- 将 Commit Hash 和版本 Tag 保存到 `prompt_version`。
- 在发布审计日志中记录同步事实。
- 补充单元测试、发布集成测试和配置文档。

### 2.2 本次不实现

- 异步 Outbox、后台 Worker 和自动重试队列。
- 从 LangSmith 反向覆盖 IOC Prompt。
- LangSmith 作为生产运行时 Prompt 唯一读取源。
- 自动灰度流量、复杂 A/B 或多模型自动比较。
- 将现有全部 Prompt 批量上传。
- 未经确认上传真实业务 Prompt 或真实运营数据。

## 3. 核心原则

1. IOC 仍是 Prompt 编辑、审核、发布和回滚的权威控制面。
2. LangSmith 保存与 IOC 不可变版本对应的 Prompt Commit。
3. 当 `LANGSMITH_PROMPT_SYNC_ENABLED=true` 时，同步失败必须阻止灰度和正式发布。
4. 同步失败不能停用当前 active release，也不能更新 Prompt 当前版本。
5. 当同步开关关闭时，本地开发和自动化测试仍可离线发布。
6. Trace 与 Prompt Hub 使用同一个 Commit Hash 关联，但 IOC 本地审计链继续保留。
7. 自动化测试只使用 Fake Client，不产生远程上传。

## 4. 方案选择

### 4.1 采用：发布前同步

在 `_release` 完成本地发布变更之前同步 LangSmith。同步成功或已有 Commit 后，才允许继续创建本地 Release。

优点：

- 同步时机与真正生效时机一致。
- 未发布的审核版本不会污染 LangSmith Prompt Hub。
- 同步失败不会改变当前生产版本。
- 不需要引入后台任务系统。

### 4.2 未采用：审核通过时同步

审核通过不等于最终发布。此方案会上传从未发布的版本，并让审核动作依赖第三方服务。

### 4.3 未采用：异步 Outbox

Outbox 适合更高并发和复杂补偿，但需要任务表、Worker、重试策略和状态页面。当前一期采用同步严格发布，后续在发布量或稳定性需求增加时再演进。

## 5. 配置设计

在 `Settings` 中新增：

```python
langsmith_prompt_sync_enabled: bool = False
```

对应环境变量：

```text
LANGSMITH_PROMPT_SYNC_ENABLED=false
```

配置职责：

| 配置 | 作用 |
|---|---|
| `LANGSMITH_TRACING` | 控制 Graph Trace 是否上传 |
| `LANGSMITH_PROMPT_SYNC_ENABLED` | 控制发布时是否同步 Prompt Hub |
| `LANGSMITH_API_KEY` | 两种能力共用的认证密钥 |
| `LANGSMITH_ENDPOINT` | LangSmith API 地址 |
| `LANGSMITH_PROJECT` | Trace Project，不作为 Prompt identifier |

严格校验：

- 同步开关关闭：不调用 LangSmith，允许本地发布。
- 同步开关开启但 API Key 为空：抛出 Prompt 同步失败错误，阻止发布。
- 同步开关开启且 API Key 存在：执行远程同步。

## 6. Prompt 模板映射

### 6.1 LangSmith Prompt Identifier

直接使用 IOC `prompt_key`：

```text
ioc.safety.analysis
```

Prompt 默认保持私有。

### 6.2 ChatPromptTemplate 结构

LangSmith Commit 使用 `ChatPromptTemplate`，包含两个消息：

```text
System Message
  = prompt_version.system_content

Human Message
  = Business Role
  + Business Goal
  + Business Rules
  + Output Requirement
  + Positive Examples
  + Negative Examples
  + 当前上下文 {runtime_context}
  + 用户问题 {user_question}
```

`runtime_context` 和 `user_question` 是 LangSmith 中可见的运行时占位符。版本中的字面量花括号必须先转义，避免 JSON 示例或业务文本被误识别为模板变量。

业务内容拼装应复用 Prompt Center 已有的业务内容构建逻辑，避免 LangSmith 展示内容与 IOC 运行内容使用两套规则。

### 6.3 Commit Metadata

调用：

```python
Client.push_prompt(
    prompt_identifier=prompt_key,
    object=chat_prompt_template,
    is_public=False,
    description=prompt_description,
    tags=["ioc", "managed-prompt"],
    commit_tags=[version, "managed-by-ioc"],
    commit_description=change_reason,
)
```

保存：

- `langsmith_commit_hash`：从返回的 Prompt Commit URL 中解析。
- `langsmith_tag`：Prompt Version，如 `1.1.0`。

环境不写入版本 Tag。一个不可变版本在不同环境发布时复用同一 Commit，具体生效环境继续由 IOC `prompt_release` 和 Trace `prompt_environment` 表达。

## 7. 发布数据流

### 7.1 首次发布

```text
校验 Prompt 存在
→ 校验 Version 属于 Prompt
→ 校验 Version 状态允许发布
→ 检查同步开关
→ 构造 ChatPromptTemplate
→ LangSmith push_prompt
→ 解析 Commit Hash
→ 保存 Version Commit Hash 和 Tag
→ 停用当前环境 active release
→ 创建新 release
→ 更新 Prompt Version 状态
→ 更新 Prompt Definition 当前版本
→ 写发布审计日志
```

LangSmith 调用和 Commit 保存必须发生在 `deactivate_env` 之前。

### 7.2 重复发布

如果 Version 已有非空 `langsmith_commit_hash`：

- 不再次调用 LangSmith。
- 直接复用已有 Commit。
- 继续完成目标环境发布。

这保证同一不可变版本不会因重复发布生成多个 Commit。

### 7.3 回滚

回滚不创建新的 LangSmith Commit：

- 目标旧版本必须保留原有 Commit Hash。
- 回滚后 active release 指向旧版本。
- 后续 Trace 自动读取旧版本 Commit Hash。

为了兼容历史版本，旧版本 Commit Hash 为空时仍允许本地回滚；回滚是故障恢复动作，不应因第三方同步缺失而被阻断。

## 8. 一致性与失败处理

### 8.1 严格失败语义

新增错误码：

```text
PROMPT_SYNC_FAILED
HTTP 502
```

错误消息应区分：

- 同步已开启但 API Key 未配置。
- LangSmith Client 初始化失败。
- Prompt 模板序列化失败。
- LangSmith API 请求失败。
- 返回 URL 无法解析 Commit Hash。
- Commit Hash 保存失败。

对外响应不暴露 API Key、远程响应正文或敏感 Prompt 内容。

### 8.2 状态保护

同步失败时必须保持：

- 原 active release 不变。
- 新 release 不创建。
- Prompt Definition 当前版本不变。
- Version 发布状态不变。
- 不写“发布成功”审计日志。

如果远程 Commit 已创建，但 IOC 保存 Commit Hash 失败，可能产生一个远程孤立 Commit。下次发布允许重新同步；当前一期不引入分布式事务或远程删除补偿。

### 8.3 数据安全

Prompt Hub 同步上传的是版本化 Prompt 模板，不包含本次运行的设备数据、告警、用户信息和模型输出。

模板中可能包含业务规则、示例和输出 Schema，因此：

- Prompt 必须保持 private。
- 日志不能打印完整 Prompt 或 API Key。
- 真实远程验收必须使用脱敏测试 Prompt，并获得明确确认。

## 9. 组件职责

### 9.1 `LangSmithPromptClient`

职责：

- 根据当前配置判断同步是否启用。
- 创建 LangSmith Client。
- 构造或接收 `ChatPromptTemplate`。
- 调用 `push_prompt`。
- 解析并返回结构化同步结果。

建议返回值：

```python
@dataclass(frozen=True)
class PromptSyncResult:
    commit_hash: str
    tag: str
    url: str
```

客户端不直接写数据库，也不决定发布状态。

### 9.2 Prompt 同步服务

新增独立应用层服务，职责：

- 接收 Prompt Definition 和 Prompt Version。
- 复用已有 Commit 或调用客户端同步。
- 保存 `langsmith_commit_hash` 和 `langsmith_tag`。
- 将底层异常转换为统一业务错误。

发布服务只调用：

```python
ensure_prompt_version_synced(db, prompt, version)
```

### 9.3 发布服务

职责保持为：

- 校验发布状态。
- 在本地发布变更前确保版本已同步。
- 创建 release、更新版本和定义状态。
- 记录包含 Commit Hash 的审计事实。

## 10. 审计与可观测性

发布审计 `after_data` 增加：

```json
{
  "environment": "production",
  "release_type": "full",
  "version": "1.1.0",
  "langsmith_commit_hash": "commit-hash",
  "langsmith_tag": "1.1.0"
}
```

Operation Graph 已有 metadata 注入逻辑，无需改变字段协议。发布成功后，下一次分析 Trace 应出现：

```json
{
  "prompt_key": "ioc.safety.analysis",
  "prompt_version": "1.1.0",
  "prompt_commit_hash": "commit-hash",
  "prompt_environment": "production"
}
```

## 11. 测试设计

所有行为使用 TDD 实现。

### 11.1 Prompt Client

- 使用当前 SDK 正确调用 `push_prompt`。
- Prompt identifier、private、Prompt tags、Commit tags 和描述正确。
- 能从返回 URL 解析 Commit Hash。
- 返回 URL 不含 Commit Hash 时失败。
- SDK 异常转换为同步异常。

### 11.2 同步服务

- 开关关闭时不调用远程 Client。
- 开关开启但 API Key 缺失时失败。
- 首次同步保存 Commit Hash 和 Tag。
- 已同步版本直接复用，不重复调用远程 Client。
- 保存失败时不能报告同步成功。

### 11.3 发布集成

- 同步成功后才能创建 release。
- 同步失败时 active release、Prompt Definition 和 Version 状态不变。
- 灰度发布和正式发布都执行同步。
- 回滚不调用同步 Client。
- 审计日志包含 Commit Hash 和 Tag。

### 11.4 回归验证

- V2 Prompt 专项测试。
- 后端全量测试。
- Alembic Head 检查。
- 前端 TypeScript 和构建检查仅在接口类型发生变化时执行。
- `git diff --check`。

## 12. 文档与运行说明

更新以下配置说明：

- `backend/.env.example`
- `backend/README.md`
- `docs/v2-prompt/项目总结.md`
- `docs/v2-prompt/项目面试.md`

运行模式：

```text
# 本地离线开发
LANGSMITH_PROMPT_SYNC_ENABLED=false

# 严格远程同步
LANGSMITH_PROMPT_SYNC_ENABLED=true
LANGSMITH_API_KEY=<secret>
```

自动化测试必须显式关闭远程同步，或通过 Fake Client 覆盖，确保测试不会上传数据。

## 13. 验收标准

满足以下条件才视为实现完成：

1. SDK 调用与当前 `langsmith 0.9.8` 契约一致。
2. 同步开关开启时，首次灰度或正式发布自动生成 Commit。
3. Commit Hash 和 Tag 保存到对应 Prompt Version。
4. 同步失败返回 502，且当前生产 Release 不变。
5. 同一 Version 重复发布不产生重复 Commit。
6. 回滚不依赖新建 Commit。
7. 发布审计包含 Commit Hash 和 Tag。
8. 下一次 Graph Trace 能从数据库读取 Commit Hash。
9. 专项测试和后端全量测试通过。
10. 未经明确确认，不执行真实业务 Prompt 远程上传。

