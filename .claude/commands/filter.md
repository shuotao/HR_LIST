你是 hr-talent-screener 技能的執行器。請嚴格遵循 `.agent/skills/hr-talent-screener/SKILL.md` 的完整 SOP。

## 任務：對 ANALYSIS.md 執行三階段清洗 + 候選人篩選

> 這是整個流程的 Step 1。
> ANALYSIS.md 是從 104 系統擷取的大量候選人摘要清單（上游大池子）。
> 本步驟的目的是從數百人中篩出值得深入看的人，讓 HR 決定要下載誰的 PDF 完整履歷。

### 角色模式（多角色 overlay）

從 v9.0 起，本指令支援 `--role` 參數，依職缺角色套用不同 overlay：

| 角色 | 用途 | 命令 |
|------|------|------|
| `default` | 廠務 / 一般 MEP（既有 v8.13 行為，預設） | `screen_candidates.py ANALYSIS.md` |
| `mep-design` | MEP 設計工程師（用 BIM 做深） | `screen_candidates.py ANALYSIS_BIM.md --role=mep-design` |
| `space-manager` | 空間管理（用 BIM 做廣） | `screen_candidates.py ANALYSIS_BIM.md --role=space-manager` |

各角色的 overlay 規格詳見 `.agent/skills/hr-talent-screener/references/role_overlays/`。

### 步驟 1：確認來源
- 確認專案根目錄存在 `ANALYSIS.md`（或 `ANALYSIS_BIM.md` 等角色專屬輸入）
- 若不存在，詢問使用者提供檔案路徑

### 步驟 2：三階段資料清洗
執行以下指令（清洗腳本與角色無關）：
```
c:\Users\01102088\Desktop\python-3.14.2-embed-amd64\python.exe .agent/skills/hr-talent-screener/scripts/pipeline_clean.py ANALYSIS.md
```
- 向使用者回報清洗統計（雜訊移除數、唯一候選人數、重複移除數、三區塊分布）

### 步驟 3：候選人篩選

**default 模式**（不帶 `--role`，行為與 v8.13 完全一致）：
```
c:\Users\01102088\Desktop\python-3.14.2-embed-amd64\python.exe .agent/skills/hr-talent-screener/scripts/screen_candidates.py ANALYSIS.md
```

**mep-design 模式**（找 MEP 設計工程師）：
```
c:\Users\01102088\Desktop\python-3.14.2-embed-amd64\python.exe .agent/skills/hr-talent-screener/scripts/screen_candidates.py ANALYSIS_BIM.md --role=mep-design
```

**space-manager 模式**（找空間管理工程師）：
```
c:\Users\01102088\Desktop\python-3.14.2-embed-amd64\python.exe .agent/skills/hr-talent-screener/scripts/screen_candidates.py ANALYSIS_BIM.md --role=space-manager
```

- 向使用者分區塊呈現候選名單，每人附命中理由摘要
- 若使用了 `--role`，輸出開頭會有「角色模式: <role>」與 overlay 載入摘要

### 步驟 4：等待回饋
詢問使用者：
1. 這份名單是否有漏選？請提供漏選的人名。
2. 是否有誤選？請指出不應入選的人名。
3. 若使用 overlay 模式，特別詢問：「BIM × MEP 共現規則是否應收緊或放寬？」、「D7 BIM-only 降級的擊殺力是否合適？」

> 下一步：HR 根據此名單到 104 下載 PDF 履歷，再用 `/merge` 轉為 CSV。
> 收到漏選/誤選回饋後，可用 `/improve --role=<role>` 精煉規則。
