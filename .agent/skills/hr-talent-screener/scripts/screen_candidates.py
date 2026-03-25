# -*- coding: utf-8 -*-
"""
screen_candidates.py — 候選人篩選引擎

根據「人才候選計畫.md」中定義的規則，對清洗完的 ANALYSIS.md 進行評分篩選。
輸出符合條件的候選人姓名、所屬區塊與命中理由摘要。

用法：python screen_candidates.py <ANALYSIS.md 路徑>
"""

import sys
import re
import os
import io

# Ensure UTF-8 output on Windows terminals (prevents cp950 UnicodeEncodeError)
if sys.stdout.encoding != 'utf-8':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

# ============================
# 規則定義（來自人才候選計畫.md）
# ============================

# 必要條件 M1: 近期職稱關鍵字
TITLE_KEYWORDS = [
    '機電', '廠務', '空調', 'HVAC', '監造', '監工', '水處理', '純水',
    '廢水', '管線', '配管', '電機', '機械', '水電', '工程師', '主任',
    '副主任', '課長', '副理', '專案', '工務', '儀電', '技術員',
    '品管', '採購', '維運', '繪圖員', '襄理', '組長', '焊工', '營造工程師',
]

# 必要條件 M2: 產業/公司關鍵字
COMPANY_KEYWORDS = [
    '中鼎', '泰興', '仲量聯行', 'JLL', '達欣', '潤弘', '大林組',
    '營造', '建設', '台積', '世界先進', '美光', '聯電', '欣興',
    '長春', '亞東氣體', '東元', '中興電工', '士林電機', '能源',
    '半導體', '光電', 'EPC', '統包', '建廠', '擴廠',
    '大陸工程', '日月光', '力晶', '鴻海', '齊裕', '中麟', '閎大', '立穩',
    '臻鼎', '台灣神隆', '中聯資源', '泰創', '興富發', '日揮', '恩智浦',
]

# 加分條件 N1: 學歷科系關鍵字 (★★★)
EDU_KEYWORDS = [
    '電機', '機械', '冷凍空調', '冷凍', '空調', '化工', '化學',
    '環工', '環境工程', '環境', '土木', '建築', '營建', '能源',
    '輪機', '水電', '機電', '自動化', '動力',
]

# 加分條件 N2-N3: 知名公司 (★★★)
PREMIUM_COMPANIES = [
    '中鼎', '泰興', '達欣', '潤弘', '大林組', '仲量聯行', 'JLL',
    '台積', '世界先進', '美光', '聯電', '欣興', '長春', '亞東氣體',
    '大陸工程', '日月光', '力晶', '鴻海', '臻鼎', '台灣神隆', '日揮', '恩智浦',
]

# 加分條件 N4: 管理職關鍵字 (★★☆)
MGMT_KEYWORDS = ['主任', '課長', '副理', '經理', '協理', '處長', '總監']

# 加分條件 N5: 多系統工作內容關鍵字 (★★☆)
MULTISYS_KEYWORDS = [
    '空調', 'HVAC', '消防', '電力', '配電', '給排水', '純水', '廢水',
    '冰水主機', '冷卻水塔', '無塵室', '潔淨室', '管線', '配管',
    'BIM', 'Revit', 'AutoCAD', 'PLC', 'DCS', 'SCADA', 'DDC',
    '中央監控', '建廠', '擴廠', 'EPC', '統包', 'MEP', '五大管線',
    '機電', '變電', '發電機', 'UPS', 'P&ID',
    'BMS', 'BACnet', 'Modbus', '充電樁', '太陽能', '逆變器', '儲能',
    '高低壓', '變電站', '鋼構', '焊接', '品管', '查驗', '品質管理',
    '計價', '發包', '水污', '空污', '號誌', '軌道', '捷運',
]

# 排除條件
EXCLUDE_TITLES = [
    '保全', '門市', '餐飲', '銷售', '業務員', '店長', '服務生',
    '司機', '總幹事', '保險', '房仲', '理財',
]

SKIP_PREFIXES = ('希望工作地', '居住地', '甄試歷程')


# ============================
# 解析候選人區塊
# ============================
def parse_candidates(lines):
    """解析 ANALYSIS.md，將每位候選人封裝為字典。"""

    id_indices = []
    for i, line in enumerate(lines):
        if line.startswith("代碼："):
            id_indices.append(i)

    candidates = []

    group_ranges = []
    for i, line in enumerate(lines):
        if '【第一區塊' in line:
            group_ranges.append(('G1_土木建築', i))
        elif '【第二區塊' in line:
            group_ranges.append(('G2_機電相關', i))
        elif '【第三區塊' in line:
            group_ranges.append(('G3_其他', i))

    def get_group(line_num):
        g = '未分類'
        for g_name, g_start in group_ranges:
            if line_num >= g_start:
                g = g_name
        return g

    for idx, id_line_num in enumerate(id_indices):
        start = max(0, id_line_num - 4)
        end = max(0, id_indices[idx + 1] - 4) if idx + 1 < len(id_indices) else len(lines)
        block = lines[start:end]

        name = block[0].strip() if block else ""
        age = block[2].strip() if len(block) > 2 else ""

        # 找學歷行
        edu = ""
        for j in range(5, min(12, len(block))):
            bl = block[j]
            if any(bl.startswith(p) for p in SKIP_PREFIXES):
                continue
            if bl.startswith("希望職稱"):
                continue
            if '工作經驗' in bl and len(bl) < 20:
                continue
            edu = bl
            break

        # 找希望職稱
        desired_title = ""
        for j in range(5, min(15, len(block))):
            bl = block[j]
            if bl.startswith("希望職稱"):
                desired_title = bl
                break

        # 提取工作經歷行
        work_lines = []
        for j in range(5, len(block)):
            bl = block[j]
            if re.match(r'\d{4}/\d{2}', bl):
                work_lines.append(bl)

        # 全文（用於關鍵字搜尋）
        full_text = '\n'.join(block)

        group = get_group(id_line_num)

        candidates.append({
            'name': name,
            'age': age,
            'edu': edu,
            'desired_title': desired_title,
            'work_lines': work_lines,
            'full_text': full_text,
            'group': group,
        })

    return candidates


# ============================
# 評分引擎
# ============================
def score_candidate(c):
    """對單一候選人進行規則評分，回傳 (分數, 理由列表, 是否排除)。"""

    score = 0
    reasons = []
    full = c['full_text']
    edu = c['edu']
    desired = c['desired_title']
    first_work = c['work_lines'][0] if c['work_lines'] else ""

    # --- 排除條件 ---
    # E1: 經歷純粹為保全/門市/餐飲
    if desired:
        exclude_hit = [kw for kw in EXCLUDE_TITLES if kw in desired]
        # 只有當希望職稱「全部」都是排除字且沒有任何工程字時才排除
        has_eng = any(kw in desired for kw in ['工程', '技術', '機電', '廠務', '監造', '主任'])
        if exclude_hit and not has_eng:
            return 0, [f"排除(E1/E2): 希望職稱={desired[:30]}"], True

    # E2: 希望職稱完全與工程無關（另一層檢查）
    if desired and not any(kw in desired for kw in TITLE_KEYWORDS):
        # 但如果工作經歷中有相關，不排除
        work_text = '\n'.join(c['work_lines'])
        if not any(kw in work_text for kw in TITLE_KEYWORDS[:15]):
            pass  # 不立即排除，只是不加分

    # --- 必要條件 M1: 職稱 ---
    m1_hits = [kw for kw in TITLE_KEYWORDS if kw in first_work or kw in desired]
    if m1_hits:
        score += 10
        reasons.append(f"M1職稱命中: {','.join(m1_hits[:3])}")

    # --- 必要條件 M2: 產業 ---
    m2_hits = [kw for kw in COMPANY_KEYWORDS if kw in full]
    if m2_hits:
        score += 10
        reasons.append(f"M2產業命中: {','.join(m2_hits[:3])}")

    # --- 必要條件 M3: 年資≥3年 ---
    if len(c['work_lines']) >= 2:
        score += 5
        reasons.append(f"M3年資: {len(c['work_lines'])}段經歷")

    # 如果三個必要條件都未命中，直接返回低分
    if score == 0:
        return 0, ["未命中任何必要條件"], False

    # --- 加分條件 ---
    # N1: 學歷科系 (★★★)
    n1_hits = [kw for kw in EDU_KEYWORDS if kw in edu]
    if n1_hits:
        score += 15
        reasons.append(f"N1學歷對口: {','.join(n1_hits[:2])}")

    # N2/N3: 知名公司 (★★★)
    n23_hits = [kw for kw in PREMIUM_COMPANIES if kw in full]
    if n23_hits:
        score += 15
        reasons.append(f"N2/N3知名企業: {','.join(n23_hits[:2])}")

    # N4: 管理職 (★★☆)
    n4_hits = [kw for kw in MGMT_KEYWORDS if kw in first_work or kw in desired]
    if n4_hits:
        score += 8
        reasons.append(f"N4管理職: {','.join(n4_hits[:2])}")

    # N5: 多系統覆蓋 (★★☆)
    n5_hits = [kw for kw in MULTISYS_KEYWORDS if kw in full]
    if len(n5_hits) >= 3:
        score += 10
        reasons.append(f"N5多系統: {','.join(n5_hits[:4])} ({len(n5_hits)}項)")
    elif len(n5_hits) >= 1:
        score += 5
        reasons.append(f"N5系統: {','.join(n5_hits[:3])}")

    # N7: 監造 (★★☆) — 品管已移至 N13 獨立計分
    if any(kw in full for kw in ['監造', '監工', '施工監督']):
        score += 5
        reasons.append("N7監造經驗")

    # N8: 建廠/擴廠 (★★☆)
    if any(kw in full for kw in ['建廠', '擴廠', '擴建', '新建', 'EPC']):
        score += 5
        reasons.append("N8建廠/擴廠經驗")

    # N13: 品管 (★★☆)
    if any(kw in full for kw in ['品管', '品質管理', '查驗', '品管工程師']):
        score += 5
        reasons.append("N13品管經驗")

    # N14: 採購/發包 (★☆☆)
    if any(kw in full for kw in ['採購', '發包', '議價', '標單']):
        score += 3
        reasons.append("N14採購/發包經驗")

    # N15: 能源工程 (★☆☆)
    if any(kw in full for kw in ['太陽能', '儲能', '充電樁', '逆變器', '高低壓']):
        score += 3
        reasons.append("N15能源工程經驗")

    # N16: 鋼構/焊接 (★☆☆)
    if any(kw in full for kw in ['鋼構', '焊接', 'CO2焊', '鋼結構']):
        score += 3
        reasons.append("N16鋼構/焊接經驗")

    return score, reasons, False


# ============================
# 主流程
# ============================
def main():
    if len(sys.argv) < 2:
        print("用法: python screen_candidates.py <ANALYSIS.md路徑>")
        sys.exit(1)

    filepath = sys.argv[1]
    if not os.path.isfile(filepath):
        print(f"錯誤：找不到檔案 {filepath}")
        sys.exit(1)

    with open(filepath, 'r', encoding='utf-8') as f:
        lines = f.read().replace('\r\n', '\n').split('\n')

    candidates = parse_candidates(lines)
    print(f"共解析 {len(candidates)} 位候選人\n")

    # 篩選
    results = {'G1_土木建築': [], 'G2_機電相關': [], 'G3_其他': [], '未分類': []}
    excluded = 0
    below_threshold = 0
    threshold = 15  # 最低分數門檻

    for c in candidates:
        score, reasons, is_excluded = score_candidate(c)
        if is_excluded:
            excluded += 1
            continue
        if score >= threshold:
            results[c['group']].append({
                'name': c['name'],
                'age': c['age'],
                'score': score,
                'reasons': reasons,
            })
        else:
            below_threshold += 1

    # 排序（各組內按分數降序）
    for group in results:
        results[group].sort(key=lambda x: -x['score'])

    # 輸出
    total_selected = sum(len(v) for v in results.values())
    print("=" * 60)
    print(f"篩選結果：候選 {total_selected} 人 / 排除 {excluded} 人 / 未達門檻 {below_threshold} 人")
    print("=" * 60)

    for group_name, group_label in [
        ('G1_土木建築', '第一區塊 — 土木+建築背景'),
        ('G2_機電相關', '第二區塊 — 機電/電機/化工/環工等'),
        ('G3_其他', '第三區塊 — 其他背景（實務轉型）'),
    ]:
        group_list = results[group_name]
        print(f"\n### {group_label} ({len(group_list)} 人)")
        print("-" * 50)
        for r in group_list:
            reason_str = " | ".join(r['reasons'][:3])
            print(f"  {r['name']} (age:{r['age']}, score:{r['score']}) — {reason_str}")

    # 未分類
    if results['未分類']:
        print(f"\n### 未分類 ({len(results['未分類'])} 人)")
        for r in results['未分類']:
            reason_str = " | ".join(r['reasons'][:3])
            print(f"  {r['name']} (age:{r['age']}, score:{r['score']}) — {reason_str}")


if __name__ == '__main__':
    main()
