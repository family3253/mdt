# 司礼监 → 户部：MDRGNB 每日深度简报调度模板

【司礼监调度令｜MDRGNB日报】
任务目标：完成当日 MDRGNB 新发表文献深度简报并推送。
负责人部门：户部
截止时间：当日 20:00（Asia/Singapore）
输入资料：
- /home/chenyechao/.openclaw/workspace/mdrgnb_proj/evaluated_papers.json
- PubMed 当日新发表检索结果

执行要求：
1. 仅检索当天新发表文献（Asia/Singapore）
2. 去重后通读候选（优先全文）
3. 评选 Top3
4. 每篇完成：10问深度总结 + 四维评分（工程应用/架构创新/理论贡献/结果可靠性）
5. 落盘：papers/<pmid>/summary.md 与 scores.md
6. 更新 evaluated_papers.json
7. 产出《MDRGNB 每日深度简报》并推送

回传格式：
- 今日新增检索数量
- Top3（标题+PMID+链接）
- 每篇10问要点与四维评分
- 当日结论与明日建议
- 若无高质量新增：明确说明并给1条高价值综述知识点
