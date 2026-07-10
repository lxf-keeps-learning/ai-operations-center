"""
Application 层 — 业务编排层

位于 API 层和底层服务之间，负责：
  1. 将 API 请求转为业务任务（AgentTask）
  2. 调用下层服务（Runtime、Tool Center、Graph）执行任务
  3. 管理会话生命周期（创建/查询/删除）
  4. 提供 SSE 流式事件推送
  5. 处理用户反馈

当前（Sprint1~2）使用内存存储（runtime_store）实现，
后续接入真实数据库后替换存储实现，接口保持不变。
"""
