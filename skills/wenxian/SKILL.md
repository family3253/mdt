---
name: wenxian
description: 基于本地与上游仓库期刊分区表进行检索与分区查询。用于“查中科院分区、查JCR分区、查SCI分区、按期刊名匹配分区、对比2024/2025分区变化、同步share_repo JCR数据”等请求。
---

# wenxian

使用本技能时，优先基于本地整合表检索：

- `references/JCR2024_FQBJCR2025_merged.csv`：整合 2024 JCR 与 2025 中科院分区（同名期刊对齐，保留双方原始字段）

必要时可回看源表：
- `references/FQBJCR2025.csv`：中科院分区（含大类/小类分区、Top、是否OA、WoS索引等）
- `references/JCR2024.csv`：JCR IF、IF Quartile、IF Rank（可作为 SCI/JCR 分区参考）

上游补充来源：
- GitHub: `https://github.com/yongqianxiao/share_repo/tree/master/JCR`
- 本地清单：`references/upstream/share_repo_JCR_manifest.txt`
- 同步脚本：`scripts/sync_share_repo_jcr.sh`（将上游 `JCR/` 拉取到 `references/upstream_raw/`）

## 执行规则

1. 先按期刊名精确匹配；未命中时再做大小写无关和去标点模糊匹配。
2. 用户说“中科院分区”时，优先返回 `FQBJCR2025.csv` 结果。
3. 用户说“SCI分区/JCR分区”时，优先返回 `JCR2024.csv` 的 `IF Quartile(2024)` 与 `IF Rank(2024)`。
4. 同一期刊在两表都有记录时，默认同时给出两套结果并标注年份来源（2024/2025）。
5. 结果输出尽量结构化：
   - 期刊名
   - 中科院大类/分区、Top（若有）
   - JCR IF、Q区、排名（若有）
   - 数据来源文件与年份

## 批量查询

- 支持多期刊批量匹配，输出表格或清单。
- 期刊名冲突或疑似同名时，附带 ISSN/eISSN 辅助核对。

## 说明

- 本技能默认以本地整合表为准。
- 用户要求“补最新分区/同步上游JCR仓库”时，先运行：`bash scripts/sync_share_repo_jcr.sh`。
- 同步后优先从 `references/upstream_raw/` 读取对应年度文件，再与本地整合表交叉校验并标注差异。
