# 專案執行守則 (HRMD 專案 GEMINI.md)

## 角色指定與任務邊界

- **預設身分角色**: 專案自動化執行器 (Project Automaton Executor)
- **執行核心原則**:
  - 文件即為法律，不存在自由心證。
  - 任務邊界絕對清晰，沒有被授權與規範的處理動作皆視為越權。

---

## 專案總覽

本專案為「104 履歷自動化解析與人才篩選系統」，用於協助 HR 從 104 人力銀行的大量候選人中，快速篩選出符合機電/廠務/工程職缺的面試人選。

### 業務流程（必須理解的上下游關係）

```
┌─────────────────────────────────────────────────────────────────┐
│  104 人力銀行                                                    │
│                                                                  │
│  HR 在 104 系統上以條件搜尋，得到數百位候選人的「摘要清單」        │
│  （姓名、年齡、學歷、希望職稱、工作經驗摘要）                     │
│  → 這份清單被擷取下來，就是 ANALYSIS.md                          │
│                                                                  │
│  HR 從清單中挑出有興趣的人，逐一下載他們的「完整 PDF 履歷」       │
│  → 這些 PDF 就是專案根目錄下的 *.pdf 檔案                        │
└─────────────────────────────────────────────────────────────────┘
```

**因此，正確的作業順序是：**

```
ANALYSIS.md（上游：大池子，數百人摘要）
    │
    ▼
Step 1: /filter — 篩選：從大池子中挑出值得深入看的人
    │
    ▼
使用者確認名單（漏選/誤選回饋）
    │
    ▼
Step 2: /improve — 精煉：疊代學習 + 落差分析 + 問題確認
    │
    ▼
HR 根據最終名單，到 104 下載那些人的 PDF 完整履歷
    │
    ▼
Step 3: /merge — 合併：把 PDF 轉成結構化 CSV（HR_Data_Summary.csv）
    │
    ▼
Step 4: /review — 結案：基於 CSV 全面審閱、落差確認、精煉規則
                        → CSV 新增「審閱結果建議」+「審閱排除理由簡述」欄位
                        → PDF/MD 依結果分流至 excluded/ downgraded/ reserve/
```

> **關鍵認知：ANALYSIS.md 是上游（粗篩來源），PDF 是下游（精選結果）。**
> Agent 絕不可搞反這個順序。

---

## 兩大技能

### 技能一：hr-talent-screener（人才篩選）— 對應 `/filter`
- **輸入**：`ANALYSIS.md`（104 系統擷取的大量候選人摘要清單）
- **處理**：三階段清洗（雜訊移除 → 代碼去重 → 學歷分類排序）→ M/N/E 規則評分
- **產出**：候選人名單 + 各人命中理由摘要
- **SKILL 文件**：`.agent/skills/hr-talent-screener/SKILL.md`
- **腳本**：
  - `scripts/pipeline_clean.py` — 三階段清洗
  - `scripts/screen_candidates.py` — 評分篩選引擎
  - `scripts/pick_candidates_util.py` — 輔助工具

### 技能二：hr-resume-parser（履歷解析）— 對應 `/merge`
- **輸入**：HR 從 104 下載的個別候選人 PDF 履歷（`*.pdf`）
- **處理**：PDF → Markdown → 8 大欄位擷取 + 防幻覺驗證
- **產出**：`HR_Data_Summary.csv`（utf-8-sig 編碼，初始 9 欄；經 /review 後擴充為 11 欄）
- **CSV 欄位順序**：序號, 姓名, 年紀, 語文能力, 學歷, 近期工作, 近期工作內容, **審閱結果建議**, 總年資, 前二次任職公司, **審閱排除理由簡述**
- **SKILL 文件**：`.agent/skills/hr-resume-parser/SKILL.md`
- **腳本**：
  - `scripts/convert_pdfs.py` — PDF 轉 Markdown
  - `scripts/extract_hr_data.py` — Markdown 擷取欄位，產出 CSV

### 疊代學習 — 對應 `/improve`
- **輸入**：`HR_Data_Summary.csv`（已確認的選人結果）或使用者的漏選/誤選回饋
- **處理**：比對選人特徵 vs 現行規則 → 找出缺口 → 更新規則與程式碼
- **更新目標**：
  - `references/screening_rules.md`（規則）+ `screen_candidates.py`（程式碼）
  - `references/iteration_log.md`（日誌追加）+ `references/historical_selections.csv`（歷史資料追加）

### 結案審閱 — 對應 `/review`
- **輸入**：`HR_Data_Summary.csv`（/merge 產出的完整履歷結構化資料）
- **處理**：地毯式逐人掃描 → 識別不適任/降級/儲備 → 落差分析 → 使用者確認
- **產出**：
  - CSV 新增「審閱結果建議」欄（總年資之前）+ 「審閱排除理由簡述」欄（末欄）
  - 排除候選人 PDF/MD 搬移至 `excluded/`
  - 降級候選人 PDF/MD 搬移至 `downgraded/`
  - 碩士儲備候選人 PDF/MD 搬移至 `reserve/`
  - 正式候選人 PDF/MD 留在專案根目錄

---

## 參考文件

| 文件 | 位置 | 用途 |
|------|------|------|
| screening_rules.md | hr-talent-screener/references/ | 跨批次永久有效的純規則手冊（M/N/E 條件 + 關鍵字 + 經驗法則） |
| iteration_log.md | hr-talent-screener/references/ | 疊代日誌（歷史累積，只追加不刪除） |
| historical_selections.csv | hr-talent-screener/references/ | 歷史選人紀錄（跨批次累積） |
| clear_RULE.md | hr-talent-screener/references/ | 三階段清洗規則定義 |
| 人才候選計畫.md | 專案根目錄 | 基於首批 56 位選人反推的企業畫像與規則起源 |

---

## 篩選規則體系簡述

篩選引擎依據三層規則對每位候選人評分：

- **必要條件 (M1-M3)**：職稱含機電/廠務/監造等、有 EPC/營造/半導體經歷、3年以上年資。至少命中一項才納入候選池。
- **加分條件 (N1-N17)**：學歷對口、知名企業、管理職、多系統覆蓋、品管、能源工程、鋼構、高科技建廠核心(N17)等。累計加分。
- **排除條件 (E1-E8)**：保全/門市/餐飲、非工程職稱、年資不足、純土建、製程製造、低階維修、環安衛、絕對封殺(軟工/展場)。命中任一項即排除。
- **動態調整 (D1-D5)**：傳統重電降階、年資防呆、廠務維運防呆、製造端降階、採購內業防呆。依條件動態扣分。

完整規則定義請參閱 `.agent/skills/hr-talent-screener/references/screening_rules.md`。

### 關鍵經驗法則
- **能力 > 學歷**：非本科但有 5 年以上機電/廠務實戰經驗可入選
- **年齡不設上限**：20~70 歲皆有歷史入選記錄
- **年資甜蜜區**：6~20 年為主力（佔 68%），但低年資（名校+半導體）與高年資（管理/專家級）也有機會
- **營造工地管理**：國中學歷但機電主任 10 年+ 仍可入選
- **品管/採購/能源**：非純技術職也在需求範圍內

---

## 核心規範：SKILL 執行絕對紀律 (Anti-Hallucination & Execution Sandbox)

當在本專案目錄內執行被部署於 `.agent/skills/` 的專長能力，Agent 必須絕對遵循以下強制規範：

### 1. 嚴禁擅自發明工具腳本 (Anti-Improvisation)
- 所有資料轉換、解析及清洗作業，僅可調用 `SKILL.md` 內明示規定的已驗證腳本資源。
- **絕對禁止**在遇到錯誤或效率瓶頸時，擅自憑空建立、撰寫或使用未經官方定案的任何指令與 Python 腳本（如自行創設 `convert_all.py` 或 PowerShell 批次迴圈）。

### 2. 阻斷錯誤蔓延與越權修復 (Halt on Error)
- 當透過命令列呼叫的腳本或工具（包含 `markitdown` 轉檔工具、自訂的 Python 直譯器等）出現任何 `Traceback` 崩潰、編碼錯誤、檔案存取權限或其他未預期之異常狀態時，Agent 必須**立即且無條件中斷所有後續處理流程**。
- **嚴禁**自行臆測錯誤解法、擅自修改腳本並嘗試強制重跑；必須直接將最後的錯誤輸出紀錄原始地呈報給使用者，直到使用者給予新的明確指令。

### 3. 強制限縮環境路徑 (Strict Environment Restrictions)
- **Python 路徑**：`c:\Users\01102088\Desktop\python-3.14.2-embed-amd64\python.exe`
- **禁止**在背景呼叫 Windows 系統全域的預設解析器。若無法找到指定的綠色環境工具路徑，同樣觸發上述的 Halt on Error 原則中止任務。

### 4. 文件生態維護 (Document Ecosystem Integrity)
- 每次疊代後，必須同步更新 `screening_rules.md`（規則）與追加 `iteration_log.md`（日誌）。
- `HR_Data_Summary.csv` 永遠只保留當批次最新版（覆蓋）。歷史數據僅存放於 `historical_selections.csv`。
- 專案根目錄保持乾淨，不得產生臨時檔案。
- `/review` 結案後，CSV 須新增「審閱結果建議」與「審閱排除理由簡述」兩欄，並將排除/降級/儲備候選人的 PDF/MD 搬移至對應子資料夾（`excluded/` `downgraded/` `reserve/`），根目錄僅保留正式候選人檔案。

### 5. 唯一腳本原則 (Single Source of Scripts)
- 只能使用各技能 `scripts/` 目錄內的官方腳本。
- 嚴禁在專案目錄下另建任何臨時腳本。
- 若需要修改腳本邏輯，必須修改官方腳本本身並向使用者說明變更內容。
