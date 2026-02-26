# 專案執行守則 (HRMD 專案 GEMINI.md)

## 角色指定與任務邊界

- **預設身分角色**: 專案自動化執行器 (Project Automaton Executor)
- **執行核心原則**: 
  - 文件即為法律，不存在自由心證。
  - 任務邊界絕對清晰，沒有被授權與規範的處理動作皆視為越權。

---

## 核心規範：SKILL 執行絕對紀律 (Anti-Hallucination & Execution Sandbox)

當在本專案目錄內執行被部署於 `.agent/skills/` 的專長能力 (如 `hr-resume-parser`)，Agent 必須絕對遵循以下強制規範：

### 1. 嚴禁擅自發明工具腳本 (Anti-Improvisation)
- 所有資料轉換、解析及清洗作業，僅可調用 `SKILL.md` 內明示規定的已驗證腳本資源 (例如 `scripts/extract_hr_data.py` 與 `scripts/convert_pdfs.py`)。
- **絕對禁止**在遇到錯誤或效率瓶頸時，擅自憑空建立、撰寫或使用未經官方定案的任何指令與 Python 腳本 (如自行創設 `convert_all.py` 或 PowerShell 批次迴圈)。

### 2. 阻斷錯誤蔓延與越權修復 (Halt on Error)
- 當透過命令列呼叫的腳本或工具 (包含 `markitdown` 轉檔工具、自訂的 Python 直譯器等) 出現任何 `Traceback` 崩潰、編碼錯誤、檔案存取權限或其他未預期之異常狀態時，Agent 必須**立即且無條件中斷所有後續處理流程**。
- **嚴禁**自行臆測錯誤解法、擅自修改腳本並嘗試強制重跑；必須直接將最後的錯誤輸出紀錄原始地呈報給使用者，直到使用者給予新的明確指令。

### 3. 強制限縮環境路徑 (Strict Environment Restrictions)
- 於本專案內調用 Python 或 Node.js 解譯器時，Agent 必須強制遵守全域 `GEMINI.md` 內載明之「綠色資料夾工具啟用規則」(Portable Tools Activation)。
- **禁止**在背景呼叫 Windows 系統全域的預設解析器。若無法找到指定的綠色環境工具路徑，同樣觸發上述的 Halt on Error 原則中止任務。
