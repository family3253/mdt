---
name: aether-pool-maintainer
description: "维护 Aether 的 gpt 号池：从 CPA/CLIProxyAPI 的 Codex OAuth auth-files 中筛选 refresh_token，批量导入 Aether provider-oauth 的 gpt provider，清理失效 key，并通过 OpenClaw cron 在 08:00/20:00 自动维护到目标账号数（默认 200）。触发：aether补号/号池维护/导入 gpt 池/Aether 目标200/修复 token_invalidated/代理节点不可用。"
---

# Aether GPT 号池维护（CPA → Aether）

## 目标
- 把 Aether 的 GPT provider（provider_id）维护到目标账号数（通常 200）。
- 数据来源：CPA/CLIProxyAPI（本机 8080）管理接口 `/v0/management/auth-files` 里 codex provider 的 refresh_token。
- 导入方式：Aether `provider-oauth` 的 `batch-import`。

## 已知坑（必须记住）
1) **不要导入 token_invalidated**
- CPA 的 `auth-files.status_message` 出现 `token_invalidated`，直接跳过（已在脚本里内置过滤）。

2) **proxy_node_id 可能导致 503**
- 如果 Aether 返回：`代理节点 ... 不可用`，先不要传 `--proxy-node-id`，先把能导入的导入。

3) OAuth 建号链路
- `codex-auth-url` 生成的 state/code 不能复用；必须一轮一套。
- webui 模式 (`?is_webui=1`) 需要 CPA 能监听 `127.0.0.1:1455`；本机如果有 ssh -L 占用 1455，会导致 `failed to start callback server`。

## 关键参数（当前环境）
- CPA base: `http://127.0.0.1:8080`
- CPA management key: `3323092216`
- Aether base: `http://127.0.0.1:8084`
- Aether admin: `1145569340@qq.com`
- Aether admin password: `3323092216`
- GPT provider id: `81e53f4e-b0fb-48d1-9466-ea54013fec1e`

## 执行入口（脚本）
维护脚本：
- `/home/chenyechao/.openclaw/workspace/scripts/aether_gpt_pool_maintain.py`

推荐安全模式（不删除，只补）：
```bash
python3 /home/chenyechao/.openclaw/workspace/scripts/aether_gpt_pool_maintain.py \
  --cpa-base http://127.0.0.1:8080 \
  --cpa-mgmt-key 3323092216 \
  --aether-base http://127.0.0.1:8084 \
  --aether-email 1145569340@qq.com \
  --aether-password 3323092216 \
  --provider-id 81e53f4e-b0fb-48d1-9466-ea54013fec1e \
  --target-keys 200 \
  --cleanup-limit 20 \
  --import-limit 50 \
  --safe \
  --fallback-to-existing-cpa
```

## Cron 固化（已创建）
- 08:00 Aether: `aether-gpt-pool-maintenance-0800`
- 20:00 Aether: `aether-gpt-pool-maintenance-2000`
- 08:00 CPA: `daily-pool-maintenance-0800-once`（模型已改为 cpa/gpt-5.2-codex）
- 20:00 CPA: `cpa-pool-maintenance-2000`

## 成功判据
- Aether `/api/admin/pool/<provider_id>/keys` 的 `total` 增长，目标接近 200。
- batch-import 返回 `success > 0` 且 `top_errors` 可解释。
