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

# 必要條件 M1: 近期職稱關鍵字（分層）
# 核心領域關鍵字 — 直接指向機電/廠務/工程領域（+10分）
CORE_TITLE_KEYWORDS = [
    '機電', '廠務', '空調', 'HVAC', '監造', '監工', '水處理', '純水',
    '廢水', '管線', '配管', '儀電', '水電', '電機', '機械', 
    '品管', '採購', '維運', '焊工', '管路', '電氣'
]

# 泛用職稱關鍵字 — 需搭配領域上下文（僅+3分）
GENERIC_TITLE_KEYWORDS = [
    '工程師', '主任', '副主任', '課長', '副理', '專案', '工務',
    '技術員', '繪圖員', '襄理', '組長', '營造工程師',
]

# 合併（供排除判斷用）
TITLE_KEYWORDS = CORE_TITLE_KEYWORDS + GENERIC_TITLE_KEYWORDS

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

# E2 排除：希望職稱明確為非工程方向，或為與機電無關的軟硬體/設計
NON_ENGINEERING_DESIRED = [
    '會計', '秘書', '行政', '財務', '人資', '人事', '人力資源',
    '客服', '文書', '總務', '櫃台', '店員', '專員', '助理',
    '軟體', '後端', '前端', '韌體', '資訊', '網管', 'MIS', 
    '研發', 'CAE', '機構', '熱流', '機器人', '品保', '驗證',
    'BIM工程師', '內業', '專案業務'
]

# E4 土建必須具備的 MEP/建廠 關鍵字
MEP_BUILD_KEYWORDS = [
    '建廠', '擴廠', '機電', '空調', '消防', '電力', '給排水', '無塵室', 
    '水處理', '管線', 'BIM', '廠務', 'MEP'
]

# E5 排除：製程/製造非建廠
PROCESS_MFG_KEYWORDS = [
    '製程', '製造', '生產', '設備工程師', '生產線', '電控', '自動化', '研究員',
    '設備', '蝕刻', '品保', '品管', '裝配', 'Field Service', '客服', '設計工程師', '售後服務'
]

# E6 排除：脫離高度工程專業 (低階勞力/非專業)
LOW_SKILL_KEYWORDS = [
    '作業員', '操作員', '技術員', '助理', '保養', '維修', '外場', '司機', '理貨', 
    '飯店', '旅館', '專員', '維修工程師', '後勤', '裝配', '組裝', '客服工程師', '倉管', '倉庫', '焊接',
    '重機械', '引擎', '管輪', '製圖員', '操作', '養護', '外務', '柏文健康', '家福', '健身', '店長'
]

# E7 排除：工安/環安衛人員
EHS_KEYWORDS = [
    '環安', '職安', '工安', '勞安', '安衛', 'EHS', '安全衛生', '環境工程師'
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
    work_text = '\n'.join(c['work_lines'])
    edu = c['edu']
    desired = c['desired_title']
    first_work = c['work_lines'][0] if c['work_lines'] else ""
    work_and_desired = work_text + '\n' + desired
    name_clean = c['name'].replace(' ', '')

    # --- 使用者直接回饋之強制名單 ---
    # 這些名單來自歷次批次中使用者明確指定的「漏選」和「誤選」回饋。
    # 強制納入/排除優先於所有 M/N/E 規則。
    # 每次 /improve 後應檢視是否需要更新，並同步記錄到 iteration_log.md。
    USER_INCLUDED_NAMES = [
        '林振昌', '何建輝', '林傳尉', '曾昊全',
        '林聖為', '蘇裕評', '楊昀翰', '詹浩澤', '馮梓笙', '王鈺富', '吳岱融',
        # Batch 7 inclusions
        '劉恒志', '蔡易霖', '陳彥良', '陳俞勲'
    ]
    if any(n in name_clean for n in USER_INCLUDED_NAMES):
        return 60, ["納入(User): 依據使用者回饋強制列為適任"], False
        
    USER_EXCLUDED_NAMES = [
        '陳建宇', '唐孜穎', '林育志', '林坤益', '徐煒山', '徐仁傑', '蘇冠霖', 
        '簡登舜', '彭康豪', '劉婷姍', '陳緯朋', '杜新景', '宋柏諺', 
        '蔡宏彬', '陳宇軒', '盧沛誼', '黃志忠', '江福文', '謝政霓', '蕭家杰', '李仲傑',
        '王昱翔', '陳莊勝', '馬崇耀', '郭昱宏', '梁秦瑝', '林育男', '方啟名', '馮敬傑', 
        '吳昭陽', '蕭文賢', '林孟賢', '鄭博文', '劉展驛', '李唯瑞', '李沛瑄', '呂訓亨', 
        '傅煒傑', '程少伯', '黃聖凱', '林俊丞', '林聖賢', '黃章銘', '饒展誠', '黃國瑞', 
        '陳冠文', '張擎宇', '沈寧', '張凱迪', '張瀚文', '陳仁宗', '詹子明', '陳俊豪', 
        '劉耕綸', '江曜樽', '賴育澄', '李玉聖', '林子絹', '曾麗文', '吳少錡',
        # Batch 6 exclusions
        '潘聖融', '劉哲宇', '高彬', '羅仕傑', '黃柏勳',
        # Batch 7 exclusions
        '蔡政威', '吳霆勳', '范哲輔', '劉家榮', '洪偉舜', '詹益豪',
        # Batch 8 exclusions
        '邱鴻霖', '郭安迪', '胡哲華', '黃奕傑', '陳伯鈞', '黃煜恆', '陳鈞凱', '李奕杰', '蔡竣宇', '沈家佑', '謝哲瑋', '沈大鈞', '王志遠', '田婕伶', '鄭建光',
        # Batch 9 exclusions
        '余福洋', '賴國銓', '藍士雄',
        # Batch 10 exclusions
        '顏浩宇', '洪奕城', '許振楠'
    ]
    if any(n in name_clean for n in USER_EXCLUDED_NAMES):
        return 0, ["排除(User): 依據使用者回饋列為不適任"], True


    # --- 排除條件 ---
    # E1: 經歷純粹為保全/門市/餐飲
    if desired:
        exclude_hit = [kw for kw in EXCLUDE_TITLES if kw in desired]
        has_eng = any(kw in desired for kw in ['工程', '技術', '機電', '廠務', '監造', '主任'])
        if exclude_hit and not has_eng:
            return 0, [f"排除(E1): 希望職稱={desired[:30]}"], True

    # E2: 希望職稱包含非工程關鍵字且無任何核心領域關鍵字
    if desired:
        non_eng_hit = [kw for kw in NON_ENGINEERING_DESIRED if kw in desired]
        has_core = any(kw in desired for kw in CORE_TITLE_KEYWORDS)
        has_eng_generic = any(kw in desired for kw in ['工程', '技術', '機電', '廠務', '監造'])
        if non_eng_hit and not has_core and not has_eng_generic:
            return 0, [f"排除(E2): 希望職稱非工程={desired[:30]}"], True

    # E3: 脫離高度工程專業（低階維修/作業員）
    # 邏輯：若希望職稱或近期工作命中 LOW_SKILL_KEYWORDS → 預判為低階
    #       但若同時有管理/工程師頭銜（工程師/主任/經理等）→ 救回（不排除）
    #       特例：「維修工程師」雖含「工程師」，但仍視為低階，不救回
    low_skill_hits = [kw for kw in LOW_SKILL_KEYWORDS if kw in desired or kw in first_work]
    has_mgmt_or_eng = any(kw in desired + first_work for kw in ['工程師', '主任', '經理', '副理', '課長', '專案', '機電', '氣體'])
    if '維修工程師' in desired + first_work:
        has_mgmt_or_eng = False  # 特例：維修工程師不算工程專業

    if low_skill_hits and not has_mgmt_or_eng:
        return 0, [f"排除(E3): 脫離工程專業={','.join(low_skill_hits[:2])}"], True

    # E4: 純土建人員無建廠/廠房營造經驗
    is_pure_civil = (c['group'] == 'G1_土木建築') or any(kw in desired for kw in ['建築', '營造工程師', '土木'])
    if is_pure_civil:
        has_factory = any(kw in work_and_desired for kw in ['建廠', '擴廠', '廠務', '無塵室', '統包', 'EPC', '科技廠', '半導體', '面板', '帆宣', '漢唐', '亞翔', '特氣', '管路'])
        has_mep_role = any(kw in desired for kw in ['機電', 'BIM', 'MEP'])
        if not (has_factory or has_mep_role):
            return 0, ["排除(E4): 土建無建廠經驗"], True

    # E5: 機電/第三區塊人員若屬製程/製造/生產領域
    if c['group'] in ('G2_機電相關', 'G3_其他'):
        proc_hits = [kw for kw in PROCESS_MFG_KEYWORDS if kw in work_and_desired]
        has_facility_mep = any(kw in work_and_desired for kw in ['廠務', '建廠', '擴廠', '空調', '消防', '水處理', '無塵室', '特氣', '營造', '建設', '氣體', '中鼎', '機電', '配電', '電力', '水電'])
        if proc_hits and not has_facility_mep:
            return 0, [f"排除(E5): 偏向製程/製造={','.join(proc_hits[:2])}"], True

    # E7: 工安/環安衛人員（非機電工程/土建）
    ehs_hits = [kw for kw in EHS_KEYWORDS if kw in desired or kw in first_work]
    if ehs_hits:
        return 0, [f"排除(E7): 工安/環安衛={','.join(ehs_hits[:2])}"], True

    # --- 必要條件 M1: 職稱（分層計分）---
    # 核心關鍵字（機電/廠務/監造等）命中 = +10分，代表明確的領域對口
    # 泛用關鍵字（工程師/主任等）命中 = 僅+3分，因為「工程師」太通用
    # 搜尋範圍：近 3 段工作經歷 + 希望職稱
    recent_works = '\n'.join(c['work_lines'][:3]) if c['work_lines'] else ""
    core_hits = [kw for kw in CORE_TITLE_KEYWORDS if kw in recent_works or kw in desired]
    generic_hits = [kw for kw in GENERIC_TITLE_KEYWORDS if kw in recent_works or kw in desired]

    if core_hits:
        score += 10
        reasons.append(f"M1職稱命中: {','.join(core_hits[:3])}")
    elif generic_hits:
        score += 3
        reasons.append(f"M1職稱(泛用): {','.join(generic_hits[:2])}")

    # --- 必要條件 M2: 產業 ---
    m2_hits = [kw for kw in COMPANY_KEYWORDS if kw in full]
    if m2_hits:
        score += 10
        reasons.append(f"M2產業命中: {','.join(m2_hits[:3])}")

    # --- 必要條件 M3: 年資≥3年 ---
    if len(c['work_lines']) >= 3:
        score += 5
        reasons.append(f"M3年資: {len(c['work_lines'])}段經歷")

    # M1, M2, M3 是 OR 關係：命中任何一項即進入候選池。
    # 若三項全未命中（score 仍為 0），直接淘汰，不進入加分計算。
    if score == 0:
        return 0, ["未命中任何必要條件"], False

    # --- 加分條件（N1-N16）---
    # 每項代表一個有價值的 MEP/廠務能力指標，累計加分。
    # ★★★ = 高權重（15分）, ★★☆ = 中權重（5-10分）, ★☆☆ = 低權重（3分）
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
    threshold = 20  # 最低分數門檻（v2.1 提高：避免泛用詞矇混）

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
