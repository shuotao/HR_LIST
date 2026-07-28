# HRMD — 104 履歷自動化篩選與解析系統

專為人資主管與徵才團隊設計：從 104 人力銀行的大量候選人摘要中篩選出目標人選，再將其完整 PDF 履歷轉為結構化資料，並透過疊代學習持續提升篩選精準度。

**v9.2 起為雙角色架構**：本專案歷史上始終只有 2 個角色——v9.0~v9.1 過渡期錯誤拆分為 3 類，v9.2 修正合併。同一條 4 步驟流程可透過 `--role` 參數套用：
- `default` = **MEP**（廠務 + MEP 設計合一）
- `space-manager` = **空間管理**

各角色規格詳見 [`.agent/skills/hr-talent-screener/references/role_overlays/`](.agent/skills/hr-talent-screener/references/role_overlays/) 與下方「角色與哲學」章節。

---

## 業務流程

```
104 系統搜尋結果（數百人摘要）
        │
        ▼
   ANALYSIS.md（角色 overlay 透過 --role 切換）
        │
  Step 1: /filter [--role=<role>] ── 篩選：從大池子中挑出值得深入看的人
        │
        ▼
   使用者確認名單（漏選/誤選回饋）
        │
  Step 2: /improve [--role=<role>] ─ 精煉：疊代學習 + 落差分析 + 問題確認
        │
        ▼
   HR 到 104 下載入選者的 PDF 完整履歷
        │
  Step 3: /merge ─── 合併：PDF → Markdown → 結構化 CSV（角色無關）
        │
        ▼
   HR_Data_Summary.csv（完整履歷細節，10 欄）
        │
  Step 4: /review [--role=<role>] ── 結案：基於 CSV 全面審閱 + 反饋精煉規則
        │              → Agent 產出判決草稿與「差異清單」
        │              → 【閘門 A】你簽核差異筆（可說「代打」交 gatekeeper）
        │              → apply_review_decisions.py 寫入 CSV（12 欄）+ CSV↔PDF 強制驗證
        │              → 【閘門 B】你回答規則問題選項（可代打）→ 規則落地
        │              → regression_check.py 黃金集回歸守門（0 新翻盤才放行）
        │              → 【結案】永遠由你確認（不可代打）
        │              → gatekeeper agent 全程記錄你的決策 → gate_playbook.md
        ▼
   下一次 /filter 更精準（且 gatekeeper 越來越懂你的判準）
```

**支援的角色（`--role` 值）：**
- `default`（不帶 `--role`，預設）：**MEP** 工程師——廠務 / MEP 設計合一，做廣 + 做深
- `space-manager`：空間管理工程師（跨系統整合 + 法規理解；含 BIM 重型人才的細緻區分規則）
- ~~`mep-design`~~：v9.0~v9.1 過渡名稱，v9.2 起為 deprecated alias 自動 fallback 至 `default`

**口語速記對映**（完整表見 [CLAUDE.md 速記解碼表](CLAUDE.md#速記解碼表-shorthand-decoder--agent-必先查表)）：
- `step1/2/3/4` → `/filter` / `/improve` / `/merge` / `/review`
- `MEP / 廠務 / 設計 / 機電` → `--role=default`
- `空管 / 空間管理 / 跨系統 / 法規 / BIM`（作為候選人標籤時）→ `--role=space-manager`

---

## 角色與哲學（v9.2 修正回原始架構）

> **核心觀點**：「BIM 是外衣，工程深度才是骨幹。BIM 技術會逐漸被組織變成基礎使用工具。」

中鼎工程系統部的 MEP 工程師需求不是切成多個獨立物種。**廠務、機電設計、施工監造是同一個職務的不同面向**——同部門互相支援、知識交流：

| 角色 | 涵蓋工作 | 風格 |
|------|---------|------|
| **MEP（`default`）** | 廠務 + 機電系統設計 + 監造 + 施工管理 + BIM 整合 | **做廣 + 做深合一** |
| **Space Manager（`space-manager`）** | 跨系統空間整合、法規理解 | **做廣為主** |

**架構紀錄**：v9.0~v9.1 曾誤將 default（廠務/一般 MEP）與 mep-design（MEP 設計）拆為獨立角色，v9.2 已合併修正——這兩種工作風格在中鼎屬同一職務，分開反而違反「同部門知識交流」的架構哲學。

每個角色的詳細規格在 `.agent/skills/hr-talent-screener/references/role_overlays/<role>.md`（含 N/E/D 條件 overlay、評分維度權重、樣本特徵）。

---

## Step 1：篩選（/filter）

從 ANALYSIS.md（104 系統擷取的候選人摘要清單）中，依目標角色篩出符合條件的候選人。

**執行方式（依角色）：**

```bash
# 三階段清洗（與角色無關，所有模式共用）
python scripts/pipeline_clean.py ANALYSIS.md

# default = MEP 角色（廠務 + MEP 設計合一，預設）
python scripts/screen_candidates.py ANALYSIS.md

# space-manager（空間管理：跨系統整合 + 法規理解）
python scripts/screen_candidates.py ANALYSIS.md --role=space-manager

# （deprecated）mep-design v9.0~v9.1 過渡名稱，v9.2 後自動 fallback 至 default
# python scripts/screen_candidates.py ANALYSIS.md --role=mep-design
```

**角色 overlay 對 N/E/D 規則的影響**：
- `default` (MEP)：N6 BIM 獨立計分 +12、N18 BIM × MEP 共現、E22 零 MEP 信號排除、E23 純結構排除、E24 軌跡偏離、E26-E29 BIM/跳槽/繪圖防呆、D7 BIM-only 降級、D12 純建模降級
- `space-manager`：上述全包，再加 N19 空間/法規、N20 跨系統整合、D11 BIM 講師、D13 純土建結構、D14 傳統基層、Q1-Q4 VIP 解禁；學歷與管理權重微降

**三階段清洗：**
1. 移除 104 系統雜訊（版權宣告、選單、公告等）
2. 以代碼為唯一鍵去除重複候選人
3. 依學歷科系分三區塊重新排序（土木建築 / 機電相關 / 其他）

**篩選規則（現行 v11.9，完整定義見 screening_rules.md）：**

規則分 M/N/E/D 四層（N 至 N20、E 至 E34 含 E5c、D 至 D17；各層完整條件編號與定義以 `screening_rules.md` 與 `role_overlays/<role>.md` 為準）：

| 類型 | 說明 |
|------|------|
| 必要條件 (M 層) | 職稱含機電/廠務/監造等、有 EPC/營造/半導體經歷、3年以上年資 |
| 加分條件 (N 層) | 學歷對口、知名企業、管理職、多系統覆蓋、品管、能源工程、高科技建廠核心等 |
| 排除條件 (E 層) | 保全/門市/餐飲、非工程職稱、年資不足、純土建、製程製造、低階維修、環安衛、軟體/研發/光電、公寓物業、雜魚履歷、自動化/航太防呆等 |
| 動態調整 (D 層) | 傳統重電降階、年資防呆、廠務維運防呆、製造端降階、採購內業防呆 |

完整規則定義：`.agent/skills/hr-talent-screener/references/screening_rules.md`

---

## Step 2：精煉（/improve）— 「先蒐集，後分析」雙階段

不再每批 `/filter` 後立即改規則，而是先跨批次累積回饋，樣本足量後才統一分析落地。

**階段一 · 名單蒐集（每次 `/filter` 後可重複多輪，此階段不改規則）：**
- 排除/誤選回饋（引擎放行但判定不合格）→ 從 `ANALYSIS.md` 取完整區塊 append 至 `unqualify.md`
- 漏選/入選回饋（引擎排除但判定合格）→ 從 `ANALYSIS.md` 取完整區塊 append 至 `qualify.md`
- 兩檔以「代碼：」去重、append-only，**Agent 不清空**；下一次 `/filter` 會自動標 ★（unqualify）／☆（qualify）

**階段二 · 規則疊代（使用者說「Step 2」才進入）更新目標：**
- `screening_rules.md` — 新增/修正 M/N/E/D 條件與關鍵字
- `screen_candidates.py` — 同步程式碼中的關鍵字與評分邏輯
- `iteration_log.md` — 追加本輪日誌
- `historical_selections.csv` — 追加歷史選人紀錄

**品質稽核迴圈（v11.10 起，規則落地後強制）：**
規則一旦落地，必須跑一輪多 Agent 品質稽核，確保本輪 improve **沒有以人名作為封殺依據**（守「廢除人名黑白名單」原則）：
1. **紀錄（Sonnet）** — spawn `improve-recorder`，整檔覆寫 `references/improve_record.md`（latest-only，非 append）：步驟軌跡、決策點、規則變更理由、受影響候選人（含命中依據）、去識別化自述、回歸結果
2. **稽核（Opus）** — spawn `improve-verifier`，稽核 (a) 去識別化（程式碼無姓名級控制流）+ (b) 投機辨識（跑「姓名匿名化黃金測試」：診斷測試檔姓名全匿名後重跑，判決集合須與匿名前完全一致）
3. **迴圈** — FAIL → 把姓名捷徑改為可泛化特徵 → 重跑回歸 → 重錄 → 複驗，直到 PASS
4. **收尾** — PASS 後 Fable5 規劃跨檔文件對齊、Opus 落地文件修正（本 README 即由此迴圈維護）

**疊代原則：**
- 讀 `unqualify.md`（誤選）+ `qualify.md`（漏選）逐人歸因，做跨批次統計，只對統計顯著模式改規則
- 每個規則缺口必須歸因到具體條件；新增規則必須同時更新 `screening_rules.md`（文件）與 `screen_candidates.py`（程式碼）
- 修改後立即重跑 `/filter` 驗證效果；完成後不清空 `unqualify.md`／`qualify.md`

---

## Step 3：合併（/merge）

將 HR 從 104 下載的個別候選人 PDF 履歷，轉為結構化 CSV。

**執行方式：**
```bash
python scripts/convert_pdfs.py        # PDF → Markdown
python scripts/extract_hr_data.py     # Markdown → CSV（含自動防幻覺抽檢 + 序號編排）
```

**擷取欄位（10 欄）：** 序號、姓名、年紀、Email、語文能力、學歷、近期工作、近期工作內容、總年資、前二次任職公司

**範例結果（個資已模糊化）：**

| 序號 | 姓名 | 年紀 | 學歷 | 近期工作 | 總年資 | 前二次任職公司 |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| 001 | 候選人 A | 42 | 大學畢業 ○○學院 營建科技 | 儀控工程師 | 10 | ○○科技、××文教 |
| 002 | 候選人 B | 31 | 碩士畢業 ○○科大 冷凍空調 | 空調工程師 | 4 | ○○空調、××綠能 |

---

## Step 4：結案審閱（/review）

基於 CSV 全面審閱所有候選人，標註分類結果並反饋精煉規則。

**處理流程（2026-07-02 起含閘門機制）：**
1. 官方腳本 `generate_review_decisions.py` 重跑篩選引擎，產生逐人分數與判決草稿
2. Agent 逐人核對完整履歷，整理**差異清單**（腳本判決 vs Agent 建議不一致的人 + 分數在門檻 ±5 的邊界人，通常一批只有 5~8 筆）
3. **【閘門 A】你逐筆簽核差異清單**（一致筆自動放行，不打擾你；也可以說「代打」交給 gatekeeper）
4. 跑官方腳本將定稿判決寫入 CSV（新增「審閱結果建議」+「審閱排除理由簡述」兩欄，擴充為 12 欄）並自動執行 CSV↔PDF 強制驗證：
   ```
   python .agent/skills/hr-talent-screener/scripts/apply_review_decisions.py review_decisions.json
   ```
5. Agent 產出落差分析報告 + 問題選項（Q1: A/B/C 選擇題）
6. **【閘門 B】你回答問題選項**——你沒回答之前，Agent 嚴禁修改任何規則檔
7. 規則落地後必跑 `regression_check.py` 黃金集回歸（歷史已確認名單 0 新翻盤才放行）
8. **你確認結案**（結案永遠由你，不可代打）

> **僅在 CSV 內標註，不搬移任何 PDF/MD 檔案，不建立子資料夾**。
> gatekeeper agent 全程以觀察者身分記錄你在每個閘門的決策，累積成 `gate_playbook.md`——這是它未來代打的判準來源。

> **嚴禁**為 /review 自行撰寫一次性腳本以 hardcode dict 修改 CSV——所有審閱結果一律走 `review_decisions.json` → `apply_review_decisions.py` 此單一通道（CLAUDE.md 唯一腳本原則）。

**反饋迴路（關鍵！）：**
- 審閱中發現的「漏網之魚」（應在 /filter 階段就被排除但未被攔截的人），必須回頭分析其特徵
- 將新發現的排除特徵更新至 `screening_rules.md` 與 `screen_candidates.py`
- 確保下一次 `/filter` 能自動攔截同類型候選人，形成閉環精煉

---

## Step 4 閘門操作手冊（人類驗證者指南）

你在每批次 /review 只需要出場 **3 次**，總耗時約 5 分鐘：

| 互動點 | 你會看到什麼 | 你要回什麼 | 耗時 |
|--------|-------------|-----------|------|
| 閘門 A | 5~8 筆差異清單（每筆附姓名、分數、兩造判決、關鍵證據） | 逐筆「同意」或「改為X」 | 2~3 分 |
| 閘門 B | 2~4 題規則選擇題（Q1: A/B/C） | 每題選一個字母 | 1~2 分 |
| 結案 | 任務摘要（人數統計、規則變更、回歸結果） | 「結案」 | 30 秒 |

### 閘門 A 怎麼簽

Agent 呈現差異清單後，一行回覆全部即可，例如：

```
007 同意；012 改為降級觀察；023 同意；031 改為排除
```

只有差異筆需要你看——腳本判決與 Agent 判斷一致、且分數離門檻夠遠的人自動放行。

### 閘門 B 怎麼答

每題都是選擇題，C 永遠是「這是誤判，不需調整規則」：

```
Q1: A
Q2: C
```

你沒回答之前，Agent **嚴禁**修改 `screening_rules.md` / `role_overlays/` / `screen_candidates.py`——這是憲法強制條款。

### 想偷懶時：叫 gatekeeper 代打

在閘門 A 或閘門 B 出現時，直接說：

```
代打
```

（或「代打閘門」「幫我過閘門」，見 CLAUDE.md 速記解碼表）

gatekeeper 會讀取 `gate_playbook.md`（它從你歷次簽核中蒸餾出的決策模式）逐筆代判，每筆附歷史依據。**行為邊界（你在 2026-07-02 定的）：**

- **查無歷史模式的新型案例一律「掛起」回頭找你**，它不硬猜——所以前幾批它掛起的會比較多，你簽得越多它越能代
- 代打的判決在紀錄中標記 `agent-proxy`，與你親自的判決永遠可區分
- 代打的規則變更（閘門 B）必須通過回歸測試 0 新翻盤才落地，翻盤就停下等你
- **結案永遠不能代打**

### 回歸測試 FAIL 時會發生什麼

`regression_check.py` 會用歷史已確認的選人紀錄（`historical_selections.csv`，隨批次追加成長）重跑新規則。若有「歷史已確認正式候選的人被新規則排除」（或反向）即 FAIL 並列出翻盤名單：

- 翻盤是**刻意的**（新規則本來就要排除這類人）→ 你核准後 Agent 跑 `--accept` 更新基準
- 翻盤是**意外的** → Agent 退回修正規則，不落地

> 技術限制：歷史紀錄只有 CSV 摘要（無完整履歷），既存誤差已由 baseline 機制吸收，回歸測試只對「新翻盤」報警。

### 未來的「免確認模式」

等 gate_playbook.md 累積幾批、代打命中率穩定後，可以把預設切成：一致筆 + 有把握的差異筆全自動，只有回歸翻盤和新型案例才找你。到時只要跟 Agent 說一聲，把 CLAUDE.md 閘門條款改為 auto 模式即可。

---

## CSV 欄位定義（12 欄最終版）

| 欄位 | 說明 |
|------|------|
| 序號 | 三位數編號（001, 002...），依姓名筆劃排序 |
| 姓名 | 候選人全名 |
| 年紀 | 數字 |
| Email | 候選人聯絡信箱（從履歷正則擷取） |
| 語文能力 | 語言種類與程度 |
| 學歷 | 完整學歷字串 |
| 近期工作 | 公司名稱 + 職稱 |
| 近期工作內容 | 最近一份工作的完整敘述 |
| **審閱結果建議** | 正式候選 / 排除 / 降級觀察 / 碩士儲備（/review 後新增） |
| 總年資 | 數字 |
| 前二次任職公司 | 扣除最新一家後的近兩次經歷 |
| **審閱排除理由簡述** | 非正式候選人的排除/降級原因（/review 後新增） |

> **歷史選人 CSV（`historical_selections.csv`）多了一個 `角色` 欄**（v9.0 起），標記每筆記錄屬於哪個角色（default / space-manager；歷史條目中的 mep-design 視同 default）。

---

## 參考文件

| 文件 | 位置 | 用途 |
|------|------|------|
| 人才候選計畫.md | 專案根目錄 | 基於歷史選人反推的篩選規則與企業畫像 |
| unqualify.md | 專案根目錄 | 誤選累積名單（引擎放行但判定不合格；append-only，/improve 蒐集階段維護，比對標 ★） |
| qualify.md | 專案根目錄 | 漏選累積名單（引擎排除但判定合格；append-only，/improve 蒐集階段維護，比對標 ☆） |
| screening_rules.md | .agent/skills/hr-talent-screener/references/ | 跨批次永久有效的純規則手冊（M/N/E/D） |
| iteration_log.md | .agent/skills/hr-talent-screener/references/ | 疊代日誌（每批次追加，不刪除） |
| historical_selections.csv | .agent/skills/hr-talent-screener/references/ | 歷史選人紀錄（跨批次累積） |
| clear_RULE.md | .agent/skills/hr-talent-screener/references/ | 三階段清洗規則定義 |
| improve_record.md | .agent/skills/hr-talent-screener/references/ | /improve 品質稽核快照（latest-only 整檔覆寫，非 append；improve-recorder 產出、improve-verifier 稽核） |
| regression_baseline.json | .agent/skills/hr-talent-screener/references/ | 回歸測試已知誤差基準（僅 regression_check.py 讀寫，吸收 CSV 摘要 vs 完整履歷既存誤差） |
| gate_playbook.md | .agent/skills/hr-talent-screener/references/ | 閘門決策手冊（gatekeeper 自動蒸餾，代打判準來源） |
| gate_interactions.jsonl | .agent/skills/hr-talent-screener/references/ | 閘門互動流水帳（append-only，user/agent-proxy 判決皆入帳） |
| gatekeeper.md | .claude/agents/ | 閘門觀察/代理 subagent 定義（RECORD/PROXY 雙模式） |
| improve-recorder.md | .claude/agents/ | /improve 品質稽核·紀錄 subagent（固定 Sonnet；整檔覆寫 improve_record.md） |
| improve-verifier.md | .claude/agents/ | /improve 品質稽核·稽核 subagent（固定 Opus；去識別化 + 姓名匿名化黃金測試） |
| CLAUDE.md | 專案根目錄 | **專案唯一憲法**（Agent 執行守則，所有規則的單一權威來源） |
| GEMINI.md | 專案根目錄 | 單行指標，指向 CLAUDE.md（嚴禁追加內容） |

---

## 注意事項

- **個資保護**：本工具建議於企業內網環境使用。所有範例人名須模糊化處理。
- **編碼規範**：CSV 採 `utf-8-sig` 編碼，可直接以 Excel 開啟。
- **Python 環境**：使用專案指定的綠色版 `python-3.14.2-embed-amd64`，不依賴系統全域安裝。
- **檔案管理**：所有 PDF/MD 一律保留在根目錄，分類結果僅記錄於 CSV 欄位。
- **唯一腳本原則**：僅使用 `.agent/skills/*/scripts/` 內的官方腳本，嚴禁自建臨時腳本。
