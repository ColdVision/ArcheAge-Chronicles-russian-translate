"""Новые и изменённые строки после обновления игры — для перевода субагентом.
  python scripts/update_build.py <old-build> <new-build> [--chunk 40000]  -> work/upd/upd_<n>.txt
Строки: `KEY | NEW|CHG | EN | старый RU (для CHG)`; у реплик — соседние строки сцены с пометкой CTX (не переводить)."""
import argparse, collections, csv, json, os, re, sys
sys.stdout.reconfigure(encoding='utf-8')
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, 'work', 'upd')
ap = argparse.ArgumentParser(); ap.add_argument('old'); ap.add_argument('new'); ap.add_argument('--chunk', type=int, default=40000)
a = ap.parse_args()
def L(b):
    with open(os.path.join(ROOT, 'work', f'en-{b}.csv'), encoding='utf-8-sig', newline='') as f:
        return {r['key']: r['text'] for r in csv.DictReader(f)}
old, en = L(a.old), L(a.new)
kop = os.path.join(ROOT, 'work', f'ko-{a.new}.csv')
ko = {r['key']: r['text'] for r in csv.DictReader(open(kop, encoding='utf-8-sig'))} if os.path.exists(kop) else {}
prj = json.load(open(os.path.join(ROOT, 'project', 'aa.x5tr'), encoding='utf-8'))
ru = {k: t for ns, k, t in prj['Tr']}
stale = {k for ns, k in prj['Stale']}
new = [k for k in en if k not in old and not ru.get(k)]
todo = set(new) | stale
cl = lambda s: s.replace('\r', '').replace('\n', '\\n')
def scene(k):
    m = re.match(r'TXT_(DIALOGUESELECTION|DIALOGUE|CAPTION)_(\d{10})_', k)
    return m.group(2) if m else None
by_scene = collections.defaultdict(list)
for k in en:
    s = scene(k)
    if s: by_scene[s].append(k)
groups = collections.OrderedDict()
for k in sorted(todo):
    s = scene(k)
    groups.setdefault(s or re.sub(r'_\d.*', '', k), []).append(k)
blocks = []
for g, ks in groups.items():
    rows = []
    keys = sorted(by_scene[g]) if g in by_scene else ks
    for k in keys:
        if k in todo:
            rows.append(f'{k} | {"CHG" if k in stale else "NEW"} | {cl(en[k])}' + (f' | {cl(ru.get(k, ""))}' if k in stale else '') + (f' | KO: {cl(ko[k])}' if ko.get(k) else ''))
        elif ru.get(k):
            rows.append(f'CTX {k[4:]} | {cl(en[k])} | {cl(ru[k])}')
    blocks.append(f'### {g}\n' + '\n'.join(rows) + '\n')
chunks, cur = [], ''
for b in blocks:
    if cur and len(cur) + len(b) > a.chunk: chunks.append(cur); cur = ''
    cur += b + '\n'
if cur: chunks.append(cur)
os.makedirs(OUT, exist_ok=True)
for f in os.listdir(OUT):
    if f.startswith('upd_') and f.endswith('.txt'): os.remove(os.path.join(OUT, f))
for i, c in enumerate(chunks, 1):
    open(os.path.join(OUT, f'upd_{i}.txt'), 'w', encoding='utf-8').write(c)
print(f'новых: {len(new)}, изменённых: {len(stale)}, файлов: {len(chunks)}')
