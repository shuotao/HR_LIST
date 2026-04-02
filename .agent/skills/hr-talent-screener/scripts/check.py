import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
from screen_candidates import parse_candidates

with open('../../ANALYSIS.md', 'r', encoding='utf-8') as f:
    lines = f.read().split('\n')
cands = parse_candidates(lines)

names_to_exclude = set('黃健超 陳彥達 簡利穎 張雅芸 林益立 顏明緒 郭駿鴻 陳劭瑋 季佳霖 楊忠仁 許俊德 馬進龍 洪建彰 李濬騰 陳岱源 紀盛馭 陳勇志 余宗霖 黃室齊 陳師誠 王瑞發 王泳富 吳坤錠 許哲耀 姚自強 張世宗 林家樑 羅自強 楊智能 王奕晨 吳啟宏 陳騰昇 許晉源 廖晉德 劉銘哲 黃淇琪 林谷鴻 孫瑋祥 許蠑籲 莊宗銘 黃建文 劉建良 吳汶澤 羅人傑 張斌傑 詹益豪 蕭家杰'.split())

for c in cands:
    if c['name'] in names_to_exclude:
        print(f"[{c['group']}] {c['name']} - 期望:{c['desired_title']}")
        for wl in c['work_lines'][:2]: 
            print('  ' + wl)
