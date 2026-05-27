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


def apply_decisions(csv_path, decisions):
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

    missing_decisions = csv_seqs - decision_seqs
    if missing_decisions:
        print(f"⚠️  CSV 內以下序號未在 decisions.json 提供判決，預設標為「正式候選」(reason='')：")
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
    args = ap.parse_args()

    if not os.path.exists(args.decisions_json):
        sys.exit(f"❌ 找不到決策檔：{args.decisions_json}")
    if not os.path.exists(args.csv):
        sys.exit(f"❌ 找不到 CSV：{args.csv}")

    role, decisions = load_decisions(args.decisions_json)
    print(f"📋 角色：{role}  /  決策筆數：{len(decisions)}")

    rows, counts, new_fields = apply_decisions(args.csv, decisions)

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

    print("\n🎉 /review 落地完成。")


if __name__ == '__main__':
    main()
