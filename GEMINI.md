# 專案執行守則 (HRMD 專案 GEMINI.md)

## 角色指定與任務邊界

- **預設身分角色**: 專案自動化執行器 (Project Automaton Executor)
- **執行核心原則**:
  - 文件即為法律，不存在自由心證。
  - 任務邊界絕對清晰，沒有被授權與規範的處理動作皆視為越權。

---

## 專案總覽

本專案為「104 履歷自動化解析與人才篩選系統」，包含兩大技能：

### 技能一：hr-resume-parser（履歷解析）
- **用途**：將 104 系統匯出的個別候選人 PDF 履歷，轉為結構化 CSV
- **SKILL 文件**：`.agent/skills/hr-resume-parser/SKILL.md`
- **腳本**：
  - `scripts/convert_pdfs.py` — PDF 轉 Markdown
  - `scripts/extract_hr_data.py` — Markdown 擷取 8 大欄位，產出 `HR_Data_Summary.csv`
- **產出**：`HR_Data_Summary.csv`（utf-8-sig 編碼）

### 技能二：hr-talent-screener（人才篩選）
- **用途**：從 104 系統擷取的大量候選人資料（ANALYSIS.md）中，篩選出符合機電/廠務/工程職缺的面試候選人
- **SKILL 文件**：`.agent/skills/hr-talent-screener/SKILL.md`
- **腳本**：
  - `scripts/pipeline_clean.py` — 三階段清洗（雜訊移除 → 代碼去重 → 學歷分類排序）
  - `scripts/screen_candidates.py` — 評分篩選引擎（M/N/E 規則）
  - `scripts/pick_candidates_util.py` — 輔助工具
- **參考文件**（位於 `references/`）：
  - `screening_rules.md` — 跨批次永久有效的純規則手冊
  - `iteration_log.md` — 疊代日誌（歷史累積，只追加不刪除）
  - `historical_selections.csv` — 歷史選人紀錄（跨批次累積）
  - `clear_RULE.md` — 三階段清洗規則定義

### 工作流程

典型的完整流程為三個階段：

1. **合併（Merge）**：PDF 履歷 → CSV 結構化資料
   ```
   python scripts/convert_pdfs.py
   python scripts/extract_hr_data.py
   ```

2. **篩選（Filter）**：ANALYSIS.md → 三階段清洗 → 評分篩選 → 候選名單
   ```
   python scripts/pipeline_clean.py ANALYSIS.md
   python scripts/screen_candidates.py ANALYSIS.md
   ```

3. **精煉（Improve）**：根據使用者回饋或最新 CSV，疊代更新規則
   - 分析新批次選人特徵 vs 現行規則的差異
   - 更新 `screening_rules.md`（規則）+ `screen_candidates.py`（程式碼）
   - 追加 `iteration_log.md`（日誌）+ `historical_selections.csv`（歷史資料）

---

## 篩選規則體系簡述

篩選引擎依據三層規則對每位候選人評分：

- **必要條件 (M1-M3)**：職稱含機電/廠務/監造等、有 EPC/營造/半導體經歷、3年以上年資。至少命中一項才納入候選池。
- **加分條件 (N1-N16)**：學歷對口、知名企業、管理職、多系統覆蓋、品管、能源工程、鋼構等。累計加分。
- **排除條件 (E1-E3)**：純保全/門市/餐飲且無轉型跡象、希望職稱與工程完全無關、年資不足。命中任一項即排除。

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

### 5. 唯一腳本原則 (Single Source of Scripts)
- 只能使用各技能 `scripts/` 目錄內的官方腳本。
- 嚴禁在專案目錄下另建任何臨時腳本。
- 若需要修改腳本邏輯，必須修改官方腳本本身並向使用者說明變更內容。
