# HEARTBEAT.md

# Keep this file empty (or with only comments) to skip heartbeat API calls.

# Add tasks below when you want the agent to check something periodically.

\## 记忆维护任务（每周执行）

检查 `memory/heartbeat-state.json` 中的 `lastMemoryMaintenance`。

距今超过 7 天时执行：

1\. 读取最近 7 天日志
2\. 提炼长期价值信息 → 归档到 projects.md / lessons.md
3\. 压缩已完成的一次性任务为单行总结
4\. 删除完全过期的临时信息
5\. 更新 `lastMemoryMaintenance` 为当前日期

\## 全渠道不回复自动修复（每次 heartbeat 执行）

目标：自动发现“收到消息但不回复/明显卡住”的高概率状态，并自愈。

适用范围：除 Telegram 外，所有已启用对话渠道（webchat/discord/qqbot/feishu/wecom 等）。

执行步骤：

1\. 运行 `openclaw status`，重点看：
- 各渠道 direct/group session token 占比是否 >= 75%
- 是否出现 gateway timeout / delivery timeout / announce timeout 迹象
- 是否存在 channel state 非 OK

2\. 若命中异常：
- 先执行 `openclaw sessions cleanup`
- 再执行 `openclaw gateway restart`
- 重启后等待 8-12 秒，再执行一次 `openclaw status` 复检

3\. 将处理结果写入 `memory/heartbeat-state.json`：
- `lastGlobalAutoFixAt`
- `lastGlobalAutoFixReason`
- `lastGlobalAutoFixResult`
- `lastGlobalAutoFixChannels`

4\. 冷却机制：
- 2 小时内最多自动修复 1 次；命中冷却期则只记录，不重复重启

5\. 若复检仍异常：
- 输出告警文本（不要输出 HEARTBEAT_OK），简要说明异常与建议人工介入。

