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

**v9.2 起為雙角色架構**：同一條 4 步驟流程（`/filter` → `/merge` → `/improve` → `/review`）以 `--role` 參數分流支援 **兩種**角色：
- `default` = **MEP**（廠務 / 一般 MEP / MEP 設計合一；BIM 為基礎工具，做廣與做深皆涵蓋）
- `space-manager` = **空間管理工程師**（跨系統整合、法規理解）

> **重要架構紀錄**：本專案歷史上從未分為 3 個角色。v9.0~v9.1 過渡期短暫拆分為 `default`/`mep-design`/`space-manager` 三類為錯誤分流，v9.2 已合併修正回原始 2 角色概念。`mep-design` 保留為 deprecated alias 自動 fallback 至 `default`，僅為向後相容。

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
- **產出**：候選人名單 + 各人命中理由摘要（命中 `unqualify.md` 者標 `★`＝應排除卻仍入選；命中 `qualify.md` 者標 `☆`＝應入選，並於結尾另列「仍被引擎漏掉」清單）
- **SKILL 文件**：`.agent/skills/hr-talent-screener/SKILL.md`
- **腳本**：
  - `scripts/pipeline_clean.py` — 三階段清洗（Stage 1: 雜訊移除, Stage 2: 代碼去重, Stage 3: 學歷分類排序）
  - `scripts/screen_candidates.py` — 評分篩選引擎（雙層 M1 關鍵字, M2 產業比對, M3 經歷數, N/E/D 多層加分/排除/動態扣分（完整見 screening_rules.md）, 門檻=20分；自帶 unqualify.md/qualify.md 比對標記 ★/☆ 並列出漏網清單）
  - `scripts/generate_review_decisions.py` — /review 自動產生 `review_decisions.json`（讀 CSV + 對應 .md 重跑 score_candidate，支援 `--role`）
  - `scripts/apply_review_decisions.py` — /review 把判決寫入 CSV 並驗證 CSV↔PDF 一致性
  - `scripts/regression_check.py` — 黃金集回歸測試（規則變更守門員；重跑 historical_selections.csv，偵測新翻盤，baseline 機制吸收 CSV 摘要既存誤差）
  - `scripts/append_review_to_golden.py` — /review 結案後把 12 欄 `HR_Data_Summary.csv` 追加至回歸黃金集 `historical_selections.csv`（欄位映射 drop 序號/Email + prepend batch/角色；冪等守門避免重複 batch；append-only；支援 `--dry-run`）
  - `scripts/pick_candidates_util.py` — 輔助工具

### 技能二：hr-resume-parser（履歷解析）— 對應 `/merge`
- **輸入**：HR 從 104 下載的個別候選人 PDF 履歷（`*.pdf`）
- **處理**：PDF → Markdown → 8 大欄位擷取 + 防幻覺驗證
- **產出**：`HR_Data_Summary.csv`（utf-8-sig 編碼，初始 10 欄；經 /review 後擴充為 12 欄）
- **CSV 欄位順序**：序號, 姓名, 年紀, Email, 語文能力, 學歷, 近期工作, 近期工作內容, **審閱結果建議**, 總年資, 前二次任職公司, **審閱排除理由簡述**
- **SKILL 文件**：`.agent/skills/hr-resume-parser/SKILL.md`
- **腳本**：
  - `scripts/convert_pdfs.py` — PDF 轉 Markdown（使用 MarkItDown 函式庫）
  - `scripts/extract_hr_data.py` — Markdown 擷取欄位，產出 CSV（含 NFKC 正規化、自動防幻覺抽檢 15 組、序號編排、改名驗證）
  - `scripts/verify_extraction.py` — 防幻覺手動抽驗（直接讀 PDF 原始檔比對 CSV，預設 15 組，支援指定姓名清單）
- **QAQC**：腳本自動抽檢 15 組 + 必須執行 `verify_extraction.py` 另抽 15 組比對原始 PDF（非 .md）

### 疊代學習 — 對應 `/improve`（「先蒐集，後分析」雙階段模型）

> **核心哲學（v11.5, 2026-07-08）**：捨棄「每批 `/filter` 後立即改規則」的舊模式（單批樣本量小、口語記憶依賴、易過度擬合單批特例、無法跨批次累積）。改為**先跨批次累積回饋樣本至 `unqualify.md`／`qualify.md`，樣本足量後才統一分析、統計歸類、落地規則**。

- **輸入（階段二分析素材）**：
  - `unqualify.md`（誤選累積：引擎放行但使用者判定不合格者，false positive）
  - `qualify.md`（漏選累積：引擎排除但使用者判定合格者，false negative）
  - 或既有 `HR_Data_Summary.csv`（已確認選人結果，輔助佐證）

- **階段一 · 名單蒐集（每次 `/filter` 後可重複多輪；此階段嚴禁改規則）**：
  - **嚴禁**改規則、改 `screen_candidates.py`、進入 `/improve` 疊代分析——這階段只蒐集、不分析。
  - 收到**排除/誤選**回饋（如「排除 林XX」「unqualify 王XX」）→ 從 `ANALYSIS.md` 取該人完整資料區塊，以 **append（不取代）** 寫入 `unqualify.md`。
  - 收到**漏選/入選**回饋（如「qualify 張XX」「加回 陳XX」）→ 從 `ANALYSIS.md` 取該人完整資料區塊，以 **append（不取代）** 寫入 `qualify.md`。
  - 兩檔以「代碼：」為唯一鍵去重，避免重複 append 同一人。**兩檔皆 append-only；Agent 嚴禁自動清空或歸檔**（僅使用者可人為處理）。
  - 下一次 `/filter` 會自動比對此兩檔：命中 `unqualify.md` 標 ★、命中 `qualify.md` 標 ☆ 並列漏網清單，供蒐集進度追蹤。

- **階段二 · 規則疊代（使用者說「Step 2」／`/improve` 才進入）**：
  - 讀 `unqualify.md` 逐人歸因：引擎為何放行？→ 找排除規則（E/D）的系統性缺口。
  - 讀 `qualify.md` 逐人歸因：引擎為何排除？→ 找過嚴規則或缺漏的加分條件（N）／關鍵字。
  - **跨批次統計歸類**：樣本已達 20+ 筆，須做統計（如「誤選中 60% 是製造端設備工程師包裝成廠務」），**只對統計顯著的模式改規則**，避免過度擬合單一案例。
  - 落差分析 + 問題選項（Q1: A/B/C）→ 使用者確認後才落地規則。**完成後不清空** `unqualify.md`／`qualify.md`。

- **更新目標**：
  - `references/screening_rules.md`（規則）+ `screen_candidates.py`（程式碼，兩者必須同步）
  - `references/iteration_log.md`（日誌追加）+ `references/historical_selections.csv`（歷史資料追加）

- **品質稽核迴圈（v11.10）**：規則落地後強制跑「improve-recorder（Sonnet）紀錄 → improve-verifier（Opus）去識別化 + 投機辨識稽核」同步迴圈，PASS 才收尾（Fable5 規劃 → Opus 落地文件對齊）。編排細節見「多 Agent 編排規範」章節。

### 結案審閱 — 對應 `/review`
- **輸入**：`HR_Data_Summary.csv`（/merge 產出的完整履歷結構化資料）
- **處理**：地毯式逐人掃描 → 差異清單 → 【閘門 A】使用者簽核 → 落差分析 → 【閘門 B】問題選項確認（兩閘門皆可由使用者說「代打」交 gatekeeper PROXY 代理，詳見「閘門機制」章節）
- **產出**：
  - CSV 新增「審閱結果建議」欄（總年資之前）+ 「審閱排除理由簡述」欄（末欄）
  - **僅在 CSV 內標註分類結果（正式候選 / 排除 / 降級觀察 / 碩士儲備），不搬移任何 PDF/MD 檔案**
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

## 速記解碼表 (Shorthand Decoder) — Agent 必先查表

> **目的**：使用者常用口語/簡寫下指令（如「step1 BIM」「跑空管」），本表把這些 shorthand 釘定為唯一對映，避免 Agent 推導歧義。
> **規則**：未列入此表的 shorthand，Agent **一律停下來問**，使用者答覆後 **Agent 必須立即把新對映補進此表並 commit**。

### Step → Command 對映

| 速記 | 正式指令 | 中文名 |
|------|----------|--------|
| Step 1 / step1 / S1 | `/filter` | 篩選 |
| Step 2 / step2 / S2 | `/improve` | 精煉（疊代學習） |
| Step 3 / step3 / S3 | `/merge` | 合併（PDF → CSV） |
| Step 4 / step4 / S4 | `/review` | 結案審閱 |

### Role 速記 → `--role` 對映

| Shorthand | `--role` 值 | 說明 |
|-----------|-------------|------|
| MEP / 廠務 / 設計 / 機電 / default / 不帶字 | `default` | 預設角色 |
| 空管 / 空間管理 / 跨系統 / 法規 / **BIM** | `space-manager` | 含 BIM 重型人才的細緻區分規則 |
| ~~mep-design~~ | 自動 fallback 至 `default` | deprecated alias |

### 「BIM」歧義消解（重要）

CLAUDE.md 中「BIM 是組織級基礎工具」是**業務哲學**——說明 BIM 不該被視為某職務的專業，兩個 role 都會用到。

但**作為候選人標籤的 shorthand**，「BIM」一律指向 `space-manager`。理由：只有 `space-manager` overlay 有區分 BIM 純度的規則（D11 BIM 講師降級、D12 純建模降級、Q1 BIM Developer 解禁、Q4 BIM VIP 解禁、N6 BIM 獨立計分）。default 把 BIM 當基礎工具但不細分 BIM 純度。

> 速記範例：「step1 BIM」 → `python screen_candidates.py ANALYSIS.md --role=space-manager`

### 閘門速記（2026-07-02 新增）

| Shorthand | 對映 |
|-----------|------|
| 代打 / 代打閘門 / 幫我過閘門 | spawn `gatekeeper`（MODE: PROXY）代打當前閘門（A 或 B）；查無歷史模式的筆掛起回頭找使用者 |
| （使用者親自簽核/答題後） | 主 Agent 必須 spawn `gatekeeper`（MODE: RECORD）記錄互動 |

### /improve 名單蒐集速記（2026-07-08 新增）

> 對映 `/improve` 的「先蒐集，後分析」雙階段（詳見「兩大技能 → 疊代學習」章節）。蒐集階段**只 append、不改規則**。

| Shorthand | 對映動作 |
|-----------|----------|
| 排除 XXX / unqualify XXX / 誤選 XXX | 從 `ANALYSIS.md` 取 XXX 完整區塊 **append** 至 `unqualify.md`（蒐集階段，**嚴禁改規則**） |
| 加回 XXX / qualify XXX / 漏選 XXX / 入選 XXX | 從 `ANALYSIS.md` 取 XXX 完整區塊 **append** 至 `qualify.md`（蒐集階段，**嚴禁改規則**） |
| Step 2 / step2 / `/improve`（在累積數輪之後） | 結束蒐集、進入規則疊代階段（讀 unqualify.md + qualify.md 統計分析後才落地規則） |

---

## 指令速查

所有腳本必須使用指定的嵌入式 Python：
```
D:\green-tools\python-3.14.2-embed-amd64\python.exe
```

### /filter
```bash
# 三階段清洗（與角色無關，永遠先跑這個）
"D:/green-tools/python-3.14.2-embed-amd64/python.exe" .agent/skills/hr-talent-screener/scripts/pipeline_clean.py ANALYSIS.md

# default = MEP 角色（廠務 + MEP 設計合一，預設）
"D:/green-tools/python-3.14.2-embed-amd64/python.exe" .agent/skills/hr-talent-screener/scripts/screen_candidates.py ANALYSIS.md

# space-manager（空間管理工程師：跨系統整合 + 法規理解）
"D:/green-tools/python-3.14.2-embed-amd64/python.exe" .agent/skills/hr-talent-screener/scripts/screen_candidates.py ANALYSIS.md --role=space-manager

# （deprecated）mep-design 為 v9.0~v9.1 過渡名稱，v9.2 後自動 fallback 至 default
# "D:/green-tools/python-3.14.2-embed-amd64/python.exe" .agent/skills/hr-talent-screener/scripts/screen_candidates.py ANALYSIS.md --role=mep-design
```

> **輸入檔統一為 `ANALYSIS.md`**（單一來源原則）。HR 視該批次要找哪個角色，僅切換 `--role` 參數，不需要為每個角色另存一份 ANALYSIS 檔。

### /merge
```bash
# 與角色無關
"D:/green-tools/python-3.14.2-embed-amd64/python.exe" .agent/skills/hr-resume-parser/scripts/convert_pdfs.py
"D:/green-tools/python-3.14.2-embed-amd64/python.exe" .agent/skills/hr-resume-parser/scripts/extract_hr_data.py

# QAQC 手動抽驗（從 CSV 隨機抽 15 筆比對 PDF 原始檔）
"D:/green-tools/python-3.14.2-embed-amd64/python.exe" .agent/skills/hr-resume-parser/scripts/verify_extraction.py
```

### /improve [--role=<role>]
「先蒐集，後分析」雙階段（完整說明見「疊代學習」章節）：
- **階段一 · 名單蒐集**：收到回饋且仍在蒐集階段時，**嚴禁**改規則/改程式碼/進入疊代。排除/誤選 → append 至 `unqualify.md`；漏選/入選 → append 至 `qualify.md`（皆從 `ANALYSIS.md` 取完整資料區塊，以「代碼：」去重，append-only 不取代、Agent 不清空）。
- **階段二 · 規則疊代**（使用者說「Step 2」才進入）：讀 `unqualify.md`（誤選）+ `qualify.md`（漏選）逐人歸因 → 跨批次統計歸類（僅對統計顯著模式改規則）→ 更新規則（default 寫主規則檔 + `role_overlays/default.md`；space-manager 寫 `role_overlays/space-manager.md`）+ `screen_candidates.py` → 落差分析 Q&A → 追加 `iteration_log.md` + `historical_selections.csv`（含「角色」欄）
- **品質稽核迴圈（v11.10 升級，規則落地後強制）**：規則落地後必跑「Sonnet 紀錄 → Opus 稽核」迴圈，確保 improve **未以人名作為封殺依據**（守 4.11 / v8.0）。① spawn `improve-recorder`（Sonnet、單次、**清空前次**整檔覆寫 `references/improve_record.md`）記錄步驟/決策/修正理由/受影響人命中依據；② spawn `improve-verifier`（Opus）稽核**去識別化**（無姓名級控制流）+ **投機辨識**（姓名匿名化黃金測試：測試檔姓名全匿名後重跑，判決集合須與匿名前完全一致）；③ FAIL → 改姓名捷徑為可泛化特徵 + 重跑回歸 + 重錄 + 複驗，PASS 才收尾。收尾 spawn **Fable5**（規劃文件對齊）→ **Opus**（落地）校對 CLAUDE/README/.py/.md 一致性。詳見 `.claude/commands/improve.md` 步驟 7–8 與 `SKILL.md` 4.5–4.6。

### /review [--role=<role>]
半自動流程（**所有步驟必須使用官方腳本，嚴禁自寫一次性 .py**）。**2026-07-02 起含閘門機制**（詳見「閘門機制與 gatekeeper Agent」章節）：

```bash
# Step 1：自動產生 review_decisions.json 草稿（讀 CSV + 對應 .md 重跑 score_candidate）
"D:/green-tools/python-3.14.2-embed-amd64/python.exe" .agent/skills/hr-talent-screener/scripts/generate_review_decisions.py --role=default

# Step 2：Agent 逐人核對完整履歷、微調草稿（合法 result 限 正式候選 / 排除 / 降級觀察 / 碩士儲備），
#         並產出「差異清單」：(a) 腳本判決 vs Agent 建議不一致筆；(b) 分數在門檻 ±5 的邊界筆

# Step 3：【閘門 A】使用者逐筆簽核差異清單（回覆「同意」或「改為X」）
#         使用者明示「代打」→ spawn gatekeeper（MODE: PROXY）；掛起筆回頭找使用者
#         簽核完成後 → spawn gatekeeper（MODE: RECORD）記錄互動
#         ⛔ 未過閘門 A，嚴禁執行 Step 4

# Step 4：寫入 CSV 並執行 CSV↔PDF 強制驗證
"D:/green-tools/python-3.14.2-embed-amd64/python.exe" .agent/skills/hr-talent-screener/scripts/apply_review_decisions.py review_decisions.json

# Step 5：落差分析報告 + 問題選項（Q1: A/B/C 格式）

# Step 6：【閘門 B】使用者回答問題選項（或「代打」→ gatekeeper PROXY）→ RECORD
#         ⛔ 未取得回答前，嚴禁修改 screening_rules.md / role_overlays / screen_candidates.py

# Step 7：規則落地（screening_rules.md / overlay + screen_candidates.py 同步 + iteration_log.md 追加）
#         → 之後必跑黃金集回歸測試：
"D:/green-tools/python-3.14.2-embed-amd64/python.exe" .agent/skills/hr-talent-screener/scripts/regression_check.py
#         FAIL（新翻盤）：向使用者呈報翻盤名單；刻意翻盤經使用者核准後跑 --accept 更新 baseline
#         代打模式下 FAIL 一律停下等使用者裁決

# Step 8：結案確認（永遠由使用者，不可代打）→ gatekeeper RECORD 記錄 closure

# Step 9（結案後·可選）：把本批已審閱定案的 12 欄 CSV 追加至回歸黃金集，讓下一輪回歸守門保護本批人類判決
#         （先 --dry-run 預覽；冪等守門會擋重複 batch）
"D:/green-tools/python-3.14.2-embed-amd64/python.exe" .agent/skills/hr-talent-screener/scripts/append_review_to_golden.py --role=default --batch=<角色>-<YYYY-MM-DD>-review --dry-run
"D:/green-tools/python-3.14.2-embed-amd64/python.exe" .agent/skills/hr-talent-screener/scripts/append_review_to_golden.py --role=default --batch=<角色>-<YYYY-MM-DD>-review
#         追加後可跑 regression_check.py --accept 一次，把本批新增列的 CSV 摘要既存誤差吸收進 baseline（需使用者核准）
```

`review_decisions.json` 格式：
```json
{"role": "default", "decisions": {"001": {"result": "正式候選", "reason": ""}, ...}}
```

> **嚴禁**為 /review 自行撰寫一次性腳本以 hardcode dict 修改 CSV，違反唯一腳本原則。所有審閱結果一律走 `generate_review_decisions.py` → `review_decisions.json` → `apply_review_decisions.py` 此單一通道。

---

## 閘門機制與 gatekeeper Agent（2026-07-02 上線）

> /review 的兩道人類簽核點 + 一個觀察/代理 agent + 一道機器守門（黃金集回歸）。
> 目的：讓「影響下一輪 /filter 的規則變更」永遠有人類（或有歷史依據的代理）把關。

### 閘門定義與強制條款

| 閘門 | 位置 | 使用者動作 | 強制條款 |
|------|------|-----------|----------|
| **閘門 A** | apply_review_decisions.py 之前 | 逐筆簽核「差異清單」（腳本判決 vs Agent 建議不一致筆 + 分數門檻 ±5 邊界筆），回覆「同意」或「改為X」 | 未過閘門 A，**嚴禁**執行 apply |
| **閘門 B** | 修改規則檔之前 | 回答落差分析問題選項（Q1: A/B/C，C=誤判不調整） | 未取得回答，**嚴禁**修改 screening_rules.md / role_overlays / screen_candidates.py |
| **回歸守門** | 規則落地之後 | （機器自動）`regression_check.py` 黃金集 0 新翻盤才算通過 | FAIL 時：翻盤若為刻意的規則效果，須使用者核准後 `--accept`；否則退回修正規則 |
| **結案** | 全部完成後 | 使用者確認結案 | **永遠由使用者，不可代打** |

### gatekeeper Agent（`.claude/agents/gatekeeper.md`）

雙模式，由每次 spawn prompt 第一行 `MODE:` 決定（**非持久狀態**——使用者親自答題它就是觀察者，叫它代打才是代理人，下次自動回到觀察者）：

- **MODE: RECORD（預設身分）**：使用者親自完成閘門 A / 閘門 B / 結案後，主 Agent **必須** spawn gatekeeper 記錄互動至 `gate_interactions.jsonl`，並蒸餾決策模式至 `gate_playbook.md`。
- **MODE: PROXY（代理）**：使用者明示「代打」時，gatekeeper 讀 playbook 依歷史模式代打判決（`decided_by=agent-proxy`，附 confidence 與歷史依據）。**查無類似模式的新型案例一律掛起待人裁，嚴禁硬猜**（使用者 2026-07-02 親定邊界）。代打的規則變更必須通過回歸守門才落地。

### 閘門資料檔

- `references/gate_interactions.jsonl` — 閘門互動流水帳（**append-only**，只追加不修改）
- `references/gate_playbook.md` — 決策模式手冊（gatekeeper 自動蒸餾；PROXY 代打的唯一判準來源）
- `references/regression_baseline.json` — 回歸測試已知誤差基準（僅由 regression_check.py 讀寫；CSV 摘要 vs 完整履歷的既存誤差由此吸收）

---

## 多 Agent 編排規範 (Multi-Agent Orchestration Spec)（v11.10 上線）

> **核心原則**：本專案凡 spawn sub-agent，**每支 agent 的模型（orchestrator model）必須於 spawn 時顯式指定**，嚴禁依賴 harness 的 default 模型繼承。default 繼承常造成兩種浪費／失準：①該用 Sonnet 的機械性工作誤吃 Opus（成本浪費）；②該用 Opus 的嚴謹稽核誤吃小模型（品質失準）。**模型選用＝成本與能力的刻意取捨，必須顯式、不可省略。**

### 目前唯一的「多 Agent + 同步驅動 LOOP」：/improve Step 2 品質稽核迴圈
- **全專案僅 `/improve`（Step 2）規則落地後的「品質稽核迴圈」屬於「多 agent 且同步驅動的迴圈」編排。** 其餘 agent 使用情境（如 /review 的 `gatekeeper`）皆為**單次、單 agent** 的 spawn，不構成迴圈。
- **同步驅動（前景序列相依）**：此迴圈所有 agent 一律 `run_in_background: false`——recorder 先產出紀錄 → verifier 依紀錄稽核 → 主 agent 依稽核結果決定是否迴圈。**嚴禁背景並行**（後手 agent 依賴前手輸出，並行會拿到空/舊資料）。

### 各 Agent 的顯式模型與職責（固定綁定，不吃 default）
| Agent | 固定模型（spawn 時顯式帶入） | 職責 | 為何綁這個模型 |
|-------|------------------------------|------|----------------|
| `improve-recorder` | **Sonnet**（`claude-sonnet-5`） | 記錄 improve 步驟/決策/修正理由；**latest-only 整檔覆寫** `references/improve_record.md`（清空前次，非 append） | 機械性彙整、成本敏感，Sonnet 足矣；用 Opus 是浪費 |
| `improve-verifier` | **Opus**（`claude-opus-4-8`） | 去識別化 + 投機辨識稽核（含**姓名匿名化黃金測試**：測試檔姓名全匿名後重跑，判決集合須與匿名前完全一致） | 需嚴謹推理與反投機判斷，須 Opus |
| 文件對齊·指揮 | **Fable 5**（`claude-fable-5`） | 稽核文件生態（CLAUDE/README/.py/.md/overlay/command）一致性、產出對齊計畫 | 統籌/規劃，Fable5 |
| 文件對齊·執行 | **Opus**（`claude-opus-4-8`） | 依 Fable5 計畫落地跨檔文件修正 | 跨檔精確編修，須 Opus |
| `gatekeeper`（/review） | 單次 spawn（MODE: RECORD/PROXY，見閘門章節） | 閘門互動記錄/代理 | 單次、非迴圈；模型依 spawn 情境於 prompt 顯式指定 |

### 編排鐵則
1. **顯式模型**：每次 spawn sub-agent 一律在 spawn 設定顯式帶模型參數（如 Agent 工具 `model` 或 workflow `agent(..,{model})`）；**禁止靠 default 繼承**。
2. **同步序列**：/improve 稽核迴圈為前景序列（recorder → verifier →（FAIL 時）主 agent 修正 + 重跑回歸 + 重錄 + 複驗），不背景並行。
3. **迴圈收斂**：verifier **FAIL** → 依問題節點把姓名捷徑改為可泛化特徵（改 `screen_candidates.py`／規則）+ 重跑 `regression_check.py` + 再 spawn recorder 清空重錄 + 再 spawn verifier 複驗，**直到 PASS 才進文件對齊**。
4. **範疇邊界**：目前**唯 /improve Step 2** 有此多 agent 同步迴圈；未來若新增其他多 agent 迴圈編排，**必須比照本規範顯式指定各 agent 模型、註明是否同步驅動，並更新本表**。

> 落地位置：agent 定義 `.claude/agents/improve-recorder.md`、`.claude/agents/improve-verifier.md`；流程接線見 `.claude/commands/improve.md` 步驟 7–8 與 `SKILL.md` 4.5–4.6。

---

## 雙角色 Overlay 機制（v9.2 修正回原始架構）

> **架構紀錄**：本專案歷史上始終只有 2 個角色，v9.0~v9.1 過渡期錯誤拆分為 3 類，v9.2 已修正合併。
>
> **核心架構洞察**：BIM 是組織級的基礎工具，不是某職務的專業。MEP 工程師需要做廣（廠務統合）也做深（系統設計），這在中鼎是同一個職務，所以 `default` 角色已涵蓋兩種工作風格。

### Commons 與 Overlay 的劃分原則

**Commons（兩角色共用）**——寫在主規則檔 `screening_rules.md`：
- M1-M3 必要條件（保證候選人先有工程底）
- E19 致命防呆 / E20a 零經歷防呆 / E25 在學中無台灣公司 / D6b 短期跳槽防呆
- CSV 欄位結構（10/12 欄含 Email）
- 三階段清洗、PDF→Markdown→欄位擷取

**Overlay（角色專屬）**——寫在 `role_overlays/<role>.md`：
- `default` (MEP)：N6 BIM 獨立計分、N18 BIM × MEP 共現、E22 零 MEP 信號、E23 純結構、E24 軌跡偏離、E26-E29 BIM/跳槽/繪圖防呆、D7 BIM-only、D12 純建模
- `space-manager`：上述 default 所有規則 + N19 空間/法規、N20 跨系統、D11 BIM 講師、D13 純土建結構、D14 傳統基層、Q1-Q4 VIP 解禁
- 評分維度權重翻轉（`bim_scorer.py`）

### 角色清單

| Role 代碼 | 中文名 | 主任務 | 風格 |
|-----------|--------|--------|------|
| `default` | **MEP** 工程師（廠務 / 機電設計合一） | 廠務、施工、維運、機電監造、設計圖整合 | **做廣 + 做深** |
| `space-manager` | 空間管理工程師 | 跨系統空間整合、法規理解 | **做廣為主** |
| ~~`mep-design`~~ | （deprecated alias） | v9.0~v9.1 暫用名，自動 fallback 至 `default` | — |

### 新增角色的 SOP

未來若要新增角色（如 `commissioning`、`energy-specialist`）：

1. 在 `role_overlays/` 新增 `<role-name>.md`，遵循既有檔案結構
2. 在 `screen_candidates.py` 的 `SUPPORTED_ROLES` 與 `get_overlay()` 新增對應 entry
3. 在 `bim_scorer.py` 的 `ROLE_WEIGHTS` 新增對應權重 dict
4. 跑既有 ANALYSIS.md（不帶 `--role`）驗證 default 行為未變
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
| gate_playbook.md | .agent/skills/hr-talent-screener/references/ | 閘門決策手冊（gatekeeper 自動蒸餾，PROXY 代打判準） |
| gate_interactions.jsonl | .agent/skills/hr-talent-screener/references/ | 閘門互動流水帳（append-only） |
| regression_baseline.json | .agent/skills/hr-talent-screener/references/ | 回歸測試已知誤差基準（僅 regression_check.py 讀寫） |
| 人才候選計畫.md | 專案根目錄 | 基於首批 56 位選人反推的企業畫像與規則起源 |
| unqualify.md | 專案根目錄 | 誤選累積名單（引擎放行但判定不合格；append-only，/improve 蒐集階段維護，Agent 不清空；`screen_candidates.py` 比對標 ★） |
| qualify.md | 專案根目錄 | 漏選累積名單（引擎排除但判定合格；append-only，/improve 蒐集階段維護，Agent 不清空；`screen_candidates.py` 比對標 ☆ 並列漏網清單） |
| improve_record.md | .agent/skills/hr-talent-screener/references/ | /improve 品質稽核快照（latest-only 整檔覆寫，非 append；由 improve-recorder 產出、improve-verifier 稽核；永久歷史在 iteration_log.md） |

---

## 篩選規則體系簡述

篩選引擎依據 M/N/E/D 四層規則對每位候選人評分（各層的完整條件編號與定義以 `screening_rules.md` 為準）：

- **必要條件 (M 層)**：職稱含機電/廠務/監造等、有 EPC/營造/半導體經歷、3年以上年資。至少命中一項才納入候選池。
- **加分條件 (N 層)**：學歷對口、知名企業、管理職、多系統覆蓋、品管、能源工程、鋼構、高科技建廠核心等。累計加分。
- **排除條件 (E 層)**：保全/門市/餐飲、非工程職稱、年資不足、純土建、製程製造/研發/光電、低階維修、環安衛、絕對封殺(軟工/展場)、大樓物業、履歷單薄、雜魚經歷、非專業科系、自動化/航太、純軟體/業務等。命中任一項即排除。
- **動態調整 (D 層)**：傳統重電降階、年資防呆、廠務維運防呆、製造端降階、採購內業防呆等。依條件動態扣分。

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
- **Python 路徑**：`D:\green-tools\python-3.14.2-embed-amd64\python.exe`
- **禁止**在背景呼叫 Windows 系統全域的預設解析器。若無法找到指定的綠色環境工具路徑，同樣觸發上述的 Halt on Error 原則中止任務。

### 4. 文件生態維護 (Document Ecosystem Integrity)
- 每次疊代後，必須同步更新 `screening_rules.md`（規則）與追加 `iteration_log.md`（日誌）。
- `HR_Data_Summary.csv` 永遠只保留當批次最新版（覆蓋）。歷史數據僅存放於 `historical_selections.csv`。
- 專案根目錄保持乾淨，不得產生臨時檔案。
- `/review` 結案後，CSV 須新增「審閱結果建議」與「審閱排除理由簡述」兩欄。**嚴禁搬移任何 PDF/MD 檔案至子資料夾**，所有檔案一律保留在根目錄，分類結果僅記錄於 CSV 欄位中。

### 5. 唯一腳本原則 (Single Source of Scripts)
- 只能使用各技能 `scripts/` 目錄內的官方腳本。
- 嚴禁在專案目錄下另建任何臨時腳本（包含 `scratch/`、根目錄裸 `.py`、`tmp_*.py` 等任何形式）。
- 若需要修改腳本邏輯，必須修改官方腳本本身並向使用者說明變更內容。
- **若發現規範要求 Agent 做某動作但缺對應官方工具（工具缺口）**：必須立即停下，向使用者報告缺口、提議升格為官方腳本，而非自行在 `scratch/` 寫一次性 .py 繞過。歷史上 30 個 scratch 檔即源於此問題，已於 2026-05-27 整治。

### 5a. 臨時檢視 / 除錯一律使用內建工具 (No Throwaway Scripts)
- **禁止場景**：所有「我想看一下 XX」「我想 grep YY」「我想抽驗 ZZ」的瞬間需求，**不得**寫 `.py` 檔案執行。
- **替代方案**：
  - 看檔案內容 → `Read` tool
  - 搜尋字串 / pattern → `Grep` tool
  - 跑一行 Python / git / 系統指令 → `Bash` tool 的 one-liner（如 `python -c "..."`、`git log -- path`）
  - 跑多步驟分析 → 同樣用 `Bash` 串 `&&`，**不落地成 `.py` 檔**
- **唯一例外**：若同一個檢視邏輯**未來會重複使用 3 次以上**，才應升格為官方腳本放入對應 skill 的 `scripts/` 目錄，並更新本文件「指令速查」段落。

### 5b. 工具缺口回報機制 (Tool Gap Escalation)
- 當執行 SOP 中發現「規範要 Agent 做某件事，但沒有對應官方腳本」時，Agent 必須：
  1. 中止任務（觸發 Halt on Error 原則）。
  2. 向使用者報告：缺口位置、為何需要工具、建議的升格路徑（新腳本檔名 + 放置位置 + 參數設計）。
  3. 取得使用者確認後，將腳本建立於正式 `scripts/` 目錄，並同步更新 CLAUDE.md 指令速查與本檔的工具清單。
- **嚴禁**先在 scratch/ 寫了再說。一次破例就會繁殖。

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
8. **名單蒐集階段禁改規則**: 收到 `/filter` 後的漏選/誤選回饋時，若仍在蒐集階段，只能 append 至 `qualify.md`／`unqualify.md`（皆 append-only，以「代碼：」去重，Agent 不得自動清空或歸檔），**嚴禁**同時改規則或 `screen_candidates.py`。規則變更一律等使用者說「Step 2」進入疊代階段、對統計顯著模式才統一處理，避免過度擬合單批特例。
