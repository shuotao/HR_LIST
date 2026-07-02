你是 hr-talent-screener 技能的結案審閱執行器。請嚴格遵循 `.agent/skills/hr-talent-screener/SKILL.md` 步驟 5（結案審閱）的完整流程。

## 任務：基於 HR_Data_Summary.csv 全面審閱所有候選人，標註分類並反饋規則

> 這是整個流程的 Step 4（結案）。
> 前置條件：HR 已完成 `/filter` → `/merge`，`HR_Data_Summary.csv` 已產出 10 欄結構化履歷資料。
> 本步驟的目的是地毯式審閱每位候選人的完整履歷，將 CSV 擴充為 12 欄（加「審閱結果建議」與「審閱排除理由簡述」），並把審閱中發現的「漏網之魚」反饋回規則。

### 角色模式（多角色 overlay）

v9.2 雙角色架構，依職缺角色採用不同質性審閱重點：

| 角色 | 審閱重點 |
|------|----------|
| `default`（不帶參數，預設）= **MEP** | 廠務 + MEP 設計合一視角：建廠 EPC、廠務維運、機電監造、施工管理、單系統設計品質、BIM × MEP 共現、E2/E6/E8 條件化解禁、D7 BIM-only 降級、E22-E29 |
| `space-manager` | 空間管理視角：跨系統整合、法規理解、空間規劃；管理權重降低；上述 default 規則全包再加 N19/N20/D11/D13/D14 |
| ~~`mep-design`~~ | deprecated alias，v9.2 起自動 fallback 至 default |

各角色的 overlay 規格詳見 `.agent/skills/hr-talent-screener/references/role_overlays/<role>.md`。

> **注意**：`/review` 是 Agent 質性審閱流程，不需要外部評分工具。`/filter` 階段的所有 overlay 規則已內嵌於 `screen_candidates.py:get_overlay()`，本步驟讀取 CSV 後以同樣的質性視角逐人審視即可。`web/backend/bim_scorer.py` 是體檢 web app 的內部模組，與本流程獨立。

### 步驟 1：地毯式逐人審閱

讀取 `HR_Data_Summary.csv` 與專案根目錄下的 `*.pdf` / `*.md`：
- 對每位候選人，跨欄綜合評估：學歷 + 近期工作 + 工作內容 + 總年資 + 前公司
- 依「建廠 / 廠務 / 機電 / BIM 整合」相關程度做質性判斷
- 若使用 `--role`，以對應角色的審閱重點（見上表）逐人質性評估

### 步驟 2：標註分類

每位候選人標註為以下之一（**這四個值為合法 result 的唯一集合**，傳給 `apply_review_decisions.py` 時必須完全一致，否則腳本會中止）：
- **正式候選**：完全符合，可進入面試池
- **排除**：不適任（給出理由）
- **降級觀察**：部分符合但需更多資訊或培訓
- **碩士儲備**：碩士新人 / 潛力但缺乏直接經驗，留作未來機會

### 步驟 3：差異清單 + 【閘門 A】使用者簽核

1. 先跑官方腳本產生判決草稿（逐人分數 + 基線判決）：
   ```
   D:\green-tools\python-3.14.2-embed-amd64\python.exe .agent/skills/hr-talent-screener/scripts/generate_review_decisions.py --role=<role>
   ```
2. Agent 逐人核對完整履歷微調，產出**差異清單**（腳本判決 vs Agent 建議不一致筆 + 分數門檻 ±5 邊界筆），每筆附序號、姓名、分數、兩造判決、關鍵證據 1~2 行。
3. 呈現差異清單給使用者逐筆簽核（回覆「同意」或「改為X」）：
   - 使用者說「代打」→ spawn `gatekeeper`（MODE: PROXY）；查無歷史模式的筆掛起，回頭請使用者裁決
   - 簽核完成後 → spawn `gatekeeper`（MODE: RECORD）記錄互動
4. ⛔ **未過閘門 A，嚴禁執行步驟 4 的 apply**

### 步驟 4：產出 `review_decisions.json` 並執行官方落地腳本

**嚴禁自行撰寫一次性腳本以 hardcode dict 方式修改 CSV**（違反 CLAUDE.md 唯一腳本原則）。所有判決必須走以下單一通道：

1. Agent 將定稿判決（含閘門 A 簽核結果）整理為 `review_decisions.json`（放在專案根目錄），格式：
   ```json
   {
     "role": "default",
     "decisions": {
       "001": {"result": "正式候選", "reason": ""},
       "002": {"result": "排除",     "reason": "E12 純物業..."}
     }
   }
   ```
2. 執行官方腳本將判決寫入 `HR_Data_Summary.csv`（由原 10 欄擴充為 12 欄）並執行強制驗證：
   ```
   D:\green-tools\python-3.14.2-embed-amd64\python.exe .agent/skills/hr-talent-screener/scripts/apply_review_decisions.py review_decisions.json
   ```
3. 腳本特性：
   - 冪等性（可重跑，欄位不會疊加）
   - 越權 result 值自動中止
   - 自動執行 CSV ↔ PDF 一致性驗證（見步驟 4，由腳本內建）
   - 自動印出各分類人數統計

> **欄位約束**：「審閱結果建議」由腳本插在「總年資」之前，「審閱排除理由簡述」追加在末欄。正式候選者的 reason 自動留空。

> **檔案約束**：僅在 CSV 內標註，**不搬移任何 PDF/MD 檔案**，**不建立 excluded/ downgraded/ reserve/ 子資料夾**。所有 PDF/MD 一律保留在根目錄。

### 步驟 5：強制驗證 CSV ↔ PDF 一致性（由腳本自動執行）

`apply_review_decisions.py` 會在步驟 3 末段自動執行此驗證——逐筆比對 CSV 序號與根目錄 PDF 檔名 `{序號}_{姓名}.pdf`：
- 若任一筆不一致，腳本立即報錯並退出，CSV 已寫入但 Agent 必須回報失敗
- 全部一致才可宣告結案

### 步驟 6：落差分析 + 【閘門 B】+ 反饋迴路（核心）

1. 產出落差分析報告與問題選項（Q1: A/B/C 格式，C 永遠是「誤判，不需調整」）。
2. 【閘門 B】等使用者回答問題選項（或「代打」→ gatekeeper PROXY 依歷史答題傾向代答，查無傾向的題掛起）→ 完成後 spawn `gatekeeper`（MODE: RECORD）。
   ⛔ **未取得回答前，嚴禁修改 `screening_rules.md` / `role_overlays/` / `screen_candidates.py`**。
3. 審閱中發現「漏網之魚」（應在 `/filter` 階段就被排除但未攔截）：
   - 歸因到具體規則缺口
   - 更新 `screening_rules.md`（default 角色）或 `role_overlays/<role>.md`（角色 overlay）
   - 同步更新 `screen_candidates.py` 中對應的關鍵字 / 條件
   - 追加 `iteration_log.md` 日誌（記錄本次 `/review` 的反饋內容、role 標籤）
4. 規則落地後**必跑**黃金集回歸測試：
   ```
   D:\green-tools\python-3.14.2-embed-amd64\python.exe .agent/skills/hr-talent-screener/scripts/regression_check.py
   ```
   - PASS（0 新翻盤）→ 規則變更成立
   - FAIL → 呈報翻盤名單；刻意翻盤經使用者核准後跑 `--accept` 更新 baseline；**代打模式下 FAIL 一律停下等使用者**

### 步驟 7：回報與結案

向使用者摘要：
- 各分類人數（正式候選 / 排除 / 降級觀察 / 碩士儲備，腳本已自動統計）
- 反饋了哪些規則缺口 + 回歸測試結果
- 下一次 `/filter` 預期的改進點

使用者確認結案後（**結案永遠由使用者，不可代打**），spawn `gatekeeper`（MODE: RECORD）記錄 closure。
