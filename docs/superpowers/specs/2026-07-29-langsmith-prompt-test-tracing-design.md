# LangSmith Prompt 测试追踪设计

## 1. 背景与目标

Prompt Center 已具备本地 Prompt 版本、测试用例、测试运行记录，以及基于
`Client.push_prompt(...)` 的 LangSmith Prompt 同步能力。当前 Prompt 测试直接调用
`LlmClient.chat()`，没有传入 LangSmith 回调，因此 LangSmith 只能看到既有 Agent
Graph Trace，不能按 Prompt Key、版本和本地测试记录定位 Prompt 测试。

本期目标是完成 Prompt 测试的可观测闭环：

- LangSmith **Prompts** 中能看到已发布 Prompt 的 Commit 和 Tag。
- LangSmith **Tracing** 中能看到 `ioc_prompt_test_run` 父 Run 及其 LLM 子 Run。
- Trace 能关联本地 Prompt、版本、测试用例和测试运行记录。
- Prompt、输入和输出经过现有递归脱敏后上传。
- LangSmith 不可用时，本地 Prompt 测试仍能完成并保留审计记录。

当前种子 Prompt `ioc.safety.analysis` 仅作为 Prompt Center 功能与合成数据验收对象，
不将其描述为已接入业务 Graph 的真实运行时 Prompt。

## 2. 范围

### 2.1 本期包含

- 扩展 `LlmClient.chat()`，允许传入 `RunnableConfig`。
- 为单条测试和数据集测试建立统一的 LangSmith 父子追踪。
- 将 LangSmith Trace ID 保存到本地 `prompt_test_run.trace_id`。
- 在 Trace 元数据中记录 Prompt 版本事实。
- 沿用 `sanitize_trace_payload` 和 `LANGSMITH_MASK_INPUTS_OUTPUTS`。
- 启用当前环境的 Prompt 自动同步，并补同步当前已发布版本。
- 使用一条合成测试用例完成远程验收。
- 增加关闭追踪、正常追踪、异常降级和元数据传递测试。

### 2.2 本期不包含

- 上传真实 IOC 业务数据。
- 自动 Prompt 优化、A/B 测试或自动回滚。
- 修改现有确定性评分规则和 `expected_output` 语义评估。
- 将 `ioc.safety.analysis` 接入真实业务 Graph。
- 用 LangSmith 替换 IOC 本地 `ai_trace` 或 Prompt 测试记录。

## 3. 方案选择

采用 **LangChain Runnable 父子追踪**：

- 父 Run 表示一次完整 Prompt 测试，名称固定为 `ioc_prompt_test_run`。
- 子 Run 表示实际 Chat Model 调用。
- 通过现有 `build_langsmith_config()` 显式注入 `LangChainTracer`。

未采用仅追踪模型调用的扁平方案，因为它不能清晰表达本地测试与 LLM 调用的边界。
未采用手工维护 `RunTree`，因为 Runnable 已能提供父子关系、异常结束和回调传播，
手工生命周期管理会增加重复代码和未结束 Run 的风险。

## 4. 架构与职责

### 4.1 Prompt 测试服务

`prompt_test_service.run_single_test()` 负责：

1. 校验 Prompt 和版本。
2. 渲染待测试消息。
3. 创建本地 `prompt_test_run`，初始状态为 `running`。
4. 生成可关联的 `trace_id` 并写回本地记录。
5. 组装 Prompt 测试追踪元数据。
6. 调用 Prompt 测试 Runnable。
7. 保存输出、Token、耗时和最终状态。

数据集测试继续逐条复用 `run_single_test()`，每个测试用例产生独立父 Run，便于在
LangSmith 和本地记录间一一对应。

### 4.2 Prompt 测试 Runnable

在 `prompt_center/application` 下新增 `prompt_test_tracing.py`，用
`RunnableLambda` 建立边界清晰的执行单元，职责仅限：

- 接收已经渲染的 system/user 消息和 LLM 调用参数。
- 使用 `build_langsmith_config()` 创建父级 `ioc_prompt_test_run`。
- 在父级 Runnable 内调用 `LlmClient.chat(config=...)`。
- 返回原有 `LlmResult`，不改变业务层返回契约。

该执行单元不访问数据库，不负责 Prompt 渲染，也不决定测试状态。

### 4.3 LLM Client

`LlmClient.chat()` 新增可选 `config` 参数，并将其传给
`ChatOpenAI.invoke(messages, config=config, ...)`。未传入配置时行为保持不变，
避免影响现有调用方。

### 4.4 现有观测组件

继续复用 `backend/app/observability/langsmith_tracing.py`：

- `build_langsmith_config()`：配置项目、Run 名称、Tags 和 Metadata。
- `sanitize_trace_payload()`：递归脱敏字符串、集合和凭证字段。
- `_get_client()`：根据开关、API Key 和采样率决定是否创建远程客户端。

`build_langsmith_config()` 增加可选的附加 Tags 参数；默认值为空，现有调用方行为
不变。Prompt 测试通过该参数加入 `prompt-center`、`prompt-test`、Prompt Key 和版本
Tags。

不启用全局隐式追踪，避免无意上传其他测试或业务调用。

## 5. 数据流

1. 前端调用 Prompt 单条测试或数据集测试接口。
2. 后端创建本地测试记录，获得 `test_run_id`。
3. 后端生成 `trace_id`，保存到本地记录。
4. 后端用 Prompt 版本事实构建 LangSmith 配置。
5. 父级 Runnable 记录脱敏后的测试输入。
6. LLM Client 在父级上下文中调用模型，产生 LLM 子 Run。
7. 父 Run 记录脱敏后的输出；LangSmith 自动记录模型耗时和 Token 信息。
8. 后端更新本地测试记录并返回现有 API 响应。
9. 用户可通过 `trace_id`、`prompt_key` 或 `prompt_test_run_id` 在 LangSmith 中检索。

## 6. Trace 命名与元数据

父 Run 名称固定为 `ioc_prompt_test_run`，Tags 至少包含：

- `ioc`
- 当前 `app_env`
- `prompt-center`
- `prompt-test`
- Prompt Key
- Prompt 版本

Metadata 使用稳定字段名：

| 字段 | 含义 |
| --- | --- |
| `ioc_trace_id` | 本地与 LangSmith 的关联 ID |
| `graph_name` | 固定为 `ioc_prompt_test_run` |
| `prompt_key` | Prompt 唯一键 |
| `prompt_id` | 本地 Prompt ID |
| `prompt_version_id` | 本地版本 ID |
| `prompt_version` | 版本号 |
| `prompt_commit_hash` | LangSmith Commit Hash，可为空 |
| `prompt_tag` | LangSmith Commit Tag，可为空 |
| `prompt_environment` | 固定为 `test` |
| `prompt_test_run_id` | 本地测试运行 ID |
| `prompt_test_case_id` | 本地测试用例 ID，可为空 |
| `model_name` | 本次测试选择的模型 |
| `provider_name` | 模型 Provider，可为空 |
| `operator_ref` | 操作者不可逆短引用，可为空 |

Commit 或 Tag 为空时仍上传其他版本事实，不伪造远程版本；补同步成功后，新测试必须
携带真实 Commit 和 Tag。

## 7. 安全与数据边界

- 保持 `LANGSMITH_MASK_INPUTS_OUTPUTS=true`。
- Prompt 正文、输入数据和模型输出由 `sanitize_trace_payload()` 递归脱敏。
- API Key、Token、密码和 Authorization 等凭证字段替换为
  `[REDACTED:credential]`。
- 操作者标识通过 `stable_reference()` 转为不可逆短引用。
- 自动化测试统一关闭远程追踪，不向 LangSmith 上传测试夹具。
- 远程验收仅使用现有合成测试用例，不使用真实设备、用户或生产告警数据。

## 8. 异常与降级

- LangSmith 关闭、采样率为零或客户端初始化失败：返回无回调配置，继续本地测试。
- LangSmith 回调上传失败：不得将一次成功的模型调用改判为业务失败；记录日志并保留
  本地结果。
- 模型调用失败：本地记录标记为 `failed`，父 Run 记录异常，接口保持现有失败响应契约。
- 本地数据库写入失败：按现有事务语义失败，不以远程 Trace 作为业务数据源。
- Prompt 同步失败：本地发布结果保持有效，状态保留为可重试；不伪造 Commit Hash。

IOC 数据库仍是 Prompt 版本和测试记录的主数据源，LangSmith 只承担远程版本镜像、
调用分析和效果观测。

## 9. 测试策略

### 9.1 单元测试

- `LlmClient.chat(config=...)` 将配置传入模型 `invoke()`。
- 未传配置时保持原有调用行为。
- Prompt 测试服务生成并持久化 `trace_id`。
- Metadata 包含 Prompt Key、版本、Commit、Tag 和本地测试 ID。
- 父级 Runnable 将回调传播到 LLM 子调用。
- Prompt、输入、输出和凭证字段按预期脱敏。
- 追踪关闭或初始化失败时仍返回正常本地测试结果。
- 模型异常时本地状态和 Trace 异常语义一致。

### 9.2 回归测试

- Prompt Center 测试套件通过。
- Observability 测试套件通过。
- Backend 全量测试通过。
- `git diff --check` 通过。
- 测试期间显式设置 `LANGSMITH_TRACING=false`。

### 9.3 远程验收

1. 在当前本地环境启用 `LANGSMITH_PROMPT_SYNC_ENABLED=true`。
2. 对当前已发布版本执行同步或幂等补同步。
3. 在 LangSmith Prompts 中确认 `ioc.safety.analysis`、版本 Tag 和 Commit。
4. 运行一条合成 Prompt 测试。
5. 通过 LangSmith API 回查对应 `ioc_trace_id`。
6. 确认父 Run `ioc_prompt_test_run`、LLM 子 Run、Prompt 元数据、耗时和 Token 可见。
7. 检查输入输出已脱敏，且未上传真实业务数据。

只有远程 API 回查成功，才能报告“LangSmith 已可查看 Prompt 测试信息”；本地测试通过
或本地生成 Trace 配置不能替代远程验收。

## 10. 完成标准

- 当前发布 Prompt 已同步到 LangSmith 并拥有真实 Commit 和 Tag。
- 一条合成测试在 LangSmith 中形成完整父子 Trace。
- Trace 可通过本地 `trace_id` 精确查询。
- Trace Metadata 能定位 Prompt Key、版本和本地测试记录。
- Prompt、输入和输出采用现有脱敏策略。
- LangSmith 故障不影响 IOC 本地 Prompt 测试闭环。
- 新增测试和 Backend 回归测试全部通过。
