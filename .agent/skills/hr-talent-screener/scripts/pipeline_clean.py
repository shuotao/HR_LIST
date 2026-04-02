# -*- coding: utf-8 -*-
"""
pipeline_clean.py — ANALYSIS.md 三階段清洗管線

階段一：移除 104 系統雜訊
階段二：以代碼為唯一鍵去除重複候選人
階段三：依學歷科系分三區塊重新排序

用法：python pipeline_clean.py <ANALYSIS.md 路徑>
"""

import sys
import re
import os
import io

if sys.stdout.encoding != 'utf-8':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')


# ============================
# 階段一：雜訊移除
# ============================
def stage1_remove_noise(lines):
    """逐行比對，移除 104 系統的固定雜訊文字。"""

    # 以下字串是 104 人力銀行網頁擷取時混入的系統文字（版權宣告、按鈕、狀態標籤等），
    # 不屬於候選人資料，必須逐行比對移除。
    noise_exact = {
        "一零四資訊科技股份有限公司 版權所有 © 2026 建議瀏覽器 Chrome / IE11.0 以上",
        "會員須知 本系統提供之履歷僅供徵才目的使用，請勿違法蒐集或利用，以免觸犯個人資料保護法",
        "read讀取紀錄僅保留近 60 天點閱動作",
        "重要通知：2026/04/01(三) 19:00 起 廣告暫停/關閉權限將進行調整 調整說明",
        "全部",
        "｜",
        "已讀",
        "未讀",
    }

    # 104 系統上方選單列（連續多行），以整塊比對移除
    menu_block_lines = [
        "招募管理", "人才管理", "人資市集", "人資充電", "企業學習平台",
        "雇主品牌", "招募管理", "請輸入關鍵字",
        "中鼎集團_中鼎工程股份有限公司", "江碩濤",
        "首頁", "公司", "職務", "查詢", "履歷", "甄試",
        "聯絡", "數據", "購買", "設定", "更多",
    ]

    removed_count = 0
    cleaned = []

    for line in lines:
        stripped = line.strip()
        if stripped in noise_exact:
            removed_count += 1
            continue
        cleaned.append(line)

    # 移除連續選單區塊
    content = "\n".join(cleaned)
    menu_block = "\n".join(menu_block_lines)
    occurrences = content.count(menu_block)
    content = content.replace(menu_block, "")
    removed_count += occurrences * len(menu_block_lines)

    # 清除連續三行以上的空行
    content = re.sub(r'\n{3,}', '\n\n', content)

    return content.split("\n"), removed_count


# ============================
# 階段二：重複人選剃除
# ============================
def stage2_deduplicate(lines):
    """以「代碼：」行的數字為唯一 ID，保留首次出現的區塊。"""

    id_indices = []
    for i, line in enumerate(lines):
        if line.startswith("代碼："):
            id_indices.append(i)

    if not id_indices:
        return lines, 0, 0

    # 候選人區塊結構：「代碼：」行的前 4 行是該候選人的 header（姓名、性別年齡、更新日等）
    # 因此每位候選人的起始位置 = 代碼行 - 4
    first_start = max(0, id_indices[0] - 4)
    header = lines[:first_start]

    seen = set()
    kept_blocks = []
    dup_count = 0

    for idx, id_line_num in enumerate(id_indices):
        # 每位候選人區塊：從代碼行前 4 行開始，到下一位候選人的代碼行前 4 行結束
        start = max(0, id_line_num - 4)
        end = max(0, id_indices[idx + 1] - 4) if idx + 1 < len(id_indices) else len(lines)

        match = re.search(r'代碼：(\d+)', lines[id_line_num])
        if match:
            uid = match.group(1)
            if uid not in seen:
                seen.add(uid)
                kept_blocks.append(lines[start:end])
            else:
                dup_count += 1
        else:
            kept_blocks.append(lines[start:end])

    result = header[:]
    for block in kept_blocks:
        result.extend(block)

    return result, len(seen), dup_count


# ============================
# 階段三：學歷背景分類排序
# ============================
G1_KEYWORDS = ['土木', '建築', '營建', '景觀', '都市計畫']
G2_KEYWORDS = [
    '水處裡', '水處理', '水電', '環工', '環境工程', '機電', '電機',
    '機械', '動力機械', '電力', '化學', '化工', '氣體', '空調',
    '冷凍空調', '冷凍', '管線', '配管', '自動化', '能源', '輪機',
]

SKIP_PREFIXES = ('希望工作地', '居住地', '希望職稱', '甄試歷程')


def _find_edu_line(block):
    """從候選人區塊中定位學歷行。"""
    for j in range(5, min(12, len(block))):
        line = block[j]
        if any(line.startswith(p) for p in SKIP_PREFIXES):
            continue
        if '工作經驗' in line and len(line) < 20:
            continue
        return line
    return ""


def stage3_classify_sort(lines):
    """將候選人依學歷分三區塊並重新排序。"""

    id_indices = []
    for i, line in enumerate(lines):
        if line.startswith("代碼："):
            id_indices.append(i)

    if not id_indices:
        return lines, 0, 0, 0

    header = lines[:max(0, id_indices[0] - 4)]
    g1, g2, g3 = [], [], []

    for idx, id_line_num in enumerate(id_indices):
        start = max(0, id_line_num - 4)
        end = max(0, id_indices[idx + 1] - 4) if idx + 1 < len(id_indices) else len(lines)
        block = lines[start:end]
        edu = _find_edu_line(block)

        is_g1 = any(k in edu for k in G1_KEYWORDS)
        is_g2 = any(k in edu for k in G2_KEYWORDS)

        # 分類優先順序：G2(機電) > G1(土木) > G3(其他)
        # 若同時命中 G1+G2（如「土木+機電」雙學位），優先歸入 G2（機電是核心需求）
        if is_g1 and not is_g2:
            g1.append(block)
        elif is_g2:
            g2.append(block)
        else:
            g3.append(block)

    result = header[:]
    for label, group in [
        (f"【第一區塊：土木、建築相關背景】 (共 {len(g1)} 名)", g1),
        (f"【第二區塊：水處理、機電、電機、機械、電力、化學、氣體、空調、管線等相關背景】 (共 {len(g2)} 名)", g2),
        (f"【第三區塊：其他非上述相關背景】 (共 {len(g3)} 名)", g3),
    ]:
        result.append("")
        result.append("## ==========================================================")
        result.append(f"## {label}")
        result.append("## ==========================================================")
        result.append("")
        for block in group:
            result.extend(block)

    return result, len(g1), len(g2), len(g3)


# ============================
# 主流程
# ============================
def main():
    if len(sys.argv) < 2:
        print("用法: python pipeline_clean.py <ANALYSIS.md路徑>")
        sys.exit(1)

    filepath = sys.argv[1]
    if not os.path.isfile(filepath):
        print(f"錯誤：找不到檔案 {filepath}")
        sys.exit(1)

    with open(filepath, 'r', encoding='utf-8') as f:
        raw = f.read().replace('\r\n', '\n')
    lines = raw.split('\n')
    total_before = len(lines)

    print("=" * 60)
    print("ANALYSIS.md 三階段清洗管線")
    print("=" * 60)
    print(f"原始行數: {total_before}")

    # 階段一
    lines, noise_removed = stage1_remove_noise(lines)
    print(f"\n[階段一 雜訊移除] 移除了 {noise_removed} 行雜訊文字")

    # 階段二
    lines, unique_count, dup_count = stage2_deduplicate(lines)
    print(f"[階段二 去重] 唯一候選人: {unique_count}, 移除重複: {dup_count}")

    # 階段三
    lines, g1, g2, g3 = stage3_classify_sort(lines)
    print(f"[階段三 分類] G1(土木建築): {g1}, G2(機電相關): {g2}, G3(其他): {g3}")

    with open(filepath, 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines))

    print(f"\n清洗完成。最終行數: {len(lines)}")
    print("=" * 60)


if __name__ == '__main__':
    main()
