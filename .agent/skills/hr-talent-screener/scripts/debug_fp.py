import sys, io, os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
from screen_candidates import parse_candidates, score_candidate

with open('c:/Users/01102088/Desktop/HRMD/ANALYSIS.md', 'r', encoding='utf-8') as f:
    lines = f.read().split('\n')
cands = parse_candidates(lines)

excl_list = ['邱鴻霖', '郭安迪', '胡哲華', '黃奕傑', '陳伯鈞', '黃煜恆', '陳鈞凱', '李奕杰', '蔡竣宇', '沈家佑', '謝哲瑋', '沈大鈞', '王志遠', '田婕伶', '鄭建光']

with open('debug_out.txt', 'w', encoding='utf-8') as out:
    out.write("=== FALSE POSITIVES (誤選) ===\n")
    for c in cands:
        name_clean = c['name'].replace(' ', '')
        if any(n in name_clean for n in excl_list):
            score, reasons, excluded = score_candidate(c)
            out.write(f"[{c['group']}] {c['name']} (Score: {score})\n")
            out.write(f"  Reasons: {reasons}\n")
            out.write(f"  Desired: {c['desired_title']}\n")
            for w in c['work_lines'][:5]: out.write(f"  Work: {w}\n")
