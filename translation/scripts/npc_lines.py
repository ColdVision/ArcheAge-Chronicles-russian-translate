"""Реплики и сцены одного NPC — точно, по игровым таблицам Dialogue.csv / Caption.csv (говорящий = speakerNameValue = ID NPC).
  python scripts/npc_lines.py "Lasa" [--ru Ласа] [--ids 1002096,1002573]
Пишет npc/<Name>/lines.md (все сцены с участием NPC: кто говорит, EN и RU) и npc/<Name>/lines.json (ключи реплик NPC для пакетной правки).
ID NPC по умолчанию — все TXT_NPC_<id>_NAME с этим английским именем."""
import argparse, csv, json, os, re, subprocess, sys, collections
sys.stdout.reconfigure(encoding='utf-8')
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CMS = os.path.join(os.path.dirname(ROOT), 'game-data-26495283', 'X5', 'Content', 'Design', 'CMS')
ap = argparse.ArgumentParser(); ap.add_argument('name'); ap.add_argument('--ru', default=''); ap.add_argument('--ids', default='')
a = ap.parse_args()

en = {r[1]: r[3] for r in csv.reader(open(os.path.join(ROOT, 'work', 'en.csv'), encoding='utf-8-sig')) if len(r) > 3}
ruA_csv = os.path.join(ROOT, 'work', 'ruA.csv'); locA = os.path.join(ROOT, 'releases', '0.1.0', 'github', 'String-A.locres')
if not os.path.exists(ruA_csv) or os.path.getmtime(ruA_csv) < os.path.getmtime(locA):
    subprocess.run([os.path.join(os.path.dirname(ROOT), 'X5Tr.Cli', 'bin', 'Release', 'net10.0', 'x5tr.exe'), 'export-csv', locA, ruA_csv], check=True, stdout=subprocess.DEVNULL)
ru = {r[1]: r[3] for r in csv.reader(open(ruA_csv, encoding='utf-8-sig')) if len(r) > 3}
npcname = {re.match(r'TXT_NPC_0*(\d+)_NAME', k).group(1): v for k, v in en.items() if re.match(r'TXT_NPC_\d+_NAME$', k)}
ids = set(x for x in a.ids.split(',') if x) or {i for i, v in npcname.items() if v.strip() == a.name}
if not ids: sys.exit(f'Не нашёл NPC с именем {a.name!r} (укажите --ids).')
model = {r['id']: r['fk_ClothesModelName'] for r in csv.DictReader(open(os.path.join(CMS, 'UnitModel.csv'), encoding='utf-8-sig'))}
npcrow = {r['id']: r for r in csv.DictReader(open(os.path.join(CMS, 'Npc.csv'), encoding='utf-8-sig'))}
bodies = sorted({model.get(npcrow[i]['FK_modelId'], '') for i in ids if i in npcrow} - {''})
factions = sorted({npcrow[i]['faction'] for i in ids if i in npcrow} - {'', 'None'})

def load(fn, prefix):
    lines = collections.defaultdict(list)   # сцена -> [(seq, key, speakerType, speakerId)]
    for r in csv.DictReader(open(os.path.join(CMS, fn), encoding='utf-8-sig')):
        try: sid, seq = int(r['id']), int(r['sequenceOrder'])
        except ValueError: continue
        k = f'TXT_{prefix}_{sid:010d}_{seq:010d}_TEXT'
        lines[f'{prefix[0]}{sid:010d}'].append((seq, k, r['speakerName'], r['speakerNameValue']))
    return lines
scenes = load('Dialogue.csv', 'DIALOGUE'); scenes.update(load('Caption.csv', 'CAPTION'))
sel = collections.defaultdict(list)  # (сцена, seq) -> ответы героя
for k in en:
    m = re.match(r'TXT_DIALOGUESELECTION_(\d{10})_(\d{10})_\d+_TEXT', k)
    if m: sel[('D' + m.group(1), int(m.group(2)))].append(k)

own = []; sc_ids = []
for sc, ls in scenes.items():
    mine = [k for seq, k, t, v in ls if t == 'Npc' and v in ids]
    if mine: own += mine; sc_ids.append(sc)
rx = re.compile(r'(?<![A-Za-z])' + re.escape(a.name) + r'(?![A-Za-z])')
mention_sc = sorted({sc for sc, ls in scenes.items() for seq, k, t, v in ls if rx.search(en.get(k, ''))} - set(sc_ids))
mentions = sorted(k for k in en if rx.search(en[k]) and not re.match(r'TXT_(DIALOGUE|DIALOGUESELECTION|CAPTION)_', k))

def who(t, v):
    if t == 'Npc': return ('**★ ' + a.name + '**') if v in ids else (npcname.get(v, f'NPC {v}') + f' ({v})')
    return {'User': 'герой', 'Doodad': f'объект {v}', 'None': '—'}.get(t, f'{t} {v}')
cell = lambda s: s.replace('|', '\\|').replace('\r', '').replace('\n', '<br>')
out = os.path.join(ROOT, 'npc', re.sub(r'[^\w-]+', '_', a.name)); os.makedirs(out, exist_ok=True)
with open(os.path.join(out, 'lines.md'), 'w', encoding='utf-8', newline='\n') as f:
    f.write(f'# {a.name}' + (f' — {a.ru}' if a.ru else '') + ': реплики и сцены\n\n')
    f.write(f'Модель (раса_пол): {", ".join(bodies) or "?"}; фракция в данных: {", ".join(factions) or "?"}.\n\n')
    f.write(f'ID NPC: {", ".join(sorted(ids))}. Реплик: **{len(own)}** в {len(sc_ids)} сценах (по Dialogue.csv / Caption.csv). '
            f'Ещё {len(mention_sc)} сцен, где NPC упоминают, и {len(mentions)} упоминаний в квестах/записках/именах.\n\n')
    def scene(sc, title):
        f.write(f'## {title} {sc[1:]}\n\n| Ключ | Кто | EN | RU |\n|---|---|---|---|\n')
        for seq, k, t, v in sorted(scenes[sc]):
            f.write(f'| {k[4:]} | {who(t, v)} | {cell(en.get(k, "(нет строки)"))} | {cell(ru.get(k, ""))} |\n')
            for s in sorted(sel.get((sc, seq), [])):
                f.write(f'| {s[4:]} | герой (ответ) | {cell(en[s])} | {cell(ru.get(s, ""))} |\n')
        f.write('\n')
    for sc in sorted(sc_ids): scene(sc, 'Диалог' if sc[0] == 'D' else 'Ролик')
    if mention_sc:
        f.write('# Сцены, где NPC упоминают\n\n')
        for sc in mention_sc: scene(sc, 'Диалог' if sc[0] == 'D' else 'Ролик')
    f.write(f'# Упоминания вне сцен ({len(mentions)})\n\n| Ключ | EN | RU |\n|---|---|---|\n')
    for k in mentions: f.write(f'| {k[4:]} | {cell(en[k][:300])} | {cell(ru.get(k, "")[:300])} |\n')
replies = sorted({s for sc in sc_ids for (scc, seq), ss in sel.items() if scc == sc for s in ss})
json.dump({'name': a.name, 'ids': sorted(ids), 'own': sorted(own), 'player_replies': replies, 'scenes': sorted(sc_ids), 'mention_scenes': mention_sc, 'mentions': mentions},
          open(os.path.join(out, 'lines.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
print(f'{a.name} {sorted(ids)}: реплик {len(own)} в {len(sc_ids)} сценах, ответов героя {len(replies)}, сцен с упоминанием {len(mention_sc)}, прочих упоминаний {len(mentions)} -> {out}')
