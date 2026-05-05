# -*- coding: utf-8 -*-
"""
bim_scorer.py — Role-aware position scoring (default / mep-design / space-manager)

For default role: scores against the legacy CTCI BIM Manager (BIM主任) profile
(100 points across 5 dimensions; existing web app behavior preserved).

For mep-design / space-manager roles: applies multi-role overlay system per
.agent/skills/hr-talent-screener/references/role_overlays/<role>.md spec.
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

# Overlay-only keyword groups
SPACE_KEYWORDS = [
    '空間規劃', '空間整合', '空間管理', 'Space Planning', '淨高', '淨空',
    '樓層配置', '配置', '平面規劃', '機房', '管道間', 'Shaft',
]

REGULATION_KEYWORDS = [
    '建築技術規則', '消防法規', '無障礙', '綠建築', 'IECC', 'ASHRAE', 'NFPA',
    '規範', '法規', '標準', 'Code', '合規', '申照', '檢查', '查驗',
]

CROSS_SYSTEM_KEYWORDS = [
    '跨系統', '界面整合', '界面協調', 'Coordination', 'Clash',
    '衝突檢測', '碰撞檢測', 'Integration', '整合', '協調',
    '跨領域', 'Multi-discipline',
]


# Role-specific dimension weight table (max points per dimension)
ROLE_WEIGHTS = {
    'default': {
        'education_match': 20,
        'bim_experience': 25,
        'english_proficiency': 15,
        'engineering_skills': 25,
        'management_level': 15,
    },
    'mep-design': {
        'education_match': 20,
        'engineering_depth': 35,   # raised (core competency)
        'bim_experience': 15,      # lowered (avoid keyword stuffing)
        'english_proficiency': 15,
        'management_level': 15,
    },
    'space-manager': {
        'education_match': 15,     # slightly lowered
        'engineering_depth': 20,   # slightly lowered
        'bim_experience': 15,      # lowered
        'cross_system_integration': 20,  # NEW core
        'regulation_understanding': 10,  # NEW
        'english_proficiency': 15,
        'management_level': 5,     # significantly lowered (not management-oriented)
    },
}


def _count_bim_engineering_cooccurrence(work_lines, engineering_token_pool):
    """Count work-history segments where a BIM keyword AND an engineering keyword co-occur."""
    cooccur = 0
    for line in work_lines:
        has_bim = any(kw.lower() in line.lower() for kw in BIM_KEYWORDS)
        has_eng = any(kw in line for kw in engineering_token_pool)
        if has_bim and has_eng:
            cooccur += 1
    return cooccur


def _score_bim_experience_legacy(combined, sen_num):
    """Legacy keyword-count BIM scoring (default role)."""
    bim_hits = [kw for kw in BIM_KEYWORDS if kw.lower() in combined.lower()]
    if len(bim_hits) >= 5:
        score = 25
        reason = f"豐富BIM經驗: {','.join(bim_hits[:4])} ({len(bim_hits)}項命中)"
    elif len(bim_hits) >= 3:
        score = 20
        reason = f"良好BIM經驗: {','.join(bim_hits[:3])}"
    elif len(bim_hits) >= 1:
        score = 10
        reason = f"基礎BIM經驗: {','.join(bim_hits[:2])}"
    else:
        score = 0
        reason = "未發現BIM相關經驗"

    if bim_hits and sen_num >= 3:
        score = min(score + 5, 25)
        reason += f" + {sen_num}年資歷"
    return score, reason


def _score_bim_experience_cooccurrence(work_lines, max_pts, engineering_token_pool):
    """BIM × Engineering co-occurrence scoring (mep-design / space-manager)."""
    has_any_bim = any(any(kw.lower() in line.lower() for kw in BIM_KEYWORDS) for line in work_lines)
    cooccur_count = _count_bim_engineering_cooccurrence(work_lines, engineering_token_pool)

    if cooccur_count >= 3:
        score = max_pts
        reason = f"BIM×工程深度共現({cooccur_count}段) — 完整整合經驗"
    elif cooccur_count == 2:
        score = round(max_pts * 0.8)
        reason = f"BIM×工程共現(2段) — 良好整合經驗"
    elif cooccur_count == 1:
        score = round(max_pts * 0.55)
        reason = f"BIM×工程共現(1段) — 具基礎整合"
    elif has_any_bim:
        score = round(max_pts * 0.2)
        reason = "BIM 關鍵字命中但與工程系統未共現（疑似 BIM 表象）"
    else:
        score = 0
        reason = "未發現BIM相關經驗"
    return score, reason


def _score_education_default(edu):
    """Default role education scoring (legacy hardcoded values)."""
    if any(kw in edu for kw in EDUCATION_ENGINEERING):
        hits = [kw for kw in EDUCATION_ENGINEERING if kw in edu]
        return 20, f"工程相關科系: {','.join(hits[:2])}"
    if any(kw in edu for kw in EDUCATION_SCIENCE):
        hits = [kw for kw in EDUCATION_SCIENCE if kw in edu]
        return 10, f"理工相關: {','.join(hits[:2])}"
    if edu:
        return 5, f"其他科系: {edu[:20]}"
    return 0, "未提及學歷"


def _score_education_overlay(edu, max_pts):
    """Education score scaled to overlay max_pts (mep-design / space-manager)."""
    if any(kw in edu for kw in EDUCATION_ENGINEERING):
        hits = [kw for kw in EDUCATION_ENGINEERING if kw in edu]
        return max_pts, f"工程相關科系: {','.join(hits[:2])}"
    if any(kw in edu for kw in EDUCATION_SCIENCE):
        hits = [kw for kw in EDUCATION_SCIENCE if kw in edu]
        return round(max_pts * 0.5), f"理工相關: {','.join(hits[:2])}"
    if edu:
        return round(max_pts * 0.25), f"其他科系: {edu[:20]}"
    return 0, "未提及學歷"


def _score_engineering_skills_default(combined):
    """Default role engineering skills scoring (legacy hardcoded values)."""
    hits = [kw for kw in ENGINEERING_SKILL_KEYWORDS if kw in combined]
    if len(hits) >= 6:
        return 25, f"豐富工程經驗: {','.join(hits[:5])} ({len(hits)}項)"
    elif len(hits) >= 4:
        return 20, f"良好工程基礎: {','.join(hits[:4])}"
    elif len(hits) >= 2:
        return 12, f"基礎工程能力: {','.join(hits[:3])}"
    elif len(hits) >= 1:
        return 5, f"少量工程經驗: {','.join(hits)}"
    return 0, "未發現工程專業關鍵字"


def _score_engineering_skills_overlay(combined, max_pts):
    """Engineering depth scaled to overlay max_pts (mep-design / space-manager)."""
    hits = [kw for kw in ENGINEERING_SKILL_KEYWORDS if kw in combined]
    if len(hits) >= 6:
        return max_pts, f"豐富工程經驗: {','.join(hits[:5])} ({len(hits)}項)"
    elif len(hits) >= 4:
        return round(max_pts * 0.8), f"良好工程基礎: {','.join(hits[:4])}"
    elif len(hits) >= 2:
        return round(max_pts * 0.5), f"基礎工程能力: {','.join(hits[:3])}"
    elif len(hits) >= 1:
        return round(max_pts * 0.2), f"少量工程經驗: {','.join(hits)}"
    return 0, "未發現工程專業關鍵字"


def _score_english_default(combined, lang):
    """Default role English scoring (legacy hardcoded values)."""
    toeic_match = re.search(r'TOEIC[:\s]*(\d+)', combined, re.IGNORECASE)
    if not toeic_match:
        toeic_match = re.search(r'多益[:\s]*(\d+)', combined)
    if toeic_match:
        toeic_val = int(toeic_match.group(1))
        if toeic_val >= 700:
            return 15, f"TOEIC {toeic_val} (優秀)"
        elif toeic_val >= 500:
            return 12, f"TOEIC {toeic_val} (達標)"
        else:
            return 5, f"TOEIC {toeic_val} (未達500門檻)"
    if '精通' in lang and '英文' in lang:
        return 15, "英文精通"
    if '中等' in lang and '英文' in lang:
        return 10, "英文中等"
    if '英文' in lang:
        return 7, "具備英文能力"
    return 0, "未提及英語能力"


def _score_english_overlay(combined, lang, max_pts):
    """English scaled to overlay max_pts."""
    # Both default and overlay use same max (15), so this matches default behavior
    return _score_english_default(combined, lang) if max_pts == 15 else _scale_english(combined, lang, max_pts)


def _scale_english(combined, lang, max_pts):
    """English with custom max_pts (currently unused since all roles use 15)."""
    base_score, reason = _score_english_default(combined, lang)
    scaled = round(base_score / 15 * max_pts)
    return scaled, reason


def _score_management_default(recent_work, combined, sen_num):
    """Default role management scoring (legacy hardcoded values)."""
    mgmt_hits = [kw for kw in MANAGEMENT_KEYWORDS if kw in recent_work or kw in combined[:500]]
    senior_hits = [kw for kw in SENIOR_KEYWORDS if kw in recent_work or kw in combined[:500]]
    if mgmt_hits:
        return 15, f"管理層級: {','.join(mgmt_hits[:2])}"
    if senior_hits:
        return 10, f"資深人員: {','.join(senior_hits[:2])}"
    if sen_num >= 3:
        return 5, f"具{sen_num}年經驗"
    return 0, "一般職級"


def _score_management_overlay(recent_work, combined, sen_num, max_pts):
    """Management scaled to overlay max_pts."""
    base_score, reason = _score_management_default(recent_work, combined, sen_num)
    if max_pts == 15:
        return base_score, reason
    scaled = round(base_score / 15 * max_pts)
    return scaled, reason


def _score_cross_system(combined, max_pts):
    """Cross-system / space integration (space-manager only)."""
    space_hits = [kw for kw in SPACE_KEYWORDS if kw in combined]
    cross_hits = [kw for kw in CROSS_SYSTEM_KEYWORDS if kw in combined]
    total_hits = len(space_hits) + len(cross_hits)
    if total_hits >= 4:
        return max_pts, f"跨系統+空間整合(共 {total_hits} 項): {','.join((space_hits + cross_hits)[:3])}"
    elif total_hits >= 2:
        return round(max_pts * 0.7), f"基礎整合能力: {','.join((space_hits + cross_hits)[:2])}"
    elif total_hits >= 1:
        return round(max_pts * 0.3), f"少量整合經驗: {(space_hits + cross_hits)[0]}"
    return 0, "未發現跨系統/空間整合經驗"


def _score_regulation(combined, max_pts):
    """Regulation understanding (space-manager only)."""
    hits = [kw for kw in REGULATION_KEYWORDS if kw in combined]
    if len(hits) >= 3:
        return max_pts, f"豐富法規理解: {','.join(hits[:3])} ({len(hits)}項)"
    elif len(hits) >= 1:
        return round(max_pts * 0.6), f"基礎法規認知: {','.join(hits[:2])}"
    return 0, "未發現法規/規範關鍵字"


def score_bim_manager(candidate, role='default'):
    """
    Score a candidate against a role's overlay weights.

    Args:
        candidate: dict from extractor.extract_from_markdown()
        role: 'default' (legacy BIM Manager), 'mep-design', or 'space-manager'

    Returns:
        dict with score breakdown per dimension and recommendation
    """
    if role not in ROLE_WEIGHTS:
        role = 'default'

    full_text = candidate.get('full_text', '')
    edu = candidate.get('education', '')
    recent_work = candidate.get('recent_work', '')
    recent_work_desc = candidate.get('recent_work_desc', '')
    lang = candidate.get('language_skills', '')
    seniority = candidate.get('seniority', '')
    work_lines = candidate.get('work_lines', [])
    combined = full_text + '\n' + recent_work_desc

    # Compute total seniority years
    sen_num = 0
    if seniority:
        sen_m = re.search(r'(\d+)', seniority)
        if sen_m:
            sen_num = int(sen_m.group(1))

    weights = ROLE_WEIGHTS[role]
    details = {}

    # 1. Education match
    edu_pts = weights['education_match']
    if role == 'default':
        edu_score, edu_reason = _score_education_default(edu)
    else:
        edu_score, edu_reason = _score_education_overlay(edu, edu_pts)
    details['education_match'] = {'score': edu_score, 'max': edu_pts, 'reason': edu_reason}

    # 2. BIM experience (default = legacy keyword count; overlays = co-occurrence)
    bim_pts = weights['bim_experience']
    if role == 'default':
        bim_score, bim_reason = _score_bim_experience_legacy(combined, sen_num)
    else:
        bim_score, bim_reason = _score_bim_experience_cooccurrence(
            work_lines, bim_pts, ENGINEERING_SKILL_KEYWORDS
        )
    details['bim_experience'] = {'score': bim_score, 'max': bim_pts, 'reason': bim_reason}

    # 3. English proficiency
    eng_pts = weights['english_proficiency']
    if role == 'default':
        eng_score, eng_reason = _score_english_default(combined, lang)
    else:
        eng_score, eng_reason = _score_english_overlay(combined, lang, eng_pts)
    details['english_proficiency'] = {'score': eng_score, 'max': eng_pts, 'reason': eng_reason}

    # 4. Engineering skills/depth (key name varies: default=engineering_skills, overlay=engineering_depth)
    if role == 'default':
        eng_skill_key, eng_skill_pts = 'engineering_skills', weights['engineering_skills']
        eng_skill_score, eng_skill_reason = _score_engineering_skills_default(combined)
    else:
        eng_skill_key, eng_skill_pts = 'engineering_depth', weights['engineering_depth']
        eng_skill_score, eng_skill_reason = _score_engineering_skills_overlay(combined, eng_skill_pts)
    details[eng_skill_key] = {'score': eng_skill_score, 'max': eng_skill_pts, 'reason': eng_skill_reason}

    # 5. Management level
    mgmt_pts = weights['management_level']
    if role == 'default':
        mgmt_score, mgmt_reason = _score_management_default(recent_work, combined, sen_num)
    else:
        mgmt_score, mgmt_reason = _score_management_overlay(recent_work, combined, sen_num, mgmt_pts)
    details['management_level'] = {'score': mgmt_score, 'max': mgmt_pts, 'reason': mgmt_reason}

    # 6. Space-manager only: cross-system + regulation
    if role == 'space-manager':
        cs_pts = weights['cross_system_integration']
        cs_score, cs_reason = _score_cross_system(combined, cs_pts)
        details['cross_system_integration'] = {'score': cs_score, 'max': cs_pts, 'reason': cs_reason}

        reg_pts = weights['regulation_understanding']
        reg_score, reg_reason = _score_regulation(combined, reg_pts)
        details['regulation_understanding'] = {'score': reg_score, 'max': reg_pts, 'reason': reg_reason}

    # Total
    total_score = sum(d['score'] for d in details.values())
    max_score = sum(d['max'] for d in details.values())
    match_pct = round(total_score / max_score * 100) if max_score > 0 else 0

    # Recommendation
    role_label = {
        'default': 'BIM主任',
        'mep-design': 'MEP設計（做深）',
        'space-manager': '空間管理（做廣）',
    }[role]

    if match_pct >= 80:
        recommendation = f"強力推薦 — 高度符合{role_label}職缺，建議優先安排面試"
        level = "excellent"
    elif match_pct >= 60:
        recommendation = f"建議面試 — 具備多數所需條件，面試中可確認細節"
        level = "good"
    elif match_pct >= 40:
        recommendation = f"可考慮 — 部分條件符合，適合培訓發展或初階{role_label}職位"
        level = "partial"
    else:
        recommendation = f"不推薦 — 與{role_label}職缺需求差距較大"
        level = "low"

    return {
        'role': role,
        'score': total_score,
        'max_score': max_score,
        'match_percentage': match_pct,
        'details': details,
        'recommendation': recommendation,
        'level': level,
    }
