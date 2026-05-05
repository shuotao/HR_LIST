# 多角色 Overlay 機制（給 Agent 讀）

## 為什麼有 overlay 機制？

HRMD 專案不只服務一個職缺角色。中鼎工程系統部包含多種互相支援的角色：

- **default**：廠務 / 一般 MEP（既有 v8.13 規則）
- **mep-design**：MEP 設計（用 BIM 做深，單系統設計品質）
- **space-manager**：空間管理（用 BIM 做廣，跨系統整合與規範理解）

> **核心架構洞察（江碩濤原話）**：
> 「不管是哪一個專業，我們都是同樣部門的人，執行的任務是高科技廠房的專案，是互相支援外，知識本身就是交流與對齊的。BIM 技術會逐漸被我們的組織變成 MCP 的基礎使用工具。」

這就是為什麼採用 **同系統內 overlay 分流**，而不是 fork 成獨立 pipeline。

---

## Overlay 與 Commons 的劃分原則

### Commons（共用，所有角色一致）

寫在 `screening_rules.md` 主規則檔；任何角色都會套用：

- **M1-M3 必要條件**：所有角色共用「先有工程底」的門檻
- **CSV 欄位結構**：序號 / 姓名 / 年紀 / 語文能力 / 學歷 / ...
- **三階段清洗**（pipeline_clean.py）：與角色無關
- **PDF→Markdown→欄位擷取**：與角色無關

### Overlay（角色專屬）

寫在 `role_overlays/<role>.md`；只在指定 role 模式下啟用：

- **N 條件權重調整**：例如 N6 從 ★★☆ 升為 ★★★
- **新增 N 條件**：N18 BIM × MEP 共現、N19 空間/法規、N20 跨系統界面
- **E 條件解禁**：mep-design / space-manager 模式下，E2/E6/E8 條件化解禁
- **新增 D 條件**：D7 BIM-only 降級
- **評分維度權重翻轉**（`bim_scorer.py`）：工程深度 25→35、BIM 經驗 25→15

---

## Overlay 檔案規範

每個角色一個 markdown 檔案，路徑為 `role_overlays/<role-name>.md`。

**檔名規範**：role 名稱使用 lowercase、連字號分隔（kebab-case）：
- ✅ `mep-design.md` / `space-manager.md` / `default.md`
- ❌ `MEP_Design.md` / `space manager.md`

**檔案結構**（每個 overlay 必備章節）：

1. **角色定義**：這個角色在組織中做什麼、用 BIM 做什麼、風格（深 vs. 廣）
2. **Commons 繼承確認**：M1-M3 共用、CSV 結構共用 → 文字確認，不修改
3. **N 條件 overlay**：列出此角色的 N 條件權重表（與 default 對比）
4. **E 條件 overlay**：列出此角色解禁了哪些 E 條件、解禁的觸發條件
5. **D 條件 overlay**：新增的 D 條件（如 D7 BIM-only 降級）
6. **評分維度權重**（給 `/review` 用）：100 分制 5+ 維度權重表
7. **正面/反面樣本特徵**：給後續疊代參考的特徵描述

---

## 載入機制（Python 端）

`screen_candidates.py` 透過 `--role <role-name>` 參數選擇 overlay：

```bash
# default 模式（不帶參數，行為與 v8.13 完全一致）
python screen_candidates.py ANALYSIS.md

# mep-design 模式
python screen_candidates.py ANALYSIS_BIM.md --role=mep-design

# space-manager 模式
python screen_candidates.py ANALYSIS_BIM.md --role=space-manager
```

當 `--role` 為空或 `default` 時，腳本走原邏輯（保護既有 24 批疊代成果）。
當 `--role` 有值時，從本目錄載入對應 overlay 並套用。

`bim_scorer.py` 同理，透過 `--role` 切換評分維度權重。

---

## 新增角色的步驟

未來若要新增角色（如 `commissioning`、`energy-specialist`）：

1. 在本目錄新增 `<role-name>.md`，遵循上述章節結構
2. 在 `screen_candidates.py` 的 `ROLE_OVERLAYS` dict 新增對應 entry
3. 在 `bim_scorer.py` 的 `ROLE_WEIGHTS` dict 新增對應權重
4. 跑既有 ANALYSIS.md（不帶 `--role`）驗證 default 行為未變
5. 跑該角色的真實候選池驗證 overlay 區分力
6. 同步更新 `README.md` 和 `CLAUDE.md`

**不要 fork 整條 pipeline**——overlay 機制就是為了保護「同部門知識交流」的架構哲學。
