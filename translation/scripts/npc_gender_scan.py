"""Проверка рода в репликах по говорящему (Dialogue.csv / Caption.csv) и полу модели NPC (Npc.csv -> UnitModel.csv).
  python scripts/npc_gender_scan.py   ->  npc/gender-issues.md, npc/gender-issues.json
Ищет: (1) NPC о себе в чужом роде; (2) обращение к герою с родом («ты сделал/сделала»); (3) герой о себе с родом (ответы героя)."""
import csv, json, os, re, sys, collections
sys.stdout.reconfigure(encoding='utf-8')
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CMS = os.path.join(os.path.dirname(ROOT), 'game-data-26495283', 'X5', 'Content', 'Design', 'CMS')
ru = {k: t for ns, k, t in json.load(open(os.path.join(ROOT, 'project', 'aa.x5tr'), encoding='utf-8'))['Tr']}
en = {r[1]: r[3] for r in csv.reader(open(os.path.join(ROOT, 'work', 'en-26495283.csv'), encoding='utf-8-sig')) if len(r) > 3}
model = {r['id']: r['fk_ClothesModelName'] for r in csv.DictReader(open(os.path.join(CMS, 'UnitModel.csv'), encoding='utf-8-sig'))}
npc = {r['id']: (r['name'], model.get(r['FK_modelId'], '')) for r in csv.DictReader(open(os.path.join(CMS, 'Npc.csv'), encoding='utf-8-sig'))}
def gender(m): return 'F' if re.search(r'_F\b|Female', m) else 'M' if re.search(r'_M\b|Male', m) else ''

speaker = {}
for fn, pre in (('Dialogue.csv', 'DIALOGUE'), ('Caption.csv', 'CAPTION')):
    for r in csv.DictReader(open(os.path.join(CMS, fn), encoding='utf-8-sig')):
        try: k = f"TXT_{pre}_{int(r['id']):010d}_{int(r['sequenceOrder']):010d}_TEXT"
        except ValueError: continue
        speaker[k] = (r['speakerName'], r['speakerNameValue'])

W = r"[А-Яа-яЁё]+"
PAST_M = re.compile(r"(?<![А-Яа-яЁё])(?:[А-Яа-яЁё]+(?:ал|ял|ил|ел|ёл|ыл|ул|шёл|рёк|рос|мог|лёг|нёс|вёз|пёк))(?:ся)?(?![А-Яа-яЁё])")
PAST_F = re.compile(r"(?<![А-Яа-яЁё])[А-Яа-яЁё]+(?:ла)(?:сь)?(?![А-Яа-яЁё])")
ADJ_M = r"(?:рад|готов|должен|уверен|согласен|один|сам|счастлив|благодарен|обязан|виноват|спокоен|занят|прав|способен|намерен|вынужден|знаком|болен|жив|цел|свободен)"
ADJ_F = r"(?:рада|готова|должна|уверена|согласна|одна|сама|счастлива|благодарна|обязана|виновата|спокойна|занята|права|способна|намерена|вынуждена|знакома|больна|жива|цела|свободна)"
NOT_VERB = re.compile(r"^(?:стол|пол|дол|зал|бал|вал|кол|тыл|пыл|мел|ил|ел|бил|был|мил|фил|ангел|котёл|орёл|осёл|посол|пепел|угол|узел|дятел|козёл|сокол|пудел|котел|орел|пепел|нужно|сила|мгла|игла|скала|зола|пила|мала|вела|дела|села|стрела|мула|тела|земля|была)$", re.I)
def me_past(t, fem):  # «я ... сделал» в пределах 3 слов
    out = []
    for m in re.finditer(r"(?<![А-Яа-яЁё])[Яя](?![А-Яа-яЁё])((?:\s+[А-Яа-яЁё,]+){1,3})", t):
        for w in re.findall(W, m.group(1)):
            if NOT_VERB.match(w): continue
            if fem and PAST_M.fullmatch(w) or (not fem and PAST_F.fullmatch(w) and not w.lower().endswith(('ила', 'ала')) is False): out.append(w)
        adj = ADJ_M if fem else ADJ_F
        out += re.findall(r"(?<![А-Яа-яЁё])" + adj + r"(?![А-Яа-яЁё])", m.group(1))
    return out
def you_gender(t):  # обращение к герою с родом: «ты сделал/сделала», «ты готов/готова»
    out = []
    for m in re.finditer(r"(?<![А-Яа-яЁё])[Тт]ы(?![А-Яа-яЁё])((?:\s+[А-Яа-яЁё]+){1,2})", t):
        for w in re.findall(W, m.group(1)):
            if NOT_VERB.match(w): continue
            if PAST_M.fullmatch(w) or PAST_F.fullmatch(w) or re.fullmatch(ADJ_M + '|' + ADJ_F, w, re.I): out.append(w)
    return out

issues = collections.defaultdict(list)
for k, (t, v) in speaker.items():
    if k not in ru: continue
    text = ru[k]
    if t == 'Npc' and v in npc:
        nm, m = npc[v]; g = gender(m)
        if g:
            bad = me_past(text, g == 'F')
            if bad: issues['npc_self'].append((k, nm, v, g, bad, text, en.get(k, '')))
        yb = you_gender(text)
        if yb: issues['to_hero'].append((k, nm, v, g, yb, text, en.get(k, '')))
for k in ru:
    if k.startswith('TXT_DIALOGUESELECTION_'):
        t = ru[k]; bad = me_past(t, True) + me_past(t, False)
        if bad: issues['hero_self'].append((k, 'герой', '', '', sorted(set(bad)), t, en.get(k, '')))

os.makedirs(os.path.join(ROOT, 'npc'), exist_ok=True)
json.dump(issues, open(os.path.join(ROOT, 'npc', 'gender-issues.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
titles = {'npc_self': 'NPC о себе в чужом роде', 'to_hero': 'Обращение к герою с родом (пол героя неизвестен)', 'hero_self': 'Герой о себе с родом (ответы героя)'}
cell = lambda s: s.replace('|', '\\|').replace('\n', '<br>')
with open(os.path.join(ROOT, 'npc', 'gender-issues.md'), 'w', encoding='utf-8', newline='\n') as f:
    f.write('# Проверка рода в репликах\n\nАвтоматическая эвристика: говорящий и его пол — из Dialogue.csv / Caption.csv / Npc.csv / UnitModel.csv; подозрительные слова — прошедшее время и краткие прилагательные рядом с «я»/«ты». Возможны ложные срабатывания.\n\n')
    for c in ('npc_self', 'to_hero', 'hero_self'):
        f.write(f'## {titles[c]} — {len(issues[c])}\n\n| Ключ | Кто | Пол | Слова | RU | EN |\n|---|---|---|---|---|---|\n')
        for k, nm, v, g, bad, t, e in issues[c]: f.write(f'| {k[4:]} | {nm} | {g} | {", ".join(bad)} | {cell(t)} | {cell(e)} |\n')
        f.write('\n')
print({c: len(v) for c, v in issues.items()})
for c in ('npc_self', 'to_hero', 'hero_self'):
    for x in issues[c][:6]: print(c, x[1], x[3], x[4], '|', x[5][:90])
