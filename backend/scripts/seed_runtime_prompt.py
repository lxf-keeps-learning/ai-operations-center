"""
Seed Script — 初始化 runtime_chat Prompt 模板

插入一条 code='runtime_chat', status='active' 的 Prompt 记录，
作为 Runtime Chat 的默认 System Prompt。

运行方式：
  python -m scripts.seed_runtime_prompt
"""

from datetime import UTC, datetime

from app.db.session import get_session_local
from app.runtime.models.prompt_model import AiPrompt
from app.utils.ids import new_prompt_id


PROMPT_CONTENT = """你是智能运营中心 AI 助手，运行在 AI Agent Runtime 中。

## 身份设定
- 当前接入的模型供应商是 DeepSeek，模型名是 deepseek-chat。
- 如果用户询问「你是谁/你是什么模型/你基于什么模型」，请准确说明当前接入 DeepSeek，
  不要自称 OpenAI、ChatGPT、GPT 架构或 GPT 系列模型。

## 核心职责
你面向智能运营中心场景，帮助用户完成以下任务：
1. 运营数据分析与解读 — 结合告警、KPI、事件等数据进行综合研判
2. 告警解读与根因分析 — 分析告警产生的原因、影响范围和处理建议
3. 隐患识别与风险研判 — 从趋势和异常中发现潜在风险
4. 日常巡检与报告生成 — 协助生成日报、周报、巡检总结
5. 通用问答 — 回答与运维、监控、运营相关的问题

## Runtime 架构事实
- 当前 AI Agent Runtime 已接入 LangGraph，使用 StateGraph 编排对话流程。
- 当前流程为：START → init_session → load_prompt → call_llm → finalize → END。
- 当用户询问是否接入 LangGraph 时，应明确回答已经接入，不得回答尚未接入，
  也不要建议用户在 Runtime 上层重复接入。

## 回答规范
1. 使用中文回答
2. 先直接给出结论，再补充必要的说明和依据
3. 基于已有数据回答，不编造没有提供的实时数据
4. 如果涉及未接入的工具或数据源，明确告知并给出可执行的查询建议
5. 回答简洁专业，不输出无关套话

当前日期：{date}。"""


def seed():
    db = get_session_local()()
    try:
        existing = db.query(AiPrompt).filter(
            AiPrompt.code == "runtime_chat",
            AiPrompt.status == "active",
        ).first()
        if existing:
            print(f"已存在 active runtime_chat Prompt (version={existing.version})，跳过")
            return

        max_version = db.query(AiPrompt.version).filter(
            AiPrompt.code == "runtime_chat"
        ).order_by(AiPrompt.version.desc()).limit(1).scalar() or 0

        now = datetime.now(UTC)

        record = AiPrompt(
            id=new_prompt_id(),
            code="runtime_chat",
            name="Runtime Chat 通用对话",
            version=max_version + 1,
            content=PROMPT_CONTENT.format(date=now.strftime("%Y-%m-%d")),
            variables={},
            scene_code="runtime",
            description="Runtime Chat 的默认 System Prompt，用于通用 AI 对话场景",
            status="active",
            created_by="system",
            published_at=now,
            created_at=now,
            updated_at=now,
        )
        db.add(record)
        db.commit()
        db.refresh(record)
        print(f"成功创建 runtime_chat Prompt (id={record.id}, version={record.version}, status=active)")
    finally:
        db.close()


if __name__ == "__main__":
    seed()
