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
        │              → Agent 產出 review_decisions.json → 跑 apply_review_decisions.py
        │              → CSV 新增「審閱結果建議」+「審閱排除理由簡述」（12 欄）
        │              → 僅在 CSV 內標註，不搬移任何 PDF/MD 檔案
        │              → 腳本自動逐筆驗證 CSV 序號 ↔ PDF 檔名一致性
        │              → 審閱發現的漏網之魚反饋回對應 role overlay
        ▼
   下一次 /filter 更精準
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

**篩選規則（v8.13）：**

| 類型 | 說明 |
|------|------|
| 必要條件 (M1-M3) | 職稱含機電/廠務/監造等、有 EPC/營造/半導體經歷、3年以上年資 |
| 加分條件 (N1-N17) | 學歷對口、知名企業、管理職、多系統覆蓋、品管、能源工程、高科技建廠核心等 |
| 排除條件 (E1-E17) | 保全/門市/餐飲、非工程職稱、年資不足、純土建、製程製造、低階維修、環安衛、軟體/研發/光電、公寓物業、雜魚履歷、自動化/航太防呆等 |
| 動態調整 (D1-D5) | 傳統重電降階、年資防呆、廠務維運防呆、製造端降階、採購內業防呆 |

完整規則定義：`.agent/skills/hr-talent-screener/references/screening_rules.md`

---

## Step 2：精煉（/improve）

使用者確認 `/filter` 結果後，針對漏選/誤選回饋進行落差分析，更新篩選規則與程式碼。

**更新目標：**
- `screening_rules.md` — 新增/修正 M/N/E/D 條件與關鍵字
- `screen_candidates.py` — 同步程式碼中的關鍵字與評分邏輯
- `iteration_log.md` — 追加本批次日誌
- `historical_selections.csv` — 追加歷史選人紀錄

**疊代原則：**
- 每位被排除的候選人必須歸因到具體的規則缺口
- 新增規則必須同時更新 `screening_rules.md`（文件）與 `screen_candidates.py`（程式碼）
- 修改後立即重跑 `/filter` 驗證排除效果

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

**處理流程：**
1. 地毯式逐人掃描 CSV 中每位候選人的完整履歷資訊
2. 依據建廠/廠務/機電相關程度，將每人標記為：**正式候選 / 排除 / 降級觀察 / 碩士儲備**
3. Agent 將判決整理為 `review_decisions.json`（格式：`{"role": "...", "decisions": {"001": {"result": "正式候選", "reason": ""}, ...}}`）
4. 跑官方腳本將判決寫入 CSV（新增「審閱結果建議」欄於總年資之前 + 「審閱排除理由簡述」欄於末欄，擴充為 12 欄）並執行強制驗證：
   ```
   python .agent/skills/hr-talent-screener/scripts/apply_review_decisions.py review_decisions.json
   ```
5. **僅在 CSV 內標註，不搬移任何 PDF/MD 檔案，不建立子資料夾**
6. **強制驗證**（由腳本自動執行）：逐筆比對 CSV 序號與根目錄 PDF 檔名 `{序號}_{姓名}.pdf`，全部一致才可結案

> **嚴禁**為 /review 自行撰寫一次性腳本以 hardcode dict 修改 CSV——所有審閱結果一律走 `review_decisions.json` → `apply_review_decisions.py` 此單一通道（CLAUDE.md 唯一腳本原則）。

**反饋迴路（關鍵！）：**
- 審閱中發現的「漏網之魚」（應在 /filter 階段就被排除但未被攔截的人），必須回頭分析其特徵
- 將新發現的排除特徵更新至 `screening_rules.md` 與 `screen_candidates.py`
- 確保下一次 `/filter` 能自動攔截同類型候選人，形成閉環精煉

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
| screening_rules.md | .agent/skills/hr-talent-screener/references/ | 跨批次永久有效的純規則手冊（M/N/E/D） |
| iteration_log.md | .agent/skills/hr-talent-screener/references/ | 疊代日誌（每批次追加，不刪除） |
| historical_selections.csv | .agent/skills/hr-talent-screener/references/ | 歷史選人紀錄（跨批次累積） |
| clear_RULE.md | .agent/skills/hr-talent-screener/references/ | 三階段清洗規則定義 |
| CLAUDE.md | 專案根目錄 | **專案唯一憲法**（Agent 執行守則，所有規則的單一權威來源） |
| GEMINI.md | 專案根目錄 | 單行指標，指向 CLAUDE.md（嚴禁追加內容） |

---

## 注意事項

- **個資保護**：本工具建議於企業內網環境使用。所有範例人名須模糊化處理。
- **編碼規範**：CSV 採 `utf-8-sig` 編碼，可直接以 Excel 開啟。
- **Python 環境**：使用專案指定的綠色版 `python-3.14.2-embed-amd64`，不依賴系統全域安裝。
- **檔案管理**：所有 PDF/MD 一律保留在根目錄，分類結果僅記錄於 CSV 欄位。
- **唯一腳本原則**：僅使用 `.agent/skills/*/scripts/` 內的官方腳本，嚴禁自建臨時腳本。
