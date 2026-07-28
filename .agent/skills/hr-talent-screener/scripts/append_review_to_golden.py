# -*- coding: utf-8 -*-
"""
append_review_to_golden.py — 將 /review 結案的 HR_Data_Summary.csv(12欄) 追加至回歸黃金集

用途：
  /review 結案後，把本批已審閱定案的候選人納入 references/historical_selections.csv，
  供 regression_check.py 跨批次回歸守門（保護本批人類判決不被未來規則變更悄悄翻盤）。
  此腳本為 2026-07-15 Batch #51 /review 發現的工具缺口(唯一腳本原則)升格而來。

用法：
  python append_review_to_golden.py --role=default --batch=default-2026-07-15-review
  python append_review_to_golden.py --role=default --batch=... --csv=HR_Data_Summary.csv
  python append_review_to_golden.py --role=default --batch=... --dry-run   # 只預覽不寫入
  python append_review_to_golden.py --role=default --batch=... --force     # 允許重複 batch 覆蓋式追加(慎用)

特性：
  - 冪等守門：若 --batch 已存在於 historical_selections.csv，預設中止(除非 --force)，避免重複灌入。
  - 欄位驗證：只接受已 /review 的 12 欄 CSV(含「審閱結果建議」「審閱排除理由簡述」)；
    10 欄(未 review) 直接中止並提示先跑 /review。
  - result 白名單：審閱結果建議 僅允許 正式候選/排除/降級觀察/碩士儲備，越權值中止。
  - 欄位映射：drop 序號/Email，prepend batch/角色，重排至 historical 欄序。
  - append-only：只在檔尾追加，不改動既有列；utf-8-sig 編碼(與 regression_check 一致)。
"""

import sys
import os
import io
import csv
import argparse

# Windows cp950 防呆：確保中文輸出不觸發 UnicodeEncodeError
if sys.stdout.encoding != 'utf-8':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

VALID_RESULTS = ['正式候選', '排除', '降級觀察', '碩士儲備']

# historical_selections.csv 權威欄序
GOLDEN_HEADER = ['batch', '角色', '姓名', '年紀', '語文能力', '學歷', '近期工作',
                 '近期工作內容', '總年資', '前二次任職公司', '審閱結果建議', '審閱排除理由簡述']

# /review 後 HR_Data_Summary.csv 必備欄(12 欄)
REQUIRED_CSV_COLS = ['序號', '姓名', '年紀', 'Email', '語文能力', '學歷', '近期工作',
                     '近期工作內容', '審閱結果建議', '總年資', '前二次任職公司', '審閱排除理由簡述']


def _project_root():
    base = os.path.dirname(os.path.abspath(__file__))
    return os.path.normpath(os.path.join(base, '..', '..', '..', '..'))


def _golden_path():
    base = os.path.dirname(os.path.abspath(__file__))
    return os.path.normpath(os.path.join(base, '..', 'references', 'historical_selections.csv'))


def halt(msg):
    """Halt on Error：印出錯誤並以非零碼中止（符合專案憲法「阻斷錯誤蔓延」原則）。"""
    print(f"❌ 中止：{msg}")
    sys.exit(1)


def main():
    parser = argparse.ArgumentParser(
        description='將 /review 結案的 HR_Data_Summary.csv 追加至回歸黃金集 historical_selections.csv',
        epilog='範例: python append_review_to_golden.py --role=default --batch=default-2026-07-15-review'
    )
    parser.add_argument('--role', required=True, help='角色(default / space-manager)')
    parser.add_argument('--batch', required=True, help='批次標記字串(如 default-2026-07-15-review)')
    parser.add_argument('--csv', default=None, help='來源 CSV 路徑(預設 專案根目錄/HR_Data_Summary.csv)')
    parser.add_argument('--dry-run', action='store_true', help='只預覽將追加的列，不實際寫入')
    parser.add_argument('--force', action='store_true', help='允許 batch 已存在時仍追加(慎用)')
    args = parser.parse_args()

    src_csv = args.csv if args.csv else os.path.join(_project_root(), 'HR_Data_Summary.csv')
    golden = _golden_path()

    if not os.path.isfile(src_csv):
        halt(f"找不到來源 CSV：{src_csv}")
    if not os.path.isfile(golden):
        halt(f"找不到黃金集：{golden}")

    # --- 讀來源 CSV ---
    with open(src_csv, 'r', encoding='utf-8-sig', newline='') as f:
        reader = csv.DictReader(f)
        src_cols = reader.fieldnames or []
        src_rows = list(reader)

    # 欄位驗證：必須是已 /review 的 12 欄
    missing = [c for c in REQUIRED_CSV_COLS if c not in src_cols]
    if missing:
        if '審閱結果建議' in missing or '審閱排除理由簡述' in missing:
            halt(f"來源 CSV 缺少審閱欄位 {missing} —— 這份 CSV 似乎尚未 /review。請先完成 /review(apply_review_decisions.py)再追加。")
        halt(f"來源 CSV 缺少必要欄位：{missing}")

    if not src_rows:
        halt("來源 CSV 無資料列。")

    # result 白名單驗證
    bad = [(r.get('序號', '?'), r.get('姓名', '?'), r.get('審閱結果建議', ''))
           for r in src_rows if r.get('審閱結果建議', '').strip() not in VALID_RESULTS]
    if bad:
        detail = '; '.join(f"{s}_{n}={v!r}" for s, n, v in bad[:5])
        halt(f"發現越權/空白的審閱結果建議值(合法僅 {VALID_RESULTS})：{detail}")

    # --- 冪等守門：batch 是否已存在 ---
    with open(golden, 'r', encoding='utf-8-sig', newline='') as f:
        greader = csv.DictReader(f)
        golden_header = greader.fieldnames or []
        existing_batches = set(row.get('batch', '') for row in greader)

    if golden_header != GOLDEN_HEADER:
        halt(f"黃金集欄序與預期不符，為安全起見中止。\n  預期: {GOLDEN_HEADER}\n  實際: {golden_header}")

    if args.batch in existing_batches and not args.force:
        halt(f"batch '{args.batch}' 已存在於黃金集(冪等守門)。若確定要重複追加請加 --force。")

    # --- 建構 historical 列(欄位映射) ---
    new_rows = []
    for r in src_rows:
        new_rows.append({
            'batch': args.batch,
            '角色': args.role,
            '姓名': r.get('姓名', ''),
            '年紀': r.get('年紀', ''),
            '語文能力': r.get('語文能力', ''),
            '學歷': r.get('學歷', ''),
            '近期工作': r.get('近期工作', ''),
            '近期工作內容': r.get('近期工作內容', ''),
            '總年資': r.get('總年資', ''),
            '前二次任職公司': r.get('前二次任職公司', ''),
            '審閱結果建議': r.get('審閱結果建議', '').strip(),
            '審閱排除理由簡述': r.get('審閱排除理由簡述', ''),
        })

    # --- 統計摘要 ---
    from collections import Counter
    stat = Counter(row['審閱結果建議'] for row in new_rows)
    print(f"📋 來源：{os.path.basename(src_csv)}  /  角色：{args.role}  /  批次：{args.batch}")
    print(f"   待追加 {len(new_rows)} 列，分類統計：")
    for k in VALID_RESULTS:
        if stat.get(k):
            print(f"     {k}：{stat[k]} 人")

    if args.dry_run:
        print("\n--- 🔎 DRY-RUN 預覽(前 5 列，不寫入) ---")
        for row in new_rows[:5]:
            print(f"   {args.batch} | {row['角色']} | {row['姓名']} | {row['審閱結果建議']} | "
                  f"{row['近期工作'][:30]} | 理由={row['審閱排除理由簡述'][:24]}")
        print(f"\n(dry-run) 未寫入。移除 --dry-run 即實際追加至 {os.path.basename(golden)}。")
        return

    # --- append-only 寫入 ---
    with open(golden, 'a', encoding='utf-8-sig', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=GOLDEN_HEADER)
        for row in new_rows:
            writer.writerow(row)

    print(f"\n✅ 已追加 {len(new_rows)} 列至黃金集：{golden}")
    print("   下一步建議：跑 regression_check.py 確認黃金集自洽(本批 result 應與現行規則判決一致)。")


if __name__ == '__main__':
    main()
