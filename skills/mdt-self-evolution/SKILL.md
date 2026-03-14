---
name: mdt-self-evolution
description: 持续复盘 MDT 会诊事件，自动识别流程瓶颈/冲突热点/专家失衡，并生成可执行优化任务（backlog），驱动前后端与多agent配置持续进化。
---

# MDT Self-Evolution Skill

## 触发场景
- 用户说“继续优化/自我进化/持续迭代 MDT”
- 新增了专家、流程或可视化能力后，需要评估效果
- 会诊轮次增加，想知道哪里最该优化

## 输入数据
- `mdt.db` 中的 `mdt_events`
- （可选）`cases` 与冲突图接口输出

## 输出产物
- `backend/evolution/evolution-backlog.json`
- `backend/evolution/evolution-report.md`

## 评估维度（默认）
1. 讨论覆盖度：每轮是否有足够专家参与
2. 冲突密度：support/oppose 比例与冲突集中主题
3. 收敛效率：从讨论到 `consensus_updated` 的事件步数
4. 角色均衡：是否有专家长期缺席/过载
5. 可视化可读性：事件是否带足够结构字段（target, stance, evidence）

## 迭代规则
- 优先修“高影响+低成本”任务
- 每次最多推进 3 个 backlog 项，避免无限扩张
- 每完成一项，回写状态为 `done` 并记录 commit

## 建议工作流
1. 跑 `python backend/evolution/evolution_loop.py`
2. 读 `evolution-report.md`
3. 选 Top3 backlog 落地
4. 完成后再跑一轮，对比指标变化
