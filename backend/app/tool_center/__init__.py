# AIOps 工具中心 - 领域模块
#
# 对外暴露统一的 Tool 注册、获取、列表接口。
# 外部模块通过 from app.tool_center import registry 来使用。
#
# 基础设施依赖方向：
#   tool_center → app/core （全局异常、trace、日志、DTO）
#   其他领域模块 → tool_center （Tool 执行协议）
