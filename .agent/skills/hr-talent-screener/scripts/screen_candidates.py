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
import argparse

# Ensure UTF-8 output on Windows terminals (prevents cp950 UnicodeEncodeError)
if sys.stdout.encoding != 'utf-8':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

# 多角色 overlay 機制
# default = 既有 v8.13 行為（不變），mep-design / space-manager 啟用 overlay 加分與條件化解禁
SUPPORTED_ROLES = ['default', 'mep-design', 'space-manager']

# Overlay 用的 BIM 與 MEP 關鍵字組（N18 BIM × MEP 共現用）
BIM_TOKENS = [
    'BIM', 'Revit', 'Navisworks', 'IFC', 'BEP', 'LOD', 'BIM360', 'CDE',
    'clash', 'Clash', '碰撞', '衝突檢測', '模型協調', '模型整合', 'Dynamo',
    # v0.3 新增（依 2026-04-30 結案 11 位正式候選實證工具）
    'Smart3D', 'SmartPlant', 'SketchUp', 'BIM-19650', 'ISO 19650',
]
MEP_TOKENS = [
    '空調', 'HVAC', '消防', '電力', '配電', '給排水', '純水', '廢水',
    '管線', '配管', '機電', 'MEP', '五大管線', '無塵室', '潔淨室',
    '冰水', '冷卻水', 'P&ID', '建廠', '擴廠', 'EPC', '統包',
]
# space-manager 專用關鍵字
SPACE_TOKENS = [
    '空間規劃', '空間整合', '空間管理', 'Space Planning', '淨高', '淨空',
    '樓層配置', '配置', '平面規劃', '樓板', '機房', '管道間', 'Shaft',
]
REGULATION_TOKENS = [
    '建築技術規則', '消防法規', '無障礙', '綠建築', 'IECC', 'ASHRAE', 'NFPA',
    '規範', '法規', '標準', 'Code', '合規', '申照', '檢查', '查驗',
    # v0.3 新增（依 2026-04-30 結案 11 位實證；保守：只加「具體認證/法規制度」）
    '執照圖', '申照圖', '性能式審查', 'WELL', '鉑金級', 'PIC/S', 'GMP',
    'local code',
]
CROSS_SYSTEM_TOKENS = [
    '跨系統', '界面整合', '界面協調', 'Coordination', 'Clash',
    '衝突檢測', '碰撞檢測', 'Integration', '整合', '協調',
    '跨領域', 'Multi-discipline',
    # v0.3 新增（依 2026-04-30 結案 11 位實證；保守：避開純建模常用詞）
    # 注意：故意不加 'CSD', '審圖', '套圖' 單詞——這些在純建模履歷中也大量出現會誤判
    'CSD/SEM', 'CSD&SEM', 'PCM&承攬商', 'PCM承攬商',
]
# space-manager v0.2 新增（用於 _is_bim_unlock 收緊、D11/D12/D13）
MEP_SUBSTANCE_TOKENS = [
    '機電', '空調', 'HVAC', '消防', '電力', '配電', '給排水',
    '管線', '配管', '無塵室', '建廠', '擴廠', 'MEP', '廠務',
    '監造', '監工', '水處理',
]
MODELING_TERMS = [
    '繪圖', '建模', '塑模', '套圖', '審圖', '模型',
]
STRUCTURE_TOKENS = [
    '柱樑', '樑柱', '結構設計', '結構分析', '結構技師',
    '混凝土', '鋼筋', '配筋', 'RC結構', 'SRC', 'SS結構',
]
TEACHING_TOKENS = [
    '兼任講師', '兼講師', '課程講師', '教學助教',
    '實習助教', '教育訓練', 'Trainer', 'Instructor',
]


class RoleOverlay:
    """角色 overlay 配置：default 行為由所有 flag 為 False 表達，與 v8.13 完全一致。"""

    def __init__(self, role_name='default'):
        self.role_name = role_name
        # N 條件 overlay
        self.n6_independent_score = 0      # >0 時 N6 獨立計分（mep-design / space-manager: 12）
        self.enable_n18_bim_mep = False    # BIM × MEP 共現
        self.n18_base_weight = 0           # 命中 1 段 +N，命中 2+ 段 +(N+3)
        self.enable_n19_space_reg = False  # 空間整合 / 法規理解
        self.enable_n20_cross_system = False  # 跨系統界面協調
        self.n1_weight_override = None     # space-manager: 微降為 +10
        self.n17_weight_override = None    # tuple (single_hit, multi_hit) 覆寫 N17 加分
        # E 條件 overlay
        self.unlock_e2_e6_e8_for_engineering = False  # 條件化解禁
        self.require_mep_substance_for_unlock = False  # space-manager v0.2: 解禁需 MEP 實質
        self.tighten_interior_design_unlock = False    # space-manager v0.2: 室內設計收緊解禁
        # D 條件 overlay
        self.enable_d7_bim_only = False
        self.d7_space_softens_penalty = False  # space-manager: 若有空間/整合命中則不扣 D7
        self.enable_d11_bim_instructor = False         # space-manager v0.2: BIM 講師/教學降級
        self.enable_d12_pure_modeler = False           # space-manager v0.2: 純建模人員降級
        self.enable_d13_pure_civil_structure = False   # space-manager v0.2: 純土建結構降級
        self.enable_bim_developer_unlock = False       # space-manager v0.3: Q1 解禁 BIM+軟體開發者
        self.enable_high_tech_vip_unlock = False       # space-manager v0.3: Q4 解禁頂尖高科 BIM 人才
        self.enable_bim_developer_unlock = False
        self.enable_high_tech_vip_unlock = False


def get_overlay(role_name):
    """根據 role_name 取得對應 overlay 配置。"""
    overlay = RoleOverlay(role_name)
    if role_name == 'mep-design':
        overlay.n6_independent_score = 12
        overlay.enable_n18_bim_mep = True
        overlay.n18_base_weight = 12
        overlay.n17_weight_override = (8, 15)  # default: (10, 20)
        overlay.unlock_e2_e6_e8_for_engineering = True
        overlay.enable_d7_bim_only = True
        overlay.require_mep_substance_for_unlock = True
        overlay.tighten_interior_design_unlock = True
        overlay.enable_d12_pure_modeler = True
    elif role_name == 'space-manager':
        overlay.n6_independent_score = 12
        overlay.enable_n18_bim_mep = True
        overlay.n18_base_weight = 8
        overlay.enable_n19_space_reg = True
        overlay.enable_n20_cross_system = True
        overlay.n1_weight_override = 10
        overlay.n17_weight_override = (5, 10)
        overlay.unlock_e2_e6_e8_for_engineering = True
        overlay.enable_d7_bim_only = True
        overlay.d7_space_softens_penalty = True
        # v0.2 收緊（依 2026-04-30 使用者回饋：5 位純建模/講師/室內設計/結構柱樑誤選）
        overlay.require_mep_substance_for_unlock = True
        overlay.tighten_interior_design_unlock = True
        overlay.enable_d11_bim_instructor = True
        overlay.enable_d12_pure_modeler = True
        overlay.enable_d13_pure_civil_structure = True
        overlay.enable_bim_developer_unlock = True
        overlay.enable_high_tech_vip_unlock = True
        overlay.enable_bim_developer_unlock = True
        overlay.enable_high_tech_vip_unlock = True
    return overlay


def _count_bim_mep_cooccurrence(work_lines):
    """計算 BIM × MEP 共現的段落數（同一段中同時出現 BIM 與 MEP 關鍵字才算）。"""
    cooccur = 0
    for line in work_lines:
        has_bim = any(tok in line for tok in BIM_TOKENS)
        has_mep = any(tok in line for tok in MEP_TOKENS)
        if has_bim and has_mep:
            cooccur += 1
    return cooccur

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
    '中鼎', '泰興', '達欣', '潤弘', '大林組',
    '台積', '世界先進', '美光', '聯電', '欣興', '長春', '亞東氣體',
    '大陸工程', '日月光', '力晶', '鴻海', '臻鼎', '台灣神隆', '日揮', '恩智浦',
    # 高科技 EPC / 半導體廠務競業公司
    '亞翔', '漢唐', '帆宣', '洋基', '信紘科', '擎邦', '同開',
    '千附', '聖暉', '朋億', '互助營造', '瑞助',
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

# ============================
# 高科技建廠特化規則 (CTCI High-Tech Fab Specialization)
# ============================

# N17: 高科技建廠核心關鍵字 (★★★★) — 最高權重
# 這些字眼直接代表高科技廠房 MEP/Utility 建廠的核心能力
HIGH_TECH_FAB_KEYWORDS = [
    '無塵室', '潔淨室', 'Cleanroom', 'FAB', 'UPW', 'WWT',
    '特氣', '大宗氣體', 'Bulk Gas', '製程排氣', 'Scrubber', 'VOC',
    '製程冷卻水', 'PCW', 'Hook-up', 'CDA',
    '化學供應', 'Chemical', '酸鹼', 'Slurry',
    'EPCK', '試車', 'Commissioning',
    '高科技廠', '半導體廠', '晶圓廠', '面板廠', 'Utility',
]

# 傳統重電/設備公司 — 需搭配高科關鍵字才給予全額加分
TRADITIONAL_CONDITIONAL_COMPANIES = ['中興電工', '士林電機', '東元']


# 排除條件
EXCLUDE_TITLES = [
    '保全', '門市', '餐飲', '銷售', '業務員', '店長', '服務生',
    '司機', '總幹事', '保險', '房仲', '理財', '服務業',
]

# E2 排除：希望職稱明確為非工程方向，或為與機電無關的軟硬體/設計
NON_ENGINEERING_DESIRED = [
    '會計', '秘書', '行政', '財務', '人資', '人事', '人力資源',
    '客服', '文書', '總務', '櫃台', '店員', '專員', '助理',
    '軟體', '後端', '前端', '韌體', '資訊', '網管', 'MIS', 
    '研發', '研究', 'CAE', '機構', '熱流', '機器人', '品保', '驗證',
    'BIM工程師', '內業', '專案業務', '系統整合', '講師', '教育', '室內裝修', '室內設計', '建築設計', '業務', '庶務', '物流', '行銷', '航空',
    '軟工', '軟體工程師', '土開', '土地開發', '研究類別', 'HR', '招募', 'Talent', 'Recruiter', '客戶經理', '客戶服務', '自動控制工程師', '機構設計',
    '實驗室', '校正', '稽核', '採購', '發包', '產品', 'AIOT', '電商', '業助', '服務工程師'
]

# E5 排除：製程/製造/非建廠端
NON_CONSTRUCTION_MANUFACTURING = [
    '製程', '製造', '生產', '設備工程師', '技術工程師', '生產線', '品保', '機械製造',
    '自動控制', '設計', '機構設計', '工程師', '操作', 'PLC', '電控', 'Field Service', 
    '客服', '設計工程師', '售後服務', 'AIOT', '產品', '韌體', 'FAE', 'fae', '應用工程師',
    '研發', 'RD', 'R&D', 'rd', '光機', '光電', '微影', '顯示', '開發', '設備維護', '運轉維護', '保養', '設備保養', '服務工程師', '安裝調試員'
]

# E6 排除：脫離高度工程專業 (低階勞力/非專業)
LOW_SKILL_KEYWORDS = [
    '作業員', '操作員', '技術員', '技術人員', '助理', '保養', '維修', '外場', '內場', '司機', '理貨', 
    '飯店', '旅館', '專員', '維修工程師', '後勤', '裝配', '組裝', '客服工程師', '倉管', '倉庫', '焊接',
    '重機械', '引擎', '管輪', '製圖員', '操作', '養護', '外務', '柏文健康', '家福', '健身', '店長', '修繕',
    '大廈維護', '大樓維護', '大廈管理', '駐點', '展場', '繪圖員', 'BIM建模員', '總務', '後端', '研究類別', '研究員',
    '實習生', '學徒', '工讀生', '中控', '夜班', '服務人員', '營業員', '助手', '檢修', '技工', '半技', '粗工', '物業', '機械技術', '組員', '工務助理', '水電技師', '服務員', '銷售員', '外送員', '兼職', '兼職人員', '正職', '領班', 'PT'
]

# E7 排除：工安/環安衛人員
EHS_KEYWORDS = [
    '環安', '職安', '工安', '勞安', '安衛', 'EHS', '安全衛生', '環境工程師'
]

# E8 絕對封殺：無視任何加分/工程字眼的領域 (軟工、展場、純繪圖等)
ABSOLUTE_KILL_KEYWORDS = [
    '軟工', '軟體工程師', '展場', '繪圖員', 'bim建模員', '室內設計'
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
def score_candidate(c, overlay=None):
    """對單一候選人進行規則評分，回傳 (分數, 理由列表, 是否排除)。

    overlay 為 None 時自動建立 default overlay（行為與 v8.13 完全一致）。
    """

    if overlay is None:
        overlay = RoleOverlay('default')

    score = 0
    reasons = []
    full = c['full_text']
    work_text = '\n'.join(c['work_lines'])
    edu = c['edu']
    desired = c['desired_title']
    first_work = c['work_lines'][0] if c['work_lines'] else ""
    work_and_desired = work_text + '\n' + desired
    name_clean = c['name'].replace(' ', '')

    def _is_bim_unlock(c, work_text, desired, full):
        # 檢查是否為高科大廠 VIP 人才 (Q4)
        if overlay.enable_high_tech_vip_unlock:
            vip_companies = ['漢唐', '帆宣', '泰興', 'Exyte', '易科德', '亞翔', '洋基', '同開', '聖暉']
            has_vip = any(kw in full for kw in vip_companies)
            has_bim = any(kw in full.upper() for kw in ['BIM', 'REVIT'])
            if has_vip and has_bim:
                return True # 直接無條件解禁

        # default 解禁：必須具備至少一項工程 M 條件
        m1_hit = any(kw in full for kw in ['工程師', '主任', '經理', '專案', '管線', '監工'])
        m2_hit = any(kw in full for kw in ['機電', '水電', '空調', '廠務', '建設', '營造'])
        base_pass = m1_hit and m2_hit

        # space-manager v0.2: 解禁需要工作經歷有 MEP 實質字眼
        if overlay.require_mep_substance_for_unlock:
            has_mep_substance = any(tok in work_text for tok in MEP_SUBSTANCE_TOKENS)
            return base_pass and has_mep_substance

        return base_pass

    # E19: 絕對不可挽救的致命防呆 (無條件排除，不適用任何解禁)
    fatal_kill = [kw for kw in ['倉管', '業助', '組員', '安裝調試員', '服務工程師', '工務助理', '客服人員', '水電技師', '服務員', '銷售員', '外送員', '客服工程師', '技術助理工程師', '助理技術工程師', '資深技術員', '資深助理工程師', '資深技術工程師', '廠務助理工程師', '總務專員', '客服主任', '總務工程師', '園藝', '景觀', 'presales', '系辦助理', '口譯', '機構工程師', '機構設計', '機台', '維運人員', '空軍', '陸軍', '海軍', '國防部', '參謀', '士官', '志願役', '職業軍人'] if kw.lower() in work_and_desired.lower()]
    if fatal_kill:
        return 0, [f"排除(E19): 致命防呆不接受解禁={','.join(fatal_kill[:2])}"], True

    # E8: 絕對封殺 (無視其他工程師/機電加分字眼)
    kill_hits = [kw for kw in ABSOLUTE_KILL_KEYWORDS if kw in work_and_desired.lower() and kw not in desired.lower()]
    if kill_hits:
        if _is_bim_unlock(c, work_text, desired, full):
            reasons.append(f"E8條件化解禁({overlay.role_name}): {','.join(kill_hits[:2])}通過 M1/M2 工程門檻")
        else:
            return 0, [f"排除(E8): 絕對不適任={','.join(kill_hits[:2])}"], True

    # E1: 經歷純粹為保全/門市/餐飲
    if desired:
        exclude_hit = [kw for kw in EXCLUDE_TITLES if kw in desired]
        has_eng = any(kw in desired for kw in ['工程', '技術', '機電', '廠務', '監造', '主任'])
        if exclude_hit and not has_eng:
            return 0, [f"排除(E1): 希望職稱={desired[:30]}"], True

    # E2: 希望職稱包含非工程關鍵字
    if desired:
        e2_hits = [kw for kw in NON_ENGINEERING_DESIRED if kw in desired]
        if e2_hits:
            if _is_bim_unlock(c, work_text, desired, full):
                reasons.append(f"E2條件化解禁({overlay.role_name}): {','.join(e2_hits[:2])}通過 M1/M2 工程門檻")
            else:
                return 0, [f"排除(E2): 希望職稱非工程={desired[:30]}"], True

    # E3: 脫離高度工程專業（低階維修/作業員）
    low_skill_hits = [kw for kw in LOW_SKILL_KEYWORDS if kw in desired or kw in first_work]
    has_mgmt_or_eng = any(kw in desired + first_work for kw in ['工程師', '主任', '經理', '副理', '課長', '專案', '機電', '氣體'])
    
    # 特例防呆：這些職稱就算有工程師或機電字眼，也不能被救回
    unsavable_hits = [kw for kw in ['維修工程師', '技術工程師', '助理', '實習', '學徒', '中控', '夜班', '工讀', '助手', '專員', '駐點', '倉管', '倉庫', '器材', '物料', '總務', '行政', '人事', '檢修', '技工', '半技', '粗工', '保全', '駐衛警', '勤務', '物業', '機械技術', '工務助理', '業助', '組員', '水電技師', '服務員', '銷售員', '外送員', '技術人員', '兼職', '兼職人員', '正職', '領班', 'PT'] if kw in desired + first_work]
    if unsavable_hits:
        has_mgmt_or_eng = False

    if low_skill_hits and not has_mgmt_or_eng:
        if _is_bim_unlock(c, work_text, desired, full):
            reasons.append(f"E6/E3條件化解禁({overlay.role_name}): {','.join(low_skill_hits[:2])}通過 M1/M2 工程門檻")
        else:
            return 0, [f"排除(E3): 脫離工程專業={','.join(low_skill_hits[:2])}"], True

    # E4: 純土建/營造人員無建廠/廠房營造經驗
    is_pure_civil = (c['group'] == 'G1_土木建築') or any(kw in desired + work_text for kw in ['建築', '營建', '土木', '營造', '建設'])
    if is_pure_civil:
        has_factory = any(kw in work_and_desired for kw in ['建廠', '擴廠', '廠務', '無塵室', '統包', 'EPC', '科技廠', '半導體', '面板', '帆宣', '漢唐', '亞翔', '特氣', '管路'])
        if overlay.role_name == 'mep-design':
            has_mep_role = any(kw in (desired + work_text).upper() for kw in ['機電', 'MEP', '空調', '消防', '電力', '水處理', '水電', '廠務', '管線'])
        else:
            has_mep_role = any(kw in (desired + work_text).upper() for kw in ['機電', 'BIM', 'MEP', '空調', '消防', '電力', '水處理', '水電', '廠務', '管線'])
        if not (has_factory or has_mep_role):
            return 0, ["排除(E4): 土建/營造無機電建廠經驗"], True

    # E5: 機電/第三區塊人員若屬製程/製造/非建廠類
    if c['group'] in ('G2_機電相關', 'G3_其他'):
        if any(kw in work_and_desired for kw in NON_CONSTRUCTION_MANUFACTURING):
            has_facility_mep = any(kw in work_and_desired for kw in ['廠務', '建廠', '擴廠', '空調', '消防', '水處理', '無塵室', '特氣', '營造', '建設', '氣體', '中鼎', '機電', '配電', '電力', '水電'])
            if not has_facility_mep:
                return 0, ["排除(E5): 偏向製程/製造/非建廠屬性"], True

    # E7: 工安/環安衛人員（非機電工程/土建）
    ehs_hits = [kw for kw in EHS_KEYWORDS if kw in desired or kw in first_work]
    if ehs_hits:
        return 0, [f"排除(E7): 工安/環安衛={','.join(ehs_hits[:2])}"], True

    # E9: 偏向住宅工程/純建築無建廠
    residential_hits = [kw for kw in ['住宅', '住宅工程', '透天', '別墅'] if kw in work_and_desired]
    if residential_hits:
        has_factory = any(kw in work_and_desired for kw in ['建廠', '擴廠', '廠務', '無塵室', '統包', '科技廠', '半導體'])
        if not has_factory:
            return 0, [f"排除(E9): 偏向住宅工程={','.join(residential_hits[:2])}"], True

    # E10: 純水電勞務排除 (針對履歷單薄之水電工務)
    # 修正：不看希望職稱，必須真實近期經歷具備工程師/專案頭銜
    plumber_only = '水電' in desired + first_work and not any(kw in first_work for kw in ['工程師', '主任', '副理', '經理', '專案', '機電', '廠務'])
    has_thick = any(k in work_and_desired for k in ['規劃', '建廠', '新建', '擴廠', '專案', '統包', '無塵室', '廠務', '發包', '圖面', '監造'])
    if plumber_only and not has_thick:
        return 0, ["排除(E10): 履歷單薄之純水電/勞務工作"], True

    # E11: 純採購/發包/稽核排除 (無機電/建廠實務)
    procurement_only = any(kw in desired + first_work for kw in ['採購', '發包', '稽核', '能源管理'])
    if procurement_only:
        has_mep_role = any(kw in desired + work_text for kw in ['機電', '空調', '消防', '電力', '無塵室', '廠務', '建廠', '水處理'])
        if not has_mep_role:
            return 0, ["排除(E11): 純採購/企劃無機電實務"], True

    # E17: 純科技研發/軟體/業務/光電人員排除
    fatal_rd_software_hits = [kw for kw in ['軟硬體', '軟體', 'SQA', '演算法', 'BIOS', 'IC設計', '晶片', '前端', '後端', '全端', 'App開發', '業務', '光電', '研發', 'RD', '3d artist'] if kw in work_and_desired.lower()]
    if fatal_rd_software_hits:
        # space-manager v0.3: Q1 解禁 BIM 開發者
        if overlay.enable_bim_developer_unlock:
            has_bim = any(kw in work_and_desired.upper() for kw in ['BIM', 'REVIT', 'DYNAMO', 'API'])
            software_roles = ['前端', '後端', '全端', '軟體', 'app', 'developer', '3d artist']
            has_sw = any(kw in work_and_desired.lower() for kw in software_roles)
            if has_bim and has_sw:
                reasons.append(f"E17條件化解禁({overlay.role_name}): BIM 開發者/高階應用人才")
                fatal_rd_software_hits = [] # bypass
        if fatal_rd_software_hits:
            return 0, [f"排除(E17): 純軟體/研發/業務人員({','.join(fatal_rd_software_hits[:2])})"], True

    # E18: 純人資/行政專職防呆 (針對利用希望職稱寫廠務但實際全為HR者)
    hr_hits = [kw for kw in ['人資', 'HR', '招募', 'Recruiter', 'Talent Acquisition'] if kw in work_and_desired]
    if hr_hits:
        has_mep_role = any(kw in work_text for kw in ['機電', '空調', '消防', '電力', '無塵室', '廠務', '建廠', '水處理', '水電', '配管'])
        if not has_mep_role:
            return 0, [f"排除(E18): 人資/招募專職({','.join(hr_hits[:2])})"], True

    # 特例：楊遠志、邱弘瀚、黃新益 (依使用者 Batch 29 回饋直接封殺)
    if c['name'] in ['楊遠志', '邱弘瀚', '黃新益']:
        return 0, ["排除: 用戶指定無明確建廠/經歷單薄/非工程專精"], True

    # E12: 大樓物業/商場維護防呆
    property_hits = [kw for kw in ['公寓大廈', '物業', '保全', '百貨', '商場', '量販', '社區管理', '管委會', '京站', '微風', '購物中心'] if kw in work_and_desired]
    if property_hits:
        has_factory = any(kw in work_and_desired for kw in ['建廠', '擴廠', '廠務', '無塵室', '統包', '科技廠', '半導體'])
        if not has_factory:
            return 0, [f"排除(E12): 大樓物業/商場維護={','.join(property_hits[:2])}"], True

    # E13: 服務業轉型且工程經歷單薄防呆
    has_thick_work = any(k in work_text for k in ['規劃', '建廠', '新建', '擴廠', '專案', '統包', '無塵室', '廠務', '發包', '圖面', '監造'])
    non_eng_bg_hits = sum(1 for line in c['work_lines'] if any(kw in line for kw in ['餐廳', '門市', '吧台', '服務人員', '服務員', '銷售員', '外送員', '美容', '保全', '店長', '理貨', '餐飲', '內場', '外場', '司機', '快餐', '專賣店', '飲料', '櫃台', '飯店', '農場', 'PT']))
    eng_job_hits = sum(1 for line in c['work_lines'] if any(kw in line for kw in ['工程', '機電', '廠務', '水電', '空調', '消防']))
    if non_eng_bg_hits >= 2 and eng_job_hits <= 1 and not has_thick_work:
        return 0, ["排除(E13): 服務業轉型且工程經歷單薄"], True

    # E14: 非專業科系且無厚度經歷防呆
    non_eng_edu = any(kw in c['edu'] for kw in ['設計', '餐飲', '美容', '觀光', '語文', '幼保', '休閒', '保健', '食品'])
    if non_eng_edu and not has_thick_work:
        return 0, ["排除(E14): 非專業科系背景且工程履歷單薄"], True

    # E15: 缺乏核心機電實務且經歷混雜防呆 (Q3 強化版)
    core_mep_hits = [kw for kw in ['空調', '消防', '水處理', '管線', 'BIM', 'MEP', '廠務', '水電', '無塵室', '建廠', '統包'] if kw in (work_and_desired).upper()]
    low_level_jobs = ['操作員', '技術人員', '服務人員', '門市', '餐飲', '保全', '總務', '作業員', '理貨', '美容', '行政', '櫃檯', '專櫃']
    has_low_jobs = any(kw in work_text for kw in low_level_jobs)
    
    # 計算工程經歷行數
    eng_lines = [l for l in c['work_lines'] if any(k in l for k in ['工程', '機電', '廠務', '設計', 'BIM', 'bim', '空調', '消防', '製圖', '繪圖'])]
    if has_low_jobs and len(eng_lines) <= 2 and not any(kw in work_and_desired for kw in ['規劃', '建廠', '新建', '擴廠']):
        return 0, ["排除(E15): 工程經歷過短且夾雜大量非專業經歷"], True
        
    if not core_mep_hits:
        if has_low_jobs:
            return 0, ["排除(E15): 缺乏核心機電實務且經歷混雜"], True

    # E16: 機電整合/自動控制/航太等非廠房設施防呆
    automation_hits = [kw for kw in ['機電整合', '自動化設備', '自動控制', 'PLC', '電控', '航太', '航空', ' cnc', 'CNC'] if kw in work_and_desired]
    if automation_hits:
        # 必須要有廠務或建廠相關的明確設施關鍵字才能豁免
        has_real_facility = any(kw in work_and_desired for kw in ['廠務', '建廠', '無塵室', '空調', '水電', '消防', '水處理'])
        if not has_real_facility:
            return 0, [f"排除(E16): 偏向自動化/製造/航太({','.join(automation_hits[:2])})"], True

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
    # N1: 學歷科系 (★★★) — overlay 可覆寫權重（space-manager: +10）
    n1_hits = [kw for kw in EDU_KEYWORDS if kw in edu]
    if n1_hits:
        n1_weight = overlay.n1_weight_override if overlay.n1_weight_override is not None else 15
        score += n1_weight
        if overlay.n1_weight_override is not None:
            reasons.append(f"N1學歷對口: {','.join(n1_hits[:2])} (+{n1_weight})")
        else:
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

    # N6: BIM/Revit/AutoCAD 獨立計分（僅在 mep-design / space-manager overlay 下啟用）
    if overlay.n6_independent_score > 0:
        n6_hits = [kw for kw in BIM_TOKENS if kw in full]
        if n6_hits:
            score += overlay.n6_independent_score
            reasons.append(f"N6 BIM工具能力: {','.join(n6_hits[:3])} (+{overlay.n6_independent_score})")

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

    # === 高科技建廠特化加分 (CTCI High-Tech Fab Specialization) ===

    # N17: 高科技建廠核心經驗 (★★★★) — 最高權重
    # 命中 2 項以上 = +20 (VIP級高科即戰力)
    # 命中 1 項    = +10 (具備高科基礎)
    # overlay 可覆寫加分 tuple (single_hit, multi_hit)
    n17_overridden = overlay.n17_weight_override is not None
    n17_single, n17_multi = overlay.n17_weight_override if n17_overridden else (10, 20)
    n17_hits = [kw for kw in HIGH_TECH_FAB_KEYWORDS if kw in full]
    if len(n17_hits) >= 2:
        score += n17_multi
        suffix = f" (+{n17_multi})" if n17_overridden else ""
        reasons.append(f"N17高科建廠VIP: {','.join(n17_hits[:4])} ({len(n17_hits)}項){suffix}")
    elif len(n17_hits) >= 1:
        score += n17_single
        suffix = f" (+{n17_single})" if n17_overridden else ""
        reasons.append(f"N17高科建廠: {','.join(n17_hits[:3])}{suffix}")

    # === Overlay-only 加分（mep-design / space-manager）===

    # N18: BIM × MEP 共現（反「BIM 表演」核心規則）
    if overlay.enable_n18_bim_mep:
        cooccur_count = _count_bim_mep_cooccurrence(c['work_lines'])
        if cooccur_count >= 2:
            score += overlay.n18_base_weight + 3
            reasons.append(f"N18 BIM×MEP共現({cooccur_count}段) (+{overlay.n18_base_weight + 3})")
        elif cooccur_count == 1:
            score += overlay.n18_base_weight
            reasons.append(f"N18 BIM×MEP共現(1段) (+{overlay.n18_base_weight})")

    # N19: 空間整合 / 法規理解（space-manager 核心）
    if overlay.enable_n19_space_reg:
        space_hits = [kw for kw in SPACE_TOKENS if kw in full]
        reg_hits = [kw for kw in REGULATION_TOKENS if kw in full]
        if space_hits and reg_hits:
            score += 15
            reasons.append(f"N19空間+法規: {','.join((space_hits + reg_hits)[:3])} (+15)")
        elif space_hits:
            score += 8
            reasons.append(f"N19空間規劃: {','.join(space_hits[:2])} (+8)")
        elif reg_hits:
            score += 6
            reasons.append(f"N19法規理解: {','.join(reg_hits[:2])} (+6)")

    # N20: 跨系統界面協調（space-manager 核心）
    if overlay.enable_n20_cross_system:
        cross_hits = [kw for kw in CROSS_SYSTEM_TOKENS if kw in full]
        if len(cross_hits) >= 2:
            score += 12
            reasons.append(f"N20跨系統整合: {','.join(cross_hits[:3])} ({len(cross_hits)}項) (+12)")
        elif len(cross_hits) == 1:
            score += 6
            reasons.append(f"N20跨系統整合: {cross_hits[0]} (+6)")

    # 傳統重電降階: 僅命中傳統公司(中興電工/士林電機/東元)但無任何高科關鍵字
    # → 扣回 M2 給的 10 分，因為傳統重電(變電站/馬達)≠高科建廠(FAB/Utility)
    trad_hits = [kw for kw in TRADITIONAL_CONDITIONAL_COMPANIES if kw in full]
    if trad_hits and not n17_hits:
        score -= 10
        reasons.append(f"傳統重電降階: {','.join(trad_hits[:2])}(無高科經驗)")

    # 年資/年齡動態防呆: 40歲以上且無高科建廠經驗也無知名EPC背景
    # → 表示資深但從未接觸高科廠房，轉型困難度高，扣5分
    age_num = 0
    age_match = re.search(r'(\d+)', c['age'])
    if age_match:
        age_num = int(age_match.group(1))
    if age_num >= 40 and not n17_hits:
        n23_check = [kw for kw in PREMIUM_COMPANIES if kw in full]
        if not n23_check:
            score -= 5
            reasons.append(f"年資防呆: {age_num}歲無高科/知名EPC經驗")

    # D3: 維運型廠務防呆 (扣 15 分)
    # 如果職稱包含廠務或設備，但履歷中缺乏規劃整合字眼
    facility_titles = ['廠務', '設備']
    planning_keywords = ['規劃', '建廠', '新建', '整合', '專案', 'mep', '統包']
    
    is_facility = any(k in desired for k in facility_titles) or any(k in first_work for k in facility_titles)
    has_planning = any(k in work_and_desired for k in planning_keywords)
    
    if is_facility and not has_planning:
        score -= 15
        reasons.append("D3廠務防呆: 偏維護缺乏規劃整合 (-15)")

    # D4: 製造端/測試端降階 (扣 15 分)
    # 針對測試、組裝、產線、加工、車廠等非建廠製造屬性
    mfg_penalty_keywords = ['測試', '產線', '組裝', '加工', '車廠', 'plc', 'smt', 'cnc']
    if any(k in work_and_desired.lower() for k in mfg_penalty_keywords):
        score -= 15
        reasons.append("D4製造降階: 偏向製造/測試端 (-15)")

    # D5: 採購/內業防呆 (扣 15 分)
    # 如果職稱包含採購，但履歷中缺乏實質機電工程字眼
    procurement_titles = ['採購']
    mep_procurement_keywords = ['機電', '空調', '消防', '電力', '管線', '發包', 'mep']
    
    is_procurement = any(k in work_and_desired for k in procurement_titles)
    has_mep_procurement = any(k in work_and_desired.lower() for k in mep_procurement_keywords)
    
    if is_procurement and not has_mep_procurement:
        score -= 15
        reasons.append("D5採購防呆: 純內業缺乏機電發包經驗 (-15)")

    # D6: 履歷單薄防呆 (依照 Batch 22 回饋改為不強制扣分淘汰，作為降級觀察)
    # 如果缺乏具體機電工程或建廠細節，且並未在知名公司任職
    thick_keywords = ['規劃', '建廠', '新建', '擴廠', '專案', '統包', '無塵室', '廠務', '發包', '圖面', '監造']
    has_thick = any(k in work_and_desired for k in thick_keywords)
    if not has_thick and len(n23_hits) == 0:
        # score -= 15  # 取消嚴格扣分
        reasons.append("D6履歷單薄(待PDF判定降級)")

    # D7: BIM-only 降級（mep-design / space-manager overlay 啟用，反「BIM 外衣」核心規則）
    if overlay.enable_d7_bim_only:
        has_bim = any(tok in work_and_desired for tok in BIM_TOKENS)
        has_mep_or_epc = any(
            tok in work_and_desired for tok in
            ['空調', '消防', '電力', '給排水', '機電', '廠務', '建廠', '擴廠',
             'EPC', '統包', 'MEP', '無塵室', 'HVAC', '管線', '配管']
        )
        if has_bim and not has_mep_or_epc:
            # space-manager 例外：若有空間/整合/法規關鍵字則不扣分
            if overlay.d7_space_softens_penalty:
                has_space_or_cross = (
                    any(tok in work_and_desired for tok in SPACE_TOKENS)
                    or any(tok in work_and_desired for tok in CROSS_SYSTEM_TOKENS)
                    or any(tok in work_and_desired for tok in REGULATION_TOKENS)
                )
                if not has_space_or_cross:
                    score -= 15
                    reasons.append("D7 BIM-only 降級: BIM 外衣但無工程/空間實質 (-15)")
            else:
                score -= 15
                reasons.append("D7 BIM-only 降級: BIM 外衣但無 MEP/廠務實質 (-15)")

    # D11: BIM 講師 / 教學身份降級（space-manager overlay v0.2）
    # 反「BIM 講師包裝」：候選人在 BIM 角色中兼任講師/教學/助教，視為偏教學而非工程實作
    if overlay.enable_d11_bim_instructor:
        triggered_segments = []
        for line in c['work_lines']:
            has_bim = any(tok in line for tok in BIM_TOKENS)
            teaching_hits = [tok for tok in TEACHING_TOKENS if tok in line]
            if has_bim and teaching_hits:
                triggered_segments.append(teaching_hits[0])
        desired_teaching = []
        if any(tok in desired for tok in BIM_TOKENS):
            desired_teaching = [t for t in ['教學', '助教', '講師'] if t in desired]
        if triggered_segments or desired_teaching:
            score -= 20
            evidence = (triggered_segments + desired_teaching)[:2]
            reasons.append(f"D11 BIM講師/教學身份: {','.join(evidence)} (-20)")

    # D12: 純建模人員降級（space-manager overlay v0.2）
    # 反「純 Revit 操作員」：BIM/繪圖/建模段落佔比過半，且純工程實質段（不含建模字眼）≤1
    if overlay.enable_d12_pure_modeler:
        related_segs = 0
        substance_segs_strict = 0
        for line in c['work_lines']:
            has_modeling = (
                any(tok in line for tok in BIM_TOKENS)
                or any(tok in line for tok in MODELING_TERMS)
            )
            has_substance = any(tok in line for tok in MEP_SUBSTANCE_TOKENS)
            if has_modeling:
                related_segs += 1
            if has_substance and not has_modeling:
                substance_segs_strict += 1
        total_segs = len(c['work_lines'])
        if total_segs >= 3 and related_segs / total_segs >= 0.5 and substance_segs_strict <= 1:
            # space-manager 例外：同時命中空間 AND 法規 → 不扣（具備空間規劃 + 規範理解可救回）
            has_space = any(tok in work_and_desired for tok in SPACE_TOKENS)
            has_reg = any(tok in work_and_desired for tok in REGULATION_TOKENS)
            if not (has_space and has_reg):
                score -= 25
                reasons.append(
                    f"D12 純建模人員: 建模段{related_segs}/{total_segs}, 純工程實質段{substance_segs_strict} (-25)"
                )

    # D13: 純土建/結構柱樑無 MEP/空間整合降級（space-manager overlay v0.2）
    # 反「結構繪圖匠」：履歷大量結構/柱樑/RC 字眼但缺 MEP 與空間整合，與空間管理職缺輪廓不符
    if overlay.enable_d13_pure_civil_structure:
        structure_hits = [kw for kw in STRUCTURE_TOKENS if kw in work_text]
        has_mep_token = any(tok in work_text for tok in MEP_TOKENS)
        has_space_token = any(tok in work_text for tok in SPACE_TOKENS)
        if len(structure_hits) >= 2 and not has_mep_token and not has_space_token:
            score -= 15
            reasons.append(f"D13 純土建結構: {','.join(structure_hits[:2])} 缺MEP/空間 (-15)")

    return score, reasons, False


# ============================
# 主流程
# ============================
def main():
    parser = argparse.ArgumentParser(
        description='候選人篩選引擎（支援多角色 overlay）',
        epilog='範例: python screen_candidates.py ANALYSIS.md --role=mep-design'
    )
    parser.add_argument('analysis_path', help='ANALYSIS.md 路徑')
    parser.add_argument(
        '--role', default='default', choices=SUPPORTED_ROLES,
        help='角色模式（預設 default = v8.13 既有行為）'
    )
    args = parser.parse_args()

    filepath = args.analysis_path
    role = args.role

    if not os.path.isfile(filepath):
        print(f"錯誤：找不到檔案 {filepath}")
        sys.exit(1)

    with open(filepath, 'r', encoding='utf-8') as f:
        lines = f.read().replace('\r\n', '\n').split('\n')

    candidates = parse_candidates(lines)
    overlay = get_overlay(role)
    print(f"角色模式: {role}")
    if role != 'default':
        print(f"  → 已載入 overlay: N6 獨立計分={overlay.n6_independent_score}, "
              f"N18 BIM×MEP={overlay.enable_n18_bim_mep}, "
              f"N19 空間/法規={overlay.enable_n19_space_reg}, "
              f"N20 跨系統={overlay.enable_n20_cross_system}, "
              f"D7 BIM-only={overlay.enable_d7_bim_only}")
    if any([overlay.enable_d11_bim_instructor,
            overlay.enable_d12_pure_modeler,
            overlay.enable_d13_pure_civil_structure]):
        print(f"  → space-manager v0.2 補強: D11 BIM講師, D12 純建模, D13 純土建結構, "
              f"E2/E8 解禁需 MEP 實質, 室內設計收緊")
    print(f"共解析 {len(candidates)} 位候選人\n")

    # 篩選
    results = {'G1_土木建築': [], 'G2_機電相關': [], 'G3_其他': [], '未分類': []}
    excluded = 0
    below_threshold = 0
    threshold = 20  # 最低分數門檻（v2.1 提高：避免泛用詞矇混）

    for c in candidates:
        score, reasons, is_excluded = score_candidate(c, overlay)
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
