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
| 提交会诊讨论（按钮） | `POST /cases/open`（预开病例，幂等） + `POST /discussion/submit` | `case_id`,`message`,`round_no`,`speaker`,`confirmed_sections`,`enable_docs_context` | `generated_count`,`confirmed_adopted_count`,`docs_context_doc_count` | `提交失败: ...` |
| 二轮互评（按钮） | `POST /discussion/review` | `case_id`,`from_round`,`to_round` | `generated_count` | `二轮互评失败: ...` |
| 刷新冲突图（按钮） | `GET /cases/{case_id}/conflicts` | - | `nodes[]`,`edges[]` | `加载冲突图失败: ...` |
| WebSocket 实时事件 | `WS /ws/events` | 客户端 ping 文本 | `{"type":"mdt_event","data":...}` | 断连后 UI 显示“WebSocket 断开（轮询模式）” |
| WebSocket/默认轮询拉事件 | `GET /cases/{case_id}/events` | - | `events[]` | 统一错误提示（含 HTTP/异常信息） |

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

## 3) 新增稳定性/可观测约定

### 3.1 轮询退避
- 前端默认启用轮询。
- 失败退避：`3s -> 5s -> 8s`。
- 任意一次成功后恢复到 `3s`。

### 3.2 连接诊断区字段
- `API`：当前 API 基址。
- `models`：最近一次 `GET /models/available` 的状态/耗时/时间。
- `agents`：最近一次 `GET /agents` 的状态/耗时/时间。
- `轮询最近成功`：最近一次 `/cases/{id}/events` 轮询成功时间。
- `当前间隔`：当前轮询间隔。

### 3.3 统一请求与错误格式
- 前端所有请求统一经 `requestWithMeta()`，统一构建错误消息。
- 后端错误响应统一结构至少包含：
  - `detail`
  - `message`

## 4) 本轮回归建议

> 服务：`uvicorn backend.main:app --host 127.0.0.1 --port 8788`

1. `GET /healthz`：确认 `service/db/time/version`。
2. `GET /models/available`：确认 models 与 default_model 返回。
3. `GET /agents`：确认 Agent 列表可返回。
4. `GET /cases/{case_id}/events`：确认轮询数据源可返回（空数组也视为正常）。

## 5) 结论

前端当前所有可见交互点均已在后端具备对应能力；在 WebSocket 不稳定场景下，轮询可稳定工作，且具备诊断与退避能力，便于回归验证。
