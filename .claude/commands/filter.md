你是 hr-talent-screener 技能的執行器。請嚴格遵循 `.agent/skills/hr-talent-screener/SKILL.md` 的完整 SOP。

## 任務：對 ANALYSIS.md 執行三階段清洗 + 候選人篩選

> 這是整個流程的 Step 1。
> ANALYSIS.md 是從 104 系統擷取的大量候選人摘要清單（上游大池子）。
> 本步驟的目的是從數百人中篩出值得深入看的人，讓 HR 決定要下載誰的 PDF 完整履歷。

### 步驟 1：確認來源
- 確認專案根目錄存在 `ANALYSIS.md`
- 若不存在，詢問使用者提供檔案路徑

### 步驟 2：三階段資料清洗
執行以下指令：
```
c:\Users\01102088\Desktop\python-3.14.2-embed-amd64\python.exe .agent/skills/hr-talent-screener/scripts/pipeline_clean.py ANALYSIS.md
```
- 向使用者回報清洗統計（雜訊移除數、唯一候選人數、重複移除數、三區塊分布）

### 步驟 3：候選人篩選
執行以下指令：
```
c:\Users\01102088\Desktop\python-3.14.2-embed-amd64\python.exe .agent/skills/hr-talent-screener/scripts/screen_candidates.py ANALYSIS.md
```
- 向使用者分區塊呈現候選名單，每人附命中理由摘要

### 步驟 4：等待回饋
詢問使用者：
1. 這份名單是否有漏選？請提供漏選的人名。
2. 是否有誤選？請指出不應入選的人名。

> 下一步：HR 根據此名單到 104 下載 PDF 履歷，再用 `/merge` 轉為 CSV。
> 收到漏選/誤選回饋後，可用 `/improve` 精煉規則。
