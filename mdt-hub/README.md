# MDT Hub (OpenClaw Multi-Agent)

面向多学科会诊（MDT）的单实例多 Agent 架构骨架。

## 目标
- 1 个病例 = 1 条会诊线程（case thread）
- 1 个主持 Agent 负责编排
- 多个专科 Agent 输出结构化意见
- 全量讨论记录事件化（可审计、可回放、可可视化）

## 目录
- `configs/agents/`：每个角色的能力边界和输出约束
- `schemas/`：结构化事件和结论 schema
- `router/`：状态路由（状态机）
- `db/`：Postgres 建表脚本
- `backend/`：最小后端骨架（FastAPI + orchestrator）

## 首版角色
- `orchestrator`：流程主持与冲突收敛
- `id_specialist`：感染科
- `icu_specialist`：ICU/重症
- `micro_specialist`：微生物
- `pharm_specialist`：临床药学
- `evidence_specialist`：指南/文献证据秘书
- `scribe`：会诊记录员（结构化落盘）

## 原则
1. 主持人不做专科判断，只做流程与裁决组织。
2. 每个专科必须引用证据并给出置信度。
3. 高危条件触发“人工接管”。
4. 讨论事件必须写入数据库，前端仅消费事件流。
