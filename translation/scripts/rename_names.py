"""Единое написание имён NPC во всём проекте (целыми словами).
  python scripts/rename_names.py NNN   -> batches/NNN.json + x5tr apply"""
import csv, json, os, re, subprocess, sys
sys.stdout.reconfigure(encoding='utf-8')
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PRJ = os.path.join(ROOT, 'project', 'aa.x5tr')
X5 = os.path.join(ROOT, '..', 'X5Tr.Cli', 'bin', 'Release', 'net10.0', 'x5tr.exe')
MAP = {
    'Лаза': 'Ласа', 'Лазы': 'Ласы', 'Лазе': 'Ласе', 'Лазу': 'Ласу', 'Лазой': 'Ласой',
    'Лореа': 'Лорея',
    'Ролдан': 'Рольдан', 'Ролдана': 'Рольдана', 'Ролдану': 'Рольдану', 'Ролданом': 'Рольданом', 'Ролдане': 'Рольдане',
    'Риголл': 'Ригол', 'Риголла': 'Ригола', 'Риголлу': 'Риголу', 'Риголлом': 'Риголом', 'Риголле': 'Риголе',
    'Азра': 'Ажра', 'Азры': 'Ажры', 'Азре': 'Ажре', 'Азру': 'Ажру', 'Азрой': 'Ажрой',
    'Нианрот': 'Ниарот', 'Нианрота': 'Ниарота', 'Нианроту': 'Ниароту', 'Нианротом': 'Ниаротом', 'Нианроте': 'Ниароте',
    'Монд': 'Монде', 'Монда': 'Монде', 'Монду': 'Монде', 'Мондом': 'Монде',
}
RX = re.compile(r'(?<![А-Яа-яЁё])(' + '|'.join(sorted(map(re.escape, MAP), key=len, reverse=True)) + r')(?![А-Яа-яЁё])')
num = sys.argv[1]
en = {}
with open(os.path.join(ROOT, 'work', 'en-26495283.csv'), encoding='utf-8-sig', newline='') as f:
    for r in csv.DictReader(f): en[r['key']] = r['text']
prj = json.load(open(PRJ, encoding='utf-8'))
out = []
for ns, k, t in prj['Tr']:
    n = RX.sub(lambda m: MAP[m.group(1)], t)
    if n != t:
        out.append({'ns': ns, 'key': k, 'en': en.get(k, ''), 'ru': n})
        print(k, '|', n[:140].replace('\n', ' '))
bp = os.path.join(ROOT, 'batches', f'{num}.json')
json.dump(out, open(bp, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
print('строк:', len(out))
r = subprocess.run([X5, 'apply', PRJ, bp], capture_output=True, text=True, encoding='utf-8')
print(r.stdout[-600:], r.stderr[-600:])
