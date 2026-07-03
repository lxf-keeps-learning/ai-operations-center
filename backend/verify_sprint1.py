#!/usr/bin/env python3
"""Sprint1 验收脚本 — 测试所有接口后输出结果"""

import json
import re
import subprocess
import sys
from urllib import request as urllib_request
from urllib.error import URLError

BASE = "http://127.0.0.1:8000"
results = []


def ok(msg):
    results.append(f"  ✅ {msg}")


def fail(msg):
    results.append(f"  ❌ {msg}")


def get(path):
    try:
        resp = urllib_request.urlopen(f"{BASE}{path}", timeout=5)
        body = json.loads(resp.read())
        headers = dict(resp.headers)
        return body, headers, resp.status
    except URLError as e:
        return None, {}, 0
    except json.JSONDecodeError:
        return None, {}, 0


# ── 1. 后端启动 ──
resp = urllib_request.urlopen(f"{BASE}/docs", timeout=5)
ok(f"后端启动成功 (HTTP {resp.status})") if resp.status == 200 else fail("后端启动失败")

# ── 2. /api/v1/health 统一格式 ──
body, headers, status = get("/api/v1/health")
if body:
    fields = list(body.keys())
    ok(f"/api/v1/health fields: {fields}") if all(k in body for k in ["code", "message", "traceId", "data"]) else fail("缺少必要字段")

# ── 3. 所有基础设施接口统一格式 ──
v1_paths = [
    "/api/v1/config/models",
    "/api/v1/config/runtime",
    "/api/v1/errors/codes",
    "/api/v1/logs/recent",
    "/api/v1/logs/llm-usage",
    "/api/v1/context/current",
]
for path in v1_paths:
    body, _, _ = get(path)
    if body and all(k in body for k in ["code", "message", "traceId", "success", "data"]):
        ok(f"{path:42s} code={body['code']} success={body['success']}")
    else:
        fail(f"{path:42s} 格式异常: {list(body.keys()) if body else 'N/A'}")

# ── 4. 异常接口统一格式 ──
body, _, status = get("/api/v1/items/99999")
if body and all(k in body for k in ["code", "message", "traceId", "success", "data"]):
    ok(f"异常接口 (HTTP {status}) code={body['code']} success={body['success']} msg={body['message']}")
else:
    fail(f"异常接口格式异常")

# ── 5. traceId 响应体 + 响应头 ──
body, headers, _ = get("/api/v1/config/runtime")
header_trace = headers.get("X-Trace-Id", headers.get("x-trace-id", "N/A"))
body_trace = body.get("traceId", "N/A") if body else "N/A"
if header_trace == body_trace:
    ok(f"traceId 响应体/头一致: {body_trace}")
else:
    fail(f"traceId 不匹配: header={header_trace} body={body_trace}")

# ── 6. 日志包含 traceId ──
from app.core.logging.logger import setup_logging, get_logger
from app.core.trace.trace_context import set_trace_id
import io, logging

setup_logging()
log = get_logger("verify.sprint1")
stream = io.StringIO()
for h in logging.getLogger().handlers:
    h.stream = stream
set_trace_id("trace_sprint1_verify")
log.info("sprint1 verification")
output = stream.getvalue()
if "trace_sprint1_verify" in output:
    ok(f"日志包含 traceId: {output.strip()}")
else:
    fail("日志未包含 traceId")

# ── 7. 三种模型配置 ──
body, _, _ = get("/api/v1/config/models")
if body:
    providers = [m["provider"] for m in body["data"]]
    has_qwen = "qwen" in providers
    has_deepseek = "deepseek" in providers
    has_doubao = "doubao" in providers
    has_key = any("apiKey" in m or "api_key" in m for m in body["data"])
    if has_qwen and has_deepseek and has_doubao:
        ok(f"三种模型: qwen={has_qwen} deepseek={has_deepseek} doubao={has_doubao}")
    else:
        fail(f"缺少模型: {providers}")
    if not has_key:
        ok("API Key 未向前端暴露")
    else:
        fail("API Key 被意外暴露")

# ── 12. 代码中无 print ──
import os
backend_root = os.path.dirname(os.path.abspath(__file__))
has_print = False
for root, dirs, files in os.walk(os.path.join(backend_root, "app")):
    if ".venv" in root or "__pycache__" in root:
        continue
    for f in files:
        if f.endswith(".py"):
            path = os.path.join(root, f)
            with open(path) as fh:
                for i, line in enumerate(fh, 1):
                    stripped = line.strip()
                    if stripped.startswith("print(") and "print(" not in stripped[7:]:
                        has_print = True
                        results.append(f"  ⚠️  发现 print: {path}:{i}")
if not has_print:
    ok("代码中未发现 print 语句")

# ── 输出 ──
print(f"\n{'='*60}")
print(f"Sprint1 验收结果")
print(f"{'='*60}")
for r in results:
    print(r)
print(f"{'='*60}")
passed = sum(1 for r in results if "✅" in r)
failed = sum(1 for r in results if "❌" in r)
print(f"\n通过: {passed}  失败: {failed}")
if failed:
    sys.exit(1)
