你是一名资深 AI 应用架构师、产品架构师和全栈工程师，请基于当前 IOC 智能运营中心 Agent 能力层项目，设计并实现一个企业级的“AI 策略与 Prompt 管理中心”。

# 一、项目背景

当前项目是 IOC 智能运营中心 Agent 能力层，技术栈如下：

* 前端：Vue3、TypeScript、Vite、Element Plus
* 后端：Python、FastAPI、Pydantic
* Agent：LangChain、LangGraph
* 模型调用：支持结构化输出、Tool Calling、RAG、SSE 流式响应
* 数据库：MySQL
* 可观测与评估：LangSmith
* 架构方式：前后端分离、统一 DTO/Schema、RESTful API
* 运行环境：开发、测试、生产
* 当前已有 LangGraph Graph、Node、State、Tool、RAG、模型调用和 LangSmith Trace 能力

当前 IOC 项目中的 Prompt 可能分散在 LangGraph Node、Python 文件、配置文件中，缺少统一管理能力。

现在需要建设一个独立模块，让运营人员能够：

1. 查看当前 Agent 使用的 Prompt。
2. 理解 Prompt 的业务组成。
3. 修改允许运营调整的业务规则。
4. 使用真实或脱敏数据测试 Prompt。
5. 对比不同 Prompt 版本的效果。
6. 查看 Prompt 遵守率和评估结果。
7. 提交审核、灰度发布、正式发布和版本回滚。
8. 查看某次线上 Agent 运行实际使用的 Prompt 版本。

系统名称：

* 中文：AI 策略与 Prompt 管理中心
* 英文：AI Prompt & Strategy Center

# 二、核心设计原则

必须遵守以下原则：

1. 运营人员不能直接修改完整 System Prompt。
2. Prompt 必须拆分为系统层、业务层、运行时上下文和用户输入。
3. 系统安全约束、Tool 协议、变量定义、JSON Schema、权限控制由技术人员维护。
4. 业务分析规则、风险判断规则、表达方式、建议要求可以由运营人员维护。
5. 所有 Prompt 修改必须经过测试、评估、审核、灰度和发布流程。
6. 生产环境不能直接读取“最新 Prompt”，必须使用已发布版本、环境标签或固定版本。
7. 每次模型调用必须记录 Prompt Key、Prompt Version、Prompt Commit、Trace ID。
8. 必须支持版本回滚。
9. 必须保留完整审计日志。
10. 第一版优先实现可运行闭环，不要过度设计。

# 三、Prompt 分层模型

最终发送给模型的内容由以下部分组成：

```text
System Prompt
+ Business Prompt
+ Runtime Context
+ Conversation Context
+ User Question
```

## 3.1 System Prompt

由技术管理员维护，普通运营人员只读。

包含：

* AI 角色基础定义
* 安全约束
* Prompt 注入防护
* Tool 调用规范
* JSON Schema
* 数据权限规则
* 输出解析规范
* 不可覆盖的系统规则
* 模型行为边界

## 3.2 Business Prompt

由运营人员在授权范围内维护。

包含：

* 业务目标
* 分析重点
* 风险判断规则
* 业务术语
* 报告表达方式
* 建议生成要求
* 特殊场景说明
* 正例与反例

## 3.3 Runtime Context

由系统运行时自动注入。

可能包含：

* 设备实时数据
* 历史数据
* 告警数据
* 缺陷和隐患数据
* RAG 检索结果
* 当前用户信息
* 当前时间
* 租户信息
* 当前 Graph State
* Tool 返回结果

## 3.4 User Question

用户当前输入的问题。

# 四、业务角色与权限

设计以下角色：

## 4.1 运营查看者

权限：

* 查看 Prompt 列表
* 查看业务层 Prompt
* 查看版本记录
* 查看测试结果
* 查看遵守率
* 查看线上运行记录

## 4.2 运营编辑者

权限：

* 创建 Prompt 草稿
* 修改业务层 Prompt
* 增加业务规则
* 修改表达方式
* 维护业务示例
* 运行单条测试
* 运行测试集

不可修改：

* System Prompt
* Tool 协议
* 变量 Key
* JSON Schema
* 安全规则

## 4.3 业务审核者

权限：

* 查看 Prompt 修改差异
* 审核业务规则
* 驳回修改
* 填写审核意见

## 4.4 技术管理员

权限：

* 维护 System Prompt
* 维护变量定义
* 维护 JSON Schema
* 维护 Tool 配置
* 维护 LangGraph Node 绑定关系
* 维护 LangSmith 配置
* 查看最终完整 Prompt

## 4.5 发布管理员

权限：

* 灰度发布
* 正式发布
* 下线
* 回滚版本
* 调整灰度流量

# 五、核心功能

## 5.1 Prompt 列表

展示字段：

* Prompt 名称
* Prompt Key
* 业务场景
* 所属 Graph
* 所属 Node
* 当前版本
* 当前状态
* 负责人
* 最近修改人
* 最近发布时间
* Prompt 遵守率
* JSON 格式通过率
* 平均 Token
* 平均响应时间

支持：

* 名称搜索
* Prompt Key 搜索
* 业务场景筛选
* Graph 筛选
* Node 筛选
* 状态筛选
* 负责人筛选
* 时间筛选

## 5.2 Prompt 详情

展示：

* 基础信息
* 角色定义
* 业务目标
* 分析规则
* 动态变量
* 输出要求
* 正例
* 反例
* 当前版本
* 历史版本
* 线上表现
* LangSmith Prompt 地址或 Commit 信息

提供两种视图：

### 业务视图

面向运营人员，展示结构化、业务化内容。

### 完整视图

面向技术管理员，展示最终完整 Prompt，包括：

* System Message
* Business Message
* Runtime Context 模板
* User Message
* Tool 描述
* Output Schema

## 5.3 Prompt 编辑器

采用左右布局：

左侧：

* Prompt 基础信息
* 角色定义
* 业务目标
* 规则列表
* 表达要求
* 输出要求
* 正例
* 反例

右侧：

* 最终 Prompt 实时预览
* 消息角色预览
* 变量检查
* Token 预估
* 风险提示

要求：

* 规则列表支持新增、删除、排序和启停。
* 不允许运营人员修改受保护变量名称。
* 不允许删除系统必填规则。
* 修改时必须填写修改原因。
* 支持自动保存草稿。
* 页面离开前检查未保存内容。

## 5.4 动态变量管理

每个 Prompt 维护变量定义：

* variable_key
* variable_name
* description
* data_type
* source_type
* source_path
* required
* default_value
* example_value
* sensitive
* editable
* display_order

示例变量：

```json
[
  {
    "variable_key": "device_name",
    "variable_name": "设备名称",
    "data_type": "string",
    "source_type": "graph_state",
    "source_path": "device.name",
    "required": true,
    "editable": false
  },
  {
    "variable_key": "realtime_data",
    "variable_name": "实时数据",
    "data_type": "object",
    "source_type": "data_service",
    "source_path": "monitoring.realtime",
    "required": true,
    "editable": false
  },
  {
    "variable_key": "knowledge_context",
    "variable_name": "知识库内容",
    "data_type": "string",
    "source_type": "rag",
    "required": false,
    "editable": false
  }
]
```

## 5.5 Prompt 测试调优

支持输入：

* 手动填写测试数据
* 选择历史 Trace
* 选择预置测试用例
* 选择测试数据集
* 从线上失败案例复制

测试结果展示：

* 最终发送给模型的完整 Prompt
* 模型原始输出
* 结构化输出
* Token 使用量
* 响应时间
* 模型名称
* Prompt 版本
* Trace ID
* 格式校验结果
* Prompt 遵守评分
* 规则违反项
* Evaluator 评分说明

## 5.6 版本对比

支持对比两个 Prompt 版本：

* 角色定义差异
* 业务规则差异
* 输出要求差异
* 示例差异
* 变量差异
* JSON Schema 差异
* 模型参数差异
* 测试效果差异

效果对比指标：

* Prompt 遵守率
* JSON 格式通过率
* 无虚构率
* 证据完整率
* 建议完整率
* 平均 Token
* 平均响应时间
* 人工满意度

## 5.7 Prompt 生命周期

状态必须包含：

```text
DRAFT       草稿
TESTING     测试中
REVIEWING   待审核
APPROVED    审核通过
REJECTED    已驳回
GRAY        灰度中
PUBLISHED   已发布
OFFLINE     已下线
ARCHIVED    已归档
```

状态流转：

```text
DRAFT
→ TESTING
→ REVIEWING
→ APPROVED
→ GRAY
→ PUBLISHED
```

异常流转：

```text
REVIEWING → REJECTED → DRAFT
GRAY → PUBLISHED
GRAY → ROLLBACK
PUBLISHED → OFFLINE
PUBLISHED → ROLLBACK
```

## 5.8 发布与回滚

发布时必须记录：

* Prompt ID
* Prompt Version
* 环境
* 发布类型
* 灰度比例
* 发布人
* 审核人
* 发布时间
* LangSmith Commit Hash
* LangSmith Tag
* 变更说明
* 回滚版本

支持环境：

```text
development
testing
staging
production
```

支持发布方式：

```text
FULL
GRAY
AB_TEST
ROLLBACK
```

生产环境只能使用：

* 已发布版本
* 固定 Commit Hash
* production Tag

禁止直接读取最新草稿。

# 六、LangSmith 集成

LangSmith 用于：

* Prompt 版本同步
* Prompt Commit 管理
* Prompt Tag 管理
* Trace
* Evaluator
* Dataset
* Experiment
* Online Evaluation
* Prompt 效果分析

IOC 是业务管理入口。

LangSmith 是底层 Prompt、Trace 和评估平台。

## 6.1 同步流程

```text
运营修改业务 Prompt
→ 保存 IOC 草稿
→ 运行测试
→ 运行 Evaluator
→ 提交审核
→ 审核通过
→ 创建正式版本
→ Push 到 LangSmith
→ 保存 Commit Hash
→ 灰度发布
→ 正式发布
```

## 6.2 运行时记录

每次模型调用必须记录：

```json
{
  "prompt_key": "ioc.safety.analysis",
  "prompt_version": "1.6.0",
  "prompt_commit_hash": "commit-hash",
  "prompt_environment": "production",
  "graph_name": "safety_analysis_graph",
  "node_name": "analyze_risk",
  "trace_id": "langsmith-trace-id"
}
```

将这些信息写入：

* LangGraph State
* LangSmith metadata
* IOC 调用日志

## 6.3 遵守率评估

Prompt 遵守率不能直接通过字符串匹配完成。

必须分为：

### 确定性评估

通过代码 Evaluator 检查：

* JSON 是否有效
* 必填字段是否完整
* 风险等级是否合法
* 字段类型是否正确
* 数组是否为空
* 是否符合 Schema
* 是否出现禁止字段

### 语义评估

通过 LLM-as-a-Judge 检查：

* 是否回答了用户问题
* 是否基于输入数据
* 是否虚构数据
* 是否说明判断依据
* 是否给出可执行建议
* 是否遵守业务规则
* 数据不足时是否明确说明
* 是否符合业务表达要求

建议指标：

```text
prompt_compliance
format_compliance
risk_level_compliance
evidence_compliance
action_compliance
no_fabrication
insufficient_data_compliance
```

遵守率计算：

```text
通过的评估次数 / 总评估次数 × 100%
```

# 七、数据库设计

请基于以下核心表进行设计，并补充必要索引、唯一约束、外键、审计字段和软删除字段。

## 7.1 prompt_definition

字段建议：

```text
id
prompt_key
prompt_name
business_scene
graph_name
node_name
description
owner_id
current_version_id
status
created_by
created_at
updated_by
updated_at
deleted
```

## 7.2 prompt_version

字段建议：

```text
id
prompt_id
version
system_content
business_role_content
business_goal_content
business_rules
output_requirement
positive_examples
negative_examples
model_config
output_schema
langsmith_commit_hash
langsmith_tag
status
change_reason
created_by
created_at
```

## 7.3 prompt_variable

字段建议：

```text
id
prompt_id
variable_key
variable_name
description
data_type
source_type
source_path
required
default_value
example_value
sensitive
editable
display_order
created_at
updated_at
```

## 7.4 prompt_release

字段建议：

```text
id
prompt_id
version_id
environment
release_type
traffic_ratio
status
approved_by
released_by
released_at
rollback_version_id
release_note
```

## 7.5 prompt_test_case

字段建议：

```text
id
prompt_id
case_name
case_type
input_data
expected_output
source_trace_id
enabled
created_by
created_at
updated_at
```

## 7.6 prompt_test_run

字段建议：

```text
id
prompt_id
version_id
test_case_id
model_name
input_data
rendered_prompt
raw_output
structured_output
token_usage
latency
trace_id
status
created_by
created_at
```

## 7.7 prompt_evaluation

字段建议：

```text
id
test_run_id
evaluator_key
evaluator_type
score
passed
reason
violations
created_at
```

## 7.8 prompt_audit_log

字段建议：

```text
id
prompt_id
version_id
action
before_data
after_data
operator_id
operator_name
operator_ip
created_at
```

# 八、后端架构要求

建立统一 Prompt 模块，不允许 LangGraph Node 直接查询数据库或直接读取零散 Prompt 文件。

建议目录：

```text
app/
├── modules/
│   └── prompt_center/
│       ├── api/
│       │   ├── prompt_routes.py
│       │   ├── prompt_version_routes.py
│       │   ├── prompt_test_routes.py
│       │   └── prompt_release_routes.py
│       ├── application/
│       │   ├── prompt_service.py
│       │   ├── prompt_render_service.py
│       │   ├── prompt_version_service.py
│       │   ├── prompt_test_service.py
│       │   ├── prompt_release_service.py
│       │   └── prompt_evaluation_service.py
│       ├── domain/
│       │   ├── entities.py
│       │   ├── enums.py
│       │   ├── repositories.py
│       │   └── exceptions.py
│       ├── infrastructure/
│       │   ├── models.py
│       │   ├── repositories.py
│       │   ├── langsmith_client.py
│       │   └── prompt_cache.py
│       └── schemas/
│           ├── prompt_schema.py
│           ├── version_schema.py
│           ├── test_schema.py
│           └── release_schema.py
```

核心服务：

```text
PromptService
PromptRenderService
PromptVersionService
PromptTestService
PromptEvaluationService
PromptReleaseService
LangSmithPromptClient
```

核心方法：

```text
get_prompt()
get_prompt_detail()
get_active_version()
get_version()
create_draft()
update_draft()
validate_variables()
render_prompt()
preview_prompt()
create_version()
compare_versions()
submit_review()
approve_version()
reject_version()
run_test()
run_dataset_test()
publish_gray()
publish_production()
rollback_version()
sync_to_langsmith()
```

# 九、统一 PromptRenderResult

设计统一运行结果对象：

```python
class PromptRenderResult(BaseModel):
    prompt_id: int
    prompt_key: str
    prompt_name: str
    version: str
    environment: str
    messages: list[dict]
    variables: dict
    model_config: dict
    output_schema: dict | None = None
    langsmith_commit_hash: str | None = None
    langsmith_tag: str | None = None
```

LangGraph Node 只能通过 PromptService 获取 Prompt：

```python
async def safety_analysis_node(state: IOCState):
    prompt_result = await prompt_service.render_prompt(
        prompt_key="ioc.safety.analysis",
        environment="production",
        variables={
            "device_name": state["device_name"],
            "realtime_data": state["realtime_data"],
            "history_data": state.get("history_data"),
            "knowledge_context": state.get("knowledge_context"),
            "user_question": state["user_question"],
        },
    )

    result = await model.ainvoke(
        prompt_result.messages,
        config={
            "metadata": {
                "prompt_key": prompt_result.prompt_key,
                "prompt_version": prompt_result.version,
                "prompt_commit_hash": prompt_result.langsmith_commit_hash,
                "graph_name": "safety_analysis_graph",
                "node_name": "safety_analysis_node",
            }
        },
    )

    return {
        "analysis_result": result,
        "prompt_key": prompt_result.prompt_key,
        "prompt_version": prompt_result.version,
        "prompt_commit_hash": prompt_result.langsmith_commit_hash,
    }
```

# 十、API 设计

请实现标准 RESTful API。

## Prompt

```text
GET    /api/v1/prompts
POST   /api/v1/prompts
GET    /api/v1/prompts/{prompt_id}
PUT    /api/v1/prompts/{prompt_id}
DELETE /api/v1/prompts/{prompt_id}
```

## Prompt Version

```text
GET  /api/v1/prompts/{prompt_id}/versions
POST /api/v1/prompts/{prompt_id}/versions
GET  /api/v1/prompts/{prompt_id}/versions/{version_id}
POST /api/v1/prompts/{prompt_id}/versions/{version_id}/submit
POST /api/v1/prompts/{prompt_id}/versions/{version_id}/approve
POST /api/v1/prompts/{prompt_id}/versions/{version_id}/reject
```

## Prompt Render

```text
POST /api/v1/prompts/render
POST /api/v1/prompts/{prompt_id}/preview
```

## Prompt Test

```text
GET  /api/v1/prompts/{prompt_id}/test-cases
POST /api/v1/prompts/{prompt_id}/test-cases
POST /api/v1/prompts/{prompt_id}/versions/{version_id}/test
POST /api/v1/prompts/{prompt_id}/versions/{version_id}/dataset-test
GET  /api/v1/prompts/{prompt_id}/test-runs
GET  /api/v1/prompt-test-runs/{run_id}
```

## Prompt Compare

```text
GET /api/v1/prompts/{prompt_id}/compare?source_version_id=1&target_version_id=2
```

## Prompt Release

```text
POST /api/v1/prompts/{prompt_id}/versions/{version_id}/gray-release
POST /api/v1/prompts/{prompt_id}/versions/{version_id}/publish
POST /api/v1/prompts/{prompt_id}/rollback
GET  /api/v1/prompts/{prompt_id}/releases
```

## Prompt Metrics

```text
GET /api/v1/prompts/{prompt_id}/metrics
GET /api/v1/prompts/{prompt_id}/evaluation-trend
GET /api/v1/prompts/{prompt_id}/online-failures
```

# 十一、前端页面设计

前端目录建议：

```text
src/
├── api/
│   └── prompt-center/
├── views/
│   └── prompt-center/
│       ├── PromptList.vue
│       ├── PromptDetail.vue
│       ├── PromptEditor.vue
│       ├── PromptTest.vue
│       ├── PromptCompare.vue
│       ├── PromptRelease.vue
│       └── PromptMetrics.vue
├── components/
│   └── prompt-center/
│       ├── PromptBasicForm.vue
│       ├── PromptRuleEditor.vue
│       ├── PromptVariableTable.vue
│       ├── PromptPreview.vue
│       ├── PromptVersionTimeline.vue
│       ├── PromptDiffViewer.vue
│       ├── PromptTestPanel.vue
│       ├── PromptEvaluationPanel.vue
│       └── PromptReleaseDialog.vue
├── stores/
│   └── prompt-center.ts
└── types/
    └── prompt-center.ts
```

要求：

* 使用 Vue3 Composition API。
* 使用 TypeScript。
* 使用 Element Plus。
* API 请求统一封装。
* 所有接口有 TypeScript 类型。
* 表单有完整校验。
* 页面状态包括 loading、empty、error、success。
* 支持权限控制。
* 支持版本差异高亮。
* 规则编辑支持拖拽排序或上下移动。
* 完整 Prompt 使用代码编辑器或只读代码视图展示。
* JSON 数据使用 JSON Editor 或格式化代码区域展示。
* 不直接在 Vue 文件中编写复杂业务逻辑。

# 十二、第一期范围

第一期只实现以下闭环：

1. Prompt 列表。
2. Prompt 详情。
3. Prompt 业务化展示。
4. Prompt 草稿编辑。
5. 动态变量展示。
6. 最终 Prompt 预览。
7. 单条数据测试。
8. 版本创建。
9. 版本对比。
10. 审核。
11. 正式发布。
12. 版本回滚。
13. LangGraph 运行时读取已发布版本。
14. LangSmith Trace Metadata 记录。
15. 基础 Prompt 遵守率展示。

第一期暂不实现：

* 复杂 A/B 测试
* 自动灰度流量分配
* 多模型自动比较
* Prompt 自动优化
* 基于强化学习的 Prompt 优化
* 完整 Dataset 管理平台
* LangSmith 全能力复制

必须为后续能力预留扩展接口，但不要在第一期过度开发。

# 十三、开发要求

请先分析当前代码结构，再进行开发。

必须遵守：

1. 不要直接覆盖现有架构。
2. 优先复用已有 DTO、Schema、异常处理、数据库基类和响应结构。
3. 不要在 Prompt 模块中重复定义项目已有的公共 DTO。
4. 不要让 PromptService 与 LangGraph Node 强耦合。
5. 不要让前端直接调用 LangSmith。
6. LangSmith 调用必须经过后端封装。
7. Prompt 渲染必须检查必填变量。
8. Prompt 内容必须防止模板变量注入异常。
9. 敏感变量在日志和前端中需要脱敏。
10. 每次发布必须生成不可变版本。
11. 已发布版本不能直接修改，只能复制为新草稿。
12. 所有关键操作必须写入审计日志。
13. 核心逻辑必须有单元测试。
14. API 必须提供清晰错误码和错误信息。
15. 保持代码可运行，不输出无法落地的伪代码。

# 十四、实施步骤

请严格按以下步骤执行：

## 第一步：分析现有项目

输出：

* 当前前端目录分析
* 当前后端目录分析
* 当前 LangGraph Prompt 使用位置
* 当前 DTO 和 Schema 可复用项
* 当前数据库和权限机制
* 当前 LangSmith 接入方式
* 需要新增和修改的文件清单

不要立即大规模改代码。

## 第二步：输出技术方案

输出：

* 模块架构
* 数据流
* Prompt 生命周期
* 权限模型
* 数据库设计
* API 设计
* 前端页面结构
* LangSmith 集成方案
* LangGraph 接入方案
* 风险点
* 一期范围

## 第三步：建立后端基础结构

实现：

* 数据库模型
* Pydantic Schema
* Repository
* Service
* API Router
* 枚举
* 异常
* 审计日志

## 第四步：实现 Prompt 渲染

实现：

* 获取已发布 Prompt
* 环境选择
* 版本选择
* 变量校验
* Prompt 拼装
* 最终消息生成
* PromptRenderResult
* 缓存机制

## 第五步：接入 LangGraph

选择一个已有 Node 作为示例，将硬编码 Prompt 改为统一 PromptService。

要求：

* 不破坏原有 Graph。
* 保留回退机制。
* State 中记录 Prompt 版本。
* LangSmith Metadata 中记录 Prompt 信息。

## 第六步：实现前端页面

按顺序实现：

1. Prompt 列表
2. Prompt 详情
3. Prompt 编辑
4. Prompt 预览
5. Prompt 测试
6. 版本对比
7. 审核发布
8. 指标展示

## 第七步：实现测试和评估

实现：

* 单条 Prompt 测试
* JSON Schema 校验
* 基础规则校验
* Evaluator 结果存储
* Prompt 遵守率计算
* 测试结果页面

## 第八步：验证

必须执行：

* 后端单元测试
* API 测试
* 前端 TypeScript 检查
* 前端构建
* 数据库迁移检查
* Prompt 发布和回滚测试
* LangGraph Node 调用测试
* LangSmith Trace Metadata 检查

# 十五、输出格式

每完成一个阶段，请输出：

```text
## 当前阶段
## 已完成内容
## 新增文件
## 修改文件
## 核心设计说明
## 运行方式
## 验证结果
## 当前遗留问题
## 下一步
```

代码修改必须明确到文件路径。

不要只给建议，必须在项目中实际创建和修改代码。

不要一次性重构所有 Prompt，先选择一个典型节点完成完整闭环，再抽象为通用能力。

优先选择以下 Prompt 作为试点：

```text
Prompt 名称：设备安全分析
Prompt Key：ioc.safety.analysis
Graph：safety_analysis_graph
Node：safety_analysis_node
```

试点完成标准：

```text
运营人员创建草稿
→ 修改业务规则
→ 输入测试数据
→ 查看模型回答
→ 查看 Prompt 遵守评分
→ 创建新版本
→ 提交审核
→ 正式发布
→ LangGraph 使用新版本
→ LangSmith Trace 记录版本
→ 可以回滚旧版本
```
