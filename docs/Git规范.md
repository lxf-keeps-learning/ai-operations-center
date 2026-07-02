### Git分支规范
- main 主分支，生产稳定版本分支 
- develop 日常集成分支，开发/测试分支
- feature/* 功能开发分支
- fix/* Bug修复分支
- refactor/* 代码重构分支
- docs/* 文档分支
- release/* 发布准备分支

#### 分支示例
```text
feature/runtime-conversation
feature/tool-center-base
feature/operation-agent
fix/sse-timeout
docs/ioc-ai-005
release/v1.0.0
```

### Git-Commit规范
| 类型 | 含义 | 示例 |
|------|------|------|
| feat | 新功能 | feat: add operation graph |
| fix | 修复 | fix: resolve sse timeout |
| docs | 文档 | docs: update api design |
| refactor | 重构 | refactor: split risk nodes |
| test | 测试 | test: add tool unit tests |
| chore | 工程配置 | chore: update docker compose |
| perf | 性能优化 | perf: optimize stream output |

#### Commit示例
```
feat: 新增功能
fix: 修复问题
docs: 修改文档
style: 格式调整，不影响逻辑
refactor: 重构代码
test: 测试相关
chore: 工程配置、依赖、脚手架等

git commit -m "feat: 初始化FastAPI后端工程"
git commit -m "docs: 新增Sprint0启动说明"
git commit -m "chore: 添加docker-compose基础配置"
git commit -m "fix: 修复前端接口代理地址错误"
```