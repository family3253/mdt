---
name: mdrgnb-daily-push
description: 固化 MDRGNB 文献日/周报流程（当天新发表检索、去重、Top3 筛选、10问深度总结、四维评分、落盘与推送）。当用户提到 MDRGNB 日报、文献推送、深度总结、Top3、周报、PubMed 当日新文献时使用。
---

# MDRGNB Daily Push

执行目标：每天产出 MDRGNB 深度简报，每周产出 Top3 周报。

## 固定目录

- 项目根：`/home/chenyechao/.openclaw/workspace/mdrgnb_proj`
- 去重文件：`/home/chenyechao/.openclaw/workspace/mdrgnb_proj/evaluated_papers.json`
- 单篇输出：`/home/chenyechao/.openclaw/workspace/mdrgnb_proj/papers/<pmid>/`
  - `summary.md`
  - `scores.md`

若目录/文件不存在，先创建。

## 每日流程（严格）

1. 仅检索 **当天新发表** PubMed 文献（时区：`Asia/Singapore`）。
2. 关键词围绕 MDRGNB（多药耐药革兰阴性菌），并过滤明显不相关主题。
3. 与 `evaluated_papers.json` 去重。
4. 对候选文献逐篇通读：
   - 优先全文；
   - 无法获取全文时，完整阅读摘要并在总结中标注“全文不可得”的限制。
5. 按相关性+价值选 Top 3。
6. 每篇生成 `summary.md`：必须回答 10 个核心问题（见 `references/ten_questions.md`）。
7. 每篇生成 `scores.md`：四维评分（1-10）
   - 工程应用价值
   - 架构创新
   - 理论贡献
   - 结果可靠性
   并给出总评（简短理由）。
8. 更新 `evaluated_papers.json`（至少记录 pmid、title、date、source）。
9. 输出《MDRGNB 每日深度简报》用于推送：
   - 今日新增检索数量
   - Top3（标题 + PMID + 链接）
   - 每篇必须包含：期刊名 + 分区信息（至少中科院分区与JCR/SCI分区，若仅有其一需注明）
   - 每篇 10 问摘要要点 + 四维评分
   - 当日结论与明日建议
   - 若无高质量新增：明确说明并给 1 条高价值综述知识点

## 每周流程

- 每周日 10:00（Asia/Singapore）基于本周已评估文献生成《MDRGNB 周报 Top3》：
  - Top3 入选理由
  - 每篇核心贡献 + 期刊名 + 分区信息（中科院/JCR）+ 10问精华 + 四维评分
  - 本周趋势判断 + 下周检索建议（3条）

## 推送要求

- 默认推送到 Feishu + QQBot。
- 直接输出最终内容，避免在隔离任务中再次要求“调用 message 工具”。
- 任何发送失败必须回报失败原因和建议修复路径（目标ID、通道、权限、长度限制）。
