"""seed active runtime chat prompt

Revision ID: 20260711_0005
Revises: 20260710_0004
Create Date: 2026-07-11 09:00:00.000000
"""

from collections.abc import Sequence
from datetime import datetime

from alembic import op
import sqlalchemy as sa


revision: str = "20260711_0005"
down_revision: str | Sequence[str] | None = "20260710_0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

PROMPT_ID = "pr_seed_runtime_chat_v1"
PROMPT_CODE = "runtime_chat"
PROMPT_CONTENT = """你是智能运营中心 AI 助手，运行在 AI Agent Runtime 中。

你的主要职责是帮助用户进行运营数据分析、告警解读、隐患研判、巡检总结和通用问答。

回答要求：
1. 使用中文，先给出结论，再补充必要的说明和依据。
2. 基于用户提供的信息回答，不编造实时数据、工具结果或业务事实。
3. 未接入相应实时工具或数据源时，应明确说明限制并给出可执行的查询建议。
4. 当前默认模型供应商为 DeepSeek，不要自称 OpenAI、ChatGPT 或 GPT 系列模型。
5. 保持回答简洁、专业、可执行。"""


def upgrade() -> None:
    connection = op.get_bind()
    active_id = connection.execute(
        sa.text(
            "SELECT id FROM ai_prompt "
            "WHERE code=:code AND status='active' "
            "ORDER BY version DESC LIMIT 1"
        ),
        {"code": PROMPT_CODE},
    ).scalar()
    if active_id is not None:
        return

    max_version = connection.execute(
        sa.text("SELECT MAX(version) FROM ai_prompt WHERE code=:code"),
        {"code": PROMPT_CODE},
    ).scalar()
    now = datetime.now()
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
            "description": "Runtime Chat 默认 active Prompt，由数据库迁移初始化",
            "now": now,
        },
    )


def downgrade() -> None:
    op.get_bind().execute(
        sa.text("DELETE FROM ai_prompt WHERE id=:id"),
        {"id": PROMPT_ID},
    )

