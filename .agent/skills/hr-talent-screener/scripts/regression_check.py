# -*- coding: utf-8 -*-
"""
regression_check.py — 黃金集回歸測試（規則變更守門員）

對應 CLAUDE.md「閘門機制」：每次修改 screening_rules.md / role_overlays /
screen_candidates.py 之後必跑本腳本。以 references/historical_selections.csv
（歷史已確認的選人紀錄）為黃金集，逐列重跑 score_candidate，偵測規則變更
是否讓「歷史已確認的判決」翻盤。

baseline 機制（吸收 CSV 摘要 vs 完整履歷的既存誤差）：
- 歷史 CSV 只有 /merge 摘要欄位，資訊量低於完整 .md 履歷（work_lines 無日期
  區間，年資類規則會有系統性誤差），因此「絕對判決 vs 確認欄」的既存 mismatch
  是預期內的。
- 首次執行自動建立 references/regression_baseline.json，記錄每人當前判決與
  match 狀態，吸收全部既存誤差。
- 之後預設模式只對「新翻盤」FAIL：baseline 中 match=true 的人，在新規則下
  變成 mismatch（歷史確認正式候選被新規則排除，或反之）。
- 使用者核准翻盤（該翻盤是刻意的規則效果）後，以 --accept 更新 baseline。

判決對映：
- 引擎輸出：is_excluded 或 分數 < 門檻 → 「排除」；否則「正式候選」。
- 確認欄（審閱結果建議）：「排除」→ 期望排除；「正式候選」或空值 → 期望正式
  候選（歷史檔本質是已確認入選名單）；「降級觀察」「碩士儲備」→ 引擎無法表達
  此二值，跳過不比對（計入 skipped）。

用法：
    python regression_check.py
        [--csv <路徑，預設 references/historical_selections.csv>]
        [--baseline <路徑，預設 references/regression_baseline.json>]
        [--threshold 30]
        [--accept]        # 把當前結果寫入 baseline（需使用者核准後才可用）

退出碼：0 = PASS（無新翻盤）；1 = FAIL（有新翻盤，列出名單）；2 = 資料/環境錯誤
"""

import argparse
import csv
import json
import os
import re
import sys

# CLAUDE.md gotcha #1：Windows cp950 encoding
sys.stdout.reconfigure(encoding='utf-8')

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SCRIPT_DIR)
from screen_candidates import score_candidate, get_overlay  # noqa: E402

REF_DIR = os.path.normpath(os.path.join(SCRIPT_DIR, '..', 'references'))
DEFAULT_CSV = os.path.join(REF_DIR, 'historical_selections.csv')
DEFAULT_BASELINE = os.path.join(REF_DIR, 'regression_baseline.json')

# 引擎可表達的判決二值；確認欄的另兩個合法值跳過不比對
ENGINE_VERDICTS = ('正式候選', '排除')
SKIP_CONFIRMED = ('降級觀察', '碩士儲備')


def classify_group(edu):
    """學歷分群，與 generate_review_decisions.parse_md_to_candidate 一致。"""
    edu_lower = (edu or '').lower()
    if any(k in edu_lower for k in ["電機", "機械", "冷凍", "空調", "機電", "電子", "輪機", "化學", "環工", "環境工程"]):
        return "G2_機電相關"
    if any(k in edu_lower for k in ["土木", "建築", "營建"]):
        return "G1_土木建築"
    return "G3_其他"


def row_to_candidate(row):
    """把 historical_selections.csv 一列拼成 score_candidate 期望的 dict。

    限制：CSV 無日期區間，work_lines 的 get_line_years 一律為 0，年資類規則
    （M3/D6b 等）會系統性偏保守——由 baseline 機制吸收，本函式不偽造日期。
    """
    recent = (row.get('近期工作') or '').strip()
    prev_raw = (row.get('前二次任職公司') or '').strip()

    # 把「總年資」欄編碼成 get_line_years 讀得懂的 (X年Y個月) 格式附掛在
    # 第一段工作上——CSV 無逐段日期，若不編碼，_is_frequent_jumper 會把
    # 所有人誤判為短期跳槽（全段 0 年），年資類規則全面失真。
    work_lines = []
    if recent:
        line0 = recent
        m_yrs = re.search(r'(\d+(?:\.\d+)?)', (row.get('總年資') or '').strip())
        if m_yrs:
            total = float(m_yrs.group(1))
            yr, mo = int(total), round((total - int(total)) * 12)
            line0 = f"{recent} ({yr}年{mo}個月)" if mo else f"{recent} ({yr}年)"
        work_lines.append(line0)
    for token in re.split(r'[、,，/；;]', prev_raw):
        token = token.strip()
        if token and token not in ('無', '-', '—'):
            work_lines.append(token)

    full_text = '\n'.join(x for x in [
        (row.get('姓名') or '').strip(),
        f"{(row.get('年紀') or '').strip()}歲" if (row.get('年紀') or '').strip() else '',
        row.get('學歷') or '',
        row.get('語文能力') or '',
        recent,
        row.get('近期工作內容') or '',
        prev_raw,
        f"總年資{(row.get('總年資') or '').strip()}年" if (row.get('總年資') or '').strip() else '',
    ] if x)

    return {
        'name': (row.get('姓名') or '').strip(),
        'age': (row.get('年紀') or '').strip(),
        'edu': row.get('學歷') or '',
        'desired_title': '',
        'work_lines': work_lines,
        'full_text': full_text,
        'group': classify_group(row.get('學歷')),
    }


def expected_verdict(row):
    """確認欄 → 期望判決；回傳 None 表示跳過不比對。"""
    confirmed = (row.get('審閱結果建議') or '').strip()
    if confirmed in SKIP_CONFIRMED:
        return None
    if confirmed == '排除':
        return '排除'
    return '正式候選'  # 「正式候選」或空值（歷史入選名單）


def main():
    ap = argparse.ArgumentParser(description='黃金集回歸測試（規則變更守門員）')
    ap.add_argument('--csv', default=DEFAULT_CSV, help='歷史選人 CSV 路徑')
    ap.add_argument('--baseline', default=DEFAULT_BASELINE, help='baseline JSON 路徑')
    ap.add_argument('--threshold', type=int, default=30, help='正式候選分數門檻（與 generate_review_decisions 一致）')
    ap.add_argument('--accept', action='store_true', help='把當前結果寫入 baseline（需使用者核准）')
    args = ap.parse_args()

    if not os.path.exists(args.csv):
        print(f"❌ 找不到歷史 CSV：{args.csv}")
        sys.exit(2)

    with open(args.csv, 'r', encoding='utf-8-sig') as f:
        rows = list(csv.DictReader(f))
    if not rows:
        print("❌ 歷史 CSV 無資料列")
        sys.exit(2)

    overlay_cache = {}

    def overlay_for(role):
        role = (role or 'default').strip() or 'default'
        if role not in overlay_cache:
            try:
                overlay_cache[role] = get_overlay(role)
            except Exception:
                # 未知角色（含歷史遺留值）一律 fallback default，與 mep-design 慣例一致
                print(f"⚠️  未知角色「{role}」，fallback 至 default overlay")
                overlay_cache[role] = get_overlay('default')
        return overlay_cache[role]

    entries = {}
    skipped = 0
    seen_keys = {}
    for row in rows:
        expected = expected_verdict(row)
        if expected is None:
            skipped += 1
            continue

        c = row_to_candidate(row)
        score, reasons, is_excluded = score_candidate(c, overlay=overlay_for(row.get('角色')))
        if is_excluded:
            computed = '排除'
            trigger = reasons[0] if reasons else '命中排除條件'
        elif score < args.threshold:
            computed = '排除'
            trigger = f'未達門檻（分數={score} < {args.threshold}）'
        else:
            computed = '正式候選'
            trigger = ''

        key = f"{(row.get('batch') or '').strip()}|{c['name']}"
        if key in seen_keys:
            seen_keys[key] += 1
            key = f"{key}#{seen_keys[key]}"
        else:
            seen_keys[key] = 1

        entries[key] = {
            'expected': expected,
            'computed': computed,
            'match': computed == expected,
            'score': score,
            'trigger': trigger,
            'role': (row.get('角色') or 'default').strip() or 'default',
        }

    total = len(entries)
    mismatch_now = sum(1 for e in entries.values() if not e['match'])
    print(f"📋 黃金集：{total} 筆比對（另 {skipped} 筆為降級觀察/碩士儲備，跳過）")
    print(f"   門檻：{args.threshold}　當前 mismatch：{mismatch_now} 筆")

    if not os.path.exists(args.baseline):
        with open(args.baseline, 'w', encoding='utf-8') as f:
            json.dump({'threshold': args.threshold, 'entries': entries}, f, ensure_ascii=False, indent=1)
        print(f"\n🆕 首次執行：baseline 已建立（{args.baseline}）")
        print(f"   既存誤差 {mismatch_now} 筆已吸收為已知狀態（CSV 摘要資訊量限制所致）。")
        print("✅ PASS（baseline 初始化）")
        sys.exit(0)

    with open(args.baseline, 'r', encoding='utf-8') as f:
        baseline = json.load(f)
    base_entries = baseline.get('entries', {})

    new_flips = []      # baseline match=true → 現在 mismatch（回歸！）
    improvements = []   # baseline mismatch → 現在 match（規則變準了）
    drift = []          # baseline 就 mismatch、判決又變了（中性漂移）
    new_rows_bad = []   # baseline 沒有的新列且 mismatch（警告，不 FAIL）

    for key, e in entries.items():
        b = base_entries.get(key)
        if b is None:
            if not e['match']:
                new_rows_bad.append((key, e))
            continue
        if b['match'] and not e['match']:
            new_flips.append((key, b, e))
        elif not b['match'] and e['match']:
            improvements.append((key, b, e))
        elif not b['match'] and not e['match'] and b['computed'] != e['computed']:
            drift.append((key, b, e))

    removed = [k for k in base_entries if k not in entries]

    if improvements:
        print(f"\n📈 改善 {len(improvements)} 筆（原本誤差、新規則下與確認結果一致了）：")
        for key, b, e in improvements[:10]:
            print(f"   {key}  {b['computed']} → {e['computed']}（確認={e['expected']}）")
    if drift:
        print(f"\n↔️  中性漂移 {len(drift)} 筆（原本就誤差，判決值改變但仍不一致）")
    if new_rows_bad:
        print(f"\n⚠️  新增列 mismatch {len(new_rows_bad)} 筆（不計 FAIL，下次 --accept 時吸收）：")
        for key, e in new_rows_bad[:10]:
            print(f"   {key}  引擎={e['computed']} vs 確認={e['expected']}")
    if removed:
        print(f"\n⚠️  baseline 有但 CSV 已無 {len(removed)} 筆（歷史檔應為 append-only，請查明）")

    if args.accept:
        with open(args.baseline, 'w', encoding='utf-8') as f:
            json.dump({'threshold': args.threshold, 'entries': entries}, f, ensure_ascii=False, indent=1)
        print(f"\n💾 --accept：baseline 已更新（吸收當前 {mismatch_now} 筆 mismatch）")

    if new_flips:
        print(f"\n🚨 FAIL — 新翻盤 {len(new_flips)} 筆（歷史已確認判決被新規則推翻）：")
        for key, b, e in new_flips:
            print(f"   {key} [{e['role']}]  {b['computed']} → {e['computed']}（確認={e['expected']}，分數={e['score']}）")
            if e['trigger']:
                print(f"      觸發：{e['trigger']}")
        print("\n   → 若翻盤為刻意的規則效果，請使用者核准後執行 --accept；否則退回修正規則。")
        sys.exit(1)

    print("\n✅ PASS — 無新翻盤，規則變更未破壞歷史已確認判決")
    sys.exit(0)


if __name__ == '__main__':
    main()
