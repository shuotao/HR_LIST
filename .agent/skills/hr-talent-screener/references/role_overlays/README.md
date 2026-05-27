# 雙角色 Overlay 機制（v9.2 修正回原始 2 角色架構）

## 為什麼有 overlay 機制？

HRMD 專案服務中鼎工程系統部的兩種互相支援的角色：

- **`default` = MEP 工程師**：廠務 + MEP 設計合一，做廣 + 做深
- **`space-manager`**：空間管理（跨系統整合與規範理解，做廣為主）

> **架構紀錄**：本專案歷史上始終只有 2 個角色。v9.0~v9.1 過渡期錯誤拆分為 3 類（多出 `mep-design`），v9.2 已修正合併。`mep-design` 保留為 deprecated alias 自動 fallback 至 `default`，僅為向後相容。

> **核心架構洞察（江碩濤原話）**：
> 「不管是哪一個專業，我們都是同樣部門的人，執行的任務是高科技廠房的專案，是互相支援外，知識本身就是交流與對齊的。BIM 技術會逐漸被我們的組織變成基礎使用工具。」

這就是為什麼採用 **同系統內 overlay 分流**，而不是 fork 成獨立 pipeline；也是為什麼 default 不該再被拆成「廠務」vs「MEP 設計」兩個獨立物種。

---

## Overlay 與 Commons 的劃分原則

### Commons（兩角色共用）

寫在 `screening_rules.md` 主規則檔；任何角色都會套用：

- **M1-M3 必要條件**：保證候選人先有工程底
- **E19 致命防呆、E20a 零經歷、E25 在學中無台灣公司、D6b 短期跳槽防呆**：v9.2 起全 role 通用
- **CSV 欄位結構**：序號 / 姓名 / 年紀 / Email / 語文 / 學歷 / ...（10 欄初始，12 欄結案）
- **三階段清洗**（pipeline_clean.py）：與角色無關
- **PDF→Markdown→欄位擷取**：與角色無關

### Overlay（角色專屬）

寫在 `role_overlays/<role>.md`；只在指定 role 模式下啟用：

- **default (MEP)**：N6 BIM 獨立計分、N17 高科權重調整、N18 BIM × MEP 共現、E2/E6/E8 條件化解禁、E20b/c/d、E21、E22、E23、E24、E26-E29、D7、D12
- **space-manager**：上述 default 全包，再加 N19 空間/法規、N20 跨系統、N1 學歷略降、N17 進一步調權、D11 BIM 講師、D13 純土建結構、D14 傳統基層、Q1-Q4 VIP 解禁
- **評分維度權重翻轉**（`bim_scorer.py`）：工程深度 25→35、BIM 經驗 25→15、跨系統整合 + 法規理解（space-manager 專屬）

---

## Overlay 檔案規範

每個角色一個 markdown 檔案，路徑為 `role_overlays/<role-name>.md`。

**檔名規範**：role 名稱使用 lowercase、連字號分隔（kebab-case）：
- ✅ `default.md` / `space-manager.md`
- ❌ `Default.md` / `space manager.md`
- ⚠️ `mep-design.md` 保留為 deprecated alias 紀錄（v9.0~v9.1 過渡期遺留）

**檔案結構**（每個 overlay 必備章節）：

1. **角色定義**：這個角色在組織中做什麼、風格（深 vs. 廣）
2. **Commons 繼承確認**：M1-M3 共用、CSV 結構共用 → 文字確認，不修改
3. **N 條件 overlay**：列出此角色的 N 條件權重表（與基線對比）
4. **E 條件 overlay**：列出此角色解禁了哪些 E 條件、解禁的觸發條件
5. **D 條件 overlay**：新增的 D 條件
6. **評分維度權重**（給 `/review` 用）：100 分制權重表
7. **正面/反面樣本特徵**（去識別化典型誤選輪廓）

---

## 載入機制（Python 端）

`screen_candidates.py` 透過 `--role <role-name>` 參數選擇 overlay：

```bash
# default = MEP 角色（預設，廠務 + MEP 設計合一）
python screen_candidates.py ANALYSIS.md

# space-manager（空間管理工程師）
python screen_candidates.py ANALYSIS.md --role=space-manager

# （deprecated）mep-design 為 v9.0~v9.1 過渡名稱
# 執行時會印警告，自動 fallback 至 default
python screen_candidates.py ANALYSIS.md --role=mep-design
```

> **輸入檔統一為 `ANALYSIS.md`**：兩角色共用同一份來源資料，只切換 `--role` 參數做評分。

> **規格的單一權威來源**：overlay 的執行語意（哪些 N/E/D 條件被啟用、權重多少）以 `screen_candidates.py:get_overlay()` 為準。本目錄的 `<role>.md` 是給人讀的規格描述，必須與程式碼一致；若兩者衝突，以程式碼為準並回頭修文件。

`bim_scorer.py` 位於 `web/backend/`，是**體檢 web app（/web）的內部評分模組**，與 `/filter` CLI 流程獨立。其 `ROLE_WEIGHTS` 表只影響 web app 即時打分，不會影響 `/filter` 與 `/review`。

---

## 新增角色的步驟

未來若要新增角色（如 `commissioning`、`energy-specialist`）：

1. 在本目錄新增 `<role-name>.md`，遵循上述章節結構
2. 在 `screen_candidates.py` 的 `SUPPORTED_ROLES` 與 `get_overlay()` 新增對應 entry
3. 在 `bim_scorer.py` 的 `ROLE_WEIGHTS` dict 新增對應權重
4. 跑既有 ANALYSIS.md（不帶 `--role`）驗證 default 行為未變
5. 跑該角色的真實候選池驗證 overlay 區分力
6. 同步更新 `README.md` 和 `CLAUDE.md`

**不要 fork 整條 pipeline**——overlay 機制就是為了保護「同部門知識交流」的架構哲學。

**也不要重複 v9.0~v9.1 的錯誤**——不要把 MEP 拆成「廠務」與「設計」兩個獨立角色。
