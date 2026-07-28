# /improve 決策紀錄（latest-only，每次 improve/重跑覆寫）

> 本檔為「最新一輪 /improve 的可稽核快照」，供 Opus 驗證迴圈（去識別化 + 投機辨識）使用。
> 非 append-only；永久歷史請見 iteration_log.md。

- 批次：default-2026-07-28（Batch #52）　角色：default　日期：2026-07-28　重錄輪次：1（首次記錄）

## 1. 步驟軌跡

1. **分析素材**：`unqualify.md` 累積 39 筆（誤選，false positive；較 Batch #50 的 26 筆新增 13 筆）；`qualify.md` 空檔，0 漏選，本輪無漏選可分析。
2. **診斷方法**：複製 `unqualify.md` 至 scratchpad `diag_unqual.md` → 官方 `pipeline_clean.py` → `screen_candidates.py --role=default`（未觸動 ANALYSIS.md 或任何 sacred 檔）。落地前現況：引擎放行 31／攔截 8（8 人已被 Batch #50/#51 的 v11.7/v11.8 規則攔下）。
3. **統計歸類**（31 位殘留誤選，5 群）：
   - B1 半導體/電子/傳產「設備工程師/製程/測試」製造端 — 7 人（23%）
   - B2 傳統/製造 電機·機械·水電·儀電 技工/維修/製圖 — 6 人（19%）
   - B3 業務/PM/專案/營運ERP + 文商社科灌水 — 3 人（10%）
   - B4 營造工地監工/工務主任/室內裝修（土建端） — 3 人（10%）
   - 其他（韌體/自動化/PLC、廠務維運、大樓機電、環安衛、採購、儲能SI 等單例/邊界型） — 12 人（39%）
4. **Q&A**：使用者逐項裁決 — B1→A（收緊 E5 但保護真廠務）、B2→A（新增技工/維修排除規則）、B3→C（樣本僅 10%，暫緩僅記 log）、B4→C（樣本僅 10%，暫緩僅記 log）。
5. **落地**：(B1) E5-Q1 收緊 + (B2) 新增 E5c（all-role），程式碼與 `screening_rules.md`/`role_overlays/default.md` 同步。
6. **回歸**：`regression_check.py` PASS，黃金集 343 筆，0 新翻盤（歷史入選葉洊語未被誤翻）。

## 2. 決策點

| 決策點 | 使用者選項 | 方向 |
|--------|-----------|------|
| B1（製造/設備端主軸，23%，最大群） | A/B/C | **A** — 收緊 E5，但保護真廠務（BUILD_PROOF 或廠務≥2段才解禁） |
| B2（傳統技工/維修，19%） | A/B/C | **A** — 新增降分/排除規則（E5c） |
| B3（業務/PM/文商，10%） | A/B/C | **C** — 暫不改規則，僅記 log（樣本量不足，E30/E17 豁免易誤傷真轉型者） |
| B4（營造/土建，10%） | A/B/C | **C** — 暫不改規則，僅記 log（樣本量不足，土建監造收緊易翻盤黃金集內合格工地機電主任） |

## 3. 規則變更與修正理由

| 規則 | 變更（程式碼層面） | 修正理由（closes 什麼破口） | 觸發依據類型 |
|------|-------------------|----------------------------|-------------|
| E5-Q1（收緊） | `screen_candidates.py` L788-816：`MFG_DOMINANT_TOKENS` 新增 `'設備工程師', '設備導入', '設備維修', '設備助理', '黃光', 'support engineer', 'Support Engineer', 'technology support', '技術支援'`（註記 `# v11.9 (Batch #52, B1)`）；`desired_is_mfg` 新增 `'設備工程師', 'support engineer', 'Support Engineer'`；解禁條件由原「`has_facility_mep`/`has_vip_co`」邏輯改為新增的 `strong_facility_career = has_build_proof(BUILD_PROOF_TOKENS，單一即可) or facility_seg(廠務/無塵室/潔淨室出現段數)>=2`，並在 `mfg_dominant and not strong_facility_career` 時直接 `return 0, [...排除(E5-Q1)...], True`。移除「單一短期廠務 title／學術無塵室 role／VIP 公司名」單獨解禁的路徑。 | 破口輪廓：在半導體/電子廠做「設備工程師/設備導入/設備支援」的製造支援端人員，靠知名公司名（美光/日月光/台積）或單一短期廠務職稱／學術無塵室角色繞過 E5。CLAUDE.md 4.9：半導體廠「工程師」有製造端（排除）vs 建廠設施端（入選）兩種，公司名不足以區分。 | 關鍵字/特徵（**非人名**）：`MFG_DOMINANT_TOKENS`／`BUILD_PROOF_TOKENS`／`facility_seg` 段數統計，皆為職稱/工作內容關鍵字比對，不含姓名條件 |
| E5c（新增，all-role） | `screen_candidates.py` L821-846：新區塊，`if c['group'] == 'G2_機電相關':`（無 `role_name` 限制，屬 all-role commons，且獨立於上方 `if c['group'] in ('G2_機電相關','G3_環境','G3_其他'):` 的 role 判斷外）。邏輯：從 `work_lines` 抽取各段最新職稱（`titles_e5c`），計算 `low_tech_dominant`（最新段或 ≥50% 段命中 `LOW_TECH_TRADE` = 技術員/技工/維修員/維修/保養/修理/製圖/繪圖/配電技術/組立/裝配/計裝/幫浦/焊工/技士/配線/技術工）；若 `low_tech_dominant` 且無 `has_mgmt_e5c`（主任/課長/副理/經理/協理/廠長/處長/總監/主管/襄理）且無 `has_substance_e5c`（`E5C_SUBSTANCE` 建廠/EPC/施工圖/監造/無塵室/機電整合/機電設計/特氣/高低壓/受電/變電站/BIM/Revit/AutoCAD/半導體/面板，或 `PREMIUM_COMPANIES`）且 `facility_seg_e5c`（廠務/無塵室/水處理段數）`< 2` → `return 0, [...排除(E5c)...], True`。 | 破口：對口電機/機械學歷觸發 N1(+15) + M1 泛用「電機/機械」（常來自公司名或技工職稱），剛好 30 分過門檻，但職涯全為技工/維修/製圖/配電等執行層，零建廠/設計/高科含金量。 | 關鍵字/特徵（**非人名**）：`LOW_TECH_TRADE` 職稱關鍵字統計、`E5C_SUBSTANCE`/`PREMIUM_COMPANIES` 白名單、管理職稱關鍵字，皆為可泛化特徵，不含姓名條件 |

**版本同步**：`screening_rules.md` 版本紀錄追加 **v11.9**（表格第 440 行，"default 跨批次誤選疊代（先蒐集後分析第二役, Batch #52）"）；`role_overlays/default.md` 第 34 行同步追加對應條目。`iteration_log.md` 已追加 Batch #52 完整條目（第 1648-1691 行）。

## 4. 受影響候選人（僅作為案例佐證）

| 姓名 | 新判決 | 命中規則 | 命中依據（須為可泛化特徵，非姓名比對） |
|------|--------|---------|------------------------------------|
| 葉洊語 | 誤選→攔截 | E5-Q1 | 美光測試設備/日東設備導入 → 命中 `MFG_DOMINANT_TOKENS`「設備工程師/設備導入」；無 `BUILD_PROOF` 或廠務≥2段證據，`strong_facility_career=False` |
| 徐立庭 | 誤選→攔截 | E5-Q1 | ASML/美光設備支援 → 命中「設備」系列 token；同上不具 `strong_facility_career` |
| 王宣緯 | 誤選→攔截 | E5-Q1 | 台積製程+學術無塵室 → `mfg_dominant=True`（製程 token），學術無塵室不再被計入 `facility_seg` 的有效解禁路徑（原規則允許單一無塵室 role 解禁，本輪移除） |
| 林韋昇 | 誤選→攔截 | E5-Q1 | 松下空調機開發 → 命中製造端 token，無建廠實質證據 |
| 王育成 | 誤選→攔截 | E5c | 電機技工/計裝 → 命中 `LOW_TECH_TRADE`（技工/計裝），對口學歷但無管理職/無 `E5C_SUBSTANCE`/廠務<2段 |
| 何宗達 | 誤選→攔截 | E5c | 儀電維修技術員 → 命中 `LOW_TECH_TRADE`（維修/技術員），同上條件成立 |

以上 6 人皆是 reason 字串（`排除(E5-Q1): ...` / `排除(E5c): ...`）中列出的**關鍵字/段數統計**命中，程式碼判斷路徑中不含任何 `if name == '<姓名>'` 或姓名比對邏輯——姓名僅用於本紀錄檔的案例佐證陳述。

**殘留未攔截（刻意不過擬合，供對照）**：柯定吾/田俊雄/張家銘/許凱斌/蔡明達（傳統機電工程師 title，與合格傳統機電工程師 keyword 難分）、張凱傑/林仁智/吳瑞祥（廠務維運多段，受「保護真廠務」豁免）、蘇庭漢/許宗瑝/涂威霖（B3 業務/PM，判 C 暫緩）、洪堃木/賴柏宏/劉濬愷（B4 營造/土建，判 C 暫緩）等 25 人，依使用者裁決保留於 `unqualify.md` 持續累積，未觸發任何規則變更。

## 5. 去識別化自述

- **本輪程式碼是否出現任何「以人名作為 if 條件或名單封殺」？** 否。已對 `git diff -- .agent/skills/hr-talent-screener/scripts/screen_candidates.py` 全文（536 行 diff，涵蓋本輪 v11.9 及先前未提交的 v0.8/v11.5/v11.7/v11.8 累積變更）執行 `grep -nE "if\s+['\"][一-龥]{2,4}['\"]\s+in|NAMES\s*=|BLACKLIST\s*="`，**零命中**。E5-Q1（`screen_candidates.py` L773-819）與 E5c（L821-846）兩處本輪新增/修改邏輯，控制流條件全部是 token 清單成員檢查（`any(kw in ... for kw in [...])`）與段數比例統計（`mfg_seg/total_seg`、`low_tech_seg/total_e5c`），無任何姓名字面比對。
- **姓名僅出現於：註解／版本紀錄／回報文字？** 是。針對全 diff 逐一核對姓名出現行（`蘇庭漢`/`古芝妍`/`劉俊谷`/`謝東林`/`劉傳鑫`/`黃智謙`/`沈晉宇`/`洪立民`/`涂威霖`/`許倍群`/`李坤霖`），全部落於 `+#` 開頭的**註解行**或 docstring（如 L34/40/50/86/114/241/267/297-298/327/336/357/385/396），用途均為「典型誤選/漏網輪廓」案例引註，供未來 Agent 回溯規則緣由，**不參與任何執行期判斷邏輯**。本輪 Batch #52 直接新增的姓名引註（葉洊語/徐立庭/王宣緯/林韋昇/王育成/何宗達）同樣僅出現在 `iteration_log.md` 統計表格與版本紀錄文字中，`screen_candidates.py` 程式碼本身（E5-Q1、E5c 兩區塊）**未新增任何姓名字串**。

## 6. 回歸結果

- `regression_check.py`：**PASS**。黃金集 343 筆，**0 新翻盤**。歷史入選葉洊語（Batch #1 選入）未被誤翻——其黃金集 CSV 摘要與 `unqualify.md` 當前製造端履歷特徵不同，未觸發新規則，驗證「收緊但保護真廠務」設計成立。
