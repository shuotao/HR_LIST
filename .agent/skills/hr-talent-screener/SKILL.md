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
- **參考文件**（三份，各有不同生命週期）：
  - `references/screening_rules.md` — **純規則手冊**（跨批次永久有效，僅更新規則本身）
  - `references/iteration_log.md` — **疊代日誌**（歷史累積，每批次追加，不刪除）
  - `references/clear_RULE.md` — 三階段清洗規則定義

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
2. 依據 `references/screening_rules.md` 中的規則進行評分：
   - 必要條件 (M1-M3)：至少命中一項才納入候選池
   - 加分條件 (N1-N17；default/space-manager 啟用 N18；space-manager 額外啟用 N19-N20)：累計加分
   - 排除條件 (E1-E18 全 role 通用；default 啟用 E20b/c/d, E21-E24, E26-E29；E19/E20a/E25 全 role 通用)：命中任一項即排除
   - 動態調整 (D1-D6, D6b, D15 全 role；default/space-manager 啟用 D7、D12；space-manager 額外啟用 D11/D13/D14)
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

### 步驟 4：疊代學習 `/improve`（關鍵步驟）
根據使用者的回饋，Agent 必須執行以下 **四個子步驟**：

#### 4.1 漏選/誤選原因分析
1. **分析漏選原因**：該人的哪些特徵未被現有規則捕捉？需要增加什麼關鍵字或條件？
2. **分析誤選原因**：該人為何被錯誤納入？需要強化什麼排除條件？

#### 4.2 更新規則與日誌
3. **更新 `references/screening_rules.md`**（純規則文件）：
   - 在「第二節 篩選規則」中新增/修正 M/N/E 條件
   - 在「第三節 關鍵字清單」中補充新發現的關鍵字
   - 在「第四節 篩選經驗法則」中沉澱新的觀察
   - 若使用者回答了 Q&A，將答案從「第五節」移入正式規則
   - 在「第六節 版本紀錄」中記錄本次變更
   - **重要：`screen_candidates.py` 中的關鍵字陣列必須與 `screening_rules.md` 保持同步。** 若只改規則文件不改程式碼，篩選引擎不會生效。
4. **追加 `references/iteration_log.md`**（疊代日誌）：
   - 記錄本批次的來源統計（原始行數、唯一候選人數）
   - 記錄已確認入選/誤選/漏選的名單
   - 記錄使用者回饋的原文
   - 此文件只做 Append，絕不刪除歷史記錄
5. **追加 `references/historical_selections.csv`**（歷史選人紀錄）：
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
9. **落差分析為必要步驟**：每次 `/improve` 結束前，必須執行落差分析並向使用者提出問題選項，不可省略。

