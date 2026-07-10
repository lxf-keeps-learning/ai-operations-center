"""add LangGraph architecture facts to runtime chat prompt

Revision ID: 20260711_0006
Revises: 20260711_0005
Create Date: 2026-07-11 10:00:00.000000
"""

from collections.abc import Sequence
from datetime import datetime

from alembic import op
import sqlalchemy as sa


revision: str = "20260711_0006"
down_revision: str | Sequence[str] | None = "20260711_0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

PROMPT_ID = "pr_seed_runtime_chat_v2"
PROMPT_CODE = "runtime_chat"
PROMPT_CONTENT = """你是智能运营中心 AI 助手，运行在 AI Agent Runtime 中。

## Runtime 架构事实
- 当前 AI Agent Runtime 已接入 LangGraph，使用 StateGraph 编排对话流程。
- 当前流程为：START → init_session → load_prompt → call_llm → finalize → END。
- 当用户询问是否接入 LangGraph 时，应明确回答已经接入，不得回答尚未接入，
  也不要建议用户在 Runtime 上层重复接入。

## 核心职责
你的主要职责是帮助用户进行运营数据分析、告警解读、隐患研判、巡检总结和通用问答。

## 回答要求
1. 使用中文，先给出结论，再补充必要的说明和依据。
2. 基于用户提供的信息回答，不编造实时数据、工具结果或业务事实。
3. 未接入相应实时工具或数据源时，应明确说明限制并给出可执行的查询建议。
4. 当前默认模型供应商为 DeepSeek，不要自称 OpenAI、ChatGPT 或 GPT 系列模型。
5. 保持回答简洁、专业、可执行。"""


def upgrade() -> None:
    connection = op.get_bind()
    existing = connection.execute(
        sa.text("SELECT id FROM ai_prompt WHERE id=:id"),
        {"id": PROMPT_ID},
    ).scalar()
    if existing is not None:
        return

    max_version = connection.execute(
        sa.text("SELECT MAX(version) FROM ai_prompt WHERE code=:code"),
        {"code": PROMPT_CODE},
    ).scalar()
    now = datetime.now()
    connection.execute(
        sa.text(
            "UPDATE ai_prompt SET status='inactive', updated_at=:now "
            "WHERE code=:code AND status='active'"
        ),
        {"code": PROMPT_CODE, "now": now},
    )
    connection.execute(
        sa.text(
            "INSERT INTO ai_prompt "
            "(id, code, name, version, content, variables, scene_code, status, "
            "description, created_by, published_at, created_at, updated_at) "
            "VALUES (:id, :code, :name, :version, :content, '{}', :scene_code, "
            "'active', :description, 'system', :now, :now, :now)"
        ),
        {
            "id": PROMPT_ID,
            "code": PROMPT_CODE,
            "name": "Runtime Chat 通用对话",
            "version": int(max_version or 0) + 1,
            "content": PROMPT_CONTENT,
            "scene_code": "runtime",
            "description": "补充 LangGraph Runtime 架构事实的默认 Prompt",
            "now": now,
        },
    )


def downgrade() -> None:
    connection = op.get_bind()
    connection.execute(
        sa.text("DELETE FROM ai_prompt WHERE id=:id"),
        {"id": PROMPT_ID},
    )
    previous_id = connection.execute(
        sa.text(
            "SELECT id FROM ai_prompt WHERE code=:code "
            "ORDER BY version DESC LIMIT 1"
        ),
        {"code": PROMPT_CODE},
    ).scalar()
    if previous_id is not None:
        connection.execute(
            sa.text(
                "UPDATE ai_prompt SET status='active', published_at=:now, updated_at=:now "
                "WHERE id=:id"
            ),
            {"id": previous_id, "now": datetime.now()},
        )

