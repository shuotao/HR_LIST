# -*- coding: utf-8 -*-
"""
apply_review_decisions.py — /review 結案決策落地腳本

對應 SKILL.md 步驟 5（結案審閱）。Agent 在 /review 流程中產出審閱決策（JSON），
本腳本將其寫入 HR_Data_Summary.csv 的兩欄：
  - 「審閱結果建議」  → 插在「總年資」之前
  - 「審閱排除理由簡述」→ 追加在末欄
並強制執行 CLAUDE.md /review 規定的 CSV ↔ PDF 一致性驗證（每筆序號必須對應到
根目錄 `{序號}_{姓名}.pdf`）。

用法：
    python apply_review_decisions.py <decisions.json>
                                     [--csv HR_Data_Summary.csv]
                                     [--pdf-dir .]
                                     [--skip-verify]

decisions.json 格式：
{
  "role": "default" | "space-manager",
  "decisions": {
    "001": {"result": "正式候選", "reason": ""},
    "002": {"result": "排除",     "reason": "E12 純物業維護..."},
    ...
  }
}

合法 result 值：正式候選 / 排除 / 降級觀察 / 碩士儲備

冪等性：可重複執行。若 CSV 已含兩欄則直接覆寫舊值，不會疊加欄位。
"""

import argparse
import csv
import json
import os
import sys

# CLAUDE.md gotcha #1：Windows cp950 encoding
sys.stdout.reconfigure(encoding='utf-8')

REVIEW_COL = '審閱結果建議'
REASON_COL = '審閱排除理由簡述'
PIVOT_COL = '總年資'
VALID_RESULTS = {'正式候選', '排除', '降級觀察', '碩士儲備'}


def load_decisions(path):
    with open(path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    role = data.get('role', 'default')
    decisions = data.get('decisions', {})
    if not isinstance(decisions, dict):
        sys.exit(f"❌ decisions.json 格式錯誤：'decisions' 必須為 object，實得 {type(decisions).__name__}")
    for seq, item in decisions.items():
        if not isinstance(item, dict) or 'result' not in item:
            sys.exit(f"❌ decisions[{seq}] 缺少 'result' 欄位")
        if item['result'] not in VALID_RESULTS:
            sys.exit(f"❌ decisions[{seq}].result='{item['result']}' 不在合法集合 {sorted(VALID_RESULTS)}")
        item.setdefault('reason', '')
    return role, decisions


def build_fieldnames(existing):
    """冪等地構造新表頭：插入 審閱結果建議 於 總年資 之前，末欄補 審閱排除理由簡述。"""
    if PIVOT_COL not in existing:
        sys.exit(f"❌ CSV 缺少基準欄位 '{PIVOT_COL}'，無法定位插入點。CSV 是否為 /merge 產出？")
    out = []
    for col in existing:
        if col == PIVOT_COL and REVIEW_COL not in out:
            out.append(REVIEW_COL)
        if col not in (REVIEW_COL, REASON_COL):
            out.append(col)
    if REVIEW_COL not in out:
        out.append(REVIEW_COL)
    out.append(REASON_COL)
    return out


def apply_decisions(csv_path, decisions, allow_partial=False):
    with open(csv_path, 'r', encoding='utf-8-sig', newline='') as f:
        reader = csv.DictReader(f)
        rows = list(reader)
        old_fields = reader.fieldnames or []

    new_fields = build_fieldnames(old_fields)
    csv_seqs = {r['序號'] for r in rows}
    decision_seqs = set(decisions.keys())

    missing_in_csv = decision_seqs - csv_seqs
    if missing_in_csv:
        sys.exit(f"❌ decisions.json 內以下序號在 CSV 中找不到：{sorted(missing_in_csv)}")

    # 防線 1（v10.3+, 2026-05-27）：decisions 筆數 vs CSV 筆數對齊強制檢查
    # 起因：Agent 曾把 5 筆前批 decisions 誤套到 15 列新批 CSV 上（user 在背景換 PDF
    # 重跑 /merge 而 Agent 沒察覺），導致前 5 列被誤判 + 後 10 列被預設標「正式候選」。
    # 對齊檢查是客觀靜態事實，由腳本永久把關，不依賴 Agent 自律。
    missing_decisions = csv_seqs - decision_seqs
    if missing_decisions and not allow_partial:
        sys.exit(
            f"❌ 對齊失敗：CSV 有 {len(csv_seqs)} 筆但 decisions.json 只有 {len(decision_seqs)} 筆。\n"
            f"   CSV 內以下 {len(missing_decisions)} 筆序號缺少判決：{sorted(missing_decisions)}\n"
            f"\n"
            f"   可能原因：\n"
            f"   (1) review_decisions.json 是上一批殘留的舊檔，CSV 已換新批次（最常見）\n"
            f"   (2) Agent 漏寫了部分人的判決\n"
            f"\n"
            f"   修補方向：\n"
            f"   - 確認 review_decisions.json 對應的是「當前 CSV」批次\n"
            f"   - 補齊缺失的判決（合法 result：正式候選 / 排除 / 降級觀察 / 碩士儲備）\n"
            f"   - 若你確認真的要部分套用（極少見情境），請加 --allow-partial 旗標明確授權"
        )
    if missing_decisions and allow_partial:
        print(f"⚠️  --allow-partial 模式：CSV 內以下序號未在 decisions.json 提供判決，預設標為「正式候選」(reason='')：")
        for s in sorted(missing_decisions):
            print(f"     - {s}")

    counts = {k: 0 for k in VALID_RESULTS}
    for row in rows:
        seq = row['序號']
        decision = decisions.get(seq, {'result': '正式候選', 'reason': ''})
        result = decision['result']
        reason = decision.get('reason', '') if result != '正式候選' else ''
        row[REVIEW_COL] = result
        row[REASON_COL] = reason
        counts[result] += 1

    with open(csv_path, 'w', encoding='utf-8-sig', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=new_fields)
        writer.writeheader()
        for row in rows:
            writer.writerow({k: row.get(k, '') for k in new_fields})

    return rows, counts, new_fields


def verify_pdf_consistency(rows, pdf_dir):
    """CLAUDE.md /review 步驟 6：逐筆比對 CSV 序號 ↔ 根目錄 {序號}_{姓名}.pdf。"""
    print("\n--- 🔍 CSV ↔ PDF 一致性強制驗證 ---")
    pdf_files = {f for f in os.listdir(pdf_dir) if f.lower().endswith('.pdf')}
    failures = []
    for row in rows:
        seq = row['序號']
        name = row['姓名']
        expected = f"{seq}_{name}.pdf"
        if expected not in pdf_files:
            failures.append((seq, name, expected))
    if failures:
        print(f"❌ 驗證失敗：{len(failures)} 筆 CSV 記錄找不到對應 PDF：")
        for seq, name, expected in failures:
            print(f"   [{seq}] 期望檔名：{expected}")
        sys.exit("結案中止——請先解決檔名不一致問題。")
    print(f"✅ 驗證通過：{len(rows)} 筆 CSV 全部對應到根目錄 PDF。")


def main():
    ap = argparse.ArgumentParser(description='/review 審閱決策落地腳本')
    ap.add_argument('decisions_json', help='Agent 產出的決策 JSON 路徑')
    ap.add_argument('--csv', default='HR_Data_Summary.csv', help='CSV 檔路徑（預設：HR_Data_Summary.csv）')
    ap.add_argument('--pdf-dir', default='.', help='PDF 所在資料夾（預設：當前目錄）')
    ap.add_argument('--skip-verify', action='store_true', help='跳過 CSV↔PDF 驗證（debug 用，正式流程禁用）')
    ap.add_argument('--allow-partial', action='store_true',
                    help='允許 decisions 筆數 < CSV 筆數（極少見；預設禁止以防跨批次誤套）')
    ap.add_argument('--keep-json', action='store_true',
                    help='完成後保留 review_decisions.json（預設刪除以杜絕跨批次殘留汙染）')
    args = ap.parse_args()

    if not os.path.exists(args.decisions_json):
        sys.exit(f"❌ 找不到決策檔：{args.decisions_json}")
    if not os.path.exists(args.csv):
        sys.exit(f"❌ 找不到 CSV：{args.csv}")

    role, decisions = load_decisions(args.decisions_json)
    print(f"📋 角色：{role}  /  決策筆數：{len(decisions)}")

    rows, counts, new_fields = apply_decisions(args.csv, decisions, allow_partial=args.allow_partial)

    print(f"\n--- 📊 審閱結果統計 ---")
    total = sum(counts.values())
    for k in ('正式候選', '降級觀察', '碩士儲備', '排除'):
        v = counts.get(k, 0)
        pct = (v / total * 100) if total else 0
        print(f"  {k}：{v} 人 ({pct:.1f}%)")
    print(f"  合計：{total} 人")
    print(f"\nCSV 已更新為 {len(new_fields)} 欄。")

    if args.skip_verify:
        print("\n⚠️  已跳過 CSV↔PDF 驗證（--skip-verify）。正式結案前必須執行驗證。")
    else:
        verify_pdf_consistency(rows, args.pdf_dir)

    # 防線 3（v10.3+, 2026-05-27）：apply 成功後刪除 decisions.json，杜絕跨批次殘留汙染
    # 起因：上一批 review_decisions.json 殘留會被 Agent 在新批次誤用。
    # 刪除是「斷絕汙染源」而非「偵測汙染」，與防線 1 互補。
    if not args.keep_json:
        try:
            os.remove(args.decisions_json)
            print(f"\n🧹 已刪除 {args.decisions_json}（避免跨批次殘留汙染；下次 /review 須重新產生）")
        except OSError as e:
            print(f"\n⚠️  自動刪除 {args.decisions_json} 失敗（{e}），請手動清理。")

    print("\n🎉 /review 落地完成。")


if __name__ == '__main__':
    main()
