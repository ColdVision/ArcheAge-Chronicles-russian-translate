"""Строки, у которых «английский» оригинал на самом деле корейский (недоделки разработчиков), — для перевода с корейского.
  python scripts/ko_build.py [--chunk 40000]  -> work/ko/ko_<n>.txt
Служебные пометки разработчиков (тесты, шаблоны, флаги, «z01_…» и т. п.) отбрасываются.
Для реплик добавляется контекст: остальные строки той же сцены (EN | RU) с пометкой CTX — их не переводить."""
import argparse, collections, csv, json, os, re, sys
sys.stdout.reconfigure(encoding='utf-8')
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, 'work', 'ko')
ap = argparse.ArgumentParser(); ap.add_argument('--chunk', type=int, default=40000)
a = ap.parse_args()
H = re.compile('[가-힣]')
DEV = re.compile(r'테스트|템플릿|test|Test|TEST|^z\d|_|\[|PC ?:|NPC ?:|연출|용$|용 |Zone|BP|플래그|컨디션|더미|임시|여유분|미사용|삭제|기획|개발|^\d|local|마커|DO NOT|id:|PAHSE|PHASE')
en = {}
with open(os.path.join(ROOT, 'work', 'en-26803662.csv'), encoding='utf-8-sig', newline='') as f:
    for r in csv.DictReader(f): en[r['key']] = r['text']
ru = {k: t for ns, k, t in json.load(open(os.path.join(ROOT, 'project', 'aa.x5tr'), encoding='utf-8'))['Tr']}
cand = [k for k, t in en.items() if H.search(t) and not DEV.search(t) and not ru.get(k)]
cl = lambda s: s.replace('\r', '').replace('\n', '\\n')
def scene(k):
    m = re.match(r'TXT_(DIALOGUESELECTION|DIALOGUE|CAPTION)_(\d{10})_', k)
    return m.group(2) if m else None
by_scene = collections.defaultdict(list)
for k in en:
    s = scene(k)
    if s: by_scene[s].append(k)
groups = collections.OrderedDict()
for k in sorted(cand):
    s = scene(k)
    groups.setdefault(s or re.sub(r'_\d.*', '', k), []).append(k)
blocks = []
for g, ks in groups.items():
    rows = []
    if g in by_scene:
        for k in sorted(by_scene[g]):
            if k in ks: rows.append(f'{k} | KO | {cl(en[k])}')
            elif ru.get(k): rows.append(f'CTX {k[4:]} | {cl(en[k])} | {cl(ru[k])}')
    else:
        rows = [f'{k} | KO | {cl(en[k])}' for k in ks]
    blocks.append(f'### {g}\n' + '\n'.join(rows) + '\n')
chunks, cur = [], ''
for b in blocks:
    if cur and len(cur) + len(b) > a.chunk: chunks.append(cur); cur = ''
    cur += b + '\n'
if cur: chunks.append(cur)
os.makedirs(OUT, exist_ok=True)
for i, c in enumerate(chunks, 1):
    open(os.path.join(OUT, f'ko_{i}.txt'), 'w', encoding='utf-8').write(c)
print(f'строк к переводу: {len(cand)}, групп: {len(blocks)}, файлов: {len(chunks)}')
