# -*- coding: utf-8 -*-
"""
scoring.py — General candidate scoring engine (ported from screen_candidates.py)

All keyword lists and scoring logic are copied verbatim from the original.
Adapted to work with structured candidate data from extractor.py instead of ANALYSIS.md blocks.
"""

import re

# ============================
# Keyword lists (verbatim from screen_candidates.py)
# ============================

CORE_TITLE_KEYWORDS = [
    '機電', '廠務', '空調', 'HVAC', '監造', '監工', '水處理', '純水',
    '廢水', '管線', '配管', '儀電', '水電', '電機', '機械',
    '品管', '採購', '維運', '焊工', '管路', '電氣'
]

GENERIC_TITLE_KEYWORDS = [
    '工程師', '主任', '副主任', '課長', '副理', '專案', '工務',
    '技術員', '繪圖員', '襄理', '組長', '營造工程師',
]

TITLE_KEYWORDS = CORE_TITLE_KEYWORDS + GENERIC_TITLE_KEYWORDS

COMPANY_KEYWORDS = [
    '中鼎', '泰興', '仲量聯行', 'JLL', '達欣', '潤弘', '大林組',
    '營造', '建設', '台積', '世界先進', '美光', '聯電', '欣興',
    '長春', '亞東氣體', '東元', '中興電工', '士林電機', '能源',
    '半導體', '光電', 'EPC', '統包', '建廠', '擴廠',
    '大陸工程', '日月光', '力晶', '鴻海', '齊裕', '中麟', '閎大', '立穩',
    '臻鼎', '台灣神隆', '中聯資源', '泰創', '興富發', '日揮', '恩智浦',
]

EDU_KEYWORDS = [
    '電機', '機械', '冷凍空調', '冷凍', '空調', '化工', '化學',
    '環工', '環境工程', '環境', '土木', '建築', '營建', '能源',
    '輪機', '水電', '機電', '自動化', '動力',
]

PREMIUM_COMPANIES = [
    '中鼎', '泰興', '達欣', '潤弘', '大林組',
    '台積', '世界先進', '美光', '聯電', '欣興', '長春', '亞東氣體',
    '大陸工程', '日月光', '力晶', '鴻海', '臻鼎', '台灣神隆', '日揮', '恩智浦',
    '亞翔', '漢唐', '帆宣', '洋基', '信紘科', '擎邦', '同開',
    '千附', '聖暉', '朋億', '互助營造', '瑞助',
]

MGMT_KEYWORDS = ['主任', '課長', '副理', '經理', '協理', '處長', '總監']

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

HIGH_TECH_FAB_KEYWORDS = [
    '無塵室', '潔淨室', 'Cleanroom', 'FAB', 'UPW', 'WWT',
    '特氣', '大宗氣體', 'Bulk Gas', '製程排氣', 'Scrubber', 'VOC',
    '製程冷卻水', 'PCW', 'Hook-up', 'CDA',
    '化學供應', 'Chemical', '酸鹼', 'Slurry',
    'EPCK', '試車', 'Commissioning',
    '高科技廠', '半導體廠', '晶圓廠', '面板廠', 'Utility',
]

TRADITIONAL_CONDITIONAL_COMPANIES = ['中興電工', '士林電機', '東元']

EXCLUDE_TITLES = [
    '保全', '門市', '餐飲', '銷售', '業務員', '店長', '服務生',
    '司機', '總幹事', '保險', '房仲', '理財', '服務業',
]

NON_ENGINEERING_DESIRED = [
    '會計', '秘書', '行政', '財務', '人資', '人事', '人力資源',
    '客服', '文書', '總務', '櫃台', '店員', '專員', '助理',
    '軟體', '後端', '前端', '韌體', '資訊', '網管', 'MIS',
    '研發', '研究', 'CAE', '機構', '熱流', '機器人', '品保', '驗證',
    'BIM工程師', '內業', '專案業務', '系統整合', '講師', '教育', '室內裝修', '室內設計', '建築設計', '業務', '庶務', '物流', '行銷', '航空',
    '軟工', '軟體工程師', '土開', '土地開發', '研究類別',
    '實驗室', '校正', '稽核', '採購', '發包', '產品', 'AIOT'
]

NON_CONSTRUCTION_MANUFACTURING = [
    '製程', '製造', '生產', '設備工程師', '技術工程師', '生產線', '品保', '機械製造',
    '自動控制', '設計', '機構設計', '工程師', '操作', 'PLC', '電控', 'Field Service',
    '客服', '設計工程師', '售後服務', 'AIOT', '產品', '韌體', 'FAE', 'fae', '應用工程師',
    '研發', 'RD', 'R&D', 'rd', '光機', '光電', '微影', '顯示', '開發', '設備維護', '運轉維護', '保養', '設備保養'
]

LOW_SKILL_KEYWORDS = [
    '作業員', '操作員', '技術員', '助理', '保養', '維修', '外場', '司機', '理貨',
    '飯店', '旅館', '專員', '維修工程師', '後勤', '裝配', '組裝', '客服工程師', '倉管', '倉庫', '焊接',
    '重機械', '引擎', '管輪', '製圖員', '操作', '養護', '外務', '柏文健康', '家福', '健身', '店長', '修繕',
    '大廈維護', '大樓維護', '大廈管理', '駐點', '展場', '繪圖員', 'BIM建模員', '總務', '後端', '研究類別', '研究員',
    '實習生', '學徒', '工讀生', '中控', '夜班', '服務人員', '營業員', '助手', '檢修', '技工', '半技', '粗工', '物業', '機械技術'
]

EHS_KEYWORDS = [
    '環安', '職安', '工安', '勞安', '安衛', 'EHS', '安全衛生', '環境工程師'
]

ABSOLUTE_KILL_KEYWORDS = [
    '軟工', '軟體工程師', '展場', '繪圖員', 'bim建模員', '室內設計'
]


def _infer_group(edu_text, full_text):
    """Infer education group (G1/G2/G3) from education and full text."""
    g2_kws = ['水處理', '機電', '電機', '機械', '化工', '環工', '空調', '冷凍',
              '化學', '輪機', '能源', '動力', '自動化', '水電']
    g1_kws = ['土木', '建築', '營建', '景觀', '都市計畫']

    text = edu_text + ' ' + full_text[:500]
    if any(kw in text for kw in g2_kws):
        return 'G2_機電相關'
    if any(kw in text for kw in g1_kws):
        return 'G1_土木建築'
    return 'G3_其他'


def score_candidate_from_resume(candidate):
    """
    Score a candidate from structured resume data.

    Args:
        candidate: dict from extractor.extract_from_markdown()
            Required keys: name, age, education, recent_work, recent_work_desc,
                          seniority, work_lines, full_text

    Returns:
        dict with keys: score, reasons, excluded, threshold, passed
    """
    # Build fields compatible with original score_candidate() logic
    full = candidate.get('full_text', '')
    work_lines = candidate.get('work_lines', [])
    work_text = '\n'.join(work_lines)
    edu = candidate.get('education', '')
    recent_work = candidate.get('recent_work', '')
    recent_work_desc = candidate.get('recent_work_desc', '')

    # In PDF resumes, there's no "desired_title" — use recent_work as proxy
    desired = recent_work
    first_work = work_lines[0] if work_lines else recent_work
    work_and_desired = work_text + '\n' + desired + '\n' + recent_work_desc

    group = _infer_group(edu, full)

    score = 0
    reasons = []
    threshold = 20

    # --- Exclusion Rules ---
    # E8: Absolute kill
    kill_hits = [kw for kw in ABSOLUTE_KILL_KEYWORDS if kw in work_and_desired.lower()]
    if kill_hits:
        return _result(0, [f"排除(E8): 絕對不適任={','.join(kill_hits[:2])}"], True, threshold)

    # E1: Pure service roles
    if desired:
        exclude_hit = [kw for kw in EXCLUDE_TITLES if kw in desired]
        has_eng = any(kw in desired for kw in ['工程', '技術', '機電', '廠務', '監造', '主任'])
        if exclude_hit and not has_eng:
            return _result(0, [f"排除(E1): 近期職稱={desired[:30]}"], True, threshold)

    # E2: Non-engineering desired title
    if desired:
        if any(kw in desired for kw in NON_ENGINEERING_DESIRED):
            return _result(0, [f"排除(E2): 非工程方向={desired[:30]}"], True, threshold)

    # E3: Low-skill
    low_skill_hits = [kw for kw in LOW_SKILL_KEYWORDS if kw in desired or kw in first_work]
    has_mgmt_or_eng = any(kw in desired + first_work for kw in ['工程師', '主任', '經理', '副理', '課長', '專案', '機電', '氣體'])

    unsavable_hits = [kw for kw in ['維修工程師', '技術工程師', '助理', '實習', '學徒', '中控', '夜班', '工讀', '助手', '專員', '駐點', '倉管', '倉庫', '器材', '物料', '總務', '行政', '人事', '檢修', '技工', '半技', '粗工', '保全', '駐衛警', '勤務', '物業', '機械技術'] if kw in desired + first_work]
    if unsavable_hits:
        has_mgmt_or_eng = False

    if low_skill_hits and not has_mgmt_or_eng:
        return _result(0, [f"排除(E3): 脫離工程專業={','.join(low_skill_hits[:2])}"], True, threshold)

    # E4: Pure civil without factory
    is_pure_civil = (group == 'G1_土木建築') or any(kw in desired + work_text for kw in ['建築', '營建', '土木', '營造'])
    if is_pure_civil:
        has_factory = any(kw in work_and_desired for kw in ['建廠', '擴廠', '廠務', '無塵室', '統包', 'EPC', '科技廠', '半導體', '面板', '帆宣', '漢唐', '亞翔', '特氣', '管路'])
        has_mep_role = any(kw in desired + work_text for kw in ['機電', 'BIM', 'MEP', '空調', '消防', '電力', '水處理', '水電'])
        if not (has_factory or has_mep_role):
            return _result(0, ["排除(E4): 土建/營造無機電建廠經驗"], True, threshold)

    # E5: Manufacturing/process roles
    if group in ('G2_機電相關', 'G3_其他'):
        if any(kw in work_and_desired for kw in NON_CONSTRUCTION_MANUFACTURING):
            has_facility_mep = any(kw in work_and_desired for kw in ['廠務', '建廠', '擴廠', '空調', '消防', '水處理', '無塵室', '特氣', '營造', '建設', '氣體', '中鼎', '機電', '配電', '電力', '水電'])
            if not has_facility_mep:
                return _result(0, ["排除(E5): 偏向製程/製造/非建廠屬性"], True, threshold)

    # E7: EHS
    ehs_hits = [kw for kw in EHS_KEYWORDS if kw in desired or kw in first_work]
    if ehs_hits:
        return _result(0, [f"排除(E7): 工安/環安衛={','.join(ehs_hits[:2])}"], True, threshold)

    # E9: Residential
    residential_hits = [kw for kw in ['住宅', '住宅工程', '透天', '別墅'] if kw in work_and_desired]
    if residential_hits:
        has_factory = any(kw in work_and_desired for kw in ['建廠', '擴廠', '廠務', '無塵室', '統包', '科技廠', '半導體'])
        if not has_factory:
            return _result(0, [f"排除(E9): 偏向住宅工程={','.join(residential_hits[:2])}"], True, threshold)

    # E10: Pure plumbing
    plumber_only = '水電' in desired + first_work and not any(kw in first_work for kw in ['工程師', '主任', '副理', '經理', '專案', '機電', '廠務'])
    has_thick = any(k in work_and_desired for k in ['規劃', '建廠', '新建', '擴廠', '專案', '統包', '無塵室', '廠務', '發包', '圖面', '監造'])
    if plumber_only and not has_thick:
        return _result(0, ["排除(E10): 履歷單薄之純水電/勞務工作"], True, threshold)

    # E11: Pure procurement
    procurement_only = any(kw in desired + first_work for kw in ['採購', '發包', '稽核', '能源管理'])
    if procurement_only:
        has_mep_role = any(kw in desired + work_text for kw in ['機電', '空調', '消防', '電力', '無塵室', '廠務', '建廠', '水處理'])
        if not has_mep_role:
            return _result(0, ["排除(E11): 純採購/企劃無機電實務"], True, threshold)

    # E17: Pure software/R&D
    fatal_rd_software_hits = [kw for kw in ['軟硬體', '軟體', 'SQA', '演算法', 'BIOS', 'IC設計', '晶片', '前端', '後端', '全端', 'App開發', '業務', '光電', '研發', 'RD'] if kw in work_and_desired]
    if fatal_rd_software_hits:
        return _result(0, ["排除(E17): 純軟體/研發/業務人員"], True, threshold)

    # E12: Property management
    property_hits = [kw for kw in ['公寓大廈', '物業', '保全', '百貨', '商場', '量販', '社區管理', '管委會', '京站'] if kw in work_and_desired]
    if property_hits:
        has_factory = any(kw in work_and_desired for kw in ['建廠', '擴廠', '廠務', '無塵室', '統包', '科技廠', '半導體'])
        if not has_factory:
            return _result(0, [f"排除(E12): 大樓物業/商場維護={','.join(property_hits[:2])}"], True, threshold)

    # E13: Service industry thin engineering
    has_thick_work = any(k in work_text for k in ['規劃', '建廠', '新建', '擴廠', '專案', '統包', '無塵室', '廠務', '發包', '圖面', '監造'])
    non_eng_bg_hits = sum(1 for line in work_lines if any(kw in line for kw in ['餐廳', '門市', '吧台', '服務人員', '美容', '保全', '店長', '理貨', '餐飲']))
    eng_job_hits = sum(1 for line in work_lines if any(kw in line for kw in ['工程', '機電', '廠務', '水電', '空調', '消防']))
    if non_eng_bg_hits >= 2 and eng_job_hits <= 1 and not has_thick_work:
        return _result(0, ["排除(E13): 服務業轉型且工程經歷單薄"], True, threshold)

    # E14: Non-engineering education + thin
    non_eng_edu = any(kw in edu for kw in ['設計', '餐飲', '美容', '觀光', '語文', '幼保', '休閒', '保健', '食品'])
    if non_eng_edu and not has_thick_work:
        return _result(0, ["排除(E14): 非專業科系背景且工程履歷單薄"], True, threshold)

    # E15: No core MEP
    core_mep_hits = [kw for kw in ['空調', '消防', '水處理', '管線', 'BIM', 'MEP', '廠務', '水電', '無塵室', '建廠', '統包'] if kw in work_and_desired]
    if not core_mep_hits:
        if any(kw in work_text for kw in ['操作員', '技術人員', '服務人員', '門市', '餐飲', '保全', '總務', '作業員', '理貨', '美容']):
            return _result(0, ["排除(E15): 缺乏核心機電實務且經歷混雜"], True, threshold)

    # E16: Automation/CNC/aerospace
    automation_hits = [kw for kw in ['機電整合', '自動化設備', '自動控制', 'PLC', '電控', '航太', '航空', ' cnc', 'CNC'] if kw in work_and_desired]
    if automation_hits:
        has_real_facility = any(kw in work_and_desired for kw in ['廠務', '建廠', '無塵室', '空調', '水電', '消防', '水處理'])
        if not has_real_facility:
            return _result(0, [f"排除(E16): 偏向自動化/製造/航太({','.join(automation_hits[:2])})"], True, threshold)

    # --- Must-Have Conditions (M1-M3) ---
    recent_works = '\n'.join(work_lines[:3]) if work_lines else recent_work
    core_hits = [kw for kw in CORE_TITLE_KEYWORDS if kw in recent_works or kw in desired]
    generic_hits = [kw for kw in GENERIC_TITLE_KEYWORDS if kw in recent_works or kw in desired]

    if core_hits:
        score += 10
        reasons.append(f"M1職稱命中: {','.join(core_hits[:3])}")
    elif generic_hits:
        score += 3
        reasons.append(f"M1職稱(泛用): {','.join(generic_hits[:2])}")

    m2_hits = [kw for kw in COMPANY_KEYWORDS if kw in full]
    if m2_hits:
        score += 10
        reasons.append(f"M2產業命中: {','.join(m2_hits[:3])}")

    if len(work_lines) >= 3:
        score += 5
        reasons.append(f"M3年資: {len(work_lines)}段經歷")

    if score == 0:
        return _result(0, ["未命中任何必要條件"], False, threshold)

    # --- Bonus Conditions (N1-N17) ---
    n1_hits = [kw for kw in EDU_KEYWORDS if kw in edu]
    if n1_hits:
        score += 15
        reasons.append(f"N1學歷對口: {','.join(n1_hits[:2])}")

    n23_hits = [kw for kw in PREMIUM_COMPANIES if kw in full]
    if n23_hits:
        score += 15
        reasons.append(f"N2/N3知名企業: {','.join(n23_hits[:2])}")

    n4_hits = [kw for kw in MGMT_KEYWORDS if kw in first_work or kw in desired]
    if n4_hits:
        score += 8
        reasons.append(f"N4管理職: {','.join(n4_hits[:2])}")

    n5_hits = [kw for kw in MULTISYS_KEYWORDS if kw in full]
    if len(n5_hits) >= 3:
        score += 10
        reasons.append(f"N5多系統: {','.join(n5_hits[:4])} ({len(n5_hits)}項)")
    elif len(n5_hits) >= 1:
        score += 5
        reasons.append(f"N5系統: {','.join(n5_hits[:3])}")

    if any(kw in full for kw in ['監造', '監工', '施工監督']):
        score += 5
        reasons.append("N7監造經驗")

    if any(kw in full for kw in ['建廠', '擴廠', '擴建', '新建', 'EPC']):
        score += 5
        reasons.append("N8建廠/擴廠經驗")

    if any(kw in full for kw in ['品管', '品質管理', '查驗', '品管工程師']):
        score += 5
        reasons.append("N13品管經驗")

    if any(kw in full for kw in ['採購', '發包', '議價', '標單']):
        score += 3
        reasons.append("N14採購/發包經驗")

    if any(kw in full for kw in ['太陽能', '儲能', '充電樁', '逆變器', '高低壓']):
        score += 3
        reasons.append("N15能源工程經驗")

    if any(kw in full for kw in ['鋼構', '焊接', 'CO2焊', '鋼結構']):
        score += 3
        reasons.append("N16鋼構/焊接經驗")

    # N17: High-tech fab core
    n17_hits = [kw for kw in HIGH_TECH_FAB_KEYWORDS if kw in full]
    if len(n17_hits) >= 2:
        score += 20
        reasons.append(f"N17高科建廠VIP: {','.join(n17_hits[:4])} ({len(n17_hits)}項)")
    elif len(n17_hits) >= 1:
        score += 10
        reasons.append(f"N17高科建廠: {','.join(n17_hits[:3])}")

    # D1: Traditional heavy electrical downgrade
    trad_hits = [kw for kw in TRADITIONAL_CONDITIONAL_COMPANIES if kw in full]
    if trad_hits and not n17_hits:
        score -= 10
        reasons.append(f"傳統重電降階: {','.join(trad_hits[:2])}(無高科經驗)")

    # D2: Age penalty
    age_num = 0
    age_match = re.search(r'(\d+)', candidate.get('age', ''))
    if age_match:
        age_num = int(age_match.group(1))
    if age_num >= 40 and not n17_hits:
        if not n23_hits:
            score -= 5
            reasons.append(f"年資防呆: {age_num}歲無高科/知名EPC經驗")

    # D3: Maintenance facility penalty
    facility_titles = ['廠務', '設備']
    planning_keywords = ['規劃', '建廠', '新建', '整合', '專案', 'mep', '統包']
    is_facility = any(k in desired for k in facility_titles) or any(k in first_work for k in facility_titles)
    has_planning = any(k in work_and_desired for k in planning_keywords)
    if is_facility and not has_planning:
        score -= 15
        reasons.append("D3廠務防呆: 偏維護缺乏規劃整合 (-15)")

    # D4: Manufacturing end penalty
    mfg_penalty_keywords = ['測試', '產線', '組裝', '加工', '車廠', 'plc', 'smt', 'cnc']
    if any(k in work_and_desired.lower() for k in mfg_penalty_keywords):
        score -= 15
        reasons.append("D4製造降階: 偏向製造/測試端 (-15)")

    # D5: Procurement interior penalty
    procurement_titles = ['採購']
    mep_procurement_keywords = ['機電', '空調', '消防', '電力', '管線', '發包', 'mep']
    is_procurement = any(k in work_and_desired for k in procurement_titles)
    has_mep_procurement = any(k in work_and_desired.lower() for k in mep_procurement_keywords)
    if is_procurement and not has_mep_procurement:
        score -= 15
        reasons.append("D5採購防呆: 純內業缺乏機電發包經驗 (-15)")

    # D6: Thin resume notice
    thick_keywords = ['規劃', '建廠', '新建', '擴廠', '專案', '統包', '無塵室', '廠務', '發包', '圖面', '監造']
    has_thick_final = any(k in work_and_desired for k in thick_keywords)
    if not has_thick_final and len(n23_hits) == 0:
        reasons.append("D6履歷單薄(建議補充工程細節)")

    return _result(score, reasons, False, threshold)


def _result(score, reasons, excluded, threshold):
    return {
        'score': max(score, 0),
        'reasons': reasons,
        'excluded': excluded,
        'threshold': threshold,
        'passed': not excluded and score >= threshold,
    }
