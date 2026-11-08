"""Исправления по досье NPC.
  python scripts/dossier_fix.py build      -> work/dfix/<NPC>.txt (контекст NPC + ошибки + строки key|EN|RU)
  python scripts/dossier_fix.py apply NNN  <- work/dfix/<NPC>_ru.tsv (key<TAB>новый RU), проверка тегов/маркеров -> batches/NNN.json + x5tr apply
"""
import csv, glob, json, os, re, subprocess, sys
from collections import Counter
sys.stdout.reconfigure(encoding='utf-8')
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
NPC = os.path.join(ROOT, 'npc')
OUT = os.path.join(ROOT, 'work', 'dfix')
PRJ = os.path.join(ROOT, 'project', 'aa.x5tr')
X5 = os.path.join(ROOT, '..', 'X5Tr.Cli', 'bin', 'Release', 'net10.0', 'x5tr.exe')
EN_CSV = os.path.join(ROOT, 'work', 'en-26495283.csv')

def load():
    en = {}
    with open(EN_CSV, encoding='utf-8-sig', newline='') as f:
        for r in csv.DictReader(f): en[r['key']] = (r['namespace'], r['text'])
    prj = json.load(open(PRJ, encoding='utf-8'))
    ru = {k: t for ns, k, t in prj['Tr']}
    return en, ru

def section(md, title):
    m = re.search(r'^## ' + title + r'.*?$(.*?)(?=^## |\Z)', md, re.S | re.M)
    return m.group(1).strip() if m else ''

def keys_in(text, allkeys):
    found = []
    for tok in re.findall(r'\b(?:TXT_)?[A-Z][A-Z0-9]*(?:_[0-9A-Z]+)+\b', text):
        for c in (tok, 'TXT_' + tok, tok + '_TEXT', 'TXT_' + tok + '_TEXT'):
            if c in allkeys:
                found.append(c); break
    # сокращения: PREFIX_<10 цифр> без хвоста -> все ключи с этим началом
    for pre, did in re.findall(r'(?<![A-Z0-9_])(?:TXT_)?([A-Z]+)_(\d{10})(?![_\d])', text):
        found += sorted(k for k in allkeys if k.startswith(f'TXT_{pre}_{did}_'))[:12]
    # «0002050140_0002», «1008011074_3 и _4»
    for did, tail in re.findall(r'(?<![_\d])(\d{10})((?:_\d{1,10})(?:\s*(?:и|,)\s*_\d{1,10})*)', text):
        for n in re.findall(r'_(\d{1,10})', tail):
            seq = n.zfill(10)
            for p in ('TXT_DIALOGUE_', 'TXT_CAPTION_'):
                if f'{p}{did}_{seq}_TEXT' in allkeys: found.append(f'{p}{did}_{seq}_TEXT')
            found += sorted(k for k in allkeys if k.startswith(f'TXT_DIALOGUESELECTION_{did}_{seq}_'))
    # голые id диалогов: «Диалоги 0103040065, 0103040066»
    for did in re.findall(r'(?<![_\d])(\d{10})(?![_\d])', text):
        for p in ('TXT_DIALOGUE_', 'TXT_DIALOGUESELECTION_', 'TXT_CAPTION_'):
            found += sorted(k for k in allkeys if k.startswith(p + did + '_'))
    return list(dict.fromkeys(found))

def build(p2=False):
    en, ru = load()
    allkeys = set(en)
    os.makedirs(OUT, exist_ok=True)
    total = 0
    for d in sorted(glob.glob(os.path.join(NPC, '*', 'dossier.md'))):
        name = os.path.basename(os.path.dirname(d))
        md = open(d, encoding='utf-8').read()
        head = '\n'.join(l for l in md.splitlines() if re.match(r'\| (Имя|Склонение|Пол|Фракция|Где|Окружение) ', l))
        char = section(md, 'Характер')
        errs = section(md, 'Найденные ошибки')
        iss_p = os.path.join(NPC, name, 'issues.md')
        iss = open(iss_p, encoding='utf-8').read() if os.path.exists(iss_p) else ''
        ks = keys_in(errs, allkeys)
        ks2 = [k for k in keys_in(iss, allkeys) if k not in ks]
        if p2:
            prev = open(os.path.join(OUT, name + '.txt'), encoding='utf-8').read()
            done = set(re.findall(r'^(?:AUTO )?(TXT_[A-Z0-9_]+)\|', prev, re.M))
            ks = [k for k in ks + ks2 if k not in done]; ks2 = []
            if not ks: continue
        lines = [f'# NPC {name}', head, '', '## Характер и речь', char, '', '## Ошибки из досье (исправить)', errs, '',
                 '## Строки (key|EN|текущий RU). Сначала ключи из досье, затем «AUTO» — автонаходки по роду (могут быть ложными: проверь сам)']
        for tag, group in (('', ks), ('AUTO ', ks2)):
            for k in group:
                e = en[k][1].replace('\r', '').replace('\n', '\\n')
                r = ru.get(k, '').replace('\r', '').replace('\n', '\\n')
                lines.append(f'{tag}{k}|{e}|{r}')
        open(os.path.join(OUT, name + ('.p2.txt' if p2 else '.txt')), 'w', encoding='utf-8').write('\n'.join(lines) + '\n')
        total += len(ks) + len(ks2)
        print(f'{name}: {len(ks)} из досье + {len(ks2)} авто')
    print('всего строк:', total)

TAGRE = re.compile(r'<[^>]+>')
MARK = re.compile(r'\{\{n:([a-z0-9_]+)\|[a-z]+\}\}')

def apply(num):
    en, ru = load()
    out, bad = {}, []
    for p in sorted(glob.glob(os.path.join(OUT, '*_ru*.tsv'))):
        for ln in open(p, encoding='utf-8-sig').read().splitlines():
            if not ln.strip() or '\t' not in ln: continue
            k, t = ln.split('\t', 1)
            k = k.strip().removeprefix('AUTO ').strip()
            if not k.startswith('TXT_'): k = 'TXT_' + k
            if k not in en and k + '_TEXT' in en: k += '_TEXT'
            t = t.strip().replace('\\n', '\n')
            if k not in en: bad.append((p, k, 'нет ключа')); continue
            old = ru.get(k, '')
            if Counter(TAGRE.findall(t)) != Counter(TAGRE.findall(en[k][1])):
                bad.append((p, k, 'теги')); continue
            if Counter(MARK.findall(t)) != Counter(MARK.findall(old)):
                bad.append((p, k, 'маркеры: ' + t)); continue
            out[k] = t  # последний файл побеждает (zz_Manual* — ручные правки — последними)
    for b in bad: print('ОТКЛОНЕНО', os.path.basename(b[0]), b[1], b[2])
    bp = os.path.join(ROOT, 'batches', f'{num}.json')
    out = [{'ns': en[k][0], 'key': k, 'en': en[k][1], 'ru': t} for k, t in out.items() if t != ru.get(k, '').replace('\r', '')]
    json.dump(out, open(bp, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    print('изменено строк:', len(out))
    r = subprocess.run([X5, 'apply', PRJ, bp], capture_output=True, text=True, encoding='utf-8')
    print(r.stdout[-800:], r.stderr[-800:])

if __name__ == '__main__':
    if sys.argv[1] == 'apply': apply(sys.argv[2])
    else: build(sys.argv[1] == 'build2')
