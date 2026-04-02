import sys, io, os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
from screen_candidates import parse_candidates, score_candidate

with open('c:/Users/01102088/Desktop/HRMD/ANALYSIS.md', 'r', encoding='utf-8') as f:
    lines = f.read().split('\n')
cands = parse_candidates(lines)

excl_raw = '王昱翔 陳莊勝 馬崇耀 郭昱宏 梁秦瑝 林育男 方啟名 吳岱融 馮敬傑 吳昭陽 蕭文賢 林孟賢 鄭博文 劉展驛 李唯瑞 李沛瑄 呂訓亨 傅煒傑 程少伯 黃聖凱 林俊丞 林聖賢 黃章銘 饒展誠 黃國瑞 陳冠文 張擎宇 沈寧 張凱迪 張瀚文 陳仁宗 詹子明 陳俊豪 王鈺富 吳少錡 劉耕綸 江曜樽 賴育澄 李玉聖 林子絹 曾麗文 林    聖賢'
incl_raw = '林聖為 蘇裕評 楊昀翰 詹浩澤 馮梓笙 王鈺富 吳岱融'

fps = set(excl_raw.split())
fns = set(incl_raw.split())

# Remove from fps if they are in fns
for n in fns:
    if n in fps:
        fps.remove(n)

with open('debug_batch5.txt', 'w', encoding='utf-8') as out:
    out.write("=== FALSE NEGATIVES (漏選) ===\n")
    for c in cands:
        name_clean = c['name'].replace(' ', '')
        if any(n in name_clean for n in fns):
            score, reasons, excluded = score_candidate(c)
            out.write(f"[{c['group']}] {c['name']} (Score: {score}, Excluded: {excluded})\n")
            out.write(f"  Reasons: {reasons}\n")
            out.write(f"  Desired: {c['desired_title']}\n")
            out.write(f"  Edu: {c['edu']}\n")
            for w in c['work_lines'][:3]: out.write(f"  Work: {w}\n")

    out.write("\n=== FALSE POSITIVES (誤選) ===\n")
    for c in cands:
        name_clean = c['name'].replace(' ', '')
        if any(n in name_clean for n in fps):
            score, reasons, excluded = score_candidate(c)
            out.write(f"[{c['group']}] {c['name']} (Score: {score})\n")
            out.write(f"  Reasons: {reasons}\n")
            out.write(f"  Desired: {c['desired_title']}\n")
            for w in c['work_lines'][:2]: out.write(f"  Work: {w}\n")
