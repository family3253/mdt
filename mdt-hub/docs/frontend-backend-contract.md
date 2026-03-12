# MDT Hub 前后端交互契约清单

> 范围：`frontend.html` ↔ `backend/main.py`
> 
> 目标：前端每个可见交互均有后端能力支撑，且请求/响应字段、失败提示可对齐。

## 1) 交互点总览

| 前端可见效果/交互 | 后端接口 | 请求关键字段 | 响应关键字段 | 失败提示（前端） |
|---|---|---|---|---|
| 页面初始化加载模型下拉 | `GET /models/available` | - | `models[]`, `default_model`, `fallback`, `note` | `加载模型列表失败: ...` |
| 页面初始化加载 Agent 列表/模型行 | `GET /agents` | - | `count`, `agents[]` | `加载 Agent 列表失败: ...` |
| 新增 Agent（按钮） | `POST /agents` | `agent_id`,`role`,`specialty`,`model`,`prompt`,`auto_learn_web` | `agent_id`,`model`,`skill_suggestions[]` | `新增失败: ...` |
| 更新 Agent 模型（保存） | `POST /agents/{agent_id}/model` | `model` | `ok`,`agent_id`,`model` | `模型更新失败: ...` |
| 文本知识注入 | `POST /agents/{agent_id}/knowledge` | `content`,`source`,`tags[]` | `ok`,`agent_id` | `喂知识失败: ...` |
| 网址知识注入 | `POST /agents/{agent_id}/knowledge/url` | `url`,`source` | `ok`,`agent_id` | `网址注入失败: ...` |
| 文件知识注入 | `POST /agents/{agent_id}/knowledge/upload` (multipart) | `file`,`tags` | `ok`,`agent_id` | `文件注入失败: ...` |
| 网址病历导入 | `POST /cases/{case_id}/documents/url` | `url`,`source` | `doc_id`,`sections{imaging,labs,medications}` | `病历网址导入失败: ...` |
| 文件病历上传 | `POST /cases/{case_id}/documents/upload` (multipart) | `file` | `doc_id`,`sections{...}` | `病历文件导入失败: ...` |
| 加载最近病历解析结果 | `GET /cases/{case_id}/documents` | - | `documents[]`（按 id 倒序） | `加载失败: ...` |
| 提交会诊讨论（按钮） | `POST /cases/open`（预开病例） + `POST /discussion/submit` | `case_id`,`message`,`round_no`,`speaker`,`confirmed_sections`,`enable_docs_context` | `generated_count`,`confirmed_adopted_count`,`docs_context_doc_count` | `提交失败: ...` |
| 二轮互评（按钮） | `POST /discussion/review` | `case_id`,`from_round`,`to_round` | `generated_count` | `二轮互评失败: ...` |
| 刷新冲突图（按钮） | `GET /cases/{case_id}/conflicts` | - | `nodes[]`,`edges[]` | `加载冲突图失败: ...` |
| WebSocket 实时事件 | `WS /ws/events` | 客户端 ping 文本 | `{"type":"mdt_event","data":...}` | 断连后 UI 显示“WebSocket 断开（轮询模式）” |
| WebSocket 断连兜底轮询 | `GET /cases/{case_id}/events` | - | `events[]` | 轮询失败静默重试 |

## 2) 字段对齐说明（已核验）

1. `confirmed_sections`
   - 前端提交结构：
     - `imaging/labs/medications: [{text, confirmed}]`
   - 后端 `DiscussionInput.confirmed_sections` 与 `ConfirmedSections` 完整兼容。

2. 病历解析 `sections`
   - 后端 `documents/upload|url` 返回 `sections` 为字符串数组。
   - 前端 `normalizeSectionItems` 兼容字符串数组与对象数组（自动归一为 `{text, confirmed}`）。

3. 事件流字段
   - 前端事件渲染依赖：`event_id`,`event_type`,`speaker`,`payload`,`timestamp`,`round_no`,`confidence`。
   - 后端 `/cases/{case_id}/events` 与 WS 广播数据结构一致，可互相替代。

## 3) 本次修复（最小改动）

### 修复点 A：WebSocket 连接变量可重连
- 问题：前端将 `ws` 声明为 `const`，在 `connectWS()` 中再次赋值会抛错（重连逻辑失效）。
- 修复：改为 `let ws = null;`，由 `connectWS()` 统一创建连接。

### 修复点 B：二轮互评失败分支缺失
- 问题：`runReviewRound()` 未判断 `resp.ok`，失败时也显示“完成”。
- 修复：增加 `!resp.ok` 分支，显示 `二轮互评失败: ...`。

### 修复点 C：Agent 列表加载失败分支缺失
- 问题：`loadAgents()` 未判断 `resp.ok`。
- 修复：增加失败提示 `加载 Agent 列表失败: ...`。

### 修复点 D：冲突图加载失败分支缺失
- 问题：`loadConflictGraph()` 未判断 `resp.ok`。
- 修复：增加失败提示 `加载冲突图失败: ...`。

## 4) 关键流程本地验证记录

> 服务：`uvicorn backend.main:app --host 127.0.0.1 --port 8788`

1. `/models/available`
   - 命令：`curl -sS http://127.0.0.1:8788/models/available`
   - 结果：返回 `models[]` 与 `default_model`，`fallback=false`。

2. `/agents` 列表 + 更新模型
   - 命令：
     - `curl -sS http://127.0.0.1:8788/agents`
     - `curl -sS -X POST http://127.0.0.1:8788/agents/mdt-id/model -H 'content-type: application/json' -d '{"model":"openai-codex/gpt-5.3-codex"}'`
   - 结果：返回 `{"ok":true,...}`，再次查询 `mdt-id.model` 已更新。

3. 病历上传/解析 sections
   - 命令：`curl -sS -X POST http://127.0.0.1:8788/cases/CASE-LIVE-001/documents/upload -F 'file=@/tmp/mdt_case.txt;type=text/plain'`
   - 结果：返回 `sections.imaging/labs/medications`，字段完整。

4. `discussion/submit` 携带 `confirmed_sections`
   - 命令：`curl -sS -X POST http://127.0.0.1:8788/discussion/submit ...`
   - 结果：`accepted=true`，`confirmed_sections_received=true`，`confirmed_adopted_count=2`，`docs_context_doc_count=2`。

5. WebSocket 断连兜底（轮询路径）可拉 events
   - 命令：`curl -sS http://127.0.0.1:8788/cases/CASE-LIVE-001/events`
   - 结果：返回 `events[]`（示例 `count=24`，末条 `event_type=conflict_detected`），可作为前端断连轮询数据源。

## 5) 结论

前端当前所有可见交互点均已在后端具备对应能力；关键字段对齐，失败分支补齐后可读性达标。WebSocket 重连与轮询兜底链路可用。