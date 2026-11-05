"""Склейка частей от субагентов.
  python scripts/merge_parts.py names NNN K   work/bNNN_r0..K-1.txt (номера = индекс в bNNN_uniq.json) -> work/bNNN_ru.txt
  python scripts/merge_parts.py desc  NNN K   work/bNNN_r0..K-1.txt (номера = индекс строки в bNNN_src.json) -> work/bNNN_ru.txt
Пропуски печатаются; одинаковые английские строки получают один перевод."""
import json, sys
sys.stdout.reconfigure(encoding='utf-8')
mode, nnn, k = sys.argv[1], sys.argv[2], int(sys.argv[3])
src = json.load(open(f'work/b{nnn}_src.json', encoding='utf-8'))
norm = lambda s: s.replace('\r\n', '\n').replace('\n', '¶').strip()
got = {}
import os
parts = [int(x) for x in os.environ['PARTS'].split(',')] if os.environ.get('PARTS') else range(k)
for p in parts:
    try: lines = open(f'work/b{nnn}_r{p}.txt', encoding='utf-8-sig').read().split('\n')
    except FileNotFoundError: print('нет файла части', p); continue
    for l in lines:
        if '|' in l:
            i, t = l.split('|', 1)
            if i.strip().isdigit(): got[int(i)] = t.rstrip('\r')
by_en = {}
if mode == 'names':
    u = json.load(open(f'work/b{nnn}_uniq.json', encoding='utf-8'))
    for i, e in enumerate(u):
        if i in got: by_en[e] = got[i]
else:
    for i, t in got.items(): by_en[norm(src[i]['en'])] = t
out = []; miss = 0
for i, r in enumerate(src):
    t = by_en.get(norm(r['en']))
    if t is None: miss += 1; continue
    out.append(f'{i}|{t}')
open(f'work/b{nnn}_ru.txt', 'w', encoding='utf-8', newline='\n').write('\n'.join(out) + '\n')
print('строк', len(out), 'пропусков', miss)
