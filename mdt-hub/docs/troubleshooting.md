# MDT Hub 故障排查（WebSocket/轮询）

## 1) 为什么 WebSocket 经常断开？

常见原因：
- 反向代理/网关未正确透传 Upgrade 头。
- 公司网络/校园网对长连接有中间设备超时策略。
- 浏览器页面跨源访问时，WS 地址不可达或被拦截。
- 后端重启导致现有连接被动断开。

> 结论：前端已默认轮询模式，WS 不稳定不会阻塞核心功能。

## 2) 如何确认“轮询在工作”

打开页面左侧“连接诊断”区，观察：
- `轮询最近成功` 时间持续更新。
- `当前间隔` 在成功时维持 3s。
- 若连续失败会看到间隔升为 5s/8s（指数退避生效）。

也可直接 curl：

```bash
curl -sS http://127.0.0.1:8788/cases/CASE-LIVE-001/events
```

能返回 JSON（即使 `events: []`）说明轮询数据源可用。

## 3) 常见失败定位步骤

### 步骤 A：先看健康状态

```bash
curl -sS http://127.0.0.1:8788/healthz
```

确认字段：`service`、`db`、`time`、`version`。

### 步骤 B：看基础接口

```bash
curl -sS http://127.0.0.1:8788/models/available
curl -sS http://127.0.0.1:8788/agents
curl -sS http://127.0.0.1:8788/cases/CASE-LIVE-001/events
```

### 步骤 C：看前端诊断区
- `models/agents` 若显示 `HTTP xxx`：优先排查后端响应体中的 `detail/message`。
- 若显示异常（如网络错误）：优先排查 API 基址、跨域、端口连通性。

### 步骤 D：看后端访问日志（关键接口）
后端已对以下接口增加访问日志（路径、方法、状态、耗时）：
- `/models/available`
- `/agents`
- `/agents/{id}/model`
- `/cases/{id}/events`
- `/discussion/submit`

如果日志无记录，通常是请求未到达后端（前端地址或网络层问题）。

## 4) 错误响应格式约定

后端统一错误结构至少包含：

```json
{
  "detail": "...",
  "message": "..."
}
```

前端会直接展示这两个字段，便于快速定位。
