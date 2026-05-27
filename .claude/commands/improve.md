你是 hr-talent-screener 技能的疊代學習執行器。請嚴格遵循 `.agent/skills/hr-talent-screener/SKILL.md` 步驟 4（疊代學習）的完整流程。

## 任務：根據最新的 HR_Data_Summary.csv 或使用者回饋，精煉篩選規則

> 這是整個流程的 Step 3（最後一步）。
> 前置條件：HR 已完成 `/filter`（篩選）→ `/merge`（合併 PDF 為 CSV）。
> `HR_Data_Summary.csv` 代表 HR 最終確認要深入看的人選，是「正確答案」。
> 本步驟的目的是用這份正確答案回頭精煉篩選規則，讓下一次 `/filter` 自動篩出更接近 HR 期望的結果。

### 角色模式（v9.2 雙角色 overlay）

| 角色 | 規則更新寫入位置 |
|------|------------------|
| `default`（不帶參數，預設）= **MEP** 角色 | 主規則檔 `screening_rules.md` + `role_overlays/default.md` + 程式碼 `screen_candidates.py` |
| `space-manager` | overlay 檔 `role_overlays/space-manager.md` + 程式碼 overlay 區段 |
| ~~`mep-design`~~ | deprecated alias，v9.2 起 fallback 至 default（過渡 v9.0~v9.1 留存的歷史條目視同 default） |

兩角色共寫 **疊代日誌（iteration_log.md）、歷史選人 CSV（historical_selections.csv）**——支持「同部門知識交流」哲學。CSV 的「角色」欄會標記每筆記錄。

### 輸入來源（按優先順序）
1. 若使用者剛執行完 `/filter` 並提供了漏選/誤選回饋 → 以該回饋為依據
2. 若專案根目錄存在最新的 `HR_Data_Summary.csv` → 以該 CSV 為已確認入選名單

### 步驟 1：分析差異
- 讀取 `HR_Data_Summary.csv`（排除非候選人列如 ANALYSIS、clear_RULE 等）
- 讀取 `.agent/skills/hr-talent-screener/references/iteration_log.md` 了解歷史批次
- 讀取 `.agent/skills/hr-talent-screener/references/screening_rules.md` 了解現行規則
- 比對新批次選人特徵 vs 現行規則，找出規則缺口（漏選原因）與過寬之處（誤選原因）

### 步驟 2：更新規則文件
更新 `.agent/skills/hr-talent-screener/references/screening_rules.md`：
- 新增/修正 M/N/E 條件
- 補充新發現的關鍵字
- 沉澱新的經驗法則
- 更新版本紀錄

### 步驟 3：同步更新程式碼
更新 `.agent/skills/hr-talent-screener/scripts/screen_candidates.py`：
- 同步新增的關鍵字到對應的 Python 常數列表
- 同步新增的 N 條件到評分邏輯
- 確認無重複計分問題

### 步驟 4：追加疊代日誌
追加 `.agent/skills/hr-talent-screener/references/iteration_log.md`：
- 記錄本批次來源統計、入選名單、規則洞察、使用者回饋
- 只做 Append，不刪除歷史

### 步驟 5：追加歷史選人紀錄
將本批次的 CSV 資料（排除非候選人列）追加至 `.agent/skills/hr-talent-screener/references/historical_selections.csv`，加上 `batch` 欄位與 `角色` 欄位標記（角色為 default 或 space-manager；歷史條目中的 mep-design 視同 default）。

### 步驟 6：回報
向使用者摘要報告：
- 新增了哪些規則/關鍵字
- 修正了哪些問題
- 建議下一步動作（通常是：等下一批 ANALYSIS.md 進來，再跑 `/filter`）
