# HRMD — 104 履歷自動化篩選與解析系統

專為人資主管與徵才團隊設計：從 104 人力銀行的大量候選人摘要中篩選出目標人選，再將其完整 PDF 履歷轉為結構化資料，並透過疊代學習持續提升篩選精準度。

---

## 業務流程

```
104 系統搜尋結果（數百人摘要）
        │
        ▼
   ANALYSIS.md
        │
  Step 1: /filter ── 篩選：從大池子中挑出值得深入看的人
        │
        ▼
   HR 到 104 下載那些人的 PDF 完整履歷
        │
  Step 2: /merge ─── 合併：PDF → Markdown → 結構化 CSV
        │
        ▼
   HR_Data_Summary.csv
        │
  Step 3: /improve ─ 精煉：用最終選人結果回頭精煉篩選規則
        │
        ▼
   下一次 /filter 更精準
```

---

## Step 1：篩選（/filter）

從 ANALYSIS.md（104 系統擷取的候選人摘要清單）中，篩出符合機電/廠務/工程職缺的候選人。

**執行方式：**
```bash
python scripts/pipeline_clean.py ANALYSIS.md       # 三階段清洗
python scripts/screen_candidates.py ANALYSIS.md     # 評分篩選
```

**三階段清洗：**
1. 移除 104 系統雜訊（版權宣告、選單、公告等）
2. 以代碼為唯一鍵去除重複候選人
3. 依學歷科系分三區塊重新排序（土木建築 / 機電相關 / 其他）

**篩選規則：**

| 類型 | 說明 |
|------|------|
| 必要條件 (M1-M3) | 職稱含機電/廠務/監造等、有 EPC/營造/半導體經歷、3年以上年資 |
| 加分條件 (N1-N16) | 學歷對口、知名企業、管理職、多系統覆蓋、品管、能源工程等 |
| 排除條件 (E1-E3) | 純保全/門市/餐飲且無轉型跡象 |

---

## Step 2：合併（/merge）

將 HR 從 104 下載的個別候選人 PDF 履歷，轉為結構化 CSV。

**執行方式：**
```bash
python scripts/convert_pdfs.py        # PDF → Markdown
python scripts/extract_hr_data.py     # Markdown → CSV
```

**擷取欄位：** 姓名、年紀、語文能力、學歷、近期工作、工作內容、總年資、前二次任職公司

**範例結果（個資已模糊化）：**

| 姓名 | 年紀 | 語文能力 | 學歷 | 近期工作 | 總年資 | 前二次任職公司 |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| 候選人 A | 42 | 英文(略懂)、台語 | 大學畢業 ○○學院 營建科技 | 儀控工程師 | 10 | ○○科技、××文教 |
| 候選人 B | 31 | 英文(中等)、台語 | 碩士畢業 ○○科大 冷凍空調 | 空調工程師 | 4 | ○○空調、××綠能 |
| 候選人 C | 46 | 英文(略懂)、台語 | 國中畢業 | 機電主任 | 15 | ○○事業、××建設 |

---

## Step 3：精煉（/improve）

用 `HR_Data_Summary.csv`（已確認的最終選人結果）或使用者的漏選/誤選回饋，回頭精煉篩選規則，讓下一次 `/filter` 更精準。

**更新目標：**
- `screening_rules.md` — 新增/修正 M/N/E 條件與關鍵字
- `screen_candidates.py` — 同步程式碼中的關鍵字與評分邏輯
- `iteration_log.md` — 追加本批次日誌
- `historical_selections.csv` — 追加歷史選人紀錄

---

## 參考文件

| 文件 | 位置 | 用途 |
|------|------|------|
| 人才候選計畫.md | 專案根目錄 | 基於歷史選人反推的篩選規則與企業畫像 |
| screening_rules.md | hr-talent-screener/references/ | 跨批次永久有效的純規則手冊 |
| iteration_log.md | hr-talent-screener/references/ | 疊代日誌（每批次追加，不刪除） |
| clear_RULE.md | hr-talent-screener/references/ | 三階段清洗規則定義 |
| GEMINI.md | 專案根目錄 | Agent 執行守則 |

---

## 注意事項

- **個資保護**：本工具建議於企業內網環境使用。所有範例人名須模糊化處理。
- **編碼規範**：CSV 採 `utf-8-sig` 編碼，可直接以 Excel 開啟。
- **Python 環境**：使用專案指定的綠色版 Python，不依賴系統全域安裝。
