---
name: auto-pool-maintainer
description: 维护 CLIProxyAPI 号池。用于“号池维护/补号/剔除无效账号/每天定时维护/candidates 阈值维护”等请求。基于 auto_pool_maintainer.py 执行清理401、补号、收敛。
---

# Auto Pool Maintainer

用于维护本机 CPA/CLIProxyAPI 账号池。

## 何时使用
- 用户要求：补号、清理无效账号、维持 candidates 阈值
- 用户要求：定时自动维护（如每天 8:00）

## 执行路径
- 脚本：`scripts/auto_pool_maintainer.py`
- 依赖：`scripts/requirements.txt`
- 配置模板：`references/config.template.json`

## 标准执行步骤
1. 确保 venv 存在；不存在则创建并安装依赖。
2. 使用运行配置 `runtime/config.json`（不要把敏感 key 写进模板）。
3. 执行：
   - 试跑：`python scripts/auto_pool_maintainer.py --config runtime/config.json --min-candidates 2 --timeout 10`
   - 正式：`python scripts/auto_pool_maintainer.py --config runtime/config.json --min-candidates <目标值> --timeout 10`
4. 查看日志目录 `runtime/logs/`，回报成功/失败和当前候选数。

## 定时任务约定
- 需要每日维护时，创建 cron：`0 8 * * *`（Asia/Shanghai）
- 任务内容应调用上述正式命令，目标值由用户指定（默认 200）

## 必问项（缺失时）
- CPA 管理 token（`clean.token`）
- 邮箱 API key（`email.api_key`）
- 代理端口（如 10809）是否可用

## 安全
- 不在聊天中回显完整密钥
- 不把明文密钥提交到 git
