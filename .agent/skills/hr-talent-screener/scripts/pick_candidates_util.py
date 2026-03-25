import sys
import os

_base = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _base)
_project_root = os.path.normpath(os.path.join(_base, '..', '..', '..', '..'))

import screen_candidates

with open(os.path.join(_project_root, 'ANALYSIS.md'), 'r', encoding='utf-8') as f:
    lines = f.read().replace('\r\n', '\n').split('\n')

candidates = screen_candidates.parse_candidates(lines)
results = []
for c in candidates:
    score, reasons, excluded = screen_candidates.score_candidate(c)
    if not excluded and score >= 15:
        results.append((score, c['name'], c['age'], reasons))

results.sort(key=lambda x: -x[0])

with open(os.path.join(_project_root, 'final_list.txt'), 'w', encoding='utf-8') as fout:
    fout.write(f"共解析 {len(candidates)} 位候選人，篩選出 {len(results)} 人：\n\n")
    for s, n, a, r in results:
        fout.write(f"- {n} (年齡: {a}, 分數: {s}) — {' | '.join(r)}\n")
