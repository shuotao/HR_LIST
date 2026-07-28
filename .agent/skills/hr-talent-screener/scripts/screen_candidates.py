# -*- coding: utf-8 -*-
"""
screen_candidates.py — 候選人篩選引擎

根據「人才候選計畫.md」中定義的規則，對清洗完的 ANALYSIS.md 進行評分篩選。
輸出符合條件的候選人姓名、所屬區塊與命中理由摘要。

同時比對名單蒐集階段的持久化回饋（皆 append-only，跨批次累積，由 /improve 蒐集階段維護）：
  ★ 命中 unqualify.md（引擎放行但使用者判定不合格 / 誤選 / false positive）
  ☆ 命中 qualify.md（引擎排除但使用者判定合格 / 漏選 / false negative；另列於結尾漏網清單）

用法：python screen_candidates.py <ANALYSIS.md 路徑> [--role=<role>]
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
# default = 主規則檔現行行為（版本見 screening_rules.md 第六節）；mep-design / space-manager 啟用 overlay 加分與條件化解禁
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
# 具體跨系統詞（語意明確，恆計入 N20）
CROSS_SYSTEM_SPECIFIC = [
    '跨系統', '界面整合', '界面協調', 'Coordination', 'Clash',
    '衝突檢測', '碰撞檢測', '跨領域', 'Multi-discipline',
    # v0.3 新增（依 2026-04-30 結案 11 位實證；保守：避開純建模常用詞）
    # 注意：故意不加 'CSD', '審圖', '套圖' 單詞——這些在純建模履歷中也大量出現會誤判
    'CSD/SEM', 'CSD&SEM', 'PCM&承攬商', 'PCM承攬商',
]
# 裸詞（v0.8, 2026-07-09 蘇庭漢回饋收緊）：易被 ERP/營運「系統整合」「資源整合」等
# 非建築語境誤命中，N20 須與工程領域上下文（CROSS_SYSTEM_CONTEXT）共現才計入。
CROSS_SYSTEM_LOOSE = ['整合', '協調', 'Integration']
# 向後相容：D7 例外等仍引用全集
CROSS_SYSTEM_TOKENS = CROSS_SYSTEM_SPECIFIC + CROSS_SYSTEM_LOOSE
# N20 裸詞上下文閘：工程領域證據詞。刻意不含裸「電力」「建設」——易被公司名
# （如「向陽優能電力」「◯◯建設」）誤觸，正是蘇庭漢型 ERP PM 混入的破口。
CROSS_SYSTEM_CONTEXT = [
    '機電', 'MEP', '管線', '配管', '空調', 'HVAC', '消防', '給排水',
    '純水', '廢水', '無塵室', '潔淨室', '建築', '土建', '結構', '機房',
    '弱電', '水電', '電氣', '施工圖', '圖面', 'P&ID', 'CSD', '套圖', '審圖',
]


def _n20_cross_hits(full):
    """N20 有效跨系統命中：具體詞恆計；裸詞（整合/協調/Integration）須與工程領域
    上下文共現才計（避免 ERP/營運『系統整合』等非建築語境誤命中——蘇庭漢型）。"""
    hits = [kw for kw in CROSS_SYSTEM_SPECIFIC if kw in full]
    loose = [kw for kw in CROSS_SYSTEM_LOOSE if kw in full]
    if loose and any(ctx in full for ctx in CROSS_SYSTEM_CONTEXT):
        hits.extend(loose)
    return hits
# space-manager v0.2 新增（用於 _is_bim_unlock 收緊、D11/D12/D13）
MEP_SUBSTANCE_TOKENS = [
    '機電', '空調', 'HVAC', '消防', '電力', '配電', '給排水',
    '管線', '配管', '無塵室', '建廠', '擴廠', 'MEP', '廠務',
    '水處理', '水電', 'Piping', 'piping', 'PIPING', 'Utility',
    'utility', 'UTILITY', 'Utilities', 'utilities', 'UTILITIES',
    'P&ID', '電機', '電氣', '電控', '配線',
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
    """角色 overlay 配置：default 行為由所有 flag 為 False 表達，即主規則檔現行行為（版本見 screening_rules.md 第六節）。"""

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
        # v10.2 新增（2026-05-27 4 人回饋）
        self.enable_d17_no_mgmt_potential = False  # 年資 ≥3 無管理抬頭且無規劃/整合軌跡 → 扣分
        self.enable_presales_escape = False        # E19 presales 若前 ≥2 段強相關 → 改 D 扣分而非排除
        self.enable_e4_global_consult_escape = False  # E4 若履歷含頂級工程顧問 + PCM/專案管理 → 解禁
        # v0.8 (2026-07-09 space-manager 回饋)：落地長期文件化但未實作的 D14
        self.enable_d14_traditional_field_worker = False  # 無 BIM/空間/法規/跨系統任一亮點 → -25


def get_overlay(role_name):
    """根據 role_name 取得對應 overlay 配置。"""
    # 處理 mep-design (deprecated alias) 自動 fallback 至 default
    if role_name == 'mep-design':
        role_name = 'default'

    overlay = RoleOverlay(role_name)
    if role_name == 'default':
        overlay.n6_independent_score = 12
        overlay.enable_n18_bim_mep = True
        overlay.n18_base_weight = 12
        overlay.n17_weight_override = (8, 15)  # default: (8, 15)
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
        # v10.2 (2026-05-27 4 人回饋)
        overlay.enable_d17_no_mgmt_potential = True
        overlay.enable_presales_escape = True
        overlay.enable_e4_global_consult_escape = True
        # v0.8 (2026-07-09)：落地 D14 傳統基層降級（規則早列於 screening_rules.md/overlay v0.4，程式碼漏實作）
        overlay.enable_d14_traditional_field_worker = True
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
    '中鼎', '漢科', '泰興', '仲量聯行', 'JLL', '達欣', '潤弘', '大林組',
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
    '中鼎', '漢科', '泰興', '達欣', '潤弘', '大林組',
    '台積', '世界先進', '美光', '聯電', '欣興', '長春', '亞東氣體',
    '大陸工程', '日月光', '力晶', '鴻海', '臻鼎', '台灣神隆', '日揮', '恩智浦',
    # 高科技 EPC / 半導體廠務競業公司
    '亞翔', '漢唐', '帆宣', '洋基', '信紘科', '擎邦', '同開',
    '千附', '聖暉', '朋億', '互助營造', '瑞助',
    # 全球頂級工程顧問 (v10.2 新增；2026-05-27 李承翰回饋：WSP/科進栢誠 PCM 經歷未被識別)
    'AECOM', '科進栢誠', 'WSP', 'Jacobs', 'Arup', 'Arcadis',
    'Mott MacDonald', 'Buro Happold', '鼎漢',
]

# Q4: 頂尖高科 EPC 大廠（space-manager VIP 解禁清單）
HIGH_TECH_VIP_COMPANIES = ['漢唐', '帆宣', '泰興', 'Exyte', '易科德', '亞翔', '洋基', '同開', '聖暉']


def _is_high_tech_vip_bim(full):
    """Q4 高科大廠 VIP + BIM 人才判定（v0.8, 2026-07-09 古芝妍回饋）。
    帆宣/洋基/漢唐等頂尖 EPC 大廠的 BIM 整合經驗＝正牌建廠整合，不應被當「BIM 外衣」，
    據此豁免 D3/D7 純建模懲罰（僅 space-manager 啟用 enable_high_tech_vip_unlock 時生效）。"""
    has_vip = any(kw in full for kw in HIGH_TECH_VIP_COMPANIES)
    has_bim = any(kw in full.upper() for kw in ['BIM', 'REVIT'])
    return has_vip and has_bim

# Q5: 中鼎內部轉發信號（v10.2 新增；2026-05-27 李承翰回饋）
# 條件：履歷甄試歷程含「@ctci.com」email → HR 內部已認可，自動 VIP 解禁
# 效果：+30 強加分，並豁免 E2/E4/E6/E8/E19 排除
CTCI_INTERNAL_SIGNAL = '@ctci.com'

# v10.3 (2026-05-27)：實質類關鍵字必須在 work_text 命中（不能被希望職稱單獨觸發）
# 楊國清回饋：希望職稱寫「國內外建廠」但工作經歷全是工地主任，被希望職稱關鍵字「灌水」入選
WORK_TEXT_ONLY_KEYWORDS = ['建廠', '擴廠', 'EPC統包', 'EPC建廠']

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
    '研發', 'RD', 'R&D', 'rd', '光機', '光電', '微影', '顯示', '開發', '設備維護', '運轉維護', '保養', '設備保養', '服務工程師', '安裝調試員',
    # v11.4 (Q4): 製造設備維修/加工端補漏——蔡明融型(CNC/機台/風機/輪轂設備維護，零建廠)
    'CNC', '機台組裝', '機台操作', '機械組裝', '輪轂', '風機維護', '風力發電機', '銑床'
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
def _back_n_nonblank(lines, anchor_idx, n=4):
    """從 anchor_idx 往前找第 n 個非空行的索引。

    Why: pipeline_clean.stage1 已壓掉所有空行；但若使用者沒跑 clean 直接餵原始
    ANALYSIS.md 給 parse_candidates，仍要安全。雙保險：anchor - n 改為「跳空行
    往前數 n 個非空行」，並在取出 block 後再過濾一次空行確保 block[N] 索引正確。
    """
    start = anchor_idx
    found = 0
    while start > 0 and found < n:
        start -= 1
        if lines[start].strip():
            found += 1
    return start


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
        start = _back_n_nonblank(lines, id_line_num, 4)
        end = _back_n_nonblank(lines, id_indices[idx + 1], 4) if idx + 1 < len(id_indices) else len(lines)
        raw_block = lines[start:end]
        # 防禦：壓縮為非空行序列後再用 hardcode 索引，與 pipeline_clean.stage1
        # 的緊湊化形成雙保險（單跑 parse 也安全）。
        block = [l for l in raw_block if l.strip()]

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
                if any(k in bl for k in ['應徵履歷', '意願通知', '主動應徵', '甄試歷程', '系統通知', '發出詢問', '專案聯絡']):
                    continue
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
# ============================
# 輔助函式定義
# ============================
def get_line_years(line):
    match_yr = re.search(r'\((\d+)年', line)
    match_mo = re.search(r'\(?(\d+)個月\)?', line)
    yr = int(match_yr.group(1)) if match_yr else 0
    mo = int(match_mo.group(1)) if match_mo else 0
    if not match_yr and '個月' in line:
        match_mo_only = re.search(r'\(?(\d+)個月\)?', line)
        mo = int(match_mo_only.group(1)) if match_mo_only else 0
    if '在職' in line:
        match_date = re.search(r'(\d{4})/(\d{2})', line)
        if match_date:
            start_yr = int(match_date.group(1))
            start_mo = int(match_date.group(2))
            curr_yr = 2026
            curr_mo = 5
            months = (curr_yr - start_yr) * 12 + (curr_mo - start_mo)
            if months > 0:
                yr = months // 12
                mo = months % 12
    return yr + mo / 12.0


def score_candidate(c, overlay=None):
    """對單一候選人進行規則評分，回傳 (分數, 理由列表, 是否排除)。

    overlay 為 None 時自動建立 default overlay（即主規則檔現行行為，版本見 screening_rules.md 第六節）。
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

    # ===== Q5: 中鼎內部轉發 VIP 解禁 (v10.2 新增, 2026-05-27) =====
    # 履歷甄試歷程含「@ctci.com」email → HR 內部已認可，強訊號
    # 效果：+30 強加分，並豁免 E2/E4/E6/E8/E19 排除規則
    # v11.2 限制：若近期工作段落含有業務或Sales，限制其VIP豁免(避免業務人員誤判入選)
    ctci_vip = CTCI_INTERNAL_SIGNAL in full
    if ctci_vip:
        has_recent_sales = False
        for line in c['work_lines'][:3]:
            if any(kw in line.lower() for kw in ['業務', 'sales']):
                has_recent_sales = True
                break
        if has_recent_sales:
            ctci_vip = False
            reasons.append("Q5 VIP bypass restricted due to recent Sales/業務 role")
        else:
            score += 30
            reasons.append("Q5 中鼎內部轉發 VIP (+30): HR 已認可, 豁免 E2/E4/E6/E8/E19")

    def _is_bim_unlock(c, work_text, desired, full):
        # 檢查是否為高科大廠 VIP 人才 (Q4)
        if overlay.enable_high_tech_vip_unlock:
            if _is_high_tech_vip_bim(full):
                return True # 直接無條件解禁

        # default 解禁：必須具備至少一項工程 M 條件
        # 移除「建設」在「土建設計」、「營建設計」等相鄰產生的 false positive 匹配
        full_for_unlock = re.sub(r'(土建|營建|建築|室內|裝修|估算)設計', '', full)
        
        m1_hit = any(kw in full_for_unlock for kw in ['工程師', '主任', '經理', '專案', '管線', '監工'])
        m2_hit = any(kw in full_for_unlock for kw in ['機電', '水電', '空調', '廠務', '建設', '營造'])
        base_pass = m1_hit and m2_hit
        
        # 修正(林耿輝 E3 領班漏洞)：若沒有實質的歷任工程管理職稱，不可解鎖基層勞務
        has_real_work_eng = any(kw in work_text for kw in ['工程師', '主任', '副理', '經理', '專案', '廠務', '監造', '監工'])
        # v11.2: 領班且具電機/機械相關學歷與對口希望職稱，可視同具備工程管理職
        if '領班' in work_text:
            has_ee_me_hvac_degree = any(k in edu for k in ['電機', '機械', '冷凍空調', '機電'])
            has_eng_desired = any(k in desired for k in ['工程師', '主任', '主管'])
            if has_ee_me_hvac_degree and has_eng_desired:
                has_real_work_eng = True
        if not has_real_work_eng:
            base_pass = False

        # space-manager v0.2: 解禁需要工作經歷有 MEP 實質字眼
        if overlay.require_mep_substance_for_unlock:
            has_mep_substance = any(tok in work_text for tok in MEP_SUBSTANCE_TOKENS)
            return base_pass and has_mep_substance

        return base_pass

    # E19: 絕對不可挽救的致命防呆 (無條件排除，不適用任何解禁)
    fatal_kill = [kw for kw in ['倉管', '業助', '組員', '安裝調試員', '服務工程師', '工務助理', '客服人員', '水電技師', '服務員', '銷售員', '外送員', '客服工程師', '技術助理工程師', '助理技術工程師', '資深技術員', '資深助理工程師', '資深技術工程師', '廠務助理工程師', '總務專員', '客服主任', '總務工程師', '園藝', '景觀', 'presales', '系辦助理', '口譯', '機構工程師', '機構設計', '機台', '維運人員', '空軍', '陸軍', '海軍', '國防部', '參謀', '士官', '志願役', '職業軍人', '銷售', '營業員', '物流', '測試工程師', '電信工程師', '通訊工程師', '通信工程師', '通訊系統工程師'] if kw.lower() in work_and_desired.lower()]
    # v11.11 (Batch #53, /review Q1, 2026-07-28): E19 軍種字眼 context guard。
    # 破口：E19 對「國防部/陸軍/海軍/空軍/參謀/士官/志願役/職業軍人」無條件排除，但這些字眼若出現在
    #   「專案名/客戶名」(如「國防部軍備局205廠營區新建工程」——候選人做該案電力設計)而非本人軍職，
    #   會誤殺實質工程設計者(吳承融：成大電機碩就學中 + 正宇電機技師事務所 電力系統設計/台電送審)。
    # 修正：軍種字眼須為「本人軍職」context 才致命；若其所有出現位置皆落在工程/專案/建廠 context、
    #   且無任何服役 context、且未出現在希望職稱，則豁免（移出 fatal_kill）。真軍職(帶兵役/退伍/上兵等)不受影響。
    MILITARY_FATAL_KWS = {'空軍', '陸軍', '海軍', '國防部', '參謀', '士官', '志願役', '職業軍人'}
    mil_in_fatal = [k for k in fatal_kill if k in MILITARY_FATAL_KWS]
    if mil_in_fatal:
        service_ctx = ['兵役', '服役', '退伍', '役畢', '預官', '連隊', '部隊', '軍旅', '入伍',
                       '上兵', '下士', '中士', '上士', '士官長', '排長', '連長', '軍團', '基地專精']
        project_ctx = ['工程', '新建', '擴建', '擴廠', '營區', '廠', '案', '專案', '建置', '施工',
                       '設計', '監造', '標', '工區', '驗收', '系統', '建廠', '配電', '變電', '軍備局']
        for k in mil_in_fatal:
            idxs = [m.start() for m in re.finditer(re.escape(k), full)]
            if not idxs:
                continue
            all_project = True
            any_service = False
            for i in idxs:
                window = full[max(0, i - 15): i + 20]
                if any(sc in window for sc in service_ctx):
                    any_service = True
                if not any(pc in window for pc in project_ctx):
                    all_project = False
            if all_project and not any_service and (k not in desired):
                fatal_kill.remove(k)
                reasons.append(f"E19 軍種 context 豁免: 「{k}」僅出現於工程/專案名(非本人軍職)")

    if fatal_kill == ['水電技師'] or (len(fatal_kill) > 0 and set(fatal_kill) == {'水電技師'}):
        has_high_tech_or_epc = any(kw in full for kw in ['台積', '聯電', '美光', '日月光', '中鼎', '帆宣', '漢唐', '亞翔', '泰創', '聖暉', '積體電路', '聯華電子'])
        if has_high_tech_or_epc:
            reasons.append("E19水電技師豁免: 具備高科技廠房/設備工程師或EPC經歷")
            fatal_kill = []

    # v10.2 (2026-05-27): E19 presales escape (space-manager only)
    # 劉書愛回饋：當前 Presales 但前 ≥2 段強相關（BIM/MEP/營造）→ 改 D 扣分而非排除
    if overlay.enable_presales_escape and 'presales' in [k.lower() for k in fatal_kill]:
        strong_prior_kws = list(BIM_TOKENS) + list(MEP_TOKENS) + ['營造', '建設', '建築']
        strong_prior_count = sum(
            1 for line in c['work_lines'][1:]  # 排除當前段 (work_lines[0])
            if any(t in line for t in strong_prior_kws)
        )
        if strong_prior_count >= 2:
            score -= 15
            reasons.append(f"E19 presales escape (space-manager): 前段 {strong_prior_count} 段強相關，改 D 扣分 (-15)")
            fatal_kill = [k for k in fatal_kill if k.lower() != 'presales']

    # v10.2: CTCI VIP 豁免 E19
    if ctci_vip and fatal_kill:
        reasons.append(f"E19 豁免 (Q5 CTCI VIP): 略過致命防呆 {','.join(fatal_kill[:2])}")
        fatal_kill = []

    # v10.5: E19 歷史低階經歷豁免 (林帛融 escape)
    # 若最新工作經歷為實質工程/管理職，且致命關鍵字僅存在於較舊的歷史經歷中（不在 desired 和 first_work 中），則豁免
    # v11.1 (E34 限制): 若最新工作持任 < 1.0 年，需額外檢查先前歷史中是否有 >= 2 年非致命 MEP 工程經歷才准予豁免
    if fatal_kill:
        strong_eng_titles = ['工程師', '主任', '主管', '副理', '經理', '專案', '廠務', '監造', '監工', '技師', '機電長']
        has_strong_first_work = any(t in first_work for t in strong_eng_titles) or ('長' in first_work and any(kw in first_work for kw in ['工程', '營造', '機電', '廠務']))
        has_recent_sales = any(any(kw in line.lower() for kw in ['業務', 'sales']) for line in c['work_lines'][:3])
        if has_strong_first_work and not has_recent_sales:
            # E34 restriction: 最新工作 < 1 年，檢查是否有實質先前工程經歷
            first_work_yrs = get_line_years(c['work_lines'][0]) if c['work_lines'] else 0
            e34_block = False
            if first_work_yrs < 1.0 and len(c.get('work_lines', [])) > 1:
                # 檢查先前工作是否有至少一段 >= 2 年的 MEP/工程經歷（排除致命關鍵字及電信/電力基建所在行）
                e19_fatal_all = ['倉管', '業助', '服務員', '銷售員', '外送員', '測試工程師',
                                 '電信工程師', '通訊工程師', '通信工程師', '通訊系統工程師',
                                 '水電工', '水電行', '水電人員']
                # 電信/通訊/變電等電力基建經歷不算 MEP 建廠實務
                non_mep_infra_kws = ['電信', '通訊', '通信', '變電', '變電所', '中華電信', '台灣電力']
                has_solid_prior = False
                for pl in c['work_lines'][1:]:
                    pl_yrs = get_line_years(pl)
                    has_fatal_in_line = any(k in pl for k in e19_fatal_all)
                    has_infra_in_line = any(k in pl for k in non_mep_infra_kws)
                    has_eng_in_line = any(k in pl for k in ['設計', '規劃', '機電', '空調', '消防', '建廠', '擴廠', '廠務', '水處理', '監造', '監工'])
                    if pl_yrs >= 2.0 and has_eng_in_line and not has_fatal_in_line and not has_infra_in_line:
                        has_solid_prior = True
                        break
                if not has_solid_prior:
                    e34_block = True
                    reasons.append(f"E34 限制: 最新工作僅{first_work_yrs:.1f}年，且先前歷史無 >= 2年實質 MEP 工程經歷，不准予 E19 歷史豁免")

            if not e34_block:
                exempted_kws = []
                for kw in list(fatal_kill):
                    not_in_desired_or_first = (kw.lower() not in desired.lower()) and (kw.lower() not in first_work.lower())
                    # v11.7 (Q4, 2026-07-15): 致命職稱若出現在 ≥2 段工作經歷，屬職涯主軸而非單一舊職，
                    # 不予歷史豁免。破口：劉俊谷（機構工程師 x2，消費電子ODM 全職涯機構設計），
                    # 因最新抬頭「資深主任工程師」含主任/工程師而讓「機構工程師」被判定僅存於舊經歷。
                    seg_count = sum(1 for wl in c['work_lines'] if kw.lower() in wl.lower())
                    if not_in_desired_or_first and seg_count < 2:
                        exempted_kws.append(kw)
                        fatal_kill.remove(kw)
                if exempted_kws:
                    reasons.append(f"E19 歷史低階經歷豁免: {','.join(exempted_kws)} 僅存在於舊歷史經歷中，且最新工作為實質工程/管理職")

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

    # E20a: 零經歷防呆
    if len(c['work_lines']) == 0:
        return 0, ["排除(E20a): 零工作經歷"], True

    # E20b: 僅 1 段且無「設計/規劃/整合/廠務/統包/建廠/施工/監造/機電/電機」等字眼
    if len(c['work_lines']) == 1:
        has_thick_words = any(k in work_text for k in ['設計', '規劃', '整合', '廠務', '統包', '建廠', '施工', '監造', '機電', '空調', '消防', '電力', '水電', '電機'])
        if not has_thick_words:
            return 0, ["排除(E20b): 僅1段經歷且工作中缺乏核心機電建廠實務"], True

    # E20e: 核心工程經歷單一且其餘為低階/無關經歷防呆
    has_thick_work = any(k in work_text for k in ['規劃', '建廠', '新建', '擴廠', '專案', '統包', '無塵室', '廠務', '發包', '圖面', '監造'])
    low_level_or_unrelated = ['加油員', '加油站', '游泳教練', '救生員', '餐廳', '門市', '吧台', '服務員', '銷售員', '外送員', '作業員', '保全', '店員', '理貨', '美容', '行政', '櫃檯', '專櫃']
    unrelated_count = sum(1 for line in c['work_lines'] if any(kw in line for kw in low_level_or_unrelated))
    real_eng_count = sum(1 for line in c['work_lines'] if any(kw in line for kw in ['工程師', '主任', '副理', '經理', '專案', '廠務', '監造', '監工']))
    if len(c['work_lines']) >= 2 and real_eng_count <= 1 and unrelated_count >= 1 and not has_thick_work:
        # v11.2: 若最新經歷為資深/領導職稱(如機電長、主任、經理，或含「長」且包含機電/工程/廠務)，則予以豁免
        has_senior_lead_first = any(k in first_work for k in ['機電長', '主任', '經理']) or ('長' in first_work and any(kw in first_work for kw in ['機電', '工程', '廠務']))
        if has_senior_lead_first:
            reasons.append("E20e 豁免: 最新工作為資深/領導職稱(機電長等)")
        else:
            return 0, ["排除(E20e): 核心工程經歷單一且其餘為低階/無關經歷"], True

    # E3: 脫離高度工程專業（低階維修/作業員）
    low_skill_hits = [kw for kw in LOW_SKILL_KEYWORDS if kw in desired or kw in first_work]
    has_mgmt_or_eng = any(kw in desired + first_work for kw in ['工程師', '主任', '經理', '副理', '課長', '專案', '機電', '氣體'])
    
    # 特例防呆：這些職稱就算有工程師或機電字眼，也不能被救回
    unsavable_hits = [kw for kw in ['維修工程師', '技術工程師', '助理', '實習', '學徒', '中控', '夜班', '工讀', '助手', '專員', '駐點', '倉管', '倉庫', '器材', '物料', '總務', '行政', '人事', '檢修', '技工', '半技', '粗工', '保全', '駐衛警', '勤務', '物業', '機械技術', '工務助理', '業助', '組員', '水電技師', '服務員', '銷售員', '外送員', '技術人員', '兼職', '兼職人員', '正職', '領班', 'PT'] if kw in desired + first_work]
    
    # v11.2: 專員豁免 (若最新職稱為專員但位於工程/營造公司，或先前有 >=2 段工程經歷，則不視為 unsavable)
    if '專員' in unsavable_hits and '專員' in first_work:
        has_eng_company = any(kw in first_work for kw in ['工程', '營造'])
        prior_eng_count = sum(1 for line in c['work_lines'][1:] if any(k in line for k in ['工程師', '主任', '主管', '副理', '經理', '技師']))
        if has_eng_company or prior_eng_count >= 2:
            unsavable_hits.remove('專員')

    # v11.2: 領班豁免 (若具備電機/機械學歷且希望職稱含工程師/主任/主管，則不視為 unsavable)
    if '領班' in unsavable_hits:
        has_ee_me_hvac_degree = any(k in edu for k in ['電機', '機械', '冷凍空調', '機電'])
        has_eng_desired = any(k in desired for k in ['工程師', '主任', '主管'])
        if has_ee_me_hvac_degree and has_eng_desired:
            unsavable_hits.remove('領班')

    # 修正(張承翰 E3 救回)：若命中「正職」，但第一段工作經歷為明確工程專業，則不視為 unsavable
    if '正職' in unsavable_hits:
        # v11.2: 納入技師與工程公司負責人作為實質工程經歷
        has_real_eng_first = any(k in first_work for k in ['工程師', '主任', '副理', '經理', '專案', '廠務', '技師']) or ('負責人' in first_work and any(kw in first_work for kw in ['工程', '營造']))
        if has_real_eng_first:
            unsavable_hits.remove('正職')
            
    # v10.5: 修正(吳柏瑢 E3 救回)：若第一段/最新工作經歷為實質工程專業或主管職，且該 unsavable 關鍵字僅出現在希望職稱中，則允許豁免
    # （代表此人實際具有工程經驗，僅在找工作時寫得比較寬泛）
    if unsavable_hits:
        # v11.2: 納入工程公司負責人
        first_is_real_eng = any(k in first_work for k in ['工程師', '主任', '主管', '副理', '經理', '專案', '廠務', '監造', '監工', '技師']) or ('負責人' in first_work and any(kw in first_work for kw in ['工程', '營造']))
        only_in_desired = all(kw not in first_work for kw in unsavable_hits)
        if first_is_real_eng and only_in_desired:
            reasons.append(f"E3/E6 豁免: 最新工作為實質工程專業，且低階關鍵字僅存於希望職稱")
            unsavable_hits = []

    if unsavable_hits:
        has_mgmt_or_eng = False

    if low_skill_hits and not has_mgmt_or_eng:
        if not unsavable_hits and _is_bim_unlock(c, work_text, desired, full):
            reasons.append(f"E6/E3條件化解禁({overlay.role_name}): {','.join(low_skill_hits[:2])}通過 M1/M2 工程門檻")
        else:
            return 0, [f"排除(E3): 脫離工程專業={','.join(low_skill_hits[:2])}"], True

    # E4: 純土建/營造人員無建廠/廠房營造經驗 (v10.8: 限制為 G1 組且 MEP 關鍵字僅檢查工作職稱而非公司名)
    is_pure_civil = (c['group'] == 'G1_土木建築')
    if is_pure_civil:
        titles = []
        for line in c['work_lines']:
            # Remove date range pattern (like 2016/10~2024/04 or 2016/10~仍在職) from anywhere in the line
            cleaned = re.sub(r'\d{4}/\d{2}(~\d{4}/\d{2}|~仍在職)?\s*', '', line)
            # Remove parentheses content like (7年7個月)
            cleaned = re.sub(r'\s*\(.*?\)', '', cleaned)
            parts = cleaned.split()
            if parts:
                titles.append(parts[-1])
        titles_text = '\n'.join(titles)

        has_factory = any(kw in work_and_desired for kw in ['建廠', '擴廠', '廠務', '無塵室', '統包', 'EPC', '科技廠', '半導體', '面板', '帆宣', '漢唐', '亞翔', '特氣', '管路'])
        mep_kws = ['機電', 'MEP', '空調', '消防', '電力', '水處理', '水電', '廠務', '管線'] if overlay.role_name == 'mep-design' else ['機電', 'BIM', 'MEP', '空調', '消防', '電力', '水處理', '水電', '廠務', '管線']
        has_mep_role = any(kw in (desired + titles_text).upper() for kw in mep_kws)

        # v10.2 (2026-05-27): E4 escape - 全球頂級工程顧問 + PCM/專案管理經歷 → 豁免
        # 李承翰回饋：WSP/科進栢誠 PCM 建築專業經歷被誤判為純土建
        e4_global_escape = False
        if overlay.enable_e4_global_consult_escape:
            global_consults = ['AECOM', '科進栢誠', 'WSP', 'Jacobs', 'Arup', 'Arcadis', 'Mott MacDonald', 'Buro Happold', '鼎漢']
            has_global = any(kw in full for kw in global_consults)
            has_pcm = any(kw in work_and_desired for kw in ['PCM', '專案管理', 'Project Management', '專案經理'])
            if has_global and has_pcm:
                e4_global_escape = True
                reasons.append(f"E4 豁免 (v10.2 space-manager): 含全球頂級顧問 + PCM/專案管理經歷")

        # v10.2: CTCI VIP 豁免 E4
        if ctci_vip:
            reasons.append("E4 豁免 (Q5 CTCI VIP)")
        elif e4_global_escape:
            pass  # 已加 reasons 在上面
        elif not (has_factory or has_mep_role):
            return 0, ["排除(E4): 土建/營造無機電建廠經驗"], True

        # E4b: G1組(土木建築)候選人，若其實質機電/MEP相關年資累計 < 2 年，視為偏向工務/土建且機電經驗不足，直接排除
        mep_keywords = ['機電', 'MEP', '空調', 'HVAC', '消防', '電力', '水處理', '水電', '廠務', '管線', '弱電', '儀電', 'BIM', 'Revit', '漢科', '亞翔', '漢唐', '帆宣', '洋基', '信紘科', '擎邦', '同開', '千附', '聖暉', '朋億', '泰創']
        mep_years = 0.0
        for line in c['work_lines']:
            if any(kw in line.upper() for kw in mep_keywords):
                mep_years += get_line_years(line)
        if mep_years < 2.0:
            return 0, [f"排除(E4b): 土建背景但機電/MEP實務經驗僅{mep_years:.1f}年(不足2年)"], True

    # E5b: 環境/環工純採樣人員且無實質 MEP 建廠/設施經驗防呆
    is_env_bg = any(kw in edu for kw in ['環境工程', '環工']) or any(kw in work_text for kw in ['採樣', '監測', '檢測'])
    if is_env_bg:
        has_real_mep = any(kw in work_text for kw in ['空調', '消防', '電力', '配電', '給排水', '管線', '配管', '無塵室', '建廠', '擴廠', 'BIM', 'Revit', 'AutoCAD', '機電', '水電', '電機', '機械']) or any(kw in full for kw in ['漢唐', 'Exyte', '中鼎', '帆宣', '泰創', '聖暉'])
        if not has_real_mep:
            return 0, ["排除(E5b): 環工/採樣背景且工作中缺乏實質機電建廠經歷"], True

    # E5: 機電/第三區塊人員若屬製程/製造/非建廠類
    if c['group'] in ('G2_機電相關', 'G3_環境', 'G3_其他'):
        if any(kw in work_and_desired for kw in NON_CONSTRUCTION_MANUFACTURING):
            # Define low-skill/repair keywords to clean the work text
            low_skill_repair = ['技術員', '維修員', '修繕', '水電工', '學徒', '助理', '作業員', '操作員', '物業', '保全', '電器行', '冷氣行', '飯店', '酒店', '門市', '店員']
            clean_work_text_for_mep = '\n'.join([l for l in c['work_lines'] if not any(k in l for k in low_skill_repair)])
            has_facility_mep = any(kw in clean_work_text_for_mep for kw in ['機電', '電力', '電機', '水電', '儀電', '電力系統']) or any(kw in work_and_desired for kw in ['廠務', '建廠', '擴廠', '空調', '消防', '水處理', '無塵室', '特氣', '營造', '建設', '中鼎', '配管', '配電', '案場', '帆宣', '漢科', '大鼎'])
            has_vip_co = any(kw in full for kw in PREMIUM_COMPANIES)

            # v11.7 (Q1, 2026-07-15): 製造/製程主軸收緊。
            # 破口輪廓：在半導體/電子/機械/食品廠做 製程/可靠度/bumping/機構/生產 的人，
            #   靠「知名公司名(日月光/台積, has_vip_co)」或泛用「機電/電力/電機」字眼繞過 E5。
            #   CLAUDE.md 4.9：半導體廠「工程師」有 製造端(排除) vs 建廠設施端(入選) 兩種，
            #   公司名不足以區分。→ 若職涯主軸為製造，須有實質建廠/廠務設施/設計證據才解禁。
            #   保護：真正在半導體廠做廠務設施者履歷帶 廠務/無塵室/建廠/監造/施工圖 → 仍解禁。
            MFG_DOMINANT_TOKENS = ['製程', '製造', '生產', '產線', '量產', '可靠度',
                                   '機構工程師', '機構設計', '封裝', 'bumping', 'Bumping', 'BUMPING',
                                   'CNC', '銑床', '製造部', '測試工程師', '晶圓', 'Wafer', 'wafer', 'MEMS',
                                   # v11.9 (Batch #52, B1): 設備/製造支援端主軸偵測（設備工程師/導入/維修/技術支援/黃光）
                                   '設備工程師', '設備導入', '設備維修', '設備助理', '黃光',
                                   'support engineer', 'Support Engineer', 'technology support', '技術支援']
            STRONG_FACILITY_TOKENS = ['建廠', '擴廠', '無塵室', '潔淨室', 'Cleanroom', 'FAB',
                                      '特氣', '大宗氣體', '統包', 'EPC', 'EPCK', '廠務',
                                      '水處理', '純水', '廢水', 'UPW', 'WWT', 'PCW', 'CDA',
                                      'Hook-up', '試車', 'Commissioning', '五大管線', '機電整合',
                                      '施工圖', '竣工圖', '監造', 'MEP', '高低壓', '受電', '變電站']
            mfg_seg = sum(1 for l in c['work_lines'] if any(k in l for k in MFG_DOMINANT_TOKENS))
            total_seg = max(1, len(c['work_lines']))
            desired_is_mfg = any(k in desired for k in ['製程', 'Process', '製造', '生產', '可靠度',
                                                        '設備工程師', 'support engineer', 'Support Engineer'])
            mfg_dominant = (mfg_seg / total_seg >= 0.5) or desired_is_mfg
            # v11.9 (Batch #52, B1): 保護真廠務——mfg 主軸者須有「實質建置/設計證據(BUILD_PROOF，單一即可)」
            # 或「廠務/無塵室/潔淨室 橫跨 ≥2 段」才解禁；單一短期廠務 title、學術無塵室 role、VIP 公司名(美光/日月光/台積)
            # 不再足以救回製造主軸（呼應 CLAUDE.md 4.9：公司名不足以區分製造端 vs 建廠設施端）。
            # 註：STRONG_FACILITY_TOKENS 已被下方 BUILD_PROOF_TOKENS + facility_seg 取代，保留定義供追溯。
            BUILD_PROOF_TOKENS = ['建廠', '擴廠', '統包', 'EPC', 'EPCK', '施工圖', '竣工圖', '監造', 'MEP',
                                  '五大管線', 'Hook-up', '試車', 'Commissioning', '機電整合', '機電設計',
                                  '特氣', '大宗氣體', 'Scrubber', 'UPW', 'WWT', 'PCW', 'CDA', '純水', '廢水', '水處理',
                                  '高低壓', '受電', '變電站']
            has_build_proof = any(kw in clean_work_text_for_mep for kw in BUILD_PROOF_TOKENS)
            facility_seg = sum(1 for l in c['work_lines'] if any(k in l for k in ['廠務', '無塵室', '潔淨室']))
            strong_facility_career = has_build_proof or facility_seg >= 2
            if mfg_dominant and not strong_facility_career:
                return 0, [f"排除(E5-Q1): 製造/設備主軸({mfg_seg}/{total_seg}段或desired)且無實質建廠/設計/多段廠務證據"], True

            if not has_facility_mep and not has_vip_co:
                return 0, ["排除(E5): 偏向製程/製造/非建廠屬性"], True

    # E5c: 對口電機/機械學歷但職涯主軸為傳統/製造 技工·維修·製圖·配電·組立，無建廠/設計/監造/高科/知名EPC 實質
    #      (v11.9, Batch #52, B2)。破口：對口學歷 N1(+15) + M1 泛用「電機/機械」(常來自公司名或技工職稱)
    #      = 剛好 30 分過門檻，但職涯全為技工/維修/製圖/配電等執行層，零建廠/設計/高科含金量。
    #      保護：具真實管理職(主任/課長/副理/經理/協理/廠長…)、或任一 BUILD_PROOF/BIM/知名大廠、或廠務≥2段者豁免。
    if c['group'] == 'G2_機電相關':
        LOW_TECH_TRADE = ['技術員', '技工', '維修員', '維修', '保養', '修理', '製圖', '繪圖',
                          '配電技術', '組立', '裝配', '計裝', '幫浦', '焊工', '技士', '配線', '技術工']
        titles_e5c = []
        for line in c['work_lines']:
            cleaned = re.sub(r'\d{4}/\d{2}(~\d{4}/\d{2}|~仍在職)?\s*', '', line)
            cleaned = re.sub(r'\s*\(.*?\)', '', cleaned)
            parts = cleaned.split()
            if parts:
                titles_e5c.append(parts[-1])
        total_e5c = max(1, len(titles_e5c))
        low_tech_seg = sum(1 for t in titles_e5c if any(k in t for k in LOW_TECH_TRADE))
        latest_low_tech = bool(titles_e5c) and any(k in titles_e5c[0] for k in LOW_TECH_TRADE)
        low_tech_dominant = (low_tech_seg / total_e5c >= 0.5) or latest_low_tech
        has_mgmt_e5c = any(k in work_text for k in ['主任', '課長', '副理', '經理', '協理', '廠長', '處長', '總監', '主管', '襄理'])
        E5C_SUBSTANCE = ['建廠', '擴廠', '統包', 'EPC', 'EPCK', '施工圖', '竣工圖', '監造', '無塵室',
                         '五大管線', 'Hook-up', '試車', 'Commissioning', '機電整合', '機電設計',
                         '特氣', '高低壓', '受電', '變電站', 'BIM', 'Revit', 'AutoCAD', '半導體', '面板']
        has_substance_e5c = any(kw in full for kw in E5C_SUBSTANCE) or any(kw in full for kw in PREMIUM_COMPANIES)
        facility_seg_e5c = sum(1 for l in c['work_lines'] if any(k in l for k in ['廠務', '無塵室', '水處理']))
        if low_tech_dominant and not has_mgmt_e5c and not has_substance_e5c and facility_seg_e5c < 2:
            return 0, ["排除(E5c): 對口學歷但職涯主軸為傳統/製造技工·維修·製圖·配電且無建廠/設計/監造/高科實質"], True

    # E7: 工安/環安衛人員（非機電工程/土建）
    ehs_hits = [kw for kw in EHS_KEYWORDS if kw in desired or kw in first_work]
    
    # v10.7: 判斷是否為純安全/安衛/工安履歷 (丁紀診/鄭清欽)
    # 若所有工作經歷的職稱均含 EHS 關鍵字且不含 MEP/工程實質字眼，則視為純 EHS 人選，不可豁免 E7
    is_pure_ehs = False
    if ehs_hits and c.get('work_lines'):
        ehs_titles_count = 0
        all_titles_pure_ehs = True
        ehs_kws = ['環安', '職安', '工安', '勞安', '安衛', 'EHS', '安全衛生', '環境工程']
        mep_kws = ['廠務', '機電', '電機', '空調', '消防', '水電', '配電', '電力', '儀電', 'BIM', 'Revit', '給排水', '水處理']
        for line in c['work_lines']:
            # Strip date patterns anywhere (could be at start or end of the line)
            cleaned = re.sub(r'\d{4}/\d{2}\s*~(?:仍在職|\d{4}/\d{2})?', '', line)
            cleaned = re.sub(r'\s*\(.*?\)', '', cleaned)
            parts = cleaned.split()
            if parts:
                title = parts[-1]
                has_ehs = any(kw in title for kw in ehs_kws)
                has_mep = any(kw in title for kw in mep_kws)
                if has_ehs and not has_mep:
                    ehs_titles_count += 1
                else:
                    all_titles_pure_ehs = False
            else:
                all_titles_pure_ehs = False
        is_pure_ehs = all_titles_pure_ehs and ehs_titles_count > 0

    if ehs_hits:
        # v10.3 (2026-05-27): 對 space-manager，E7 豁免必須 work_text 含「機電」或 MEP 字眼
        # 簡瑞辰回饋（環安出身，work_text 全是品管/環工）/ 吳鴻彰回饋（工安出身，work_text 純廠務維護無機電）
        # 區分：許定鈞（25年機電主任 + WSP）work_text 含「機電」 → 豁免；
        #       簡瑞辰/吳鴻彰 work_text 無「機電」 → 不豁免直接排除
        if overlay.role_name == 'space-manager':
            has_mep_strict = '機電' in work_text or 'MEP' in work_text.upper()
            if not has_mep_strict:
                return 0, [f"排除(E7 space-manager): EHS 出身且工作經歷無機電/MEP 實質字眼={','.join(ehs_hits[:2])}"], True
            # 有機電字眼則仍走 default 豁免流程（不立即 return）

        # default 角色（或 space-manager 通過機電 strict 檢查後）保留既有豁免邏輯
        # Q1 (v11.5): 只要待過知名 EPC/建廠競業，即使是純 EHS 履歷也全面豁免 E7 排除
        has_epc = any(kw in full for kw in PREMIUM_COMPANIES + ['中鼎', '漢科', '帆宣', '泰興', '達欣', '潤弘', '亞翔', '漢唐', '聖暉', '洋基'])
        if has_epc:
            reasons.append(f"E7競業豁免: 擁有知名 EPC/建廠競業經歷，豁免工安/環安衛人員排除")
            ehs_hits = []
        elif is_pure_ehs:
            return 0, [f"排除(E7 純安衛): 歷任職稱均為純工安/安衛人員且無機電實質職稱={','.join(ehs_hits[:2])}"], True
        else:
            has_non_ehs_desired = desired and any(kw in desired for kw in ['廠務', '機電', '電機', '電力', '空調', '消防', '水處理', '水電', '工程師', '監造', '品管', '經理', '設備師', '維護'])
            if has_non_ehs_desired:
                has_facility_mep = any(kw in work_text for kw in ['廠務', '建廠', '擴廠', '空調', '消防', '水處理', '無塵室', '特氣', '機電', '配電', '水電', '電力', '電機', '監造', '監工', '中鼎', '正興'])
                if has_facility_mep:
                    reasons.append(f"E7豁免: 雖有EHS關鍵字({','.join(ehs_hits)})，但有對口希望職稱且有設施經歷")
                    ehs_hits = []
        if ehs_hits:
            return 0, [f"排除(E7): 工安/環安衛={','.join(ehs_hits[:2])}"], True

    # E7b: 純EHS/職安/ESG 生涯掛工務/管理 title 逃逸防呆 (v11.8, /review Q1, 2026-07-15)
    # 破口：原 E7 靠 ehs_hits(EHS 字眼在 desired/first_work) 觸發，但職涯全為職安者一旦最新
    #   改掛「工務經理/經理」等非 EHS title、desired 也非 EHS，ehs_hits 為空 → E7 完全未觸發而逃逸。
    #   謝東林：職安系學歷 + 職安管理師/工安課長/永續課長/工安工程師 多段，最新 title=工務經理、
    #   desired=經理 → 全躲過。收緊：以「職安系學歷」或「EHS 職稱段數佔比」判純 EHS 生涯，
    #   且無任一「實質 MEP 工程職稱」(機電/廠務/監造/設計工程師等) → 排除。
    # 保護：真正做過機電工程師/廠務工程師/監造工程師等實質 MEP 職稱者(has_mep_eng_title)豁免。
    if overlay.role_name == 'default':
        ehs_title_kws = ['環安', '職安', '工安', '勞安', '安衛', 'EHS', '安全衛生', '永續', 'ESG']
        ehs_edu = any(k in edu for k in ['職業安全衛生', '安全衛生', '工業安全', '職業安全'])
        ehs_seg = sum(1 for l in c['work_lines'] if any(k in l for k in ehs_title_kws))
        total_seg_e7 = max(1, len(c['work_lines']))
        mep_eng_title = ['機電工程師', '機電技師', '廠務工程師', '空調工程師', '消防工程師',
                         '電機工程師', '機電主任', '機電副理', '機電經理', '設計工程師',
                         '監造工程師', '水電工程師', '暖通', '製程工程師', '無塵室', '建廠']
        has_mep_eng_title = any(any(t in l for t in mep_eng_title) for l in c['work_lines'])
        ehs_dominant = ehs_edu or (ehs_seg / total_seg_e7 >= 0.4)
        if ehs_dominant and ehs_seg >= 2 and not has_mep_eng_title:
            return 0, [f"排除(E7b): 純EHS/職安/ESG生涯({ehs_seg}/{total_seg_e7}段EHS職稱或職安系學歷)且無實質MEP工程職稱"], True

    # E33: 希望職稱-工作實質 mismatch 排除 (v10.3, 2026-05-27)
    # 楊國清回饋：希望職稱寫「國內外建廠/廠務主管」但工作經歷全是工地主任，無實際建廠/廠務經驗
    # 條件：希望職稱含 mismatch_intent_kws，但 work_text 中既無相同字眼也無 broader MEP/BIM 實質
    mismatch_intent_kws = ['建廠', '擴廠', '廠務', '空間管理', '空間整合']
    intent_hits = [kw for kw in mismatch_intent_kws if kw in desired]
    if intent_hits:
        has_same_in_work = any(kw in work_text for kw in intent_hits)
        if not has_same_in_work:
            broader_substance_kws = ['空調', '消防', '電力', '配電', '給排水', '機電', '無塵室',
                                      'EPC', '統包', 'BIM', '空間規劃', '空間整合', '監造', '監工']
            has_broader = any(kw in work_text for kw in broader_substance_kws)
            if not has_broader:
                return 0, [f"排除(E33): 希望職稱含{','.join(intent_hits[:2])}但工作經歷無對應實質"], True

    # E9: 偏向住宅工程/純建築無建廠
    residential_hits = [kw for kw in ['住宅', '住宅工程', '透天', '別墅'] if kw in work_and_desired]
    if residential_hits:
        has_factory = any(kw in work_and_desired for kw in ['建廠', '擴廠', '廠務', '無塵室', '統包', '科技廠', '半導體'])
        # v10.5: E9 公共工程與顧問公司豁免 (陳國卿 escape)
        has_infra = any(kw in full for kw in ['工程顧問', '捷運', '機場', '監獄', '醫院', '軌道', '高鐵', '鐵路'])
        has_premium = any(kw in full for kw in PREMIUM_COMPANIES)
        if not has_factory and not has_infra and not has_premium:
            return 0, [f"排除(E9): 偏向住宅工程={','.join(residential_hits[:2])}"], True

    # E10: 純水電勞務排除 (針對履歷單薄之水電工務)
    # 修正：不看希望職稱，必須真實近期經歷具備工程師/專案頭銜
    plumber_only = '水電' in desired + first_work and not any(kw in first_work for kw in ['工程師', '主任', '副理', '經理', '專案', '機電', '廠務'])
    has_thick = any(k in work_and_desired for k in ['規劃', '建廠', '新建', '擴廠', '專案', '統包', '無塵室', '廠務', '發包', '圖面', '監造'])
    if plumber_only and not has_thick:
        return 0, ["排除(E10): 履歷單薄之純水電/勞務工作"], True

    # E10b: 水電行/水電工歷史累積排除 (v11.1, 2026-06-23)
    # 累計水電行/水電工務/水電人員年資 >= 3年，且實質機電設計/工程管理年資 < 3年者排除
    # 排除謝勝淮樣本：水電行 + 水電工經歷過長但無實質 MEP 設計/工程管理深度
    plumber_kws = ['水電行', '水電工程行', '水電工', '水電人員']
    plumber_years = sum(get_line_years(l) for l in c['work_lines'] if any(k in l for k in plumber_kws))
    if plumber_years >= 3.0:
        mep_eng_kws = ['設計', '規劃', '無塵室', '建廠', 'EPC', '中鼎', '工程師', '主管', '課長', '經理', '主任']
        mep_eng_years = sum(get_line_years(l) for l in c['work_lines'] if any(k in l for k in mep_eng_kws) and not any(k in l for k in plumber_kws))
        if mep_eng_years < 3.0:
            return 0, [f"排除(E10b): 水電行/水電工累計{plumber_years:.1f}年，且實質工程管理年資僅{mep_eng_years:.1f}年(不足3年)"], True

    # E11: 純採購/發包/稽核排除 (無機電/建廠實務)
    procurement_only = any(kw in desired + first_work for kw in ['採購', '發包', '稽核', '能源管理'])
    if procurement_only:
        has_mep_role = any(kw in desired + work_text for kw in ['機電', '空調', '消防', '電力', '無塵室', '廠務', '建廠', '水處理'])
        if not has_mep_role:
            return 0, ["排除(E11): 純採購/企劃無機電實務"], True

    # E17: 純科技研發/軟體/業務/光電人員排除
    fatal_rd_software_hits = [kw for kw in ['軟硬體', '軟體', 'SQA', '演算法', 'BIOS', 'IC設計', '晶片', '前端', '後端', '全端', 'App開發', '業務', '光電', '研發', 'RD', '3d artist'] if kw in work_and_desired.lower()]
    if '業務' in fatal_rd_software_hits:
        # 豁免過往曾有業務經歷但近期已為實質工程/廠務/資深管理職者
        # v11.4 (Q2): 擴充資深管理職稱(副處長/處長/協理/廠長/部長/課長/主管等)與 desired 含廠務/建廠，
        #             並加 first_is_sales 守門(最新職務本身是業務者不予豁免)。
        #             修正古凱明——11 年廠務+副處長，僅一段 11 年前 6 個月業務卻遭 E17 誤殺。
        transition_titles = ['工程師', '主任', '副理', '經理', '專案', '機電', '弱電',
                             '副處長', '處長', '協理', '廠長', '部長', '課長', '主管', '副總', '總監']
        first_is_sales = ('業務' in first_work) or ('sales' in first_work.lower())
        has_transitioned = (not first_is_sales) and (
            any(kw in first_work for kw in transition_titles)
            or any(kw in desired for kw in transition_titles + ['廠務', '建廠'])
        )
        if has_transitioned:
            reasons.append("E17業務豁免: 最新職務為實質工程/廠務/資深管理職(非業務)，舊業務經歷不排除")
            fatal_rd_software_hits.remove('業務')
            
    if '光電' in fatal_rd_software_hits:
        # 豁免光電人員：若有頂尖 EPC/建廠公司經歷，或有實質廠務/機電/品管工程背景者，不因早期光電廠經歷排除
        has_thick_mep = any(kw in work_text for kw in ['機電', '廠務', '空調', '消防', '水處理', '建廠', '監造', '監工', '中鼎', '漢唐', '帆宣', '泰創', '聖暉']) or any(kw in full for kw in ['Exyte', '易科德'])
        has_real_eng_title = any(kw in first_work or kw in desired for kw in ['工程師', '主任', '副理', '經理', '專案', '廠務'])
        if has_thick_mep and has_real_eng_title:
            reasons.append("E17光電豁免: 雖過往有光電背景，但近期有實質機電廠務與大廠工程實績")
            fatal_rd_software_hits.remove('光電')

    if '研發' in fatal_rd_software_hits or 'rd' in fatal_rd_software_hits:
        # 豁免研發人員：如果近期/目前職稱為實質工程師/主管，且有知名大廠背景者不予排除
        has_real_eng = any(kw in first_work or kw in desired for kw in ['工程師', '主任', '副理', '經理', '專案', '廠務'])
        has_vip_bg = any(kw in full for kw in PREMIUM_COMPANIES)
        if has_real_eng and has_vip_bg:
            reasons.append("E17研發豁免: 雖有研發字眼，但近期具備半導體大廠實質工程師經歷")
            if '研發' in fatal_rd_software_hits: fatal_rd_software_hits.remove('研發')
            if 'rd' in fatal_rd_software_hits: fatal_rd_software_hits.remove('rd')

        # v10.2 (2026-05-27): 劉書愛回饋——「研發」keyword 在「文化資產保存與研發中心」
        # 等機構名稱中為 false positive。若 context 為文化/研究機構名稱且無「研發工程師」
        # 等明確職稱，豁免。
        rd_false_positive_contexts = ['文化資產', '研發中心', '研發機構', '保存與研發', '藝術研發', '研發處']
        if any(ctx in full for ctx in rd_false_positive_contexts):
            true_rd_titles = ['研發工程師', '研發部', '研發主任', '研發人員', '研發副理', '研發經理']
            has_true_rd_title = any(t in work_and_desired for t in true_rd_titles)
            if not has_true_rd_title:
                reasons.append("E17研發豁免 (v10.2): 「研發」出自文化資產/研發中心等機構名稱 false positive")
                if '研發' in fatal_rd_software_hits: fatal_rd_software_hits.remove('研發')
                if 'rd' in fatal_rd_software_hits: fatal_rd_software_hits.remove('rd')

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
    property_hits = [kw for kw in ['公寓大廈', '物業', '保全', '百貨', '商場', '量販', '社區管理', '管委會', '京站', '微風', '購物中心', '齊家', '酒店', '飯店', '大酒店', '大樓', '台灣大哥大', '中華電信', '遠傳電信', '遠傳'] if kw in work_and_desired]
    if property_hits:
        # 修正(陳信吉 E12 漏洞)：若最新一份工作即為物業/大樓機電/總務，且無近期「建廠/無塵室/統包/EPC」等核心營造實績，直接排除
        is_latest_property = any(kw in first_work for kw in ['物業', '大樓', '齊家', '總務', '樓管', '大廈'])
        if is_latest_property:
            has_active_construction = any(kw in first_work for kw in ['建廠', '擴廠', '無塵室', '統包', 'EPC'])
            if not has_active_construction:
                return 0, ["排除(E12): 最新工作偏向物業/大樓維護與總務"], True

        # v10.5: E12 歷史物業經歷豁免 (吳柏瑢 escape)
        # 若最新工作經歷為實質工程/管理職，且物業關鍵字僅存在於較舊的歷史經歷中（不在 desired 和 first_work 中），則豁免
        # v11.1 限制: 額外要求工作經歷中需包含建廠/設計/規劃等核心工程關鍵字，排除純建築維護管理者（賴培恩樣本）
        strong_eng_titles = ['工程師', '主任', '主管', '副理', '經理', '專案', '廠務', '監造', '監工', '技師', '機電長']
        has_strong_first_work = any(t in first_work for t in strong_eng_titles) or ('長' in first_work and any(kw in first_work for kw in ['工程', '營造', '機電', '廠務']))
        construction_depth_kws = ['建廠', '擴廠', '設計', '規劃', '無塵室', 'EPC', '統包', '施工圖', 'BIM', 'Revit', '監造', '監工', '機電', '電機', '消防']
        has_construction_depth = any(kw in work_text for kw in construction_depth_kws)
        if has_strong_first_work and has_construction_depth:
            exempted_property_hits = []
            for kw in list(property_hits):
                not_in_desired_or_first = (kw not in desired) and (kw not in first_work)
                if not_in_desired_or_first:
                    exempted_property_hits.append(kw)
                    property_hits.remove(kw)
            if exempted_property_hits:
                reasons.append(f"E12 歷史物業經歷豁免: {','.join(exempted_property_hits)} 僅存在於舊歷史經歷中，且最新工作為實質工程/管理職")

        if property_hits:
            has_factory = any(kw in work_and_desired for kw in ['建廠', '擴廠', '廠務', '無塵室', '統包', '科技廠', '半導體'])
            if not has_factory:
                return 0, [f"排除(E12): 大樓物業/商場維護={','.join(property_hits[:2])}"], True

    # E12b: 累計大樓物業/飯店維護年資 >= 3年 且 佔總年資比例 >= 50%，視為偏重大樓物業/總務庶務，無技術深度，直接排除
    property_kws = ['物業', '公寓', '大廈', '保全', '大樓', '樓管', '飯店', 'HOTEL', '酒店', '商旅', '商場', '百貨', '量販', '維保', '維護人員', '物管', '機電管理', '建經', '建築經理']
    prop_years = sum(get_line_years(l) for l in c['work_lines'] if any(k in l.upper() for k in property_kws))
    total_years = sum(get_line_years(l) for l in c['work_lines'])
    if total_years > 0:
        prop_ratio = prop_years / total_years
        if prop_years >= 3.0 and prop_ratio >= 0.5:
            return 0, [f"排除(E12b): 大樓物業/飯店維護經歷過長(累計{prop_years:.1f}年, 佔比{prop_ratio*100:.0f}%)，偏向總務庶務運維"], True

    # E12c: 非營建 O&M、安衛、品管排除 (v11.1, 2026-06-23)
    # 經歷含物業管理/維護、安全(工安/勞安/安衛)、或品保/品管，且全履歷無工程規劃字眼者排除
    # 排除莊鎰鴻樣本：保全/品管背景無任何建廠/設計/規劃等工程核心關鍵字
    om_safety_qc_kws = ['保全', '倉管', '勞安', '工安', '職安', '安衛', '品保', '品管']
    has_om_safety_qc = any(kw in work_and_desired for kw in om_safety_qc_kws)
    if has_om_safety_qc:
        construction_design_kws = ['建廠', '擴廠', '設計', '規劃', '無塵室', 'EPC', '中鼎', '施工圖', 'Revit', 'BIM']
        has_construction_depth = any(kw in work_and_desired for kw in construction_design_kws)
        if not has_construction_depth:
            # 豁免：若有知名 EPC 公司經歷或實質機電工程職稱則不排除
            has_premium = any(kw in full for kw in PREMIUM_COMPANIES)
            has_eng_title = any(kw in first_work for kw in ['工程師', '主任', '副理', '經理', '技師', '廠務', '監造'])
            if not has_premium and not has_eng_title:
                om_hits = [kw for kw in om_safety_qc_kws if kw in work_and_desired]
                return 0, [f"排除(E12c): 非營建O&M/安衛/品管({','.join(om_hits[:2])})且全履歷無工程規劃字眼"], True

    # E12d: 傳統水電行/電器行/空調維修/修繕人員年資累積排除 (v11.3, 2026-07-02)
    # 累積於水電行、電器行、冷氣行、修繕、維修、大樓物業之年資 >= 3年，且實質機電設計/工程管理年資 < 3年者排除
    repair_kws = ['電器行', '冷氣行', '維修員', '修繕', '水電工', '學徒', '物業', '公寓', '大廈', '大樓', '飯店', '酒店']
    repair_years = sum(get_line_years(l) for l in c['work_lines'] if any(k in l for k in repair_kws))
    if repair_years >= 3.0:
        mep_eng_kws = ['設計', '規劃', '無塵室', '建廠', 'EPC', '中鼎', '工程師', '主管', '課長', '經理', '主任']
        mep_eng_years = sum(get_line_years(l) for l in c['work_lines'] if any(k in l for k in mep_eng_kws) and not any(k in l for k in repair_kws) and not any(k in l.lower() for k in ['電控', '自動控制', '自動化', 'plc', '研發', 'rd', '測試', '設備', '技術員', '操作員', '作業員']))
        if mep_eng_years < 3.0:
            return 0, [f"排除(E12d): 傳統水電/電器行/修繕/物業年資累計{repair_years:.1f}年，且實質工程管理年資僅{mep_eng_years:.1f}年(不足3年)"], True

    # E12e: 產業類別防線 (v11.4, Q1, 2026-07-02)
    # 針對物業/飯店/休閒/不動產產業維修主軸漏網 (陳峰/張哲耀型)。
    # 註：產業類別欄僅存在於完整履歷(/review 與歷史 CSV)，ANALYSIS.md 摘要無此欄，故本規則
    #     主要在 /review 深度生效；/filter 摘要層由 E6 補強的低階運維內容詞輔助攔截。
    industry_lines = [l for l in full.split('\n') if l.strip().startswith('產業類別')]
    if industry_lines:
        hospitality_kws = ['旅館', '住宿', '休閒', '餐旅', '不動產', '百貨', '遊樂', '購物', '餐館', '飯店', '博弈', '觀光']
        hosp_count = sum(1 for l in industry_lines if any(k in l for k in hospitality_kws))
        if hosp_count > 0 and hosp_count * 2 >= len(industry_lines):
            has_build = any(kw in full for kw in ['建廠', '擴廠', '無塵室', 'EPC', '統包', '半導體', '科技廠', '設計定版', '系統建置'])
            if not has_build:
                return 0, [f"排除(E12e): 產業主軸為旅館/不動產/休閒維運({hosp_count}/{len(industry_lines)}段)且無建廠信號"], True

    # E6 補強: 代操/打雜等低階運維內容防呆 (v11.4, Q1)
    # 摘要層(ANALYSIS.md)與完整履歷皆可掃到的低階運維內容詞，補 E12e 在 /filter 路徑的覆蓋缺口
    low_om_content = ['代操', '打雜', '什麼都修', '雜修', '雜工']
    if any(k in full for k in low_om_content):
        has_build_depth = any(kw in work_and_desired for kw in ['建廠', '擴廠', '無塵室', 'EPC', '統包', '設計', '規劃', '監造', '監工'])
        if not has_build_depth:
            return 0, ["排除(E6補強): 工作內容為代操/打雜等低階運維且無建廠設計深度"], True

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
    core_mep_hits = [kw for kw in ['空調', '消防', '水處理', '管線', 'BIM', 'MEP', '廠務', '水電', '無塵室', '建廠', '統包', '機電', '電力', '電機'] if kw in (work_and_desired).upper()]
    low_level_jobs = ['操作員', '技術人員', '服務人員', '門市', '餐飲', '保全', '總務', '作業員', '理貨', '美容', '行政', '櫃檯', '專櫃']
    has_low_jobs = any(kw in work_text for kw in low_level_jobs)
    
    # 計算工程經歷行數
    # v11.2: 具備對口機電/機械/環工學歷時，將技術維護/運維崗位納入工程經歷行統計(避開對技術運維人員的防呆誤殺)
    eng_kws = ['工程', '機電', '廠務', '設計', 'BIM', 'bim', '空調', '消防', '製圖', '繪圖']
    has_mep_degree = any(k in edu for k in ['電機', '機械', '冷凍空調', '機電', '環工', '環境工程', '化工', '化學'])
    if has_mep_degree:
        eng_kws += ['維護', '維修', '保養', '污水', '設備']
    eng_lines = [l for l in c['work_lines'] if any(k in l for k in eng_kws)]
    
    if has_low_jobs and len(eng_lines) <= 2 and not any(kw in work_and_desired for kw in ['規劃', '建廠', '新建', '擴廠']):
        return 0, ["排除(E15): 工程經歷過短且夾雜大量非專業經歷"], True
        
    if not core_mep_hits:
        if has_low_jobs:
            return 0, ["排除(E15): 缺乏核心機電實務且經歷混雜"], True

    # E15 加強版: 針對 default/mep-design 角色
    if overlay.role_name == 'default':
        # Strip out O&M/repair/hotel/telecom lines to check if they have real MEP design/construction substance
        repair_kws = ['電器行', '冷氣行', '維修員', '修繕', '水電工', '學徒', '物業', '公寓', '大廈', '大樓', '飯店', '酒店', '台灣大哥大', '中華電信', '遠傳']
        clean_work_lines = [l for l in c['work_lines'] if not any(k in l for k in repair_kws)]
        clean_work_text = '\n'.join(clean_work_lines)
        
        mep_subsystems = ['機電', '空調', '消防', '電力', '給排水', '水處理', '配電', '水電', '配管', '管線']
        has_other_mep = any(sub in (clean_work_text).upper() for sub in mep_subsystems)
        has_facility = '廠務' in clean_work_text
        # v11.4 (Q3): 建廠信號豁免詞擴充(發包/驗收/工進/監造/系統建置/統包)，並掃描完整履歷內容——
        # 周憲章的建廠證據在「工作內容」描述行(建廠空調製程系統工進/規劃發包監工驗收)而非職稱行，
        # 原本只掃 clean_work_text(職稱行)導致遭 E15 誤殺。
        build_signal_kws = ['設計', '建廠', '擴廠', 'EPC', 'BIM', 'Revit', '發包', '驗收', '工進', '監造', '監工', '系統建置', '無塵室', '統包']
        has_design_construction = any(kw in clean_work_text for kw in build_signal_kws) \
            or any(kw in full for kw in ['建廠', '擴廠', '無塵室', 'EPC', '統包', '系統建置', '設計定版'])
        if has_facility and not has_other_mep and not has_design_construction:
            return 0, ["排除(E15): 純廠務維運且缺乏其他機電子系統及建廠設計經歷"], True

        # E15b: 大樓/設施設備維運主軸掛「機電工程師」title 逃逸防呆 (v11.8, /review Q2, 2026-07-15)
        # 破口：E15 加強只查「廠務」title；但工作內容全為大樓/設施設備維護/保養/巡檢/點檢者，
        #   一旦 title=「機電工程師」(非廠務) 即躲過。劉傳鑫：保全樓管業「大樓設備維護/保養/巡檢/
        #   點檢」，desired=作業員/水電工，卻因 title=機電工程師+電機學歷過關。
        # 收緊：工作內容(work_text)主軸為 設備維護/保養/巡檢/點檢 且處於大樓/物業/樓管情境，
        #   且無建廠/設計/監造深度 → 排除，不因 title=機電工程師 豁免。
        # 註：工作內容細節多在完整履歷(/review)，摘要層(ANALYSIS.md)以職稱行維護字眼+desired 輔助。
        maint_content_kws = ['設備維護', '設備保養', '巡檢', '點檢', '維護保養', '保養維護',
                             '例行性維護', '設施維護', '機電維護', '設備檢查', '維修保養',
                             '設備維修', '維護及修繕', '維護保修']
        # 用 full：工作內容細節在完整履歷(/review)落於 full；摘要層(ANALYSIS.md)無內容則落回職稱維護字眼
        maint_hits = sum(1 for k in maint_content_kws if k in full)
        bldg_context = any(k in full for k in ['保全樓管', '大樓設備', '大樓機電', '公寓大廈',
                                               '樓管', '物業', '商辦大樓', '大樓維護', '大廈'])
        build_design_kws = ['建廠', '擴廠', '無塵室', '統包', 'EPC', '設計', '監造', '施工圖',
                            'BIM', 'Revit', '規劃', '新建', '發包', '系統設計', '圖面', '五大管線']
        has_build_design = any(k in work_and_desired for k in build_design_kws)
        low_desired = any(k in desired for k in ['作業員', '水電工', '包裝'])
        if not has_build_design and (
                (maint_hits >= 2 and bldg_context)
                or (bldg_context and low_desired and maint_hits >= 1)):
            return 0, ["排除(E15b): 大樓/設施設備維運主軸(維護/保養/巡檢/點檢)且無建廠/設計/監造深度"], True

    # E16: 機電整合/自動控制/航太等非廠房設施防呆
    automation_hits = [kw for kw in ['自動化', '機電整合', '自動化設備', '自動控制', 'PLC', '電控', '航太', '航空', ' cnc', 'CNC', '太陽能', '光電', '電梯', '水電行'] if kw in work_and_desired]
    if automation_hits:
        # 必須要有廠務或建廠相關的明確設施關鍵字才能豁免
        # v11.3: 限制解禁白名單，移除機電、電力、電機
        has_real_facility = any(kw in work_and_desired for kw in ['廠務', '建廠', '無塵室', '空調', '水電', '消防', '水處理']) or any(kw in full for kw in ['台積', '聯電', '美光', '日月光', '中鼎', '漢唐', '帆宣', '泰創', '聖暉'])
        if not has_real_facility:
            # Only allow short transition if they actually have automation experience in their work history
            has_auto_work = any(any(kw in line for kw in automation_hits) for line in c['work_lines'])
            is_all_short_transition = has_auto_work
            mep_core_segments = 0
            for line in c['work_lines']:
                line_has_auto = any(kw in line for kw in automation_hits)
                if line_has_auto:
                    line_yrs = get_line_years(line)
                    if line_yrs >= 1.0:
                        is_all_short_transition = False
                else:
                    is_mep_core = any(kw in line.upper() for kw in ['機電', '監造', '監工', '廠務', '空調', '消防', '電力', '電力系統', '專案經理', '電機工程師'])
                    if is_mep_core:
                        mep_core_segments += 1
            if is_all_short_transition and mep_core_segments >= 2 and has_auto_work:
                reasons.append(f"E16短暫過渡期豁免: {','.join(automation_hits)} 經歷皆小於1年且有{mep_core_segments}段機電監造主軸")
                has_real_facility = True
        if not has_real_facility:
            return 0, [f"排除(E16): 偏向自動化/製造/航太({','.join(automation_hits[:2])})"], True

    # Helper to check if a candidate is a frequent jumper (having recent jumps all < 1 year)
    def _is_frequent_jumper(work_lines):
        if not work_lines:
            return False
        check_len = min(3, len(work_lines))
        if check_len < 2:
            return False
        for line in work_lines[:check_len]:
            yrs = get_line_years(line)
            if yrs >= 1.0:
                return False
        return True

    # E20c: 化妝/文學/外語/餐飲/觀光/護理/行銷學歷且無厚實字眼
    if overlay.role_name == 'default':
        low_tech_majors = ['化妝', '文學', '外語', '日語', '英語', '語言', '餐飲', '觀光', '護理', '行銷', '哲學', '人文']
        has_low_tech_major = any(m in edu for m in low_tech_majors)
        thick_kws = ['規劃', '建廠', '新建', '擴廠', '專案', '統包', '無塵室', '廠務', '發包', '圖面', '監造', '設計']
        has_thick = any(k in work_and_desired for k in thick_kws)
        if has_low_tech_major and not has_thick:
            return 0, ["排除(E20c): 非工程科系且工作中缺乏建廠核心實務"], True

    # E20d: 所有經歷皆為工讀/實習/PT/兼職/助理/包裝/作業員/技術員/中工/半技/學徒/點工/雜工
    if overlay.role_name == 'default' and len(c['work_lines']) >= 1:
        low_skill_terms = ['工讀', '實習', 'PT', '兼職', '助理', '包裝', '作業員', '技術人員', '技術員', '中工', '半技', '學徒', '點工', '雜工', '助手']
        all_low_skill = True
        for line in c['work_lines']:
            # v11.2: 具備電氣配線/繪圖等實質技術經歷，不視為 low-skill
            has_technical_skill = any(t in line for t in ['配線', '電氣', '繪圖', '工程', '設計', 'BIM', 'Revit'])
            if not any(t in line for t in low_skill_terms) or has_technical_skill:
                all_low_skill = False
                break
        if all_low_skill:
            return 0, ["排除(E20d): 經歷皆為低階打工、實習或助理工作"], True

    # E21: default (MEP) 短期純建模防呆
    if overlay.role_name == 'default' and len(c['work_lines']) >= 1:
        recent_lines = c['work_lines'][:4]
        is_e21 = True
        for line in recent_lines:
            yrs = get_line_years(line)
            has_modeling = any(tok in line for tok in BIM_TOKENS) or any(tok in line for tok in MODELING_TERMS)
            has_substance = any(tok in line for tok in ['設計工程', '設計', '規劃', '整合', '廠務', '統包', '建廠'])
            if yrs >= 2.0 or not has_modeling or has_substance:
                is_e21 = False
                break
        if is_e21 and len(recent_lines) > 0:
            return 0, ["排除(E21): 近期經歷均為短期純建模"], True

    # E22: default (MEP) 零 MEP 信號防呆
    if overlay.role_name == 'default':
        has_mep_substance = any(tok in work_and_desired for tok in MEP_SUBSTANCE_TOKENS)
        has_bim_sig = any(tok in work_and_desired.upper() for tok in ['BIM', 'REVIT', 'NAVISWORKS'])
        if not has_mep_substance and not has_bim_sig:
            return 0, ["排除(E22): 零MEP與BIM信號"], True

    # E22b: 監造/品管/監工/工安 主軸但近期無實質 MEP 子系統 (v11.7, Q3, 2026-07-15)
    # 破口：E22 只要「全職涯」任一 MEP token 即豁免，讓「舊/微量機電」救回近期為純土建監造/品管/工安者。
    #   黃智謙(營造監造/品管主任，電機是13年前綠創)、沈晉宇(營造工地主任/品管/職安，機電是舊鋼鐵維護)、
    #   洪立民(純工安/職安/勞安，靠 E7 競業豁免通關但近3段全工安)。
    # 收緊(比照 space-manager E7 收緊 + E22 精神)：近3段 ≥2 段為 監造/品管/監工/工安/職安/環境監測，
    #   且近3段+desired 無實質 MEP 子系統字眼 → 排除。
    # 保護：真在 EPC/建廠大廠做廠房監造者(履歷帶 建廠/無塵室/廠務/EPC/半導體) → 豁免。
    if overlay.role_name == 'default':
        supervision_qc_ehs_kws = ['監造', '監工', '品管', '品保', '工安', '職安', '勞安', '安衛',
                                  '環安', '工地主任', '工地副主任', '採樣', '監測', '檢測']
        recent3 = c['work_lines'][:3]
        recent3_text = '\n'.join(recent3)
        recent_is_super_qc = sum(1 for l in recent3 if any(k in l for k in supervision_qc_ehs_kws)) >= 2
        mep_sub_strict = ['機電', '空調', 'HVAC', '消防', '電力', '配電', '給排水', '純水', '廢水',
                          '無塵室', '廠務', '建廠', '擴廠', '管線', '配管', 'MEP', 'BIM', 'Revit',
                          '水處理', '特氣', '統包', 'EPC', '水電', '弱電']
        has_recent_mep = any(k.upper() in (recent3_text + desired).upper() for k in mep_sub_strict)
        if recent_is_super_qc and not has_recent_mep:
            has_premium_build = any(kw in full for kw in PREMIUM_COMPANIES) and \
                any(kw in full for kw in ['建廠', '擴廠', '無塵室', '廠務', 'EPC', '統包', '半導體', '科技廠'])
            if not has_premium_build:
                return 0, ["排除(E22b): 近3段主軸為監造/品管/工安且無實質MEP子系統"], True

    # E23: 純結構/土木技師軌跡排除
    if overlay.role_name == 'default':
        structure_titles = ['土木技師', '結構技師', '大地工程', '結構分析師']
        if any(t in desired for t in structure_titles):
            structure_job_count = sum(1 for line in c['work_lines'] if any(t in line for t in ['結構', '大地']))
            mep_strict_tokens = ['機電', 'HVAC', '空調', '消防', '配電', '給排水', 'MEP', '廠務', '水處理', '建廠', '變電', '高低壓', 'UPS', '電力系統']
            has_mep_strict = any(t in full for t in mep_strict_tokens)
            if structure_job_count >= 2 and not has_mep_strict:
                return 0, ["排除(E23): 純結構/土木技師且無MEP實質經歷"], True

    # E24: 近期軌跡偏離 MEP
    if overlay.role_name == 'default' and len(c['work_lines']) >= 2:
        recent_titles = ['工地主任', '工地副主任', '工地負責人', '工地工程師', '工務主任', '領班']
        desired_civil_titles = ['營建工程師', '土木工程師', '土木技師', '結構技師', '結構工程師']
        mep_kws = ['機電', '空調', '消防', '電力', '給排水', '水處理', '廠務', 'MEP', 'BIM', 'Revit']
        
        first_two_lines = c['work_lines'][:2]
        recent_match = True
        for line in first_two_lines:
            has_recent_title = any(t in line for t in recent_titles)
            has_mep = any(k in line.upper() for k in mep_kws)
            if not has_recent_title or has_mep:
                recent_match = False
                break
                
        desired_match = any(t in desired for t in desired_civil_titles) and not any(k in desired.upper() for k in mep_kws)
        if recent_match and desired_match:
            return 0, ["排除(E24): 近期軌跡偏離MEP且希望職稱為純土建"], True

    # E25: 在學中且無台灣正式公司
    if '就學中' in edu:
        has_company = any('公司' in line for line in c['work_lines'])
        if not has_company:
            return 0, ["排除(E25): 在學中且無正式公司經歷"], True

    # E26: 履歷極度單薄缺乏實質深度
    if overlay.role_name == 'default':
        thick_kws = ['規劃', '建廠', '新建', '擴廠', '專案', '統包', '無塵室', '發包', '圖面', '監造', '設計', 'BIM', 'Revit']
        has_thick = any(k in work_and_desired for k in thick_kws)
        has_premium = any(k in full for k in PREMIUM_COMPANIES)
        # v10.5: E26 management role & multiple jobs exemption (林帛融 escape)
        has_mgmt = any(k in work_and_desired for k in ['主任', '主管', '經理', '副理', '總監', '協理'])
        # v11.2: 具備對口科系背景且為長期領班者豁免 (林耿輝 rescue)
        has_ee_me_hvac_degree = any(k in edu for k in ['電機', '機械', '冷凍空調', '機電'])
        has_eng_desired = any(k in desired for k in ['工程師', '主任', '主管'])
        total_yrs = sum(get_line_years(l) for l in c['work_lines'])
        is_long_foreman = '領班' in work_text and total_yrs >= 5.0 and has_ee_me_hvac_degree and has_eng_desired
        # v11.2: 若為工程長/主任/經理等資深領導職，且年資達5年以上者豁免 (徐強 rescue)
        has_senior_lead_first = any(k in first_work for k in ['機電長', '機電主任', '廠務主任', '工務主任', '專案主任', '工程主任', '機電經理', '廠務經理', '工務經理', '專案經理', '工程經理']) or (any(k in first_work for k in ['主任', '經理']) and any(kw in first_work for kw in ['機電', '工程', '廠務', '工務', '專案', '施工', '監造', '水電', '空調'])) or ('長' in first_work and any(kw in first_work for kw in ['機電', '工程', '廠務']))
        # v11.2: 具備對口科系且為長期資深技術/工程人員(年資達5年以上且 desired/work_text 包含電機/機電/電氣/電控/配線)者豁免 (楊智中 rescue)
        is_long_tech_staff = total_yrs >= 5.0 and has_ee_me_hvac_degree and any(k in work_and_desired for k in ['電機', '機電', '電氣', '電控', '配線'])
        if not has_thick and not has_premium and not (has_mgmt and len(c['work_lines']) >= 3) and not is_long_foreman and not (has_senior_lead_first and total_yrs >= 5.0) and not is_long_tech_staff:
            return 0, ["排除(E26): 履歷極度單薄缺乏實質技術深度"], True

    # E27: 建築背景跨足機電且頻繁跳槽
    if overlay.role_name == 'default':
        is_arch_bg = any(kw in edu for kw in ['建築', '土木', '營建'])
        if is_arch_bg and _is_frequent_jumper(c['work_lines']):
            return 0, ["排除(E27): 建築背景且近期頻繁跳槽"], True

    # E28: 非工程背景且僅為繪圖員
    if overlay.role_name == 'default':
        has_eng_edu = any(kw in edu for kw in EDU_KEYWORDS)
        if not has_eng_edu:
            is_drawing_job = any(t in first_work or t in desired for t in ['繪圖', '製圖', '建模'])
            if is_drawing_job:
                return 0, ["排除(E28): 非工程背景且擔任繪圖/建模人員"], True

    # E28b: 專業背景但過多為繪圖工程師/建模員
    if overlay.role_name == 'default':
        drawing_terms = ['繪圖', '建模', '製圖', '建模員', '繪圖員', '繪圖工程師', '製圖員', 'BIM建模員']
        first_is_drawing = any(t in first_work for t in drawing_terms)
        # v11.2: 若最新經歷同時包含實質技術(如配線/裝配/施工/監造等)，不視為純繪圖工作
        if first_is_drawing and any(t in first_work for t in ['配線', '裝配', '施工', '監造', '監工', '廠務']):
            first_is_drawing = False
        if first_is_drawing:
            drawing_count = sum(1 for line in c['work_lines'] if any(t in line for t in drawing_terms))
            if drawing_count >= 2:
                # v11.2: 若最新繪圖工作位於 PREMIUM_COMPANIES (如 帆宣)，視為頂級廠房建廠建模核心人才，予以豁免
                is_premium_current = any(kw in first_work for kw in PREMIUM_COMPANIES)
                if is_premium_current:
                    reasons.append("E28b 豁免: 最新繪圖工作位於知名大廠/PREMIUM_COMPANIES")
                else:
                    return 0, [f"排除(E28b): 最新工作為繪圖且累計有{drawing_count}次繪圖經歷"], True

    # E29: 純BIM/繪圖且跳槽頻繁
    if overlay.role_name == 'default':
        is_bim_drawing = any(t in first_work or t in desired for t in BIM_TOKENS + MODELING_TERMS)
        if is_bim_drawing and _is_frequent_jumper(c['work_lines']):
            return 0, ["排除(E29): 純BIM/繪圖工作且頻繁跳槽"], True

    # E30: 純設計/文商社科背景防護
    non_eng_majors = ['工業設計', '大眾傳播', '外語', '日語', '英語', '語言', '政治', '社會', '企管', '行銷', '商業', '管理', '商學', '哲學', '人文']
    has_non_eng_major = any(m in edu for m in non_eng_majors)
    has_mep_civil_major = any(m in edu for m in ['機電', '電機', '土木', '機械', '空調', '冷凍', '消防', '給排水', '化工', '環工', '環境工程', '建築', '營建'])
    
    # v10.6 新增：實質轉型成功豁免
    is_exempt_e30 = False
    if has_non_eng_major and not has_mep_civil_major:
        first_is_eng = any(k in first_work for k in ['工程', '機電', '廠務', '空調', '消防', '電力', '水電', '監造', '監工', '施工', '主任', '主管', '經理', '技師'])
        eng_lines = [l for l in c['work_lines'] if any(k in l for k in ['工程', '機電', '廠務', '設計', 'BIM', 'bim', '空調', '消防', '製圖', '繪圖', '配管', '配電', '水電', '監造', '監工', '施工', '主任', '主管', '經理', '技師'])]
        has_premium = any(kw in full for kw in PREMIUM_COMPANIES)
        total_eng_years = sum(get_line_years(l) for l in eng_lines)
        if first_is_eng and len(eng_lines) >= 2 and (total_eng_years >= 3.0 or has_premium):
            is_exempt_e30 = True
            reasons.append(f"E30轉型成功豁免: 非本科但最新工作為實質工程且有{len(eng_lines)}段工程經歷 (總年資{total_eng_years:.1f}年)")

    if has_non_eng_major and not has_mep_civil_major and not is_exempt_e30:
        return 0, ["排除(E30): 純設計/文商社科背景且無機電土木雙主修"], True

    # E31: 偽專案/純業務防呆
    fake_pm_titles = ['業務經理', '產品經理', '專案管理員', '營運管理師', '銷售代表']
    is_fake_pm = any(t in first_work or t in desired for t in fake_pm_titles)
    if is_fake_pm:
        has_eng_practice = any(k in work_text for k in ['工程', '監造', '監工', '廠務', '機電', '施工', '設計', '規劃', '統包', 'BIM'])
        if not has_eng_practice:
            return 0, ["排除(E31): 偽專案/純業務且無實質工程實績"], True

    # E31b: 長期業務/行政經歷偏離防呆
    non_eng_years = 0
    eng_years = 0
    for line in c['work_lines']:
        yrs = get_line_years(line)
        is_non_eng = any(k in line for k in ['業務', '特助', '行政', '助理', '秘書', '採購', '總務', '銷售'])
        is_eng = any(k in line.upper() for k in ['工程', '設計', '施工', '監造', '監工', '廠務', '機電', '空調', '消防', '電力', 'BIM', 'REVIT', '土木', '結構'])
        if is_non_eng and not is_eng:
            non_eng_years += yrs
        elif is_eng:
            eng_years += yrs
    if non_eng_years >= 3.0 and eng_years < 1.5:
        return 0, [f"排除(E31b): 長期業務/行政經歷且工程年資僅{eng_years:.1f}年"], True

    # E31c: 業務/營運/ERP 主軸且實質 MEP 工程薄弱排除 (v11.7, Q2, 2026-07-15)
    # 破口：E17業務豁免 + E30轉型豁免 靠「工程」泛詞或最新掛工程職稱通關，但職涯主軸為業務/營運/ERP。
    #   涂威霖(59, 業務部經理/經銷業務+工程掛名, desired=業務主管)、許倍群(空調業務工程師 TRANE/開利+品保)。
    #   E31b 被「工程」泛詞矇混(工程部經理/品質工程師含『工程』計為 eng)，故另以「實質 MEP 子系統年資」重算。
    # 保護真轉型者：近2段有 ≥1年 實質 MEP 工程者豁免；實質 MEP 年資 ≥3年者豁免。
    biz_kws = ['業務', 'Sales', 'sales', '營運', 'ERP', '系統整合', '銷售', '經銷',
               '事業處', 'PMO', '產品經理', '品牌', '行銷', '客戶經理']
    real_mep_kws = ['機電', '空調', 'HVAC', '消防', '電力', '配電', '給排水', '純水', '廢水',
                    '水處理', '無塵室', '廠務', '建廠', '擴廠', '管線', '配管', '監造', '監工',
                    '施工', 'MEP', 'BIM', 'Revit', '統包', 'EPC', '水電']
    # 「業務工程師/空調業務」等賣 MEP 產品的業務，其 MEP 字眼多來自公司名(如「詮宏空調系統服務」)
    # 或產品名，非實質 MEP 工程年資 → 該段一律計為業務(修正許倍群：空調業務工程師 TRANE 7.75 年遭誤計為機電)。
    sales_markers = ['業務', '銷售', 'Sales', 'sales', '經銷', '业务']
    biz_years_31c = 0.0
    real_mep_years_31c = 0.0
    for line in c['work_lines']:
        yrs = get_line_years(line)
        has_biz = any(k in line for k in biz_kws)
        has_real_mep = any(k.upper() in line.upper() for k in real_mep_kws)
        is_sales_line = any(s in line for s in sales_markers)
        if has_biz and (is_sales_line or not has_real_mep):
            biz_years_31c += yrs
        elif has_real_mep:
            real_mep_years_31c += yrs
    total_yrs_31c = sum(get_line_years(l) for l in c['work_lines'])
    recent_is_real_mep_31c = any(
        (any(k.upper() in line.upper() for k in real_mep_kws)
         and not any(s in line for s in sales_markers)
         and get_line_years(line) >= 1.0)
        for line in c['work_lines'][:2]
    )
    # 保護：full_text 具「≥2 項強設施/建廠/電力工程實質」者不誤殺——這類實質常落在
    # /review 完整履歷的「工作內容」欄(而非職稱行)。李坤霖 regression：職稱『營運總監』帶
    # 『營運』但工作內容為 變電站/光儲電站建設/電力設備/太陽能儲能，實為電力建廠人才。
    strong_mep_facility = ['變電站', '電站', '光儲', '無塵室', '廠務', '建廠', '擴廠', 'EPC', '統包',
                           '施工圖', '受電', '高壓', '機電設備', '太陽能', '儲能', '充電樁',
                           '空調系統', '消防系統', '給排水', '純水', '廢水', '無塵', 'BIM', 'Revit']
    has_strong_facility_full = sum(1 for k in strong_mep_facility if k in full) >= 2
    if (total_yrs_31c > 0 and biz_years_31c / total_yrs_31c >= 0.30
            and real_mep_years_31c < 3.0 and not recent_is_real_mep_31c
            and not has_strong_facility_full):
        return 0, [f"排除(E31c): 業務/營運/ERP主軸(佔{biz_years_31c/total_yrs_31c*100:.0f}%)且實質MEP工程年資僅{real_mep_years_31c:.1f}年"], True

    # E32: 高齡且無機電/建廠實務防呆
    age_num = 0
    age_match = re.search(r'(\d+)', c['age'])
    if age_match:
        age_num = int(age_match.group(1))
    if age_num >= 60:
        has_mep_sig = any(tok in full for tok in MEP_SUBSTANCE_TOKENS)
        has_bim_sig = any(tok in full.upper() for tok in ['BIM', 'REVIT', 'NAVISWORKS'])
        if not has_mep_sig and not has_bim_sig:
            return 0, ["排除(E32): 高齡且無機電或BIM實質經歷"], True

    # E34: 短期最新工作限制歷史豁免 (v11.1, 2026-06-23)
    # 若最新一份工作持任未滿 1.0 年，且該工作是候選人繞過排除條件（E19歷史豁免/E12歷史豁免）的唯一原因，
    # 則必須檢查先前工作是否有至少一段非致命的實質工程經歷，否則仍排除。
    # 排除顏銘村樣本：最新工作為測試工程師(半導體大廠)短於1年，靠此繞過E19但先前經歷全為非工程
    if c['work_lines']:
        first_work_years = get_line_years(c['work_lines'][0])
        if first_work_years < 1.0:
            # 檢查先前工作（work_lines[1:]）是否有至少一段實質工程經歷
            prior_eng_kws = ['工程師', '主任', '副理', '經理', '專案', '廠務', '監造', '監工', '技師',
                             '設計', '規劃', '機電', '空調', '消防', '水處理', '建廠', '擴廠']
            prior_fatal_kws = ['倉管', '業助', '服務員', '銷售員', '外送員', '門市', '餐廳', '吧台',
                               '作業員', '加油', '保全', '駐衛警', '工讀', '兼職', '服務人員',
                               '水電工', '水電行', '水電人員', '雜工', '學徒', '半技', '點工']
            prior_lines = c['work_lines'][1:]
            has_prior_eng = False
            for pl in prior_lines:
                is_eng = any(k in pl for k in prior_eng_kws)
                is_fatal = any(k in pl for k in prior_fatal_kws)
                if is_eng and not is_fatal:
                    has_prior_eng = True
                    break
            if not has_prior_eng and len(prior_lines) > 0:
                return 0, [f"排除(E34): 最新工作持任僅{first_work_years:.1f}年，且先前經歷無實質工程背景"], True

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
    # v10.3 (2026-05-27): WORK_TEXT_ONLY_KEYWORDS 必須在 work_text 命中才算
    # 楊國清回饋：希望職稱寫「建廠」但工作經歷無實際建廠公司，被 keyword 灌水入選
    # 移除「建設」在「土建設計」、「營建設計」等相鄰產生的 false positive 匹配
    full_for_company = re.sub(r'(土建|營建|建築|室內|裝修|估算)設計', '', full)
    m2_raw = [kw for kw in COMPANY_KEYWORDS if kw in full_for_company]
    m2_hits = [kw for kw in m2_raw if kw not in WORK_TEXT_ONLY_KEYWORDS or kw in work_text]
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
    # v10.2 修 bug: 原 '新建' 在「黃志新建築師」中被誤觸（子字串「志新」+「建築」交界產生「新建」）
    # 移除 '新建' '擴建' 過泛 keyword，改用必須含「廠」字尾的複合詞
    if any(kw in full for kw in ['建廠', '擴廠', '新建廠', 'EPC統包', 'EPC建廠', 'EPC']):
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
        cross_hits = _n20_cross_hits(full)
        if len(cross_hits) >= 2:
            score += 12
            reasons.append(f"N20跨系統整合: {','.join(cross_hits[:3])} ({len(cross_hits)}項) (+12)")
        elif len(cross_hits) == 1:
            score += 6
            reasons.append(f"N20跨系統整合: {cross_hits[0]} (+6)")

    # 傳統重電降階: 僅命中傳統公司(中興電工/士林電機/東元)但無任何高科關鍵字
    # → 扣回 15 分，因為傳統重電(變電站/馬達)≠高科建廠(FAB/Utility)
    # v11.2: 若同時具備其他知名大廠或顧問經歷(PREMIUM_COMPANIES)，豁免降階
    trad_hits = [kw for kw in TRADITIONAL_CONDITIONAL_COMPANIES if kw in full]
    has_premium_other_than_trad = any(kw in full for kw in PREMIUM_COMPANIES if kw not in TRADITIONAL_CONDITIONAL_COMPANIES)
    if trad_hits and not n17_hits and not has_premium_other_than_trad:
        score -= 15
        reasons.append(f"傳統重電降階: {','.join(trad_hits[:2])}(無高科經驗) (-15)")

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
        # v11.2: 具備機電/廠務學歷且具有實質設備維護經驗，不進行 D3 降分
        has_mep_degree = any(k in edu for k in ['電機', '機械', '冷凍空調', '機電', '環工', '環境工程', '化工', '化學'])
        # v0.8 (2026-07-09 古芝妍回饋): Q4 高科大廠 BIM 人才豁免 D3（頂尖 EPC 的 BIM 整合＝正牌建廠）
        if overlay.enable_high_tech_vip_unlock and _is_high_tech_vip_bim(full):
            reasons.append("D3 豁免 (Q4 VIP 大廠 BIM): 頂尖高科 EPC 的 BIM 整合視為正牌建廠經驗")
        elif has_mep_degree and any(kw in work_text for kw in ['維護', '設備', '機電', '水電', '配線', '電控', '電機']):
            pass
        else:
            score -= 15
            reasons.append("D3廠務防呆: 偏維護缺乏規劃整合 (-15)")

    # D4: 製造端/測試端降階 (扣 15 分)
    # 針對測試、組裝、產線、加工、車廠等非建廠製造屬性
    mfg_penalty_keywords = ['測試', '產線', '組裝', '加工', '車廠', 'plc', 'smt', 'cnc']
    if any(k in work_and_desired.lower() for k in mfg_penalty_keywords):
        # v11.2: 具備機電學歷且最新職稱為廠務/工程師/設備維護，不進行 D4 製造降分
        has_mep_degree = any(k in edu for k in ['電機', '機械', '冷凍空調', '機電', '環工', '環境工程', '化工', '化學'])
        first_is_facility = any(k in first_work for k in ['廠務', '工程師', '主任', '主管', '維護', '設備', '污水'])
        if has_mep_degree and first_is_facility:
            pass
        else:
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

    # D6b: 近期短期連跳加重扣分 (v11.4, Q4)
    # 近 3 段工作全部任職未滿 1 年且無建廠厚度 → 穩定性存疑 (蔡明融型：2026 半年連跳 3 家)
    if len(c['work_lines']) >= 3:
        recent3_all_short = all(get_line_years(l) < 1.0 for l in c['work_lines'][:3])
        if recent3_all_short and not has_thick:
            score -= 20
            reasons.append("D6b 短期連跳加重: 近3段全未滿1年且無建廠厚度 (-20)")

    # D7: BIM-only 降級（mep-design / space-manager overlay 啟用，反「BIM 外衣」核心規則）
    if overlay.enable_d7_bim_only:
        has_bim = any(tok in work_and_desired for tok in BIM_TOKENS)
        has_mep_or_epc = any(
            tok in work_and_desired for tok in
            ['空調', '消防', '電力', '給排水', '機電', '廠務', '建廠', '擴廠',
             'EPC', '統包', 'MEP', '無塵室', 'HVAC', '管線', '配管']
        )
        if has_bim and not has_mep_or_epc:
            # v0.8 (2026-07-09 古芝妍回饋): Q4 高科大廠 BIM 人才豁免 D7（非「BIM 外衣」，是正牌 EPC 建廠整合）
            if overlay.enable_high_tech_vip_unlock and _is_high_tech_vip_bim(full):
                reasons.append("D7 豁免 (Q4 VIP 大廠 BIM): 頂尖高科 EPC 的 BIM 整合視為正牌建廠經驗，不視為 BIM 外衣")
            # space-manager 例外：若有空間/整合/法規關鍵字則不扣分
            elif overlay.d7_space_softens_penalty:
                has_space_or_cross = (
                    any(tok in work_and_desired for tok in SPACE_TOKENS)
                    or any(tok in work_and_desired for tok in CROSS_SYSTEM_TOKENS)
                    or any(tok in work_and_desired for tok in REGULATION_TOKENS)
                )
                if not has_space_or_cross:
                    # v10.2 (2026-05-27): 游旻姍回饋——非本科 + BIM-only + 無實質應加重
                    is_non_cognate = not any(kw in edu for kw in EDU_KEYWORDS)
                    penalty = 25 if is_non_cognate else 15
                    score -= penalty
                    if is_non_cognate:
                        reasons.append(f"D7 加重 (v10.2): 非本科學歷 + BIM-only 無工程/空間實質 (-{penalty})")
                    else:
                        reasons.append(f"D7 BIM-only 降級: BIM 外衣但無工程/空間實質 (-{penalty})")
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
            # 例外②: 具備 CSD/套圖/二次審圖能力不扣
            has_csd = any(kw in work_and_desired.upper() for kw in ['CSD', '套圖', '審圖', '二次審圖'])
            if not (has_space and has_reg) and not has_csd:
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

    # D17: 無管理潛力降級（space-manager overlay, v10.2, 2026-05-27）
    # 李思穎/游旻姍回饋：年資已累積但職涯全段無管理抬頭，且無「規劃/整合/廠務/監造」
    # 等往上發展的軌跡字眼 → 視為缺乏管理潛力，扣分
    # 假抬頭防護：「總監助理」「副主任助理」等 substring 命中但本質為助理 → 不算
    # 年齡 ≤30 加重（年資累積機會少，更難相信轉型潛力）
    # PREMIUM_COMPANIES escape：曾在大廠工作過的人不應因「無管理抬頭」被誤殺
    # （董欣寧 regression case：30歲、達欣+TSMC 經歷但無 mgmt 抬頭，第一輪通過）
    if overlay.enable_d17_no_mgmt_potential:
        mgmt_kws = ['主任', '課長', '副理', '經理', '協理', '處長', '總監']
        has_real_mgmt = False
        for line in c['work_lines']:
            for kw in mgmt_kws:
                if kw in line and '助理' not in line and '助手' not in line:
                    has_real_mgmt = True
                    break
            if has_real_mgmt:
                break
        growth_trace_kws = ['規劃', '整合', '廠務', '監造', '監工', '專案', '統包', '建廠']
        has_growth_trace = any(
            any(t in line for t in growth_trace_kws) for line in c['work_lines']
        )
        total_years_d17 = sum(get_line_years(l) for l in c['work_lines'])
        has_premium_d17 = any(kw in full for kw in PREMIUM_COMPANIES)
        if total_years_d17 >= 3 and not has_real_mgmt and not has_growth_trace and not has_premium_d17:
            penalty = 25
            age_match_d17 = re.search(r'(\d+)', c['age'])
            if age_match_d17 and int(age_match_d17.group(1)) <= 30:
                penalty = 35
            score -= penalty
            reasons.append(
                f"D17 無管理潛力 (space-manager): 年資 {total_years_d17:.1f}年全段無管理抬頭且無規劃/整合/廠務/監造軌跡且無大廠經歷 (-{penalty})"
            )

    # D14: 傳統基層現場人員降級（space-manager overlay）
    # 規則自 v8.15 / overlay v0.4 即文件化於 screening_rules.md 與 space-manager.md，
    # 但長期未落地程式碼（rules↔code desync，gotcha #5）；v0.8 (2026-07-09) 補實作。
    # 判準：完全缺乏 space-manager 核心亮點——BIM(N6)/BIM×MEP共現(N18)/空間·法規(N19)/跨系統(N20)
    # 四者全部未命中 → 屬傳統基層機電/水電/監工/工地/設備人員，與跨系統空間整合職缺輪廓不符 → -25。
    # （訊號判定與 N6/N18/N19/N20 各自的命中條件完全一致，避免邏輯漂移。）
    if overlay.enable_d14_traditional_field_worker:
        n6_sig = any(tok in full for tok in BIM_TOKENS)
        n18_sig = _count_bim_mep_cooccurrence(c['work_lines']) >= 1
        n19_sig = (any(tok in full for tok in SPACE_TOKENS)
                   or any(tok in full for tok in REGULATION_TOKENS))
        n20_sig = len(_n20_cross_hits(full)) > 0
        if not (n6_sig or n18_sig or n19_sig or n20_sig):
            score -= 25
            reasons.append("D14 傳統基層降級 (space-manager): 無 BIM/空間/法規/跨系統任一亮點 (-25)")

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
        help='角色模式（預設 default = 主規則檔現行行為，版本見 screening_rules.md 第六節）'
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

    # 載入名單蒐集階段的持久化回饋（跨批次累積、append-only；由 /improve 蒐集階段維護）
    #   unqualify.md — 引擎放行但使用者判定不合格者（誤選 / false positive）→ 標 ★
    #   qualify.md   — 引擎排除但使用者判定合格者（漏選 / false negative）→ 標 ☆ 並列漏網清單
    # 兩檔格式與 ANALYSIS.md 候選人區塊相同，以「代碼：」與重複姓名列辨識。
    _base = os.path.dirname(os.path.abspath(__file__))
    _project_root = os.path.normpath(os.path.join(_base, '..', '..', '..', '..'))

    def _load_marklist(fname):
        codes, names = set(), set()
        fpath = os.path.join(_project_root, fname)
        if os.path.isfile(fpath):
            try:
                with open(fpath, 'r', encoding='utf-8') as mf:
                    content = mf.read()
                codes = set(re.findall(r'代碼：(\d+)', content))
                mlines = content.replace('\r\n', '\n').split('\n')
                for idx_line, line_text in enumerate(mlines):
                    if '歲' in line_text and idx_line >= 2:
                        name1 = mlines[idx_line - 1].strip()
                        name2 = mlines[idx_line - 2].strip()
                        if name1 == name2 and name1:
                            names.add(name1)
            except Exception as e:
                print(f"警告：讀取 {fname} 失敗: {e}")
        return codes, names

    def _in_marklist(cand, codes, names):
        m = re.search(r'代碼：(\d+)', cand['full_text'])
        if m and m.group(1) in codes:
            return True
        return cand['name'] in names

    unqualify_codes, unqualify_names = _load_marklist('unqualify.md')
    qualify_codes, qualify_names = _load_marklist('qualify.md')

    # 篩選
    results = {'G1_土木建築': [], 'G2_機電相關': [], 'G3_其他': [], '未分類': []}
    excluded = 0
    below_threshold = 0
    threshold = 20  # 最低分數門檻（v2.1 提高：避免泛用詞矇混）
    qualify_missed = []  # qualify.md 名單中仍被引擎排除/未達門檻者（規則尚未捕捉的漏選）

    for c in candidates:
        score, reasons, is_excluded = score_candidate(c, overlay)
        is_qualify = _in_marklist(c, qualify_codes, qualify_names)
        if is_excluded:
            excluded += 1
            if is_qualify:
                qualify_missed.append((c['name'], c['age'], '被排除'))
            continue

        # 命中歷史回饋名單標記（★ = 應排除卻仍入選；☆ = 應入選）
        is_unqualify = _in_marklist(c, unqualify_codes, unqualify_names)

        if score >= threshold:
            results[c['group']].append({
                'name': c['name'],
                'age': c['age'],
                'score': score,
                'reasons': reasons,
                'is_unqualify': is_unqualify,
                'is_qualify': is_qualify,
            })
        else:
            below_threshold += 1
            if is_qualify:
                qualify_missed.append((c['name'], c['age'], f'未達門檻 score={score}'))

    # 排序（各組內按分數降序）
    for group in results:
        results[group].sort(key=lambda x: -x['score'])

    # 輸出
    total_selected = sum(len(v) for v in results.values())
    print("=" * 60)
    print(f"篩選結果：候選 {total_selected} 人 / 排除 {excluded} 人 / 未達門檻 {below_threshold} 人")
    if unqualify_codes or unqualify_names or qualify_codes or qualify_names:
        print("標記說明：★=命中 unqualify.md（應排除卻仍入選）  ☆=命中 qualify.md（應入選）")
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
            mark = (" ★" if r.get('is_unqualify') else "") + (" ☆" if r.get('is_qualify') else "")
            print(f"  {r['name']}{mark} (age:{r['age']}, score:{r['score']}) — {reason_str}")

    # 未分類
    if results['未分類']:
        print(f"\n### 未分類 ({len(results['未分類'])} 人)")
        for r in results['未分類']:
            reason_str = " | ".join(r['reasons'][:3])
            mark = (" ★" if r.get('is_unqualify') else "") + (" ☆" if r.get('is_qualify') else "")
            print(f"  {r['name']}{mark} (age:{r['age']}, score:{r['score']}) — {reason_str}")

    # qualify.md 名單中仍被引擎漏掉者 —— /improve 疊代階段要補的規則缺口
    if qualify_missed:
        print(f"\n### ☆ qualify.md 名單仍被引擎漏掉 ({len(qualify_missed)} 人) — 待 /improve 補規則缺口")
        print("-" * 50)
        for name, age, why in qualify_missed:
            print(f"  {name} ☆ (age:{age}) — {why}")


if __name__ == '__main__':
    main()
