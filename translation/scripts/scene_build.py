"""Сборка сцен целиком (диалоги, ответы героя, ролики) для редактуры по смыслу.
  python scripts/scene_build.py <regex id сцены, напр. ^D010101> <имя> [--chunk 45000]
    -> work/scenes/<имя>_<n>.txt : сцены по порядку, строки `KEY | кто (пол) | EN | RU`
  Ответы субагента: work/scenes/<имя>_<n>_ru.tsv (KEY<TAB>RU) -> применить:
    DFIX_DIR=work/scenes python scripts/dossier_fix.py apply NNN
  Сцена: D<id> — Dialogue.csv, C<id> — Caption.csv (ролики/подписи)."""
import argparse, collections, csv, json, os, re, sys
sys.stdout.reconfigure(encoding='utf-8')
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CMS = os.path.join(os.path.dirname(ROOT), 'game-data-26495283', 'X5', 'Content', 'Design', 'CMS')
OUT = os.path.join(ROOT, 'work', 'scenes')
ap = argparse.ArgumentParser(); ap.add_argument('rx'); ap.add_argument('name'); ap.add_argument('--chunk', type=int, default=45000)
a = ap.parse_args()

en = {}
with open(os.path.join(ROOT, 'work', 'en-26495283.csv'), encoding='utf-8-sig', newline='') as f:
    for r in csv.DictReader(f): en[r['key']] = r['text']
ru = {k: t for ns, k, t in json.load(open(os.path.join(ROOT, 'project', 'aa.x5tr'), encoding='utf-8'))['Tr']}
model = {r['id']: r['fk_ClothesModelName'] for r in csv.DictReader(open(os.path.join(CMS, 'UnitModel.csv'), encoding='utf-8-sig'))}
npcm = {r['id']: model.get(r['FK_modelId'], '') for r in csv.DictReader(open(os.path.join(CMS, 'Npc.csv'), encoding='utf-8-sig'))}
OVR = {'Nisol': 'Ж', 'Krokk': 'М'}  # пол по сюжету (в EN), модель в данных другая
def gender(m): return 'Ж' if re.search(r'_F\b|Female', m) else 'М' if re.search(r'_M\b|Male', m) else '?'
def npcname(v):
    k = f'TXT_NPC_{int(v):010d}_NAME' if v.isdigit() else ''
    return en.get(k, f'NPC {v}').strip(), ru.get(k, '').strip()

scenes = collections.defaultdict(list)
for fn, pre in (('Dialogue.csv', 'DIALOGUE'), ('Caption.csv', 'CAPTION')):
    for r in csv.DictReader(open(os.path.join(CMS, fn), encoding='utf-8-sig')):
        try: sid, seq = int(r['id']), int(r['sequenceOrder'])
        except ValueError: continue
        scenes[f'{pre[0]}{sid:010d}'].append((seq, f'TXT_{pre}_{sid:010d}_{seq:010d}_TEXT', r['speakerName'], r['speakerNameValue']))
# Подписи катсцен: CutScenePreset.csv в данных пустой, поэтому группируем по первым 8 цифрам id (подряд идущие реплики одного ролика)
for k in en:
    m = re.match(r'TXT_CUTSCENEPRESET_(\d{10})_CAPTIONTEXT$', k)
    if m: scenes['P' + m.group(1)[:8]].append((int(m.group(1)), k, 'None', ''))
sel = collections.defaultdict(list)
for k in en:
    m = re.match(r'TXT_DIALOGUESELECTION_(\d{10})_(\d{10})_\d+_TEXT', k)
    if m: sel[('D' + m.group(1), int(m.group(2)))].append(k)

def who(t, v):
    if t == 'Npc':
        e, r = npcname(v)
        return f'{e}' + (f' / {r}' if r else '') + f' ({OVR.get(e) or gender(npcm.get(v, ""))})'
    return {'User': 'ГЕРОЙ', 'None': '—'}.get(t, f'{t} {v}')
cl = lambda s: s.replace('\r', '').replace('\n', '\\n')
rx = re.compile(a.rx)
os.makedirs(OUT, exist_ok=True)
blocks = []
for sc in sorted(scenes):
    if not rx.search(sc): continue
    rows = []
    for seq, k, t, v in sorted(scenes[sc]):
        if k not in en or not ru.get(k): continue
        rows.append(f'{k} | {who(t, v)} | {cl(en[k])} | {cl(ru[k])}')
        for s in sorted(sel.get((sc, seq), [])):
            if ru.get(s): rows.append(f'{s} | ГЕРОЙ (вариант ответа) | {cl(en[s])} | {cl(ru[s])}')
    if rows: blocks.append(f'### {dict(D="Диалог", C="Ролик/подпись", P="Катсцена (говорящий не указан)")[sc[0]]} {sc}\n' + '\n'.join(rows) + '\n')
chunks, cur = [], ''
for b in blocks:
    if cur and len(cur) + len(b) > a.chunk: chunks.append(cur); cur = ''
    cur += b + '\n'
if cur: chunks.append(cur)
for i, c in enumerate(chunks, 1):
    open(os.path.join(OUT, f'{a.name}_{i}.txt'), 'w', encoding='utf-8').write(c)
print(f'сцен: {len(blocks)}, строк: {sum(b.count(chr(10)) - 1 for b in blocks)}, файлов: {len(chunks)} -> {OUT}')
