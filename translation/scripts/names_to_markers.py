"""Заменить обычный текст имён из names.tsv на маркеры {{n:id|case}} (для версии B).
  python scripts/names_to_markers.py NNN id1 id2 ...   -> batches/NNN.json + x5tr apply
Неоднозначные формы (одинаковые для нескольких падежей) берут первый по порядку gen, dat, acc, ins, prep."""
import csv, json, os, re, subprocess, sys
sys.stdout.reconfigure(encoding='utf-8')
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PRJ = os.path.join(ROOT, 'project', 'aa.x5tr')
X5 = os.path.join(ROOT, '..', 'X5Tr.Cli', 'bin', 'Release', 'net10.0', 'x5tr.exe')
CASES = ['nom', 'gen', 'dat', 'acc', 'ins', 'prep']
num, ids = sys.argv[1], sys.argv[2:]
forms = {}
for ln in open(os.path.join(ROOT, 'glossary', 'names.tsv'), encoding='utf-8-sig'):
    p = ln.rstrip('\n').split('\t')
    if p[0] in ids:
        for c, f in zip(CASES, p[3:9]):
            forms.setdefault(f, (p[0], c))
RX = re.compile(r'(?<![А-Яа-яЁё{|])(' + '|'.join(sorted(map(re.escape, forms), key=len, reverse=True)) + r')(?![А-Яа-яЁё])')
en = {}
with open(os.path.join(ROOT, 'work', 'en-26495283.csv'), encoding='utf-8-sig', newline='') as f:
    for r in csv.DictReader(f): en[r['key']] = r['text']
out = []
for ns, k, t in json.load(open(PRJ, encoding='utf-8'))['Tr']:
    parts = re.split(r'(\{\{n:[^}]+\}\})', t)  # не трогать существующие маркеры
    n = ''.join(s if s.startswith('{{n:') else RX.sub(lambda m: '{{n:%s|%s}}' % forms[m.group(1)], s) for s in parts)
    if n != t:
        out.append({'ns': ns, 'key': k, 'en': en.get(k, ''), 'ru': n})
        print(k, '|', n[:150].replace('\n', ' '))
bp = os.path.join(ROOT, 'batches', f'{num}.json')
json.dump(out, open(bp, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
print('строк:', len(out))
r = subprocess.run([X5, 'apply', PRJ, bp], capture_output=True, text=True, encoding='utf-8')
print(r.stdout[-600:], r.stderr[-600:])
