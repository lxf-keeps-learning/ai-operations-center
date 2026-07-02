## Sprint0 项目启动

### 目标
完成 IOC AI Agent 项目初始化，建立统一工程骨架、前后端运行环境、Git 规范、基础通信能力、MySQL 主数据库连接、Redis 可选预留、Docker Compose 后续部署配置和 README 启动文档。

---

## 1. 工程初始化

### 1.1 Git 仓库
- 创建项目总仓库：IOC-AI
- 建立 Git 分支规范：
  - main：主分支
  - develop：开发集成分支
  - feature-xxx：功能开发分支
  - fix-xxx：Bug 修复分支
- 建立 Commit 规范：
  - feat: 新功能
  - fix: 修复问题
  - docs: 文档
  - chore: 工程配置
  - refactor: 代码重构

### 1.2 项目目录
初始化项目目录：

IOC-AI/
├── frontend/
├── backend/
├── docs/
├── scripts/
├── deploy/
├── .env.example
├── README.md
└── docker-compose.yml

---

## 2. 环境初始化

### 2.1 前端初始化
- 技术栈：Vue3 + TypeScript + Vite
- 创建 frontend 工程
- 本地启动成功
- 访问 http://localhost:5173 可看到初始化页面
- 前端可调用后端 /api/health 接口
- 页面可展示后端返回数据

### 2.2 后端初始化
- 技术栈：Python + FastAPI
- 创建 backend 工程
- 本地启动成功
- 访问 http://localhost:8000/docs 可查看接口文档
- 提供 GET /api/health 接口
- 支持前端访问接口

### 2.3 数据库初始化
- 数据库：MySQL
- ORM：SQLAlchemy
- 数据库驱动：pymysql
- 数据库迁移：Alembic，Sprint0 初始化 system_items Demo 表
- 后端从 DATABASE_URL 读取数据库连接
- 后端可成功连接 MySQL
- 提供 Demo CRUD 接口，验证数据库读写能力

### 2.4 Redis 初始化
- 缓存：Redis 作为后续预留组件
- 本地开发默认 `REDIS_ENABLED=false`，不要求启动 Redis
- 后端启动时不强制连接 Redis
- 提供 GET /api/cache/ping 接口
- `REDIS_ENABLED=false` 时返回 Redis disabled
- `REDIS_ENABLED=true` 时尝试连接 Redis 并返回 pong
- 连接失败时返回清晰错误信息，不影响 MySQL 和其他接口
- Sprint0 只做配置预留和健康检查，不做复杂缓存业务

### 2.5 Docker Compose 初始化
- docker-compose.yml 保留为后续标准部署方式
- Sprint0 本地开发不依赖 Docker
- 本地数据库通过 MySQL / Navicat 初始化

---

## 3. 配置初始化

### 3.1 环境变量
- 创建 .env.example
- 配置后端端口、数据库连接、Redis 可选预留等基础变量
- .env 不提交到 Git
- .env.example 提交到 Git

### 3.2 README.md
README 需要包含：
- 项目介绍
- 技术栈
- 目录结构
- 前端启动方式
- 后端启动方式
- Docker Compose 启动方式
- 接口文档地址
- 常见问题

---

## 4. Sprint0 验收标准

- Git 仓库创建完成
- Git 分支规范建立完成
- 项目目录结构创建完成
- 前端项目可启动
- 后端项目可启动
- http://localhost:8000/docs 可访问
- 前端可调用后端 /api/health
- MySQL 可连接
- Redis 本地开发可不启用，/api/cache/ping 可返回禁用状态或连通结果
- docker-compose.yml 保留后续部署配置
- README.md 可指导新人启动项目
