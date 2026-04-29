# -*- coding: utf-8 -*-
"""
bim_scorer.py — BIM Manager position-specific scoring

Scores candidates against the CTCI High-Tech Facility Systems Department
BIM Manager (BIM主任) position requirements.

Total: 100 points across 5 dimensions.
"""

import re


# BIM-specific keyword lists
BIM_KEYWORDS = [
    'BIM', 'Revit', 'Navisworks', 'BIM360', 'CDE', 'LOD',
    'clash detection', '碰撞檢測', '衝突檢測', 'IFC', 'COBie',
    '模型整合', '模型管理', '模型協調', 'BIM主任', 'BIM Manager',
    'BIM Coordinator', '設計視覺化', 'Dynamo', 'ArchiCAD', 'Tekla',
    '3D模型', 'AutoCAD', 'BIM建模', 'BIM執行計畫', 'BEP',
]

ENGINEERING_SKILL_KEYWORDS = [
    'MEP', '機電', '管線', '空調', '消防', '電力', '給排水',
    '廠務', '建廠', '擴廠', '統包', 'EPC', '施工圖', '設計圖',
    '圖面審查', '界面整合', '管理系統', '無塵室', '潔淨室',
    '水處理', '配管', 'P&ID', '五大管線', 'HVAC', 'Utility',
]

EDUCATION_ENGINEERING = [
    '土木', '建築', '營建', '機械', '電機', '化工', '化學',
    '環工', '環境工程', '能源', '冷凍空調', '水電', '機電',
    '工程學', '營建工程', '建築工程',
]

EDUCATION_SCIENCE = [
    '資訊', '資工', '物理', '數學', '化學', '材料', '工業工程',
    '工程科學', '理工',
]

MANAGEMENT_KEYWORDS = [
    '主任', '經理', 'Manager', '協理', '處長', '總監', 'Director',
    'Lead', '部門主管',
]

SENIOR_KEYWORDS = [
    '資深', 'Senior', '副理', '課長', '組長', '襄理',
]


def score_bim_manager(candidate):
    """
    Score candidate specifically for BIM Manager position at CTCI.

    Args:
        candidate: dict from extractor.extract_from_markdown()

    Returns:
        dict with score breakdown per dimension and recommendation
    """
    full_text = candidate.get('full_text', '')
    edu = candidate.get('education', '')
    recent_work = candidate.get('recent_work', '')
    recent_work_desc = candidate.get('recent_work_desc', '')
    lang = candidate.get('language_skills', '')
    seniority = candidate.get('seniority', '')
    work_lines = candidate.get('work_lines', [])
    work_text = '\n'.join(work_lines)
    combined = full_text + '\n' + recent_work_desc

    details = {}

    # 1. Education Match (max 20)
    edu_score = 0
    edu_reason = "未提及學歷"
    if any(kw in edu for kw in EDUCATION_ENGINEERING):
        edu_score = 20
        hits = [kw for kw in EDUCATION_ENGINEERING if kw in edu]
        edu_reason = f"工程相關科系: {','.join(hits[:2])}"
    elif any(kw in edu for kw in EDUCATION_SCIENCE):
        edu_score = 10
        hits = [kw for kw in EDUCATION_SCIENCE if kw in edu]
        edu_reason = f"理工相關: {','.join(hits[:2])}"
    elif edu:
        edu_score = 5
        edu_reason = f"其他科系: {edu[:20]}"
    details['education_match'] = {'score': edu_score, 'max': 20, 'reason': edu_reason}

    # 2. BIM Experience (max 25)
    bim_score = 0
    bim_hits = [kw for kw in BIM_KEYWORDS if kw.lower() in combined.lower()]
    bim_reason = "未發現BIM相關經驗"

    if len(bim_hits) >= 5:
        bim_score = 25
        bim_reason = f"豐富BIM經驗: {','.join(bim_hits[:4])} ({len(bim_hits)}項命中)"
    elif len(bim_hits) >= 3:
        bim_score = 20
        bim_reason = f"良好BIM經驗: {','.join(bim_hits[:3])}"
    elif len(bim_hits) >= 1:
        bim_score = 10
        bim_reason = f"基礎BIM經驗: {','.join(bim_hits[:2])}"

    # Seniority boost for BIM
    sen_num = 0
    if seniority:
        sen_m = re.search(r'(\d+)', seniority)
        if sen_m:
            sen_num = int(sen_m.group(1))
    if bim_hits and sen_num >= 3:
        bim_score = min(bim_score + 5, 25)
        bim_reason += f" + {sen_num}年資歷"

    details['bim_experience'] = {'score': bim_score, 'max': 25, 'reason': bim_reason}

    # 3. English Proficiency (max 15)
    eng_score = 0
    eng_reason = "未提及英語能力"

    # Check TOEIC score
    toeic_match = re.search(r'TOEIC[:\s]*(\d+)', combined, re.IGNORECASE)
    if not toeic_match:
        toeic_match = re.search(r'多益[:\s]*(\d+)', combined)

    if toeic_match:
        toeic_val = int(toeic_match.group(1))
        if toeic_val >= 700:
            eng_score = 15
            eng_reason = f"TOEIC {toeic_val} (優秀)"
        elif toeic_val >= 500:
            eng_score = 12
            eng_reason = f"TOEIC {toeic_val} (達標)"
        else:
            eng_score = 5
            eng_reason = f"TOEIC {toeic_val} (未達500門檻)"
    elif '精通' in lang and '英文' in lang:
        eng_score = 15
        eng_reason = "英文精通"
    elif '中等' in lang and '英文' in lang:
        eng_score = 10
        eng_reason = "英文中等"
    elif '英文' in lang:
        eng_score = 7
        eng_reason = "具備英文能力"

    details['english_proficiency'] = {'score': eng_score, 'max': 15, 'reason': eng_reason}

    # 4. Engineering Skills (max 25)
    eng_skill_score = 0
    eng_skill_hits = [kw for kw in ENGINEERING_SKILL_KEYWORDS if kw in combined]
    eng_skill_reason = "未發現工程專業關鍵字"

    if len(eng_skill_hits) >= 6:
        eng_skill_score = 25
        eng_skill_reason = f"豐富工程經驗: {','.join(eng_skill_hits[:5])} ({len(eng_skill_hits)}項)"
    elif len(eng_skill_hits) >= 4:
        eng_skill_score = 20
        eng_skill_reason = f"良好工程基礎: {','.join(eng_skill_hits[:4])}"
    elif len(eng_skill_hits) >= 2:
        eng_skill_score = 12
        eng_skill_reason = f"基礎工程能力: {','.join(eng_skill_hits[:3])}"
    elif len(eng_skill_hits) >= 1:
        eng_skill_score = 5
        eng_skill_reason = f"少量工程經驗: {','.join(eng_skill_hits)}"

    details['engineering_skills'] = {'score': eng_skill_score, 'max': 25, 'reason': eng_skill_reason}

    # 5. Management Level (max 15)
    mgmt_score = 0
    mgmt_reason = "一般職級"

    mgmt_hits = [kw for kw in MANAGEMENT_KEYWORDS if kw in recent_work or kw in combined[:500]]
    senior_hits = [kw for kw in SENIOR_KEYWORDS if kw in recent_work or kw in combined[:500]]

    if mgmt_hits:
        mgmt_score = 15
        mgmt_reason = f"管理層級: {','.join(mgmt_hits[:2])}"
    elif senior_hits:
        mgmt_score = 10
        mgmt_reason = f"資深人員: {','.join(senior_hits[:2])}"
    elif sen_num >= 3:
        mgmt_score = 5
        mgmt_reason = f"具{sen_num}年經驗"

    details['management_level'] = {'score': mgmt_score, 'max': 15, 'reason': mgmt_reason}

    # Total
    total_score = sum(d['score'] for d in details.values())
    max_score = sum(d['max'] for d in details.values())
    match_pct = round(total_score / max_score * 100) if max_score > 0 else 0

    # Recommendation
    if match_pct >= 80:
        recommendation = "強力推薦 — 高度符合BIM主任職缺，建議優先安排面試"
        level = "excellent"
    elif match_pct >= 60:
        recommendation = "建議面試 — 具備多數所需條件，面試中可確認細節"
        level = "good"
    elif match_pct >= 40:
        recommendation = "可考慮 — 部分條件符合，適合初階BIM職位或培訓發展"
        level = "partial"
    else:
        recommendation = "不推薦 — 與BIM主任職缺需求差距較大"
        level = "low"

    return {
        'score': total_score,
        'max_score': max_score,
        'match_percentage': match_pct,
        'details': details,
        'recommendation': recommendation,
        'level': level,
    }
