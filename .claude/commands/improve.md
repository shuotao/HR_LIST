你是 hr-talent-screener 技能的疊代學習執行器。請嚴格遵循 `.agent/skills/hr-talent-screener/SKILL.md` 步驟 4（疊代學習）的完整流程。

## 任務：以跨批次累積的回饋名單，精煉篩選規則

> 這是整個 4 步驟流程的 **Step 2**（`/filter` → **`/improve`** → `/merge` → `/review`）。
> 採「先蒐集，後分析」雙階段模型：不再每批 `/filter` 後立即改規則，而是先跨批次累積回饋，樣本足量後才統一分析落地。

## 雙階段模型（務必先判斷目前處於哪一階段）

### 階段一 · 名單蒐集（每次 `/filter` 後可重複多輪，**此階段嚴禁改規則**）
使用者確認 `/filter` 結果後給的回饋，只做「取區塊 → append」，**不得**改規則/改 `screen_candidates.py`/進入下面的分析步驟：
- **排除/誤選 XXX**（引擎放行但不合格，false positive）→ 從 `ANALYSIS.md` 取 XXX 完整資料區塊，**append（不取代）**寫入根目錄 `unqualify.md`。
- **加回/漏選/qualify XXX**（引擎排除但合格，false negative）→ 從 `ANALYSIS.md` 取 XXX 完整資料區塊，**append（不取代）**寫入根目錄 `qualify.md`。
- 兩檔以「代碼：」去重、**append-only**；**嚴禁自動清空或歸檔**（僅使用者可人為處理）。
- 下一次 `/filter` 由 `screen_candidates.py` 自動比對：命中 `unqualify.md` 標 ★、命中 `qualify.md` 標 ☆ 並列「仍被漏掉」清單。

### 階段二 · 規則疊代（使用者說「Step 2」／`/improve` 才進入 → 執行下列步驟 1~6）

## 角色模式（v9.2 雙角色 overlay）

| 角色 | 規則更新寫入位置 |
|------|------------------|
| `default`（不帶參數，預設）= **MEP** 角色 | 主規則檔 `screening_rules.md` + `role_overlays/default.md` + 程式碼 `screen_candidates.py` |
| `space-manager` | overlay 檔 `role_overlays/space-manager.md` + 程式碼 overlay 區段 |
| ~~`mep-design`~~ | deprecated alias，v9.2 起 fallback 至 default（過渡 v9.0~v9.1 留存的歷史條目視同 default） |

兩角色共寫 **疊代日誌（iteration_log.md）、歷史選人 CSV（historical_selections.csv）**——支持「同部門知識交流」哲學。CSV 的「角色」欄會標記每筆記錄。

### 輸入來源（階段二分析素材）
1. `unqualify.md`（誤選累積：引擎放行但判定不合格）+ `qualify.md`（漏選累積：引擎排除但判定合格）→ **主要分析素材**
2. 既有 `HR_Data_Summary.csv`（已確認入選名單）→ 輔助佐證

### 步驟 1：分析差異（讀名單、逐人歸因、跨批次統計）
- 讀取 `unqualify.md` 逐人歸因：篩選引擎為何放行？→ 找排除規則（E/D）系統性缺口
- 讀取 `qualify.md` 逐人歸因：篩選引擎為何排除？→ 找過嚴規則或缺漏的加分條件（N）／關鍵字
- 讀取 `.agent/skills/hr-talent-screener/references/iteration_log.md`（歷史批次）與 `references/screening_rules.md`（現行規則）
- **跨批次統計歸類**：樣本已 20+ 筆，須做統計（如「誤選 60% 為製造端設備工程師包裝成廠務」），**只對統計顯著模式改規則**，避免過度擬合單一案例

### 步驟 2：更新規則文件
更新 `.agent/skills/hr-talent-screener/references/screening_rules.md`（default）或 `role_overlays/<role>.md`（overlay）：
- 新增/修正 M/N/E/D 條件
- 補充新發現的關鍵字
- 沉澱新的經驗法則
- 更新版本紀錄

### 步驟 3：同步更新程式碼
更新 `.agent/skills/hr-talent-screener/scripts/screen_candidates.py`：
- 同步新增的關鍵字到對應的 Python 常數列表
- 同步新增的 N/E/D 條件到評分邏輯
- 確認無重複計分問題

### 步驟 4：追加疊代日誌
追加 `.agent/skills/hr-talent-screener/references/iteration_log.md`：
- 記錄本輪來源統計（`unqualify.md`／`qualify.md` 各累積筆數）、統計歸類、規則洞察、使用者回饋
- 只做 Append，不刪除歷史

### 步驟 5：追加歷史選人紀錄
將本輪確認的選人資料追加至 `.agent/skills/hr-talent-screener/references/historical_selections.csv`，加上 `batch` 欄位與 `角色` 欄位標記（角色為 default 或 space-manager；歷史條目中的 mep-design 視同 default）。

### 步驟 6：落差分析 + 回報
向使用者摘要報告並產出落差分析：
- 本輪分析的 `unqualify.md`／`qualify.md` 樣本數與統計歸類
- 新增/修正了哪些規則/關鍵字、修正了哪些問題
- 落差分析問題選項（Q1: A/B/C，C=誤判不調整）供使用者確認
- 建議下一步動作（通常是：重跑 `/filter` 驗證，或等下一批 ANALYSIS.md）

> 完成後**不清空** `unqualify.md`／`qualify.md`（由使用者人為處理），Agent 嚴禁自動清除或歸檔。

---

## 步驟 7：品質稽核迴圈（規則落地後強制執行，v11.10 升級）

> 目的：確保本輪 improve **沒有以人名作為封殺依據**（違反 CLAUDE.md 4.11 / v8.0），避免候選人更新履歷/職能提升後仍被姓名比對誤漏。由 Sonnet 記錄、Opus 稽核，迴圈至無問題。

1. **紀錄（Sonnet）**：spawn `improve-recorder`（固定 Sonnet、單次執行）。它會**清空前次紀錄**並整檔覆寫 `references/improve_record.md`，記下本輪步驟軌跡、決策點、規則變更與修正理由、受影響候選人（含命中依據）、去識別化自述、回歸結果。spawn prompt 須提供：批次標記、role、日期、Q&A 決策、落地摘要、回歸結果、（重跑時）重錄輪次與上輪問題節點。
2. **稽核（Opus）**：spawn `improve-verifier`（固定 Opus）。它稽核 (A) **去識別化**（程式碼無姓名級控制流）與 (B) **投機辨識**（跑「姓名匿名化黃金測試」：把診斷測試檔姓名全匿名後重跑，判決集合須與匿名前完全一致）。spawn prompt 須提供診斷測試檔路徑（scratchpad 內已 pipeline_clean 的 `diag_unqual.md`）與 role。
3. **迴圈**：
   - **PASS** → 進入步驟 8。
   - **FAIL** → 依 verifier 回傳的「問題節點」：讀 `improve_record.md` 找出問題步驟 → 把姓名捷徑改為可泛化特徵（改 `screen_candidates.py`／規則）→ 重跑 `regression_check.py` → **再 spawn `improve-recorder` 清空重錄** → **再 spawn `improve-verifier` 複驗** → 直到 PASS。
   - ⛔ 未取得 PASS，不得進入步驟 8。

## 步驟 8：文件對齊（Fable5 指揮 Opus，全流程收尾）

> 品質稽核 PASS 後，統一校對文件生態與本輪規則變更一致（CLAUDE.md 守則 #4 文件生態維護）。

- spawn 一支 **Fable 5** agent 擔任「對齊指揮」：稽核 `CLAUDE.md`、`README.md`、`.agent/skills/**/*.py`、`.agent/skills/**/*.md`、overlay、command 是否與本輪 v-版本規則一致，產出「不一致清單 + 對齊計畫」。
- 依該計畫 spawn 一支 **Opus** agent 執行實際文件修正（Fable5 規劃、Opus 落地）。
- 對齊完成後回報使用者：改了哪些文件、剩餘待決項。
