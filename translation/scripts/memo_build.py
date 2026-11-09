"""Записки (TXT_MEMO_<id>_TITLE/_TEXT) для редактуры целиком: work/scenes/<имя>_<n>.txt, формат как у scene_build.
  python scripts/memo_build.py memo [--chunk 55000]"""
import argparse, collections, csv, json, os, re, sys
sys.stdout.reconfigure(encoding='utf-8')
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, 'work', 'scenes')
ap = argparse.ArgumentParser(); ap.add_argument('name'); ap.add_argument('--chunk', type=int, default=55000)
a = ap.parse_args()
en = {}
with open(os.path.join(ROOT, 'work', 'en-26495283.csv'), encoding='utf-8-sig', newline='') as f:
    for r in csv.DictReader(f): en[r['key']] = r['text']
ru = {k: t for ns, k, t in json.load(open(os.path.join(ROOT, 'project', 'aa.x5tr'), encoding='utf-8'))['Tr']}
memos = collections.defaultdict(list)
for k in en:
    m = re.match(r'TXT_MEMO_(\d+)_(TITLE|TEXT)$', k)
    if m and ru.get(k): memos[m.group(1)].append((0 if m.group(2) == 'TITLE' else 1, k))
cl = lambda s: s.replace('\r', '').replace('\n', '\\n')
blocks = []
for mid in sorted(memos):
    rows = [f'{k} | {"заголовок" if o == 0 else "текст"} | {cl(en[k])} | {cl(ru[k])}' for o, k in sorted(memos[mid])]
    blocks.append(f'### Записка {mid}\n' + '\n'.join(rows) + '\n')
chunks, cur = [], ''
for b in blocks:
    if cur and len(cur) + len(b) > a.chunk: chunks.append(cur); cur = ''
    cur += b + '\n'
if cur: chunks.append(cur)
os.makedirs(OUT, exist_ok=True)
for i, c in enumerate(chunks, 1):
    open(os.path.join(OUT, f'{a.name}_{i}.txt'), 'w', encoding='utf-8').write(c)
print(f'записок: {len(blocks)}, файлов: {len(chunks)}')
