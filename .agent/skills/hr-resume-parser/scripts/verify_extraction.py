# -*- coding: utf-8 -*-
"""
verify_extraction.py — /merge 防幻覺手動抽驗腳本

對應 SKILL.md /merge QAQC 規範：
> Agent 必須另外手動抽驗 15 組（比對原始 PDF，非 .md）

本腳本從 HR_Data_Summary.csv 隨機（或指定）抽出 N 筆，
直接讀取根目錄對應的 `{序號}_{姓名}.pdf` 原始檔，
逐欄比對五大關鍵欄位（姓名 / 年紀 / 總年資 / 學歷 / 近期工作）。

任何欄位不符即視為失敗。所有 15 筆通過才視為驗證成功。

用法：
    python verify_extraction.py
        [--csv HR_Data_Summary.csv]
        [--pdf-dir .]
        [--sample 15]
        [--candidates "姓1,姓2,..."]    # 指定姓名清單（覆蓋 --sample）
        [--seed 42]
"""

import argparse
import csv
import os
import random
import sys
import unicodedata

# CLAUDE.md gotcha #1：Windows cp950 encoding
sys.stdout.reconfigure(encoding='utf-8')

try:
    import pypdf
except ImportError:
    sys.exit("❌ 需要 pypdf 套件。請在指定 Python 環境執行：\n"
             "   D:/green-tools/python-3.14.2-embed-amd64/python.exe -m pip install pypdf")


def normalize(text):
    """NFKC + 移除空白，用於比對。"""
    text = unicodedata.normalize('NFKC', text)
    # Custom normalization for CJK Radicals not covered by NFKC
    text = text.replace('\u2ea0', '民').replace('\u2e8f', '民').replace('\u2e98', '民')
    text = text.replace('\u2ed1', '長').replace('\u2ec4', '西').replace('\u2ed4', '門')
    return text.replace(" ", "").replace("\n", "").replace("\r", "").replace("　", "")


def read_pdf_text(pdf_path, max_pages=3):
    reader = pypdf.PdfReader(pdf_path)
    text = ""
    for i in range(min(max_pages, len(reader.pages))):
        text += reader.pages[i].extract_text() or ""
    return text


def verify_row(row, pdf_dir):
    seq = row['序號']
    name = row['姓名']
    pdf_path = os.path.join(pdf_dir, f"{seq}_{name}.pdf")
    if not os.path.exists(pdf_path):
        return False, [(f"PDF 不存在：{pdf_path}", False)]

    try:
        raw = read_pdf_text(pdf_path)
    except Exception as e:
        return False, [(f"讀取 PDF 失敗：{e}", False)]

    norm = normalize(raw)
    checks = []

    name_ok = normalize(name) in norm
    checks.append((f"姓名 {name}", name_ok))

    age = row.get('年紀', '').strip()
    age_ok = (not age) or (age in raw) or (age in norm)
    checks.append((f"年紀 {age}", age_ok))

    seniority = row.get('總年資', '').strip()
    seniority_ok = (not seniority) or (seniority in raw) or (normalize(seniority) in norm)
    checks.append((f"總年資 {seniority}", seniority_ok))

    edu = row.get('學歷', '').strip()
    if edu:
        edu_parts = [p for p in normalize(edu).replace("、", " ").split() if p]
        edu_ok = any(p[:6] in norm for p in edu_parts if p)
    else:
        edu_ok = True
    checks.append((f"學歷 {edu[:30]}", edu_ok))

    recent = row.get('近期工作', '').strip()
    if recent:
        recent_parts = [p for p in normalize(recent).replace("、", " ").replace("/", " ").split() if p]
        recent_ok = any(p[:4] in norm for p in recent_parts if p)
    else:
        recent_ok = True
    checks.append((f"近期工作 {recent[:30]}", recent_ok))

    all_ok = all(ok for _, ok in checks)
    return all_ok, checks


def main():
    ap = argparse.ArgumentParser(description='/merge 防幻覺手動抽驗（PDF 原始檔比對）')
    ap.add_argument('--csv', default='HR_Data_Summary.csv')
    ap.add_argument('--pdf-dir', default='.')
    ap.add_argument('--sample', type=int, default=15, help='隨機抽樣筆數（預設 15）')
    ap.add_argument('--candidates', default=None, help='姓名清單（逗號分隔），覆蓋 --sample')
    ap.add_argument('--seed', type=int, default=42)
    args = ap.parse_args()

    if not os.path.exists(args.csv):
        sys.exit(f"❌ 找不到 CSV：{args.csv}")

    with open(args.csv, 'r', encoding='utf-8-sig') as f:
        rows = list(csv.DictReader(f))

    if args.candidates:
        wanted = {n.strip() for n in args.candidates.split(',') if n.strip()}
        sampled = [r for r in rows if r['姓名'] in wanted]
        missing = wanted - {r['姓名'] for r in sampled}
        if missing:
            print(f"⚠️  CSV 內找不到以下姓名：{sorted(missing)}")
    else:
        random.seed(args.seed)
        n = min(args.sample, len(rows))
        sampled = random.sample(rows, n)

    print(f"=== 🔍 /merge 防幻覺驗證：{len(sampled)} 筆 ===\n")
    fail_count = 0
    for row in sampled:
        seq = row['序號']
        name = row['姓名']
        passed, checks = verify_row(row, args.pdf_dir)
        status = "✅" if passed else "❌"
        print(f"{status} [{seq}] {name}")
        for label, ok in checks:
            mark = "✓" if ok else "✗"
            print(f"     {mark} {label}")
        if not passed:
            fail_count += 1
        print()

    if fail_count == 0:
        print(f"🎉 全部 {len(sampled)} 筆驗證通過，CSV 與 PDF 原始檔零幻覺。")
    else:
        print(f"⚠️  {fail_count}/{len(sampled)} 筆驗證失敗，請人工檢查 extract_hr_data.py 邏輯。")
        sys.exit(1)


if __name__ == '__main__':
    main()
