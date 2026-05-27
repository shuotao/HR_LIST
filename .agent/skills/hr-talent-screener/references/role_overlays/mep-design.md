# mep-design — **DEPRECATED** (v9.2 起合併為 default)

> **本檔案僅為過渡期向後相容的歷史紀錄**。
>
> 自 v9.2 起，`mep-design` 不再是獨立角色——本專案歷史上始終只有 2 個角色：
> - `default` = **MEP**（廠務 + MEP 設計合一）
> - `space-manager` = 空間管理
>
> v9.0~v9.1 過渡期短暫拆分為 3 類為設計失誤，v9.2 已修正合併。

---

## 當前實際行為

執行 `screen_candidates.py --role=mep-design` 時：
1. 程式偵測 `mep-design` 為 deprecated alias
2. 自動 fallback 至 `default` 並印警告
3. 套用 `default` overlay 全部規則（即原 mep-design 的全部規則 + v8.x default 行為）

## 規則內容請參見

- **`role_overlays/default.md`**：當前 default (MEP) 角色的完整 overlay 規格
- **`screening_rules.md` 第 2.2-2.4 節**：所有規則的權威定義與 overlay 標記
- **`screen_candidates.py:get_overlay('default')`**：程式碼權威來源

## 歷史紀錄（追溯用）

本檔案在 v9.0~v9.1 期間記錄的下列規則，現在皆屬於 `default` 角色生效：

- N6 BIM 工具獨立計分 +12
- N17 高科建廠核心 (1項+8 / 2項+15)
- N18 BIM × MEP 共現 (1段+12 / 2+段+15)
- E2/E6/E8 條件化解禁（M1/M2 工程門檻通過時）
- E20b/c/d 薄弱經歷防呆
- E21 短期純建模防呆
- E22 零 MEP 信號排除
- E23 純結構/土木技師軌跡排除
- E24 近期軌跡偏離 MEP
- E26 履歷極度單薄
- E27 建築背景跨機電跳槽
- E28 非工程繪圖員
- E29 純 BIM/繪圖跳槽
- D7 BIM-only 降級
- D12 純建模降級

詳細歷史描述見 `screening_rules.md` 版本紀錄（v8.17 / v9.0 / v9.1 / v9.2）與 `iteration_log.md` 對應批次。

## 為什麼合併？

「MEP 工程師」在中鼎不是切成「廠務」+「機電設計」兩個獨立物種——這是同一個職務的兩種風格（做廣 + 做深），互相支援、知識交流。把它們拆成獨立角色違反「同部門知識交流」的架構哲學。

未來新增的 MEP 相關規則一律寫入 `role_overlays/default.md` 與 `screening_rules.md`，**不要在本檔案追加內容**。
