"""
种子数据脚本 — 初始化 AI 策略与 Prompt 管理中心的基础数据。

运行方式:
    PYTHONDONTWRITEBYTECODE=1 .venv/bin/python scripts/seed_prompt_center.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.db.session import get_session_local
from app.modules.prompt_center.infrastructure.models import (
    PromptDefinition,
    PromptVersion,
    PromptVariable,
    PromptRelease,
    PromptTestCase,
)
from app.utils.timezone import now_local


def seed():
    db = get_session_local()()

    existing = db.query(PromptDefinition).filter(PromptDefinition.prompt_key == "ioc.safety.analysis").first()
    if existing:
        print("种子数据已存在，跳过")
        db.close()
        return

    prompt = PromptDefinition(
        prompt_key="ioc.safety.analysis",
        prompt_name="设备安全分析",
        business_scene="安全分析",
        graph_name="ioc_operation_analysis_graph",
        node_name="analyze_reason",
        description="对设备运行数据进行分析，识别安全隐患并生成分析报告",
        owner_id="admin",
        status="published",
        created_by="系统",
        created_at=now_local(),
        updated_at=now_local(),
    )
    db.add(prompt)
    db.flush()

    version = PromptVersion(
        prompt_id=prompt.id,
        version="1.0.0",
        status="published",
        system_content=(
            "你是企业级智能运营中心的安全分析专家。\n\n"
            "你的职责：\n"
            "1. 基于数据给出结论，不编造不存在的数据。\n"
            "2. 对异常指标进行解释，并给出可能原因。\n"
            "3. 对风险进行优先级排序。\n"
            "4. 输出可执行的运营建议。\n"
            "5. 每个关键结论必须尽量附带数据依据。\n\n"
            "你不能：\n"
            "1. 把数据缺失直接判断为业务异常。\n"
            "2. 在没有 evidence 的情况下给出确定性结论。\n"
            "3. 输出泛泛而谈的管理建议。\n"
            "4. 忽略用户当前页面筛选条件。"
        ),
        business_role_content="你是一位经验丰富的安全运营专家，专注于设备安全分析与风险评估。",
        business_goal_content="基于设备运行数据、告警信息和历史记录，分析当前安全状态，识别风险并给出可执行建议。",
        business_rules=[
            {"key": "rule_1", "content": "先判断整体状态：正常、关注、异常、数据不足", "enabled": True, "required": True, "display_order": 1},
            {"key": "rule_2", "content": "对每个异常项说明可能原因，使用「可能」「或与……有关」「建议核查」等措辞", "enabled": True, "required": True, "display_order": 2},
            {"key": "rule_3", "content": "对数据缺失项单独说明，不要直接归因为业务异常", "enabled": True, "required": True, "display_order": 3},
            {"key": "rule_4", "content": "所有结论必须引用指标数据作为依据", "enabled": True, "required": True, "display_order": 4},
            {"key": "rule_5", "content": "业务数据可以证明异常与关联，但不能单独证明唯一根因；不得使用「已确认根因」等确定性措辞", "enabled": True, "required": True, "display_order": 5},
            {"key": "rule_6", "content": "本次输入不包含 RAG 知识依据，不得虚构制度、标准、SOP 或历史案例", "enabled": True, "required": True, "display_order": 6},
        ],
        output_requirement=(
            "输出要求：\n"
            "1. 先输出整体状态判断。\n"
            "2. 按优先级排序输出异常分析。\n"
            "3. 每个异常说明可能原因和数据依据。\n"
            "4. 输出面向企业运营管理人员。\n"
            "5. 不要输出报告标题、报告时间、分析维度或寒暄语。\n"
            "6. 建议使用 3-5 条要点，语言简洁、直接。"
        ),
        positive_examples=[
            {"title": "正常状态分析", "content": "整体状态：正常。所有安全指标均在正常范围内。"},
            {"title": "异常分析", "content": "整体状态：关注。设备 A 温度达到 85°C，超过预警阈值 80°C，可能需要安排检修。"},
        ],
        negative_examples=[
            {"title": "虚构数据", "content": "该异常由设备老化导致（当前数据无法证明根因）"},
            {"title": "空泛建议", "content": "加强管理，持续关注"},
        ],
        created_by="系统",
        created_at=now_local(),
    )
    db.add(version)
    db.flush()

    variables = [
        PromptVariable(prompt_id=prompt.id, variable_key="device_name", variable_name="设备名称", data_type="string", source_type="graph_state", source_path="device.name", required=True, display_order=1),
        PromptVariable(prompt_id=prompt.id, variable_key="realtime_data", variable_name="实时数据", data_type="object", source_type="data_service", source_path="monitoring.realtime", required=True, display_order=2),
        PromptVariable(prompt_id=prompt.id, variable_key="history_data", variable_name="历史数据", data_type="object", source_type="data_service", source_path="monitoring.history", required=False, display_order=3),
        PromptVariable(prompt_id=prompt.id, variable_key="alarm_data", variable_name="告警数据", data_type="array", source_type="data_service", source_path="alarm.list", required=False, display_order=4),
        PromptVariable(prompt_id=prompt.id, variable_key="knowledge_context", variable_name="知识库内容", data_type="string", source_type="rag", required=False, display_order=5),
        PromptVariable(prompt_id=prompt.id, variable_key="user_question", variable_name="用户问题", data_type="string", source_type="user_input", required=False, editable=False, display_order=99),
    ]
    for v in variables:
        db.add(v)

    release = PromptRelease(
        prompt_id=prompt.id,
        version_id=version.id,
        environment="production",
        release_type="full",
        status="active",
        released_by="系统",
        released_at=now_local(),
        release_note="初始种子数据发布",
    )
    db.add(release)

    prompt.current_version_id = version.id
    db.commit()
    print(f"种子数据创建完成: prompt_id={prompt.id}, version_id={version.id}, version=1.0.0")
    db.close()


if __name__ == "__main__":
    seed()
