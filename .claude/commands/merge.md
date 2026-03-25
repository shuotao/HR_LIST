你是 hr-resume-parser 技能的執行器。請嚴格遵循 `.agent/skills/hr-resume-parser/SKILL.md` 的完整 SOP。

## 任務：將 PDF 履歷批次轉換為結構化 CSV

### 步驟 1：PDF 轉 Markdown
執行以下指令：
```
c:\Users\01102088\Desktop\python-3.14.2-embed-amd64\python.exe .agent/skills/hr-resume-parser/scripts/convert_pdfs.py
```
- 向使用者回報轉換結果（共幾份 PDF、是否有錯誤）

### 步驟 2：欄位擷取與 CSV 產出
執行以下指令：
```
c:\Users\01102088\Desktop\python-3.14.2-embed-amd64\python.exe .agent/skills/hr-resume-parser/scripts/extract_hr_data.py
```
- 向使用者回報處理結果（共幾位候選人）
- 回報程式自動防幻覺檢驗的 5 組抽檢結果

### 步驟 3：Agent 手動抽驗
從產出的 `HR_Data_Summary.csv` 中另外隨機挑選 5 位不同候選人，回頭讀取對應的 `.pdf` 原始檔進行比對驗證，向使用者報告結果。

### 步驟 4：完成
告知使用者 `HR_Data_Summary.csv` 已產出，採 `utf-8-sig` 編碼可直接用 Excel 開啟。
