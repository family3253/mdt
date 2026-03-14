# MDT 最小规范条目落地映射（2026-03-13）

## 联网来源（公开可访问）
1. PubMed PMID: **41061286**
   - *Quality of Decision-making at Oncology Multidisciplinary Team Meetings: A Structured Observational Study* (2024)
   - 要点：MDT 决策质量依赖“信息质量 + 团队贡献质量”；MDT-MODe 评分关注影像/病理等临床信息是否完整、讨论是否结构化。
2. PubMed PMID: **29149872**
   - *Process quality of decision-making in multidisciplinary cancer team meetings* (2017)
   - 要点：癌症相关医学信息通常较完整，但“患者偏好、心理社会信息”常缺失；信息完整性会直接影响是否能给出明确治疗建议。
3. PubMed PMID: **41167469**
   - *Enhancing multidisciplinary oncology care: Feasibility of structured tools...* (2025)
   - 要点：结构化工具（MDT-QuIC / MDT-MeDiC）可提升会议结构性和角色清晰度；建议将复杂度与检查清单常态化。

## 可落地条目 -> 系统字段

1) **病例完整性**
- 系统字段：`cases.mdt_checklist.case_completeness`
- 说明：是否具备基本病史、关键检查、病情时间线。

2) **影像/病理证据充分性**
- 系统字段：`cases.mdt_checklist.evidence_sufficiency`
- 说明：是否有足够支持/反对诊断的病理与影像证据。

3) **鉴别诊断**
- 系统字段：`cases.mdt_checklist.differential_diagnosis`
- 说明：至少记录核心鉴别方向，避免“单一路径过早收敛”。

4) **共识等级**
- 系统字段：`cases.mdt_checklist.consensus_level`
- 说明：用简化等级记录（如 pending / partial / strong）。

5) **执行与随访计划**
- 系统字段：`cases.mdt_checklist.execution_followup_plan`
- 说明：最小必要检查、执行时间窗、复评计划。

## 本次实现采用的默认文案
- 首轮任务模板：
  - `请先进一步明确诊断，结合切片复核原诊断是否准确，给出支持/反对证据、关键鉴别诊断、下一步最小必要检查。`
- 默认 checklist 值：`pending`

> 注：以上条目按“最小可用”原则落地，保持向后兼容；后续可扩展为枚举评分或多级审计日志。