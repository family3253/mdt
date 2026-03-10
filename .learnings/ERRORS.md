## [ERR-20260308-002] cron_telegram_delivery_timeout

**Logged**: 2026-03-08T23:05:00+08:00
**Priority**: high
**Status**: investigating
**Area**: openclaw-gateway

### Summary
天气 cron 在 23:00 已成功生成文本结果，但 announce 投递到 Telegram 时卡住，日志出现 `gateway timeout after 60000ms`。同时存在多条重复天气任务，增加排障复杂度。

### Error
- 用户反馈：天气没推送
- 本地 cron 会话已产出最终文本
- gateway 日志：`Subagent announce completion direct announce agent call transient failure, retrying 2/4 in 5s: gateway timeout after 60000ms`

### Context
- 任务 `0e9c8f30-2284-465e-a27c-83310cb0e1db` 于 23:00 运行
- session transcript 显示已查到天气并输出纯文本
- cron jobs 中还残留旧天气任务：`075548d0-5e0e-4ee2-91ed-74b3c1660472`、`c17249a7-ea04-4fb5-88e3-6ad7f9927439`
- `message` 工具手动发送也异常，报：`Poll fields require action "poll"`

### Suggested Fix
1. 删除所有重复天气任务，仅保留一条 23:00 任务；
2. 重启 OpenClaw gateway；
3. 手动补跑 cron 验证 delivery；
4. 如仍失败，检查当前 CLI/service 版本漂移（当前 CLI 2026.3.2，而配置由 2026.3.7 写入）。

### Metadata
- Reproducible: yes
- Related Files: /tmp/openclaw/openclaw-2026-03-08.log
- Tags: cron, telegram, gateway-timeout, delivery, version-skew
- See Also: ERR-20260308-001

---

## [ERR-20260310-001] acp_runtime_not_configured

**Logged**: 2026-03-10T08:42:00+08:00
**Priority**: high
**Status**: pending
**Area**: openclaw-acp

### Summary
尝试按用户要求做 ACP 连通性测试时失败，ACP 运行时未配置。

### Error
`ACP runtime backend is not configured. Install and enable the acpx runtime plugin.`

### Context
- 操作：`sessions_spawn`（runtime=`acp`）
- 目标：最小连通性 smoke test
- 结果：调用立即返回错误，未进入模型执行阶段

### Suggested Fix
1. 安装并启用 acpx runtime 插件；
2. 重启 gateway；
3. 再次执行 ACP 最小连通性测试。

### Metadata
- Reproducible: yes
- Related Files: N/A
- Tags: acp, runtime, plugin, smoke-test

---

