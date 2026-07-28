---
name: hr-talent-screener
description: 專門用於處理「104履歷候選人才篩選」。當使用者提供一份未整理的 ANALYSIS.md（104系統擷取的候選人總資料），需要進行資料清洗、去重、分類並篩選出面試候選名單時，請使用此技能。也適用於使用者提及「找人選」、「篩選履歷」、「幫我從名單中挑人」等情境。
---

# HR Talent Screener (人才候選篩選技能)

當使用者提供一份 `ANALYSIS.md` 原始檔案，要求從中篩選出符合機電/廠務/工程相關職缺的面試候選人時，必須觸發並嚴格遵循本技能的所有流程。

## 🎯 技能目標
將未經整理的 104 系統候選人總資料（通常上萬行），經過三階段清洗後，依據已建立的人才篩選規則（`references/screening_rules.md`），自動產出符合條件的候選人姓名一覽表。

## ⚙️ 環境設定
- **Python 路徑**：`D:\green-tools\python-3.14.2-embed-amd64\python.exe`
- **工作目錄**：ANALYSIS.md 所在的專案資料夾
- **參考文件**（四份，各有不同生命週期）：
  - `references/screening_rules.md` — **純規則手冊**（跨批次永久有效，僅更新規則本身）
  - `references/iteration_log.md` — **疊代日誌**（歷史累積，每批次追加，不刪除）
  - `references/clear_RULE.md` — 三階段清洗規則定義
  - `references/improve_record.md` — **/improve 品質稽核快照**（latest-only：每次 improve/重錄由 improve-recorder 整檔覆寫，非 append；與 iteration_log.md 的 append-only 相反）

## 📍 執行流程 (SOP)

### 步驟 1：三階段資料清洗
使用 `scripts/pipeline_clean.py` 對 ANALYSIS.md 執行以下三個階段的清洗。
**注意：此步驟會直接覆寫 ANALYSIS.md 原檔。** 清洗是強制性的，因為：(1) 104 系統雜訊會干擾評分、(2) 不去重會導致同一人被重複計分、(3) 分區排序是後續 M/N/E 規則的前提。

1. **第一階段 — 雜訊移除**：移除 104 系統的版權宣告、個資警語、狀態按鈕列、系統公告、功能選單等非候選人資訊。
2. **第二階段 — 重複人選剃除**：以「代碼：」後方的數字為唯一識別碼，從上而下掃描，保留每位候選人首次出現的區塊、捨棄後續重複。
3. **第三階段 — 學歷背景分類排序**：將候選人依學歷科系分為三區塊（土木建築 / 機電相關 / 其他），重新排列並加入區塊標題。

**執行指令**：
```
D:\green-tools\python-3.14.2-embed-amd64\python.exe scripts/pipeline_clean.py <ANALYSIS.md路徑>
```

腳本會輸出清洗統計摘要，Agent 需向使用者回報此統計。

### 步驟 2：候選人篩選
使用 `scripts/screen_candidates.py` 對清洗後的 ANALYSIS.md 進行篩選：

1. 解析每位候選人的完整資料區塊（姓名、年齡、學歷、希望職稱、工作經歷）。
2. 依據 `references/screening_rules.md` 中的規則進行評分（各層完整條件編號與定義以 `screening_rules.md` 與 `role_overlays/<role>.md` 為準）：
   - 必要條件 (M 層)：至少命中一項才納入候選池
   - 加分條件 (N 層)：全 role 通用加分；default/space-manager 另啟用 BIM 共現加分，space-manager 再加空間/法規/跨系統加分。累計加分
   - 排除條件 (E 層)：全 role 通用排除條件 + default/space-manager overlay 專屬防呆。命中任一項即排除
   - 動態調整 (D 層)：全 role 通用動態扣分 + 角色專屬降分（default/space-manager 的 BIM 純度降級、space-manager 的傳統基層/純土建降級等）
3. 輸出候選人姓名一覽表與各人的命中理由摘要。

**執行指令**（雙角色架構，輸入檔統一為 `ANALYSIS.md`）：
```
# default = MEP 角色（廠務 + MEP 設計合一，預設）
D:\green-tools\python-3.14.2-embed-amd64\python.exe scripts/screen_candidates.py ANALYSIS.md

# space-manager（空間管理工程師：跨系統整合 + 法規理解）
D:\green-tools\python-3.14.2-embed-amd64\python.exe scripts/screen_candidates.py ANALYSIS.md --role=space-manager

# （deprecated）mep-design 為 v9.0~v9.1 過渡名稱，v9.2 起自動 fallback 至 default
# D:\green-tools\python-3.14.2-embed-amd64\python.exe scripts/screen_candidates.py ANALYSIS.md --role=mep-design
```

### 步驟 3：結果呈現與確認
1. 向使用者**分區塊**呈現候選名單（第一區 / 第二區 / 第三區）。
2. 每位候選人附上 1-2 行命中理由摘要。
3. 詢問使用者：
   - 這份名單是否有**漏選**？請提供漏選的人名。
   - 是否有**誤選**？請指出不應入選的人名。

   > 回饋的處理見步驟 4.0（名單蒐集階段）：**漏選 → append `qualify.md`；誤選 → append `unqualify.md`**，此階段只蒐集、**不改規則**。

### 步驟 4：疊代學習 `/improve`（關鍵步驟，「先蒐集，後分析」雙階段）

> **v11.5（2026-07-08）改版**：捨棄「每批 `/filter` 後立即改規則」的舊模式（單批樣本量小、口語記憶依賴、易過度擬合單批特例、無法跨批次累積）。改為**先跨批次累積回饋，樣本足量後才統一分析落地規則**。

#### 4.0 名單蒐集階段（每次 `/filter` 後可重複多輪；此階段嚴禁改規則）
使用者確認 `/filter` 結果後，回饋通常分兩種。Agent 只做「取區塊 → append」，**不得改規則/改 `screen_candidates.py`/進入 4.1 之後的分析**：
- **排除/誤選回饋**（引擎放行但使用者判定不合格，false positive）→ 從 `ANALYSIS.md` 取該人完整資料區塊，**append（不取代）**寫入專案根目錄 `unqualify.md`。
- **漏選/入選回饋**（引擎排除但使用者判定合格，false negative）→ 從 `ANALYSIS.md` 取該人完整資料區塊，**append（不取代）**寫入專案根目錄 `qualify.md`。
- 兩檔以「代碼：」為唯一鍵去重，**皆為 append-only**；**Agent 嚴禁自動清空或歸檔**，僅使用者可人為處理。
- `screen_candidates.py` 下一次 `/filter` 會自動比對此兩檔：命中 `unqualify.md` 標 ★（應排除卻仍入選）、命中 `qualify.md` 標 ☆ 並列「仍被引擎漏掉」清單，供蒐集進度追蹤。

**切換信號**：累積數輪、樣本足量後，使用者直接說「Step 2」／`/improve`，才進入下列規則疊代四子步驟（4.1~4.4）。

#### 4.1 漏選/誤選原因分析（讀 `unqualify.md` + `qualify.md` 逐人歸因）
1. **分析誤選原因**（讀 `unqualify.md`）：引擎為何放行這些人？需要強化/新增什麼排除條件（E/D）？
2. **分析漏選原因**（讀 `qualify.md`）：引擎為何排除這些人？哪條規則過嚴、或缺什麼加分條件（N）／關鍵字？
3. **跨批次統計歸類**：因兩檔已累積 20+ 筆樣本，須做統計（如「誤選中 60% 是製造端設備工程師包裝成廠務」），**只對統計顯著的模式改規則**，避免過度擬合單一案例。

#### 4.2 更新規則與日誌
1. **更新 `references/screening_rules.md`**（純規則文件）：
   - 在「第二節 篩選規則」中新增/修正 M/N/E 條件
   - 在「第三節 關鍵字清單」中補充新發現的關鍵字
   - 在「第四節 篩選經驗法則」中沉澱新的觀察
   - 若使用者回答了 Q&A，將答案從「第五節」移入正式規則
   - 在「第六節 版本紀錄」中記錄本次變更
   - **重要：`screen_candidates.py` 中的關鍵字陣列必須與 `screening_rules.md` 保持同步。** 若只改規則文件不改程式碼，篩選引擎不會生效。
2. **追加 `references/iteration_log.md`**（疊代日誌）：
   - 記錄本輪蒐集的來源統計（`unqualify.md`／`qualify.md` 各累積筆數、跨批次範圍）
   - 記錄統計歸類結果與已確認入選/誤選/漏選的名單
   - 記錄使用者回饋的原文
   - 此文件只做 Append，絕不刪除歷史記錄
3. **追加 `references/historical_selections.csv`**（歷史選人紀錄）：
   - 將本批次的 `HR_Data_Summary.csv` 全部資料追加至此（加上 batch 欄位標記批次）
   - 此為技能層內唯一允許存放的 CSV 檔案，只做 Append
   - 用途：跨批次分析選人特徵趨勢，精煉篩選規則

#### 4.3 落差分析（Deviation Analysis）
Agent 在完成規則更新後，**必須主動**進行以下反思分析：

1. **辨識「意外落差」**：比對本次使用者排除的人選 vs 現有規則體系，找出以下模式：
   - 現有規則**理應已能排除**，但本次仍被大量選出的類型（表示規則有漏洞或權重失衡）
   - 使用者排除理由中出現的**新概念/新維度**，是現有規則完全未覆蓋到的
   - 使用者的排除標準與過去批次的標準出現**矛盾或演化**的跡象
2. **統計歸類**：將本次排除原因進行歸類統計，例如：
   - 製造/製程端：X 人（佔本次排除 Y%）
   - 履歷厚度不足：X 人
   - 純土建無機電：X 人
   - 行政內業：X 人
   - 其他新類型：X 人
3. **輸出落差分析報告**（向使用者呈現），格式如下：

```
📊 落差分析報告
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
■ 本次排除統計：共 N 人排除，歸類如下：
  - [類型A]：X 人 (Y%) — 規則覆蓋狀態：🟢已有/🟡部分/🔴未覆蓋
  - [類型B]：X 人 (Y%) — 規則覆蓋狀態：...

■ 意外落差點（本次最值得注意的發現）：
  1. [落差描述] — 現有規則 [Exx] 理應攔截，但仍有 X 人漏網
  2. [落差描述] — 全新排除維度，現有規則完全未覆蓋

■ 問題選項（請逐項確認）：
  Q1: [具體問題]
      A) [選項A — 代表某種規則調整方向]
      B) [選項B — 代表另一種方向]
      C) 這是我的誤判，不需調整
  Q2: ...
```

#### 4.4 等待使用者回覆問題選項
- 根據使用者對問題選項的回覆，**進一步精煉規則**
- 若使用者確認為「誤判」或「單次需求」，則不改動規則，僅在 iteration_log 中記載
- 若使用者確認需調整，則更新 screening_rules.md 與 screen_candidates.py

#### 4.5 品質稽核迴圈（規則落地後強制執行，v11.10 升級）
> 目的：確保本輪 improve **沒有以人名作為封殺依據**（違反 CLAUDE.md 4.11 / v8.0「廢除人名黑白名單」），避免候選人更新履歷/職能提升後仍被姓名比對誤漏。
1. **紀錄（Sonnet）**：spawn `improve-recorder`（固定 Sonnet、單次執行）。它**清空前次紀錄**並整檔覆寫 `references/improve_record.md`（latest-only，非 append）：步驟軌跡、決策點、規則變更與修正理由、受影響候選人（含命中依據）、去識別化自述、回歸結果。
2. **稽核（Opus）**：spawn `improve-verifier`（固定 Opus）。稽核 (A) 去識別化（程式碼無姓名級控制流）+ (B) 投機辨識（跑「姓名匿名化黃金測試」：診斷測試檔姓名全匿名後重跑，判決集合須與匿名前完全一致）。
3. **迴圈**：PASS → 進 4.6；FAIL → 依問題節點把姓名捷徑改為可泛化特徵 → 重跑 `regression_check.py` → 再 spawn recorder 清空重錄 → 再 spawn verifier 複驗，直到 PASS。⛔ 未 PASS 不得進 4.6。

#### 4.6 文件對齊（Fable5 指揮 Opus，收尾）
稽核 PASS 後，spawn **Fable 5** agent 稽核 `CLAUDE.md`／`README.md`／`.agent/skills/**/*.py`／`*.md`／overlay／command 是否與本輪版本一致並產出對齊計畫，再 spawn **Opus** agent 依計畫落地文件修正（Fable5 規劃、Opus 執行），回報使用者。

### 步驟 5：結案審閱 `/review`（在 `/merge` 之後執行）
> **此步驟不在本技能（hr-talent-screener）的 `/filter` 流程中直接執行。**
> 它發生在使用者完成 `/merge`（PDF → CSV）之後，因為只有看到完整履歷的結構化細節（`HR_Data_Summary.csv`），才能發現 ANALYSIS.md 摘要階段無法看出的落差。
>
> **🔁 階段獨立原則（v10.3+ 新增）**：每次 `/review` 必須當作獨立執行——進場第一件事**重讀 `HR_Data_Summary.csv` 與根目錄 PDF 列表**確認當前狀態，不可信任跨對話的上下文記憶或前批殘留檔案（`review_decisions.json` 可能是上一輪遺留的舊版，會被 `apply_review_decisions.py` 的對齊檢查擋下並要求重新產生）。

Agent 基於 `HR_Data_Summary.csv` 執行最終審閱（**2026-07-02 起含閘門機制**，閘門定義詳見 CLAUDE.md「閘門機制與 gatekeeper Agent」章節）：

1. **產生判決草稿**：執行官方腳本重跑篩選引擎，得逐人分數與基線判決：
   ```
   D:\green-tools\python-3.14.2-embed-amd64\python.exe scripts/generate_review_decisions.py --role=<role>
   ```
2. **Agent 微調 + 產出差異清單**：逐人核對完整履歷（.md/.pdf），把候選人分兩堆：
   - **一致筆**：腳本判決 = Agent 判斷，且分數離門檻夠遠 → 不打擾使用者
   - **差異筆**：(a) Agent 想推翻腳本判決的人；(b) 分數在門檻 ±5 的邊界人
   差異清單每筆附：序號、姓名、腳本分數、腳本判決、Agent 建議判決、關鍵證據 1~2 行。
   同時找出「誤選深層發現」（摘要合格但完整履歷不符）與「漏選深層發現」（摘要普通但其實很強）。
3. **【閘門 A】使用者簽核差異筆**：
   - 呈現差異清單，使用者逐筆回覆「同意」或「改為X」
   - 使用者說「代打」→ spawn `gatekeeper`（MODE: PROXY）：有歷史模式支持的筆代打判決，**查無模式的筆掛起**，掛起清單仍回頭請使用者裁決
   - 簽核完成後 → spawn `gatekeeper`（MODE: RECORD）記錄本次互動（含使用者對掛起筆的裁決）
   - ⛔ **未過閘門 A，嚴禁執行第 4 步**
4. **CSV 欄位新增（CSV 為 10 欄初始 → 12 欄結案，由官方腳本落地）**：
   Agent 將定稿判決整理為 `review_decisions.json`（格式如下），然後執行官方腳本 `scripts/apply_review_decisions.py` 將判決寫入 `HR_Data_Summary.csv` 並執行 CSV↔PDF 驗證。**嚴禁自行撰寫一次性腳本以 hardcode dict 方式直接修改 CSV**（違反 CLAUDE.md 唯一腳本原則）。
   - 「**審閱結果建議**」— 由腳本插在「總年資」之前，值為：`正式候選` / `排除` / `降級觀察` / `碩士儲備`
   - 「**審閱排除理由簡述**」— 由腳本追加在末欄，正式候選者自動留空
   - **`review_decisions.json` 格式**：
     ```json
     {
       "role": "default",
       "decisions": {
         "001": {"result": "正式候選", "reason": ""},
         "002": {"result": "排除",     "reason": "E12 純物業..."}
       }
     }
     ```
   - **執行指令**：
     ```
     D:\green-tools\python-3.14.2-embed-amd64\python.exe scripts/apply_review_decisions.py review_decisions.json
     ```
   - 腳本具備冪等性（可重跑），合法 result 值僅限上述四種，任何越權值會中止執行。
5. **強制驗證 CSV ↔ PDF 一致性**（由 `apply_review_decisions.py` 自動執行）：逐筆比對 CSV 序號與根目錄 PDF 檔名 `{序號}_{姓名}.pdf`，任一筆不一致即立即中止。**所有 PDF/MD 一律保留在根目錄**，**禁止建立 excluded/ / downgraded/ / reserve/ 子資料夾**，分類結果僅記錄於 CSV 的「審閱結果建議」欄位中。
6. **落差分析報告 + 問題選項**：使用步驟 4.3 的格式，基於 CSV 細節產出落差分析，整理成問題選項（Q1: A/B/C，C 永遠是「誤判，不需調整」）。
7. **【閘門 B】使用者回答問題選項**（或說「代打」→ gatekeeper PROXY 依歷史答題傾向代答，查無傾向的題掛起）→ 完成後 spawn `gatekeeper`（MODE: RECORD）。
   - ⛔ **未取得回答前，嚴禁修改 `screening_rules.md` / `role_overlays/` / `screen_candidates.py`**
8. **精煉規則 + 回歸守門**：根據閘門 B 的答案更新 `screening_rules.md`（default）或 `role_overlays/<role>.md`（overlay）與 `screen_candidates.py`（漏網之魚必須歸因到具體規則缺口），然後**必跑**黃金集回歸測試：
   ```
   D:\green-tools\python-3.14.2-embed-amd64\python.exe scripts/regression_check.py
   ```
   - PASS（0 新翻盤）→ 規則變更成立
   - FAIL → 向使用者呈報翻盤名單；翻盤若為刻意的規則效果，經使用者核准後跑 `--accept` 更新 baseline；否則退回修正規則。**代打模式下 FAIL 一律停下等使用者**。
9. **呈現本次任務摘要**：
   - 原始候選人數 → 最終入選人數
   - 本次規則變更摘要 + 回歸測試結果
   - 累計規則版本
10. **正式結案**：使用者確認後（**結案永遠由使用者，不可代打**），spawn `gatekeeper`（MODE: RECORD）記錄 closure。本次找人任務完成，規則已沉澱為下一次 `/filter` 的養分
11. **（結案後·可選）納入回歸黃金集**：把本批已審閱定案的 12 欄 `HR_Data_Summary.csv` 追加至 `references/historical_selections.csv`，讓下一輪 `regression_check.py` 保護本批人類判決不被未來規則悄悄翻盤：
    ```
    D:\green-tools\python-3.14.2-embed-amd64\python.exe scripts/append_review_to_golden.py --role=<role> --batch=<role>-<YYYY-MM-DD>-review --dry-run
    D:\green-tools\python-3.14.2-embed-amd64\python.exe scripts/append_review_to_golden.py --role=<role> --batch=<role>-<YYYY-MM-DD>-review
    ```
    - 冪等守門：同 batch 重複追加會被擋（除非 `--force`）；append-only 不改既有列。
    - 追加後可跑 `regression_check.py --accept` 一次（**需使用者核准**），吸收本批新增列的「CSV 摘要 vs 完整履歷」既存誤差進 baseline；引擎能由 CSV 摘要重現的判決（如命中 E15b/E12 者）即獲實質回歸保護，其餘因摘要資訊量不足者由 baseline 吸收。

> ⚠️ 這是一個**逐次疊代增加準度**的過程。每次執行，人才候選計畫都會變得更精準。

## ⚠️ 關鍵限制與守則
1. **不可跳過清洗**：即使使用者說「直接篩」，也必須先執行三階段清洗，否則重複資料會導致權重失真。
2. **代碼為唯一識別**：絕不可用姓名作為去重依據，同名同姓的人不能被誤刪。
3. **寧可多選不可漏選**：篩選閾值寧鬆勿緊，讓使用者從較大池中做最終決策。
4. **唯一腳本原則**：只能使用本技能 `scripts/` 內的腳本，嚴禁在專案目錄下另建臨時腳本。
5. **保持文件生態完整**：每次疊代後，必須同步更新 `references/screening_rules.md` 與追加 `references/iteration_log.md`。
6. **專案根目錄保持乾淨**：`HR_Data_Summary.csv` 永遠只保留當批次的最新版（覆蓋）。歷史數據僅存放於 `references/historical_selections.csv` 這一個 CSV 檔案中。
7. **每批次獨立評估**：即使候選人跨批次重複出現，仍需獨立評分，因為候選人可能更新了自己的履歷資訊。
8. **廢除人名黑/白名單**：v8.0 起不再使用永久人名名單進行強制納入/排除。所有判斷純粹依賴 M/N/E 規則與關鍵字匹配。歷史回饋的價值應提煉為規則，而非綁定個人姓名。
9. **落差分析為必要步驟**：每次 `/improve` 疊代階段結束前，必須執行落差分析並向使用者提出問題選項，不可省略。
10. **蒐集與疊代分離（「先蒐集，後分析」）**：名單蒐集階段（append `qualify.md`／`unqualify.md`）**嚴禁**改規則；兩檔 append-only、以「代碼：」去重、Agent 不得自動清空或歸檔。規則變更一律待使用者說「Step 2」進入疊代階段，且只對跨批次統計顯著的模式落地，避免過度擬合單批特例。

