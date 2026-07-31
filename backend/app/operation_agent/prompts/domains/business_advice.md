## 任务
基于经营改善异常、原因分析和数据依据，生成可执行的改善建议。

## 异常项
{abnormal_items}

## 原因分析
{reason_analysis}

## 数据依据
{evidence}

## 输出要求
请只输出 JSON 数组，不要输出 Markdown、解释文字或代码块。每项必须包含 title、priority（P0/P1/P2）、owner_role、action、expected_result、evidence、confidence（0-1）、assumptions、verification_steps。

边界要求：建议应明确指标核查、责任角色、改善动作和验证结果；业务数据只能说明为什么需要处理，不能保证措施一定有效；不得虚构制度、法规、标准、SOP 或历史案例；不得把可能原因称为已确认根因；避免空泛表述。
