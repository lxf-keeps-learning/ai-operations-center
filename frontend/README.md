# AIOperationsCenter Frontend

智能运营中心 AI Agent 前端工程，使用 Vue3 + Vite + TypeScript 初始化，作为项目后续页面、AI 入口、结果展示、SSE 渲染和后端接口联调的统一前端基础。

## 技术栈

- Vue3 + TypeScript + Composition API
- Vite
- Vue Router
- Pinia
- REST + SSE API 调用

## 目录结构

```text
frontend/
├── public/                 # 静态资源
├── src/
│   ├── api/                # 后端 REST / SSE 接口封装
│   ├── adapters/           # 页面上下文和业务对象适配
│   ├── assets/             # 样式与静态资源
│   ├── components/         # 公共组件
│   ├── hooks/              # 组合式逻辑
│   ├── layouts/            # 页面布局
│   ├── pages/              # 路由页面
│   ├── router/             # Vue Router 配置
│   ├── stores/             # Pinia 状态管理
│   ├── types/              # TypeScript DTO / 类型定义
│   ├── utils/              # 通用工具
│   ├── App.vue
│   └── main.ts
├── index.html
├── package.json
├── tsconfig.json
└── vite.config.ts
```

## 本地启动

```bash
npm install
npm run dev
```

默认访问地址：

```text
http://localhost:5173/
```

如果需要让局域网或容器外访问开发服务，可以临时使用：

```bash
npm run dev -- --host 0.0.0.0
```

## 环境变量

复制 `.env.example` 为 `.env.local` 后按需调整：

```bash
cp .env.example .env.local
```

```text
VITE_API_BASE_URL=/api/v1
VITE_API_PROXY_TARGET=http://127.0.0.1:8000
```

- `VITE_API_BASE_URL`：前端请求的 API 基础路径。
- `VITE_API_PROXY_TARGET`：Vite 开发代理转发到的后端 FastAPI 地址。

## 后端接口约定

前端 API 层位于 `src/api/runtime.ts`，已按项目接口文档预留：

| 方法 | 路径 | 用途 |
|------|------|------|
| GET | `/api/v1/health` | 健康检查 |
| POST | `/api/v1/agent/chat` | AI 对话 |
| POST | `/api/v1/agent/analyze` | AI 分析 |
| GET | `/api/v1/agent/stream` | SSE 流式输出 |
| GET | `/api/v1/conversations` | 会话列表 |
| POST | `/api/v1/feedback` | 用户反馈 |

开发环境下，浏览器请求 `/api/**` 会由 Vite 代理到 `VITE_API_PROXY_TARGET`。

## 常用命令

```bash
npm run dev          # 启动开发服务
npm run type-check   # TypeScript 类型检查
npm run build        # 类型检查并构建生产包
npm run preview      # 本地预览生产包
```

## 开发约定

- 页面只做组件组合和状态承接。
- 后端接口统一写在 `src/api/`。
- 页面上下文采集统一放在 `src/adapters/`。
- 复用状态放在 `src/stores/`，复杂流程不要堆在页面组件里。
- DTO 和 SSE 事件类型统一维护在 `src/types/`。
- 不在组件内直接拼接后端域名，统一通过 `VITE_API_BASE_URL` 和 Vite proxy 管理。
