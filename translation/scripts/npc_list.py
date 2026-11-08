"""Предварительный список значимых NPC по данным String.locres (без таблиц диалогов).
  python scripts/npc_list.py   ->  npc/significant-npcs.md, npc/npc-stats.csv
Признаки значимости: подписи говорящего в роликах (CHANGESPEAKERNAME), упоминания имени в диалогах/роликах/квестах/записках/дневнике."""
import csv, json, os, re, sys, collections
sys.stdout.reconfigure(encoding='utf-8')
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
en = {r[1]: r[3] for r in csv.reader(open(os.path.join(ROOT, 'work', 'en.csv'), encoding='utf-8-sig')) if len(r) > 3}
tr = {k: t for ns, k, t in json.load(open(os.path.join(ROOT, 'project', 'aa.x5tr'), encoding='utf-8-sig'))['Tr']}

names = collections.defaultdict(list)
for k, v in en.items():
    m = re.match(r'TXT_NPC_(\d+)_NAME$', k)
    if m and v.strip() and not v.startswith('-') and 'DO NOT' not in v and not re.search(r'[가-힣]', v):
        names[v.strip()].append(m.group(1))
speak = collections.Counter()
for k, v in en.items():
    if k.endswith('CHANGESPEAKERNAME') and v.strip(): speak[v.strip()] += 1

TEXT = re.compile(r'TXT_(DIALOGUE|DIALOGUESELECTION|CAPTION|CUTSCENEPRESET|QUEST|QUESTPROGRESS|MEMO|PURSUITJOURNALCLUE)_')
texts = [(k, v) for k, v in en.items() if TEXT.match(k)]

# «обычные» слова — встречаются в текстах со строчной буквы; имя собственное содержит хотя бы одно необычное слово
vocab = set()
for v in en.values():
    for w in re.findall(r"(?<![A-Za-z'])([a-z][a-z']+)", v): vocab.add(w)
def named(n): return any(w.lower() not in vocab for w in re.findall(r"[A-Za-z][a-z']+", n) if w.lower() not in ('the', 'of'))

nom = {}
for l in open(os.path.join(ROOT, 'glossary', 'names.tsv'), encoding='utf-8'):
    p = l.rstrip('\n').split('\t')
    if len(p) >= 4 and not l.startswith('#'): nom[p[0]] = p[3]
def ru_plain(t): return re.sub(r'\{\{n:([a-z0-9_]+)\|[a-z]+\}\}', lambda m: nom.get(m.group(1), m.group(0)), t)
known = {}
for l in open(os.path.join(ROOT, 'glossary', 'known-names.txt'), encoding='utf-8'):
    if ' = ' in l and not l.startswith('#'):
        a, b = l.rstrip('\n').split(' = ', 1); known[a] = b

def short(n):  # «Vesper the Ruthless» -> «Vesper», «Baron Engreven» -> «Engreven»
    n = re.sub(r'^(Baron|Captain|Commander|General|Lieutenant|Sir|Lady|Lord|Elder|Chief|Master|Old|Young|Merchant|Priest|High Priest|Guard Captain)\s+', '', n)
    return re.split(r'\s+(?:the|of)\s+|,', n)[0].strip()

# реальные реплики по игровым таблицам (говорящий = ID NPC)
CMS = os.path.join(os.path.dirname(ROOT), 'game-data-26495283', 'X5', 'Content', 'Design', 'CMS')
lines_by_id = collections.Counter(); scenes_by_id = collections.defaultdict(set)
for fn in ('Dialogue.csv', 'Caption.csv'):
    for r in csv.DictReader(open(os.path.join(CMS, fn), encoding='utf-8-sig')):
        if r['speakerName'] == 'Npc' and r['speakerNameValue']:
            lines_by_id[r['speakerNameValue']] += 1; scenes_by_id[r['speakerNameValue']].add(fn[0] + r['id'])
rows = []
for n in set(names) | set(speak):
    key = short(n)
    if len(key) < 3: continue
    rx = re.compile(r'(?<![A-Za-z])' + re.escape(key) + r'(?![A-Za-z])')
    cnt = collections.Counter(); quests = set(); scenes = set()
    for k, v in texts:
        if rx.search(v):
            t = TEXT.match(k).group(1); cnt[t] += 1
            m = re.match(r'TXT_(?:QUEST|QUESTPROGRESS)_(\d+)', k)
            if m: quests.add(m.group(1))
            m = re.match(r'TXT_(?:DIALOGUE|DIALOGUESELECTION|CAPTION)_(\d+)', k)
            if m: scenes.add(m.group(1))
    mentions = sum(cnt.values())
    nids = [str(int(i)) for i in names.get(n, [])]
    nlines = sum(lines_by_id[i] for i in nids); nsc = len(set().union(*[scenes_by_id[i] for i in nids])) if nids else 0
    score = nlines * 2 + speak[n] * 3 + mentions + 2 * len(quests)
    if score < 8: continue
    ids = names.get(n, [])
    ru = ru_plain(tr.get(f'TXT_NPC_{ids[0]}_NAME', '')) if ids else ''
    if not ru: ru = known.get(n, known.get(key, ''))
    rows.append(dict(en=n, ru=ru, key=key, ids=' '.join(ids[:6]) + (' …' if len(ids) > 6 else ''), speaker=speak[n], mentions=mentions,
                     dlg=cnt['DIALOGUE'] + cnt['DIALOGUESELECTION'], cap=cnt['CAPTION'] + cnt['CUTSCENEPRESET'], quest=cnt['QUEST'] + cnt['QUESTPROGRESS'],
                     memo=cnt['MEMO'] + cnt['PURSUITJOURNALCLUE'], nquests=len(quests), nscenes=len(scenes), lines=nlines, lscenes=nsc, score=score, named=named(n)))
best = {}
for r in sorted(rows, key=lambda r: -r['score']): best.setdefault(r['key'], r)
rows = sorted(best.values(), key=lambda r: -r['score'])

os.makedirs(os.path.join(ROOT, 'npc'), exist_ok=True)
with open(os.path.join(ROOT, 'npc', 'npc-stats.csv'), 'w', encoding='utf-8-sig', newline='') as f:
    w = csv.DictWriter(f, fieldnames=list(rows[0].keys())); w.writeheader(); w.writerows(rows)

tier = lambda r: 'A' if r['score'] >= 250 else 'B' if r['score'] >= 80 else 'C'
NAMED = [r for r in rows if r['named']]; TYPED = [r for r in rows if not r['named']]
def table(f, rs, tiers=True):
    f.write('| # |' + (' Ур. |' if tiers else '') + ' NPC (EN) | Наш перевод | Реплик (сцен) | Подписей в роликах | Упоминаний: диалоги / ролики / квесты / записки | Квестов | Сцен | ID NPC |\n')
    f.write('|---|' + ('---|' if tiers else '') + '---|---|---|---|---|---|---|\n')
    for i, r in enumerate(rs, 1):
        f.write(f"| {i} |" + (f" {tier(r)} |" if tiers else '') + f" {r['en']} | {r['ru']} | {r['lines']} ({r['lscenes']}) | {r['speaker']} | {r['dlg']} / {r['cap']} / {r['quest']} / {r['memo']} | {r['nquests']} | {r['nscenes']} | {r['ids']} |\n")
with open(os.path.join(ROOT, 'npc', 'significant-npcs.md'), 'w', encoding='utf-8', newline='\n') as f:
    f.write('# Значимые NPC — предварительный список\n\n')
    f.write('Собрано по `String.locres` без таблиц диалогов: подписи говорящего в роликах + упоминания имени в диалогах, роликах, квестах, записках и дневнике преследования.\n')
    f.write('Собственные реплики NPC в обычных диалогах здесь **не посчитаны** (в locres нет поля «кто говорит») — список уточнится после выгрузки таблицы диалогов из Cms.\n\n')
    f.write(f'## Персонажи с именами ({len(NAMED)})\n\nУровень: **A** — ключевые для сюжета, **B** — заметные, **C** — второстепенные.\n\n')
    table(f, NAMED)
    f.write(f'\n## Типовые и безымянные говорящие ({len(TYPED)})\n\nСтражники, пираты, голоса, фракции в роли говорящего и т. п. — досье не нужно, но тон и обращение стоит держать едиными.\n\n')
    table(f, TYPED, False)
print('с именами:', len(NAMED), '| A:', sum(tier(r) == 'A' for r in NAMED), 'B:', sum(tier(r) == 'B' for r in NAMED), 'C:', sum(tier(r) == 'C' for r in NAMED), '| типовых:', len(TYPED))
for r in NAMED[:45]: print(tier(r), r['en'], '|', r['ru'], '| реплик', r['lines'], 'сцен', r['lscenes'], '| упом.', r['mentions'])
