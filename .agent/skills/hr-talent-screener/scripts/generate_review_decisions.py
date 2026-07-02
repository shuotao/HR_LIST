# -*- coding: utf-8 -*-
"""
generate_review_decisions.py — /review 結案決策產生腳本

對應 SKILL.md 步驟 5（結案審閱）。
本腳本掃描 HR_Data_Summary.csv 內每位候選人，從根目錄對應的 `{序號}_{姓名}.md`
讀取完整履歷，重跑 v10.x 篩選引擎（screen_candidates.score_candidate），
依分數與排除旗標自動產生 review_decisions.json。

對應 CLAUDE.md /review 步驟 1：
> Agent 地毯式掃描 HR_Data_Summary.csv（用對應 role 的評分維度），
> 整理判決成 review_decisions.json。

本腳本提供基線判決，Agent 可在執行後人工複核 / 微調 JSON，再交給
apply_review_decisions.py 寫入 CSV。

用法：
    python generate_review_decisions.py
        [--role default|space-manager]
        [--csv HR_Data_Summary.csv]
        [--md-dir .]
        [--output review_decisions.json]
        [--threshold 30]
"""

import argparse
import csv
import json
import os
import re
import sys
import unicodedata

# CLAUDE.md gotcha #1：Windows cp950 encoding
sys.stdout.reconfigure(encoding='utf-8')

# 確保能 import screen_candidates
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SCRIPT_DIR)
from screen_candidates import score_candidate, get_overlay, SUPPORTED_ROLES  # noqa: E402

VALID_RESULTS = {'正式候選', '排除', '降級觀察', '碩士儲備'}


def normalize_text(text):
    """CLAUDE.md gotcha #2：MarkItDown 康熙部首 + 分頁符。"""
    text = unicodedata.normalize('NFKC', text)
    text = text.replace('\u2ea0', '民').replace('\u2e8f', '民')
    text = text.replace('\u2ed1', '長').replace('\u2ec4', '西').replace('\u2ed4', '門')
    return text.replace('\x0c', '\n').replace('\r', '\n')


# 104 履歷頂部固定樣板（使用公司/使用規範宣告）——會把「中鼎」注入 full_text，
# 使 score_candidate 中所有「中鼎 in full / PREMIUM in full」豁免被騙過（每位候選人
# 都被誤判有中鼎 EPC 背景）。/filter 路徑由 pipeline_clean 清除，/review 路徑必須在此比照清除。
_BOILERPLATE_MARKERS = (
    '中鼎集團_中鼎', '履歷使用公司', '本人同意本履歷', '使用人員', '使用時間',
    '履歷使用規範', '除事先告知', '第三方AI', '為保障資訊安全', '令規定',
)


def strip_boilerplate(content):
    """移除 104 頂部樣板宣告行（雜訊移除，比照 pipeline_clean stage1）。
    注意：只清頂部固定宣告，不動候選人的「甄試歷程」段落（@ctci.com VIP 訊號在該處）。"""
    kept = [l for l in content.split('\n') if not any(m in l for m in _BOILERPLATE_MARKERS)]
    return '\n'.join(kept)


def parse_md_to_candidate(md_path, name):
    """把單一 .md 履歷解析成 score_candidate 期望的 dict 結構。"""
    with open(md_path, 'r', encoding='utf-8') as f:
        content = strip_boilerplate(normalize_text(f.read()))
    lines = [l.strip() for l in content.split('\n') if l.strip()]

    age = ""
    for line in lines[:30]:
        m = re.search(r'(\d+)歲', line)
        if m:
            age = m.group(1)
            break

    edu = ""
    for i, line in enumerate(lines):
        if "最高學歷" in line and i + 1 < len(lines):
            edu = lines[i + 1]
            break
    if not edu:
        for i, line in enumerate(lines):
            if "教育背景" in line and i + 1 < len(lines):
                edu = lines[i + 1]
                break

    desired_title = ""
    for i, line in enumerate(lines):
        if line.startswith("希望職稱") and i + 1 < len(lines):
            desired_title = lines[i + 1] if not line.replace("希望職稱", "").strip() else line
            break

    work_lines = [l for l in lines if re.search(r'\d{4}/\d{2}~', l)]

    # 學歷分群（與 pipeline_clean.py 一致）
    edu_lower = edu.lower()
    if any(k in edu_lower for k in ["電機", "機械", "冷凍", "空調", "機電", "電子", "輪機", "化學", "環工", "環境工程"]):
        group = "G2_機電相關"
    elif any(k in edu_lower for k in ["土木", "建築", "營建"]):
        group = "G1_土木建築"
    else:
        group = "G3_其他"

    return {
        'name': name,
        'age': age,
        'edu': edu,
        'desired_title': desired_title,
        'work_lines': work_lines,
        'full_text': content,
        'group': group,
    }


def main():
    ap = argparse.ArgumentParser(description='/review 決策自動產生器（v9.2 雙角色架構）')
    ap.add_argument('--role', default='default', choices=SUPPORTED_ROLES,
                    help='角色 overlay（預設 default = MEP）')
    ap.add_argument('--csv', default='HR_Data_Summary.csv', help='CSV 檔路徑')
    ap.add_argument('--md-dir', default='.', help='Markdown 履歷所在資料夾')
    ap.add_argument('--output', default='review_decisions.json', help='輸出 JSON 路徑')
    ap.add_argument('--threshold', type=int, default=30, help='正式候選分數門檻（< 此值標為排除）')
    args = ap.parse_args()

    if not os.path.exists(args.csv):
        sys.exit(f"❌ 找不到 CSV：{args.csv}")

    overlay = get_overlay(args.role)
    print(f"📋 角色：{args.role}  /  門檻：{args.threshold}")

    with open(args.csv, 'r', encoding='utf-8-sig') as f:
        rows = list(csv.DictReader(f))

    decisions = {}
    missing_md = []
    for row in rows:
        seq = row['序號']
        name = row['姓名']
        md_path = os.path.join(args.md_dir, f"{seq}_{name}.md")
        if not os.path.exists(md_path):
            alt_name = name.replace('⺠', '民') if '⺠' in name else name.replace('民', '⺠')
            md_path = os.path.join(args.md_dir, f"{seq}_{alt_name}.md")
            
        if not os.path.exists(md_path):
            missing_md.append((seq, name))
            decisions[seq] = {"result": "正式候選", "reason": ""}
            continue

        c = parse_md_to_candidate(md_path, name)
        score, reasons, is_excluded = score_candidate(c, overlay=overlay)

        if is_excluded:
            result = "排除"
            reason = reasons[0] if reasons else "命中排除條件"
        elif score < args.threshold:
            result = "排除"
            reason = f"未達門檻（分數={score} < {args.threshold}）"
        else:
            result = "正式候選"
            reason = ""

        decisions[seq] = {"result": result, "reason": reason}
        print(f"  [{seq}] {name}  分數={score}  →  {result}  {reason}")

    if missing_md:
        print(f"\n⚠️  以下 {len(missing_md)} 筆找不到對應 .md，已預設標為「正式候選」（請人工複核）：")
        for seq, name in missing_md:
            print(f"     [{seq}] {name}")

    output_data = {"role": args.role, "decisions": decisions}
    with open(args.output, 'w', encoding='utf-8') as f:
        json.dump(output_data, f, ensure_ascii=False, indent=2)

    counts = {}
    for d in decisions.values():
        counts[d['result']] = counts.get(d['result'], 0) + 1
    print(f"\n--- 📊 自動判決統計 ---")
    for k in sorted(counts.keys()):
        print(f"  {k}：{counts[k]} 人")
    print(f"\n🎉 {args.output} 已產出（{len(decisions)} 筆）。下一步：")
    print(f"   python apply_review_decisions.py {args.output}")


if __name__ == '__main__':
    main()
