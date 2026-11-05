"""glossary/skills.txt -> names.tsv (id sk_*, kind skill) + пачка переводов названий умений (TXT_PERKNODE_*_NAME).
Запуск из корня проекта: python scripts/skills_gen.py [NNN]   (NNN — номер пачки; без него только обновить names.tsv)"""
import json, re, sys
sys.stdout.reconfigure(encoding='utf-8')

def slug(en): return 'sk_' + re.sub(r'[^a-z0-9]+', '_', en.lower()).strip('_')

SK = {}
for l in open('glossary/skills.txt', encoding='utf-8'):
    l = l.rstrip('\n')
    if not l.strip() or l.startswith('#'): continue
    en, ru = [x.strip() for x in l.split(' = ', 1)]
    SK[en] = ru

# статусы и механики со своими падежами (вид skill: в варианте B остаются английскими)
def reg(nom, gen, dat, acc, ins, prep): return [nom, gen, dat, acc, ins, prep]
ST = {
 'burn': ('Burn', reg('Ожог', 'Ожога', 'Ожогу', 'Ожог', 'Ожогом', 'Ожоге')),
 'shock': ('Shock', reg('Шок', 'Шока', 'Шоку', 'Шок', 'Шоком', 'Шоке')),
 'poison': ('Poison', reg('Яд', 'Яда', 'Яду', 'Яд', 'Ядом', 'Яде')),
 'bleed': ('Bleed', reg('Кровотечение', 'Кровотечения', 'Кровотечению', 'Кровотечение', 'Кровотечением', 'Кровотечении')),
 'knockdown': ('Knockdown', reg('Нокдаун', 'Нокдауна', 'Нокдауну', 'Нокдаун', 'Нокдауном', 'Нокдауне')),
 'knockback': ('Knockback', reg('Отбрасывание', 'Отбрасывания', 'Отбрасыванию', 'Отбрасывание', 'Отбрасыванием', 'Отбрасывании')),
 'stun': ('Stun', reg('Оглушение', 'Оглушения', 'Оглушению', 'Оглушение', 'Оглушением', 'Оглушении')),
 'root': ('Root', reg('Обездвиживание', 'Обездвиживания', 'Обездвиживанию', 'Обездвиживание', 'Обездвиживанием', 'Обездвиживании')),
 'foresight': ('Foresight', reg('Предвидение', 'Предвидения', 'Предвидению', 'Предвидение', 'Предвидением', 'Предвидении')),
 'onset': ('Onset', reg('Натиск', 'Натиска', 'Натиску', 'Натиск', 'Натиском', 'Натиске')),
 'resolve': ('Resolve', reg('Решимость', 'Решимости', 'Решимости', 'Решимость', 'Решимостью', 'Решимости')),
 'immortal': ('Immortal', reg('Бессмертие', 'Бессмертия', 'Бессмертию', 'Бессмертие', 'Бессмертием', 'Бессмертии')),
 'stagger_immunity': ('Stagger Immunity', reg('Иммунитет к пошатыванию', 'Иммунитета к пошатыванию', 'Иммунитету к пошатыванию', 'Иммунитет к пошатыванию', 'Иммунитетом к пошатыванию', 'Иммунитете к пошатыванию')),
 'corrosion': ('Corrosion', reg('Коррозия', 'Коррозии', 'Коррозии', 'Коррозию', 'Коррозией', 'Коррозии')),
 'hoarfrost': ('Hoarfrost', reg('Изморозь', 'Изморози', 'Изморози', 'Изморозь', 'Изморозью', 'Изморози')),
 'rime': ('Rime', reg('Иней', 'Инея', 'Инею', 'Иней', 'Инеем', 'Инее')),
 'berserk': ('Berserk', reg('Берсерк', 'Берсерка', 'Берсерку', 'Берсерк', 'Берсерком', 'Берсерке')),
 'composure': ('Composure', reg('Хладнокровие', 'Хладнокровия', 'Хладнокровию', 'Хладнокровие', 'Хладнокровием', 'Хладнокровии')),
 'fervor': ('Fervor', reg('Рвение', 'Рвения', 'Рвению', 'Рвение', 'Рвением', 'Рвении')),
 'exhaust': ('Exhaust', reg('Истощение', 'Истощения', 'Истощению', 'Истощение', 'Истощением', 'Истощении')),
 'energy_core': ('Energy Core', reg('Энергетическое ядро', 'Энергетического ядра', 'Энергетическому ядру', 'Энергетическое ядро', 'Энергетическим ядром', 'Энергетическом ядре')),
 'celestial_barrier': ('Celestial Barrier', reg('Небесный барьер', 'Небесного барьера', 'Небесному барьеру', 'Небесный барьер', 'Небесным барьером', 'Небесном барьере')),
 'celestial_blessing': ('Celestial Blessing', reg('Небесное благословение', 'Небесного благословения', 'Небесному благословению', 'Небесное благословение', 'Небесным благословением', 'Небесном благословении')),
 'guard_break': ('Guard Break', reg('Слом защиты', 'Слома защиты', 'Слому защиты', 'Слом защиты', 'Сломом защиты', 'Сломе защиты')),
 'aggressive_flow': ('Aggressive Flow', reg('Агрессивный поток', 'Агрессивного потока', 'Агрессивному потоку', 'Агрессивный поток', 'Агрессивным потоком', 'Агрессивном потоке')),
 'primed': ('Primed', reg('Готовность', 'Готовности', 'Готовности', 'Готовность', 'Готовностью', 'Готовности')),
 'swift': ('Swift', reg('Проворство', 'Проворства', 'Проворству', 'Проворство', 'Проворством', 'Проворстве')),
 'thunder': ('Thunder', reg('Гром', 'Грома', 'Грому', 'Гром', 'Громом', 'Громе')),
 'pulse': ('Pulse', reg('Импульс', 'Импульса', 'Импульсу', 'Импульс', 'Импульсом', 'Импульсе')),
}

lines = open('glossary/names.tsv', encoding='utf-8').read().split('\n')
idx = {l.split('\t')[0]: n for n, l in enumerate(lines) if l and not l.startswith('#')}
def put(i, kind, en, forms):
    row = '\t'.join([i, kind, en] + forms)
    if i in idx: lines[idx[i]] = row
    else: idx[i] = len(lines); lines.append(row)
for en, ru in SK.items(): put(slug(en), 'skill', en, [ru] * 6)
for k, (en, f) in ST.items(): put('st_' + k, 'skill', en, f)
open('glossary/names.tsv', 'w', encoding='utf-8', newline='').write('\n'.join(lines))
print('умений:', len(SK), 'статусов:', len(ST))

if len(sys.argv) > 1:
    nnn = sys.argv[1]
    src = json.load(open(f'work/b{nnn}_src.json', encoding='utf-8'))
    out = []; miss = set()
    for i, r in enumerate(src):
        en = r['en'].strip()
        if en in SK: out.append(f'{i}|{SK[en]}')
        else: miss.add(en)
    for m in sorted(miss): print('MISS', m)
    if not miss:
        open(f'work/b{nnn}_ru.txt', 'w', encoding='utf-8', newline='\n').write('\n'.join(out) + '\n'); print(len(out))
