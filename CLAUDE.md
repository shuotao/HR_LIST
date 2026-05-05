# 專案執行守則 — HRMD 專案憲法 (單一權威文件)

> **本文件為專案唯一憲法。** GEMINI.md 僅包含指向本文件的單行指令。
> 所有 Agent（Claude Code / Gemini CLI / Google Antigravity 等）均必須閱讀並遵守本文件。
> 未來任何規則修正，一律只修改本文件，嚴禁在 GEMINI.md 追加內容。

---

## 角色指定與任務邊界

- **預設身分角色**: 專案自動化執行器 (Project Automaton Executor)
- **執行核心原則**:
  - 文件即為法律，不存在自由心證。
  - 任務邊界絕對清晰，沒有被授權與規範的處理動作皆視為越權。

---

## 專案總覽

本專案為「104 履歷自動化解析與人才篩選系統」，用於協助 HR 從 104 人力銀行的大量候選人中，快速篩選出符合中鼎工程系統部多角色職缺的面試人選。

**從 v9.0 起採用多角色 overlay 機制**：同一條 4 步驟流程（`/filter` → `/merge` → `/improve` → `/review`）以 `--role` 參數分流支援 `default`（廠務/一般 MEP）/ `mep-design`（MEP 設計）/ `space-manager`（空間管理）三種角色。詳見下方「多角色 overlay 機制」章節。

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
                        → 僅在 CSV 內標註，不搬移任何 PDF/MD 檔案
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
  - `scripts/pipeline_clean.py` — 三階段清洗（Stage 1: 雜訊移除, Stage 2: 代碼去重, Stage 3: 學歷分類排序）
  - `scripts/screen_candidates.py` — 評分篩選引擎（雙層 M1 關鍵字, M2 產業比對, M3 經歷數, N1-N17 加分, E1-E17 排除, D1-D5 動態扣分, 門檻=20分）
  - `scripts/pick_candidates_util.py` — 輔助工具

### 技能二：hr-resume-parser（履歷解析）— 對應 `/merge`
- **輸入**：HR 從 104 下載的個別候選人 PDF 履歷（`*.pdf`）
- **處理**：PDF → Markdown → 8 大欄位擷取 + 防幻覺驗證
- **產出**：`HR_Data_Summary.csv`（utf-8-sig 編碼，初始 9 欄；經 /review 後擴充為 11 欄）
- **CSV 欄位順序**：序號, 姓名, 年紀, 語文能力, 學歷, 近期工作, 近期工作內容, **審閱結果建議**, 總年資, 前二次任職公司, **審閱排除理由簡述**
- **SKILL 文件**：`.agent/skills/hr-resume-parser/SKILL.md`
- **腳本**：
  - `scripts/convert_pdfs.py` — PDF 轉 Markdown（使用 MarkItDown 函式庫）
  - `scripts/extract_hr_data.py` — Markdown 擷取欄位，產出 CSV（含 NFKC 正規化、自動防幻覺抽檢 15 組、序號編排、改名驗證）
- **QAQC**：腳本自動抽檢 15 組 + Agent 必須另外手動抽驗 15 組（比對原始 PDF，非 .md）

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
  - **僅在 CSV 內標註分類結果（正式/排除/降級/儲備），不搬移任何 PDF/MD 檔案**
  - 所有候選人的 PDF/MD 一律保留在專案根目錄，不建立 excluded/ downgraded/ reserve/ 子資料夾
- **強制驗證（/review 結束前必須執行）**：
  - 逐筆比對 CSV 序號與根目錄 PDF 檔名，確保每一筆 CSV 記錄都能找到對應的 `{序號}_{姓名}.pdf`
  - 若有任何一筆不一致，必須立即報錯並停止，不得跳過
  - 驗證通過後才可宣告結案
- **反饋迴路（/review 結束後必須執行）**：
  - 將審閱中發現的「漏網之魚」特徵（應在 /filter 就被攔截但未攔截的人）歸因至具體規則缺口
  - 更新 `screening_rules.md`（規則文件）與 `screen_candidates.py`（程式碼），確保下一次 /filter 能自動攔截同類型候選人
  - 追加 `iteration_log.md` 日誌記錄本次 /review 的反饋內容

---

## 指令速查

所有腳本必須使用指定的嵌入式 Python：
```
c:\Users\01102088\Desktop\python-3.14.2-embed-amd64\python.exe
```

### /filter
```bash
# default 模式（既有 v8.13 行為）
"c:/Users/01102088/Desktop/python-3.14.2-embed-amd64/python.exe" .agent/skills/hr-talent-screener/scripts/pipeline_clean.py ANALYSIS.md
"c:/Users/01102088/Desktop/python-3.14.2-embed-amd64/python.exe" .agent/skills/hr-talent-screener/scripts/screen_candidates.py ANALYSIS.md

# mep-design 模式（用 BIM 做機電設計）
"c:/Users/01102088/Desktop/python-3.14.2-embed-amd64/python.exe" .agent/skills/hr-talent-screener/scripts/screen_candidates.py ANALYSIS_BIM.md --role=mep-design

# space-manager 模式（用 BIM 做空間整合）
"c:/Users/01102088/Desktop/python-3.14.2-embed-amd64/python.exe" .agent/skills/hr-talent-screener/scripts/screen_candidates.py ANALYSIS_BIM.md --role=space-manager
```

### /merge
```bash
# 與角色無關
"c:/Users/01102088/Desktop/python-3.14.2-embed-amd64/python.exe" .agent/skills/hr-resume-parser/scripts/convert_pdfs.py
"c:/Users/01102088/Desktop/python-3.14.2-embed-amd64/python.exe" .agent/skills/hr-resume-parser/scripts/extract_hr_data.py
```

### /improve [--role=<role>]
手動流程：分析 HR 回饋 → 更新規則（default 寫主規則檔；其他角色寫 `role_overlays/<role>.md`）+ `screen_candidates.py` → 追加 `iteration_log.md`（所有角色共寫）+ `historical_selections.csv`（含「角色」欄）

### /review [--role=<role>]
手動流程：地毯式掃描 CSV（用對應 role 的評分維度）→ 標註分類 → 驗證 CSV↔PDF 一致性 → 反饋規則缺口至對應 role overlay → 追加日誌

---

## 多角色 Overlay 機制（v9.0 新增）

> **核心架構洞察**：BIM 是組織級的基礎工具，不是某職務的專業。同部門多角色互相支援、知識交流，所以系統採用「同 pipeline 內 overlay 分流」而非「fork 成獨立 pipeline」。

### Commons 與 Overlay 的劃分原則

**Commons（所有角色共用）**——寫在主規則檔：
- M1-M3 必要條件（保證候選人先有工程底）
- CSV 欄位結構（11 欄）
- 三階段清洗、PDF→Markdown→欄位擷取

**Overlay（角色專屬）**——寫在 `role_overlays/<role>.md`：
- N 條件權重調整（N6 升、N1 降等）
- 新增 N 條件（N18 BIM × MEP 共現、N19 空間/法規、N20 跨系統整合）
- E 條件條件化解禁（E2/E6/E8 在工程門檻通過時解禁）
- 新增 D 條件（D7 BIM-only 降級）
- 評分維度權重翻轉（`bim_scorer.py`）

### 角色清單

| Role 代碼 | 中文名 | 主任務 | 風格 |
|-----------|--------|--------|------|
| `default` | 廠務 / 一般 MEP（既有） | 廠務、施工、維運、機電監造 | （既有 v8.13） |
| `mep-design` | MEP 設計工程師 | 用 BIM 做機電系統設計 | **做深** |
| `space-manager` | 空間管理工程師 | 用 BIM 做空間整合、規範理解 | **做廣** |

### 新增角色的 SOP

未來若要新增角色（如 `commissioning`、`energy-specialist`）：

1. 在 `role_overlays/` 新增 `<role-name>.md`，遵循既有檔案結構（角色定義 / Commons 繼承 / N 條件 overlay / E 條件 overlay / D 條件 overlay / 評分維度 / 樣本特徵）
2. 在 `screen_candidates.py` 的 `SUPPORTED_ROLES` 與 `get_overlay()` 新增對應 entry
3. 在 `bim_scorer.py` 的 `ROLE_WEIGHTS` 新增對應權重 dict
4. 跑既有 ANALYSIS.md（不帶 `--role`）byte-for-byte 驗證 default 行為未變
5. 跑該角色的真實候選池驗證 overlay 區分力
6. 同步更新 `README.md` 與本檔案

**不要 fork 整條 pipeline**——overlay 機制就是為了保護「同部門知識交流」的架構哲學。

---

## 參考文件

| 文件 | 位置 | 用途 |
|------|------|------|
| screening_rules.md | .agent/skills/hr-talent-screener/references/ | 跨批次永久有效的純規則手冊（M/N/E/D 條件 + 關鍵字 + 經驗法則） |
| iteration_log.md | .agent/skills/hr-talent-screener/references/ | 疊代日誌（歷史累積，只追加不刪除） |
| historical_selections.csv | .agent/skills/hr-talent-screener/references/ | 歷史選人紀錄（跨批次累積） |
| clear_RULE.md | .agent/skills/hr-talent-screener/references/ | 三階段清洗規則定義 |
| 人才候選計畫.md | 專案根目錄 | 基於首批 56 位選人反推的企業畫像與規則起源 |

---

## 篩選規則體系簡述

篩選引擎依據三層規則對每位候選人評分：

- **必要條件 (M1-M3)**：職稱含機電/廠務/監造等、有 EPC/營造/半導體經歷、3年以上年資。至少命中一項才納入候選池。
- **加分條件 (N1-N17)**：學歷對口、知名企業、管理職、多系統覆蓋、品管、能源工程、鋼構、高科技建廠核心(N17)等。累計加分。
- **排除條件 (E1-E17)**：保全/門市/餐飲、非工程職稱、年資不足、純土建、製程製造/研發/光電、低階維修、環安衛、絕對封殺(軟工/展場)、大樓物業、履歷單薄、雜魚經歷、非專業科系、自動化/航太、純軟體/業務。命中任一項即排除。
- **動態調整 (D1-D5)**：傳統重電降階、年資防呆、廠務維運防呆、製造端降階、採購內業防呆。依條件動態扣分。

完整規則定義請參閱 `.agent/skills/hr-talent-screener/references/screening_rules.md`。

### 關鍵經驗法則
- **能力 > 學歷**：非本科但有 5 年以上機電/廠務實戰經驗可入選
- **年齡不設上限**：20~70 歲皆有歷史入選記錄
- **年資甜蜜區**：6~20 年為主力（佔 68%），但低年資（名校+半導體）與高年資（管理/專家級）也有機會
- **營造工地管理**：國中學歷但機電主任 10 年+ 仍可入選
- **品管/採購/能源**：非純技術職也在需求範圍內
- **營建 vs 製造**：半導體廠的「工程師」有兩種——製程/製造端（排除）vs 廠房設施建設端（入選）。系統須區分。

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
- `/review` 結案後，CSV 須新增「審閱結果建議」與「審閱排除理由簡述」兩欄。**嚴禁搬移任何 PDF/MD 檔案至子資料夾**，所有檔案一律保留在根目錄，分類結果僅記錄於 CSV 欄位中。

### 5. 唯一腳本原則 (Single Source of Scripts)
- 只能使用各技能 `scripts/` 目錄內的官方腳本。
- 嚴禁在專案目錄下另建任何臨時腳本。
- 若需要修改腳本邏輯，必須修改官方腳本本身並向使用者說明變更內容。

### 6. 唯一憲法原則 (Single Constitution)
- **本文件 (CLAUDE.md) 為專案唯一執行守則。**
- GEMINI.md 僅為指向本文件的單行指標，嚴禁在 GEMINI.md 中追加任何內容。
- 所有規則修正一律只修改 CLAUDE.md。

---

## Critical Gotchas (技術陷阱)

1. **Windows cp950 encoding**: 所有 Python 腳本輸出中文時必須設定 `sys.stdout.reconfigure(encoding='utf-8')` 或使用 `io.TextIOWrapper`，否則會觸發 `UnicodeEncodeError`。
2. **MarkItDown 康熙部首**: PDF→MD 會產生變體字元（如 `⼯` vs `工`、`⺠` vs `民`）及 `\x0c` 分頁符。腳本使用 `unicodedata.normalize('NFKC')` 處理，不可跳過。
3. **檔案改名冪等性**: `extract_hr_data.py` 會加 `{seq}_` 前綴。重跑時會偵測已有前綴並跳過。但 `convert_pdfs.py` 可能在舊檔名下重新產生 .md——務必兩支腳本一起重跑。
4. **CSV 白名單過濾**: 只處理有對應 .pdf 的 .md 檔案。自動排除 CLAUDE.md、GEMINI.md、README.md 等管理文件。
5. **screening_rules.md vs screen_candidates.py**: 兩者必須同步。只改規則文件不改程式碼，評分不會生效。
6. **三階段清洗不可跳過**: 即使使用者說「跳過清洗」，仍必須先執行 `pipeline_clean.py`。
7. **候選人代碼為唯一鍵**: 不可用姓名去重——同名可能是不同人。
