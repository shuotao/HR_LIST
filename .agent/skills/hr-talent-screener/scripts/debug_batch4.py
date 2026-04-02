import sys, io, os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
from screen_candidates import parse_candidates, score_candidate

with open('c:/Users/01102088/Desktop/HRMD/ANALYSIS.md', 'r', encoding='utf-8') as f:
    lines = f.read().split('\n')
cands = parse_candidates(lines)

fps = '陳建宇 唐孜穎 林育志 林坤益 徐煒山 徐仁傑 蘇冠霖 簡登舜 彭康豪 馮梓笙 劉婷姍 陳緯朋 杜新景 宋柏諺 蔡宏彬 陳宇軒 盧沛誼 黃志忠 江福文 謝政霓 蕭家杰 李仲傑'.split()
fns = '林振昌 何建輝 林傳尉 曾昊全'.split()

with open('debug_out.txt', 'w', encoding='utf-8') as out:
    out.write("=== FALSE NEGATIVES (漏選) ===\n")
    for c in cands:
        if any(n in c['name'] for n in fns):
            score, reasons, excluded = score_candidate(c)
            out.write(f"[{c['group']}] {c['name']} (Score: {score}, Excluded: {excluded})\n")
            out.write(f"  Reasons: {reasons}\n")
            out.write(f"  Desired: {c['desired_title']}\n")
            out.write(f"  Edu: {c['edu']}\n")
            for w in c['work_lines'][:3]: out.write(f"  Work: {w}\n")

    out.write("\n=== FALSE POSITIVES (誤選) ===\n")
    for c in cands:
        if any(n in c['name'] for n in fps):
            score, reasons, excluded = score_candidate(c)
            out.write(f"[{c['group']}] {c['name']} (Score: {score})\n")
            out.write(f"  Reasons: {reasons}\n")
            out.write(f"  Desired: {c['desired_title']}\n")
            for w in c['work_lines'][:2]: out.write(f"  Work: {w}\n")

