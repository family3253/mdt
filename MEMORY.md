# MEMORY.md

## 用户长期偏好
- 用户偏好：干练、直接、少废话。
- 正在建设“AI 朝廷”工作流，强调可执行、可复用、可追踪。
- 重点项目：MDRGNB 文献日/周报自动化（PubMed 当天新文献、Top3、10问总结、四维评分、双通道推送）。

## 当前稳定配置（需持续保持）
- 定时任务已存在：MDRGNB 每日/每周（Feishu + QQBot）。
- QQBot 已恢复可收消息（最近一次重测已收到）。
- 模型白名单（2026-03-09 体检后）：
  - 可用：`openai-codex/gpt-5.3-codex`；`nat0-openai-{1,2,3}` 下的 `claude-opus-4-6 / glm-5 / gpt-5.3-codex / gpt-5.4 / grok-4-1-fast`。
  - 默认主模型：`openai-codex/gpt-5.3-codex`。
  - 默认 fallback：`nat0-openai-1/gpt-5.4`、`nat0-openai-1/gpt-5.3-codex`。
  - 已剔除（不可用）：`nat0-*/gemini-3.1-pro-preview`、`openai/gpt-5.2-pro`、`openai/gpt-5.3-codex`、`openai/gpt-5.3-codex-spark`、`google/*`、`google-gemini-cli/*`、`google-vertex/*`、`google-antigravity/*`。

## 协作偏好
- 先落地再解释；优先给结果与下一步。
- 涉及外部通道（QQ/Feishu/Discord）先做可达性验证，再批量上任务。
- 配置变更规则：每次修改 `openclaw.json` 前先备份旧文件（带时间戳）；新配置确认可运行后删除本次备份，异常时可立即回滚。
- 新增（2026-03-11）：用户每次下达命令后，默认先创建后台 subsession 执行；主会话持续汇报进度；遇到问题先自主排障再回报。

## 记忆维护规则
- 关键决策、通道修复、可复用模板要写入 MEMORY.md。
- 过程细节写入 daily memory（memory/YYYY-MM-DD.md）。
