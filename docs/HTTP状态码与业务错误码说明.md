# AIOperationsCenter HTTP 状态码与业务错误码说明

| 项目 | 内容 |
|------|------|
| 文档版本 | V2.0 |
| 文档类型 | API Standard |
| 项目名称 | IOC AI Agent / AIOperationsCenter |
| 适用范围 | Frontend、Backend、AI Chat、SSE、MySQL 调用日志 |
| 文档目标 | 统一 HTTP 状态码、业务码、错误信息、TraceId 与前后端处理口径 |

---

# 1. HTTP 状态码是什么

HTTP 状态码（HTTP Status Code）是服务器对客户端请求的**协议级响应标识**，表示请求在传输层、网关层、资源层是否成功送达和处理。

**职责**：表达"请求本身是否有效"。

**举例**：
- `200` — 请求已到达服务端并被正确处理
- `404` — 服务端没有找到对应资源
- `500` — 服务端内部发生了未预期的错误

**特点**：
- 由 HTTP 协议标准定义，所有 HTTP 客户端（浏览器、curl）原生识别。
- 粒度较粗，无法表达具体业务失败原因。
- 一个 HTTP 状态码可能对应多种业务失败场景。

---

# 2. 业务错误码是什么

业务错误码（Business Code）是后端在**响应体中返回的业务级标识**，表示请求进入业务逻辑后，业务处理是否成功。

**职责**：精确表达"业务为什么失败"。

**本项目的业务码字段**：响应体中的 `code` 字段。

**举例**：
```json
{
  "code": 404001,
  "message": "资源不存在",
  "traceId": "trace_20260702_xxx",
  "data": null
}
```

**特点**：
- 由项目自行定义，与 HTTP 协议无关。
- 粒度细，每个业务失败场景都有独立业务码。
- 前端可根据业务码做精确的用户提示或异常处理。
- 通过 `traceId` 可串联后端日志和数据库调用记录。

---

# 3. 为什么 HTTP 状态码和业务错误码不能混用

## 3.1 混用的典型问题

有些项目把 HTTP 状态码直接当业务码使用，例如：

```python
# 错误做法：把 HTTP 404 直接当业务码返回
return {"code": 404, "message": "会话不存在"}
```

这种做法的局限：

| 问题 | 说明 |
|------|------|
| 语义冲突 | HTTP `404` 表示资源不存在，但业务上可能是"参数错误"或"权限不足"，无法区分 |
| 粒度不足 | 同一个 HTTP 状态码下可能有多个业务失败场景，混用后前端无法精确判断 |
| 协议耦合 | 如果未来网关层改变状态码策略（如统一返回 `200`），业务码也会被破坏 |
| SSE 场景冲突 | SSE 建连时 HTTP 已是 `200`，无法再用 HTTP 状态码表达流内的业务错误 |

## 3.2 正确的分层关系

```
┌─────────────────────────────────────────────┐
│  HTTP 状态码  │  业务错误码 code               │
│───────────────│──────────────────────────────│
│  判断请求     │  判断业务是否真正成功            │
│  协议层状态   │  精确表达失败原因                │
│  浏览器/网关  │  前端/调用方精细化处理            │
│  原生识别     │  配合 traceId 可定位问题         │
└───────────────┴──────────────────────────────┘
```

## 3.3 本项目的原则

- HTTP 状态码表示"请求在协议层、网关层、资源层是否成功"。
- 业务码 `code` 表示"请求进入业务逻辑后，业务处理是否成功"。
- 正常业务成功统一返回 `code = 0`。
- 所有异常响应必须同时包含明确的 HTTP 状态码和业务码 `code`。
- 所有 AI 调用链路必须保留 `traceId`，用于串联前端错误、后端日志和数据库记录。

---

# 4. 本项目错误码分段规则

## 4.1 业务码编码规则

本项目业务码采用 **6 位数字** 格式：

```
{HTTP 状态码}{3 位序号}
```

| 位数 | 含义 | 示例 |
|------|------|------|
| 前 3 位 | 对应 HTTP 状态码 | `400`、`401`、`500` |
| 后 3 位 | 业务细分序号 | `001`、`002`、`101` |

**举例**：
- `400001` — HTTP 400 + 序号 001 → 参数错误
- `500101` — HTTP 500 + 序号 101 → 大模型调用失败

## 4.2 业务码分段总览

| 业务码范围 | 对应 HTTP 状态码 | 类型 | 说明 |
|------------|------------------|------|------|
| `0` | 200 | 成功 | 业务处理成功 |
| `400000` - `400999` | 400 | 参数错误 | 请求参数不合法 |
| `401000` - `401999` | 401 | 认证错误 | 用户未认证或 Token 失效 |
| `403000` - `403999` | 403 | 权限错误 | 用户无操作权限 |
| `404000` - `404999` | 404 | 资源错误 | 资源不存在 |
| `422000` - `422999` | 422 | 校验错误 | Pydantic 参数校验失败 |
| `429000` - `429999` | 429 | 限流错误 | 请求过于频繁 |
| `500000` - `500999` | 500 | 系统错误 | 后端未预期异常 |
| `502000` - `502999` | 502 | 网关错误 | 上游服务或模型调用异常 |
| `503000` - `503999` | 503 | 依赖不可用 | 数据库、缓存等依赖不可用 |
| `504000` - `504999` | 504 | 超时错误 | 上游服务调用超时 |

---

# 5. 常见 HTTP 状态码说明

## 5.1 状态码使用原则

| HTTP 状态码 | 使用场景 | 说明 |
|-------------|----------|------|
| `200 OK` | 查询、AI 问答任务创建、健康检查成功 | 常规成功响应 |
| `201 Created` | 新增资源成功 | 例如创建 Item |
| `400 Bad Request` | 请求参数不合法、业务请求格式错误 | 前端需要检查入参 |
| `401 Unauthorized` | 未登录或 Token 缺失 | 认证接入后启用 |
| `403 Forbidden` | 已登录但无权限 | 权限接入后启用 |
| `404 Not Found` | 资源不存在 | 会话、Prompt、Item 不存在 |
| `409 Conflict` | 资源冲突 | 重复提交、唯一键冲突 |
| `422 Unprocessable Entity` | FastAPI Pydantic 参数校验失败 | 请求体验证失败时自动触发 |
| `429 Too Many Requests` | 请求过于频繁 | Redis 限流接入后启用 |
| `500 Internal Server Error` | 后端未预期异常 | 需要记录日志并返回 traceId |
| `502 Bad Gateway` | 上游模型或外部服务网关异常 | LLM Provider、外部 Tool 异常 |
| `503 Service Unavailable` | 服务不可用 | 数据库、模型服务等依赖不可用 |
| `504 Gateway Timeout` | 上游服务超时 | LLM Provider 调用超时 |

## 5.2 状态码与业务码的对应关系

| HTTP 状态码 | 对应业务码前缀 | 说明 |
|-------------|----------------|------|
| 200 | 0 | 成功 |
| 400 | 400xxx | 参数错误 |
| 401 | 401xxx | 认证错误 |
| 403 | 403xxx | 权限错误 |
| 404 | 404xxx | 资源错误 |
| 422 | 422xxx | 校验错误 |
| 429 | 429xxx | 限流错误 |
| 500 | 500xxx | 系统错误 |
| 502 | 502xxx | 网关错误 |
| 503 | 503xxx | 依赖不可用 |
| 504 | 504xxx | 超时错误 |

---

# 6. 常见业务错误码说明

## 6.1 业务错误码总表

| code | message | HTTP 状态码 | 说明 |
|------|---------|-------------|------|
| `0` | success | 200 | 成功 |
| `400001` | 参数错误 | 400 | 请求参数不符合接口要求 |
| `400002` | 请求体不能为空 | 400 | 请求体缺失 |
| `400003` | 问题内容不能为空 | 400 | AI 问答 `message` 为空 |
| `401001` | 未登录 | 401 | 用户未认证或登录已过期 |
| `403001` | 无权限 | 403 | 用户无操作权限 |
| `404001` | 资源不存在 | 404 | 通用资源不存在 |
| `404002` | 会话不存在 | 404 | `conversation_id` 无效 |
| `404003` | Trace 不存在 | 404 | `traceId` 无效 |
| `404004` | Prompt 不存在 | 404 | `prompt_code` 无效 |
| `404005` | Item 不存在 | 404 | `item_id` 无效 |
| `404006` | SSE 流不存在 | 404 | `traceId` 找不到对应流 |
| `422001` | 参数校验失败 | 422 | Pydantic 请求体验证失败 |
| `429001` | 请求过于频繁 | 429 | 触发限流限制 |
| `500001` | 系统内部错误 | 500 | 未预期的系统异常 |
| `500002` | 数据写入失败 | 500 | 写入业务数据或日志失败 |
| `500003` | 数据查询失败 | 500 | 查询数据库失败 |
| `500004` | LLM 配置缺失 | 500 | LLM Key、Base URL、模型名缺失 |
| `500101` | 大模型调用失败 | 502 | LLM Provider 返回错误或调用异常 |
| `500102` | 大模型返回格式异常 | 502 | LLM 响应无法解析 |
| `503001` | 数据库连接失败 | 503 | MySQL 不可用 |
| `503002` | Redis 连接失败 | 503 | Redis 不可用 |
| `504101` | 大模型调用超时 | 504 | LLM Provider 调用超时 |

## 6.2 SSE 流式错误码

SSE 建连成功后，业务状态通过事件表达，业务码仍然遵循上述规则：

| 场景 | code | message | 前端处理 |
|------|------|---------|----------|
| Trace 不存在 | 404003 | Trace 不存在 | 提示会话不存在 |
| 会话不匹配 | 400001 | 参数错误 | 提示参数错误 |
| 流式输出中断 | 500001 | 系统内部错误 | 提示重试 |
| LLM 调用失败 | 500101 | 大模型调用失败 | 展示重试入口 |
| LLM 调用超时 | 504101 | 大模型调用超时 | 展示重试入口 |

---

# 7. 前端如何处理错误

## 7.1 两层错误处理

前端请求工具应按两层状态处理：

```
1. HTTP 层
   非 2xx 响应
   → 读取响应体中的 message / code / traceId
   → 抛出请求异常

2. 业务层
   HTTP 2xx 且 code != 0
   → 读取响应体中的 code / message / traceId
   → 抛出业务异常

   HTTP 2xx 且 code == 0
   → 正常使用 data 渲染页面
```

## 7.2 前端错误展示

前端展示错误时，至少需要包含以下信息：

| 信息 | 来源 | 用途 |
|------|------|------|
| `message` | 响应体 | 给用户看的错误说明 |
| `code` | 响应体 | 判断错误类型，决定展示策略 |
| `traceId` | 响应体 | 用户反馈或开发排查时定位问题 |
| `status` | HTTP 响应头 | 判断协议层问题 |

## 7.3 前端推荐实现

```typescript
// utils/request.ts 已有实现参考
// 目前已支持 HTTP 非 2xx 和 code !== 0 的异常处理

// 使用示例
try {
  const data = await listItems({ page: 1 })
  // code === 0，正常渲染 data
} catch (error) {
  if (error instanceof ApiRequestError) {
    // 展示错误信息给用户
    showToast(error.message)
    // 根据 error.code 判断错误类型
    if (error.code === 500101) {
      showRetryButton()
    }
  }
}
```

## 7.4 常见业务码的前端处理策略

| code | message | 前端处理策略 |
|------|---------|-------------|
| `400001` | 参数错误 | 表单高亮错误字段 |
| `400003` | 问题内容不能为空 | 输入框提示"请输入问题" |
| `401001` | 未登录 | 跳转登录页 |
| `403001` | 无权限 | 展示"无权限访问"提示 |
| `404001` | 资源不存在 | 展示空白状态或 404 页面 |
| `422001` | 参数校验失败 | 展示后端校验错误信息 |
| `429001` | 请求过于频繁 | 展示"请稍后重试"，倒计时 |
| `500001` | 系统内部错误 | 展示"系统异常，请稍后重试" |
| `500101` | 大模型调用失败 | 展示重试按钮 |
| `504101` | 大模型调用超时 | 展示"响应超时"和重试按钮 |

---

# 8. 后端如何抛出业务异常

## 8.1 原则

- 业务失败**不**直接 `raise HTTPException`，而是抛出业务异常或返回 `ApiResponse` 并携带明确业务码。
- 所有业务异常最终都统一转换为带 `code`、`message`、`traceId` 的 `ApiResponse` 响应。
- 后端日志必须记录 `traceId` 和业务码。

## 8.2 推荐实现方案

### 方案 1：使用全局异常处理（推荐）

定义统一业务异常类：

```python
# app/exceptions.py
class BusinessError(Exception):
    def __init__(self, code: int, message: str, status_code: int = 400):
        self.code = code
        self.message = message
        self.status_code = status_code
```

在 `app/main.py` 中注册全局异常处理器：

```python
@app.exception_handler(BusinessError)
async def business_error_handler(request: Request, exc: BusinessError):
    return JSONResponse(
        status_code=exc.status_code,
        content=ApiResponse(
            code=exc.code,
            message=exc.message,
            traceId=new_trace_id(),
            data=None,
        ).model_dump(by_alias=True),
    )

@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    return JSONResponse(
        status_code=exc.status_code,
        content=ApiResponse(
            code=exc.status_code * 1000 + 1,  # 如 404 → 404001
            message=exc.detail or "请求处理失败",
            traceId=new_trace_id(),
            data=None,
        ).model_dump(by_alias=True),
    )

@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    return JSONResponse(
        status_code=500,
        content=ApiResponse(
            code=500001,
            message="系统内部错误",
            traceId=new_trace_id(),
            data=None,
        ).model_dump(by_alias=True),
    )
```

业务代码中使用：

```python
# 业务失败时直接抛出
raise BusinessError(code=404001, message="资源不存在", status_code=404)
raise BusinessError(code=500101, message="大模型调用失败", status_code=502)
raise BusinessError(code=504101, message="大模型调用超时", status_code=504)
```

### 方案 2：直接返回 ApiResponse（当前代码方式）

当前部分接口已在使用此方式：

```python
# 成功
return ApiResponse(message="success", traceId=trace_id, data=item)

# 业务失败（不抛出 HTTPException，而是使用业务码）
return ApiResponse(
    code=404001,
    message="资源不存在",
    traceId=trace_id,
    data=None,
)
```

## 8.3 当前代码问题

当前部分代码仍在使用 `raise HTTPException`，该方式不会返回统一 `ApiResponse` 格式，会导致前端无法解析业务码：

```python
# ❌ 当前做法：前端收到 FastAPI 默认错误格式，不会走统一响应
raise HTTPException(status_code=404, detail="item not found")

# ✅ 建议改为：全局异常处理或返回 ApiResponse
raise BusinessError(code=404005, message="Item 不存在", status_code=404)
```

## 8.4 AI 调用错误处理

AI 调用（LLM Provider）的错误必须返回明确业务码，不能只返回 `500`：

```python
async def call_llm(prompt: str) -> str:
    try:
        response = await http_client.post(LLM_URL, json={"prompt": prompt})
    except httpx.TimeoutException:
        raise BusinessError(code=504101, message="大模型调用超时", status_code=504)
    except httpx.RequestError as e:
        raise BusinessError(code=500101, message=f"大模型调用失败: {e}", status_code=502)

    if response.status_code != 200:
        raise BusinessError(code=500101, message="大模型返回异常", status_code=502)
```

---

# 9. 统一响应结构

## 9.1 REST JSON 响应格式

所有 REST 接口统一返回如下结构：

```json
{
  "code": 0,
  "message": "success",
  "traceId": "trace_xxx",
  "data": {}
}
```

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| code | number | 是 | 业务码，`0` 表示业务成功，非 `0` 表示业务失败 |
| message | string | 是 | 给前端和排查人员的简要说明 |
| traceId | string | 是 | 请求追踪编号 |
| data | object/array/null | 否 | 业务数据 |

## 9.2 成功响应示例

```json
{
  "code": 0,
  "message": "success",
  "traceId": "trace_20260702_xxx",
  "data": {
    "id": 1,
    "name": "运营数据A",
    "description": "测试数据",
    "is_active": true,
    "created_at": "2026-07-02T14:30:00",
    "updated_at": "2026-07-02T14:30:00"
  }
}
```

## 9.3 失败响应示例

```json
{
  "code": 404001,
  "message": "资源不存在",
  "traceId": "trace_20260702_xxx",
  "data": null
}
```

---

# 10. SSE 流式输出规范

## 10.1 SSE 成功事件

SSE 接口建立连接时 HTTP 状态码为 `200`，具体业务状态通过事件表达：

```text
event: start
data: {"traceId":"trace_xxx","message":"analysis started"}

event: token
data: {"traceId":"trace_xxx","content":"今日运营情况如下："}

event: done
data: {"traceId":"trace_xxx","status":"success","message":"analysis finished"}
```

## 10.2 SSE 错误事件

SSE 建连成功后，业务失败不再依赖 HTTP 状态码，而是通过 `event: error` 返回业务码：

```text
event: error
data: {"traceId":"trace_xxx","code":404003,"message":"Trace 不存在"}
```

---

# 11. 推荐落地顺序

| 顺序 | 任务 | 说明 |
|------|------|------|
| 1 | 定义 `BusinessError` 异常类 | 统一业务异常表达 |
| 2 | 注册全局异常处理器 | 将 HTTPException、BusinessError、未知异常统一转换为 `ApiResponse` |
| 3 | 替换现有 `raise HTTPException` | 将散落的 `raise HTTPException` 替换为业务异常 |
| 4 | 前端对齐错误处理 | 确保前端能区分 HTTP 错误和业务错误 |
| 5 | 补充 README 与接口文档 | 对齐 Sprint1 交付物 |

---

# 12. 验收清单

- [ ] 所有 REST 成功响应都包含 `code`、`message`、`traceId`、`data`。
- [ ] 业务成功统一返回 `code = 0`。
- [ ] 业务码采用 6 位 `{HTTP状态码}{3位序号}` 格式。
- [ ] 前端能区分 HTTP 错误和业务错误。
- [ ] LLM 配置缺失、调用失败、调用超时有独立业务码。
- [ ] SSE 错误事件包含 `traceId`、`code`、`message`。
- [ ] README 或接口文档中同步说明状态码与业务码规则。

---

# 13. 总结

本项目始终遵循：

```
HTTP 状态码 → 请求是否正常到达和处理
业务码 code → 业务是否真正成功
traceId     → 串联前端错误、后端日志和数据库调用记录
```

HTTP 状态码和业务码的分层设计，是 AI 主流程能够稳定联调、稳定排错、稳定迭代的基础。
