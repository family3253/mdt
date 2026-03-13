# MDT Hub 进度存档（2026-03-13）

## 当前状态
项目优化已按用户指令暂停，后续继续。

## 今日已完成

### A. 病历解析三栏（已完成）
- 后端：新增结构化读取与确认写回
  - `GET /cases/{case_id}/parsed`
  - `POST /cases/{case_id}/parsed/confirm`
- 数据落库：`mdt_case_parsed_confirmations`（SQLite）
- 前端：影像/检验/用药三栏可编辑，并支持“确认写回”

### B. 冲突裁决建议器（已完成）
- 后端：`POST /cases/{case_id}/conflict-resolution`
- 输出结构化冲突与裁决动作（action_type/owner/deadline_hint/rationale）
- 前端：分析视图新增“一键生成冲突裁决建议”卡片

### C. 纪要自动生成卡 + PDF（已完成）
- 后端：`GET /cases/{case_id}/minutes`
- 纪要结构：基本信息、关键争议、最终共识、执行建议、风险与随访、时间线摘要、参与专家
- 前端：一键生成纪要 + 打印导出 PDF（window.print 方案）

## 联调现状
- MDT 服务可启动并访问（8788）
- 已验证案例：
  - `CASE-MINUTES-001`
  - `CASE-DEMO-ALL-EXPERTS-001`（7/7 专家参与）

## 待继续（下一阶段）
1. 病例+切片导入向导增强：保存 `source_case_url`、`slide_urls[]`、`initial_diagnosis`
2. 首轮任务模板固化：默认“进一步明确诊断并复核原诊断”
3. 将用户提供的 3 份 MDT 模板 HTML 映射为系统字段（当前未拿到文件正文）
4. 规范流程 checklist 固化到 report/minutes（病例完整性、证据充分性、鉴别诊断、共识等级、执行随访）

## 关键文件
- `backend/main.py`
- `frontend.html`
- `docs/progress-archive-2026-03-13.md`
