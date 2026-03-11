---
name: cpaclean
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

## 定时任务约定（修复版）
- 需要每日维护时，创建 cron：`0 8 * * *`（Asia/Shanghai）
- 任务内容应调用正式命令，目标值默认 200
- 每日维护默认目标：**数量恢复 + API链路可用**，不是只看 candidates
- 支持额外目标：`maintainer.extra_candidates`（用于“保护账号不计入阈值”）
  - 例如基础 `min_candidates=200` 且 `extra_candidates=1`，实际目标为 201（即“额外补200，不含保护号”）

推荐维护话术（用于 cron message）：
- “执行 cpaclean 日常维护：
  1) 先做小样本健康探测并区分错误类型；
  2) 若为权限/scope 问题，避免全量误删；
  3) 补号至 min_candidates；
  4) 最后抽样验证统一 API 输出（/v1/models、/v1/responses）。
  输出：总账号/codex账号/抽样可用性。”

## 必问项（缺失时）
- CPA 管理 token（`clean.token`）
- 邮箱 API key（`email.api_key`）
- 代理端口（如 10809）是否可用

## 本次修复后新增规则（必须遵守）

### 1) 清理策略防误杀
- 不能再用“`/v1/models` 非200即删除”做全量清理。
- 先探测 `models`，若非200再探测 `responses`；只要 `responses=200`，该账号视为可用，不删除。
- 先抽样判断失败类型：
  - `Missing scopes` / `insufficient permissions` → 属于权限问题，**先暂停批量删除**。
  - 明确 `401 token_invalidated` / 认证失效 → 才进入批量清理。
- 先小批（3-5个）验证，再放大全量操作。

### 2) 邮箱配置硬约束
- `email.base_url` 必须使用可用地址：`https://cyc3253.org/`。
- 使用 `http://cyc3253.org/` 会触发 301/405，导致补号失败。
- `email.api_key` 必须有效；无效时先做单次 API 冒烟，不直接跑补号。

### 3) OAuth scope 现实约束
- 现网 OpenAI OAuth 客户端可能拒绝 `model.request`（`invalid_scope`）。
- 发现 `invalid_scope` 时，不要重复刷 OAuth；直接切到 API key 方案恢复可用性。

### 4) 应急兜底（优先恢复可用）
- 当 OAuth 路径持续报 scope 错误时：
  - 通过 CPA 管理接口写入 `codex-api-key`；
  - 验证 `GET /v1/models` 与 `POST /v1/responses` 均 200；
  - 再回到号池维护。
- Antigravity 场景：允许“OAuth 接入到 CPA + 统一经 CPA API 输出”；验收以统一 API 调用结果为准。

### 5) 最小验收标准
- 维护完成后至少输出：
  - 总账号数 / codex账号数
  - 抽样账号 `wham/usage` 结果
  - 抽样账号 `models` 与 `responses` 可用性

## 保护账号（防误删）
- 支持在 `runtime/config.json` 中配置：`clean.protected_names`（字符串数组）
- 清理阶段命中保护名单的账号会跳过删除（日志会输出“保护名单生效”）
- 每次维护结束会输出保护账号状态（存在性 + models 探测状态）
- 当前强保护账号：
  - `codex-komptitgmanchalem@mail.com-plus.json`
  - `antigravity-chenyechao3253@gmail.com.json`

## 安全
- 不在聊天中回显完整密钥
- 不把明文密钥提交到 git
