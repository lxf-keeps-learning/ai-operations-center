#!/usr/bin/env python3
"""
Operation Agent 本地调试脚本。

用法：
    cd backend && source .venv/bin/activate
    python scripts/debug_operation_agent.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.tools.register import register_all_tools
from app.operation_agent.graph import operation_graph


def main():
    register_all_tools()

    state = {
        "trigger_type": "tab_analysis",
        "page_context": {
            "domain": "safety",
            "active_tab": "本质安全",
            "time_dimension": "month",
            "date": "2026-07",
        },
        "user_context": {
            "user_id": "demo_user",
            "role": "operation_manager",
        },
    }

    print("=" * 60)
    print("  Operation Agent 本地调试")
    print("=" * 60)
    print(f"\n输入状态: trigger_type={state['trigger_type']}, domain={state['page_context']['domain']}")

    result = operation_graph.invoke(state)

    print(f"\n结果统计:")
    print(f"  trace_id:      {result.get('trace_id', 'N/A')}")
    print(f"  abnormal_items: {len(result.get('abnormal_items', []))}")
    print(f"  advice_items:   {len(result.get('advice_items', []))}")
    print(f"  errors:         {len(result.get('errors', []))}")
    print(f"  evidence:       {len(result.get('evidence', []))}")
    print(f"  risk_items:     {len(result.get('risk_items', []))}")

    if result.get("abnormal_items"):
        print(f"\n异常项:")
        for a in result["abnormal_items"]:
            print(f"  [{a['severity']}] {a.get('metric_name', '')}: {a.get('message', '')[:60]}")

    print(f"\n{'-' * 60}")
    print("最终分析结论 (Markdown):")
    print(f"{'-' * 60}")
    print(result.get("final_answer", "N/A"))

    if result.get("errors"):
        print(f"\n{'!' * 60}")
        print("处理过程中出现错误:")
        for e in result["errors"]:
            print(f"  - {e.get('node', '')}: {e.get('message', '')}")
        print(f"{'!' * 60}")

    print(f"\n{'=' * 60}")
    print("  调试完成")
    print(f"{'=' * 60}")


if __name__ == "__main__":
    main()
