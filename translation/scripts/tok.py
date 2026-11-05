"""Пачки со служебными тегами: теги заменяются токенами ⟦k1⟧, ⟦p1⟧ …, чтобы их не потерять при переводе.
  python scripts/tok.py view NNN   из work/bNNN_src.json (после batch.py out) -> work/bNNN_view.txt  («индекс|текст с токенами»)
  python scripts/tok.py in NNN     work/bNNN_ru.txt (текст с токенами и [[...]]) -> batches/NNN.json + apply
Токены: ⟦kN⟧ <Icon KeyAction…>, ⟦iN⟧ <Icon id/UIKey…>, ⟦pN⟧ <Ref PerkNode>, ⟦sN⟧ <Ref StatusEffect>, ⟦f⟧…⟦/f⟧ FontStyle, ⟦tN⟧ прочие теги.
Сокращения: [[Название умения]] -> {{n:sk_…|nom}}; [[burn]] / [[burn:acc]] -> st_burn (или stagger, freeze, iron_shell)."""
import json, os, re, subprocess, sys
sys.stdout.reconfigure(encoding='utf-8')
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
W = os.path.join(ROOT, 'work')
X5 = os.path.join(ROOT, '..', 'X5Tr.Cli', 'bin', 'Release', 'net10.0', 'x5tr.exe')
PRJ = os.path.join(ROOT, 'project', 'aa.x5tr')
TAG = re.compile(r"<[^>]+>")

def slug(en): return 'sk_' + re.sub(r'[^a-z0-9]+', '_', en.lower()).strip('_')

def simplify(en, perk_names=None):
    en = en.replace('\r\n', '\n')
    cnt = {}; mp = {}
    def rep(m):
        t = m.group(0)
        if t.startswith('<FontStyle'):
            if "name='Class_Will'" not in t: kind = 't'
            else: return '⟦f⟧'
        elif t == '</FontStyle>': return '⟦/f⟧'
        else:
            kind = 't'
        if re.match(r'<(Icon|icon)\b', t): kind = 'k' if 'KeyAction=' in t else 'i'
        elif t.startswith("<Ref table='PerkNode'"): kind = 'p'
        elif t.startswith("<Ref table='StatusEffect'"): kind = 's'
        cnt[kind] = cnt.get(kind, 0) + 1
        tok = '⟦%s%d⟧' % (kind, cnt[kind])
        mp[tok] = t
        if kind == 'p' and perk_names:
            m2 = re.search(r"id='(\d+)'", t)
            nm = perk_names.get(m2.group(1)) if m2 else None
            if nm: return tok[:-1] + ':' + nm + '⟧'
        if kind == 'k':
            m2 = re.search(r"KeyAction='(\w+)'", t)
            return tok[:-1] + ':' + m2.group(1).replace('WeaponSkill_Slot_', '') + '⟧'
        return tok
    return TAG.sub(rep, en).replace('\n', '¶'), mp


CASES = {'nom': ['им', 'имен', 'именительный', 'и'], 'gen': ['род', 'родит', 'родительный', 'рд', 'р'], 'dat': ['дат', 'дательный', 'д'],
         'acc': ['вин', 'винительный', 'в'], 'ins': ['тв', 'твор', 'творительный', 'т'], 'prep': ['пр', 'предл', 'предложный', 'п']}
CMAP = {v: k for k, vs in CASES.items() for v in vs}
def fix_cases(s):
    return re.sub(r'\{\{n:([a-z0-9_]+)\|([^}]+)\}\}', lambda m: '{{n:%s|%s}}' % (m.group(1), CMAP.get(m.group(2).strip().lower().rstrip('.'), m.group(2).strip())), s)

def expand_names(s):
    def rep(m):
        body = m.group(1)
        case = 'nom'
        if ':' in body and body.rsplit(':', 1)[1] in ('nom', 'gen', 'dat', 'acc', 'ins', 'prep'):
            body, case = body.rsplit(':', 1)
        k = re.sub(r'[^a-z0-9]+', '_', body.lower()).strip('_')
        if body == body.lower():
            ids = [i for i in ('st_' + k, k) if i in KNOWN]
            if not ids: raise SystemExit('нет статуса ' + body)
            return '{{n:%s|%s}}' % (ids[0], case)
        i = slug(body)
        if i not in KNOWN: raise SystemExit('нет умения ' + body)
        return '{{n:%s|%s}}' % (i, case)
    return re.sub(r'\[\[([^\]]+)\]\]', rep, s)

KNOWN = set(l.split('\t')[0] for l in open(os.path.join(ROOT, 'glossary', 'names.tsv'), encoding='utf-8') if l.strip() and not l.startswith('#'))

def perk_names():
    d = {}
    try:
        for r in json.load(open(os.path.join(W, '_all.json'), encoding='utf-8')):
            m = re.match(r'TXT_PERKNODE_0*(\d+)_NAME$', r.get('key', ''))
            if m: d[m.group(1)] = r.get('en', '')
    except Exception: pass
    return d

if __name__ == '__main__':
    cmd, nnn = sys.argv[1], sys.argv[2]
    src = json.load(open(os.path.join(W, f'b{nnn}_src.json'), encoding='utf-8'))
    if cmd == 'view':
        pn = perk_names(); maps = []
        with open(os.path.join(W, f'b{nnn}_view.txt'), 'w', encoding='utf-8') as f:
            seen = {}
            for i, r in enumerate(src):
                t, mp = simplify(r['en'], pn); maps.append(mp)
                f.write(f"{i}|{t}\n")
        json.dump(maps, open(os.path.join(W, f'b{nnn}_map.json'), 'w', encoding='utf-8'), ensure_ascii=False)
        print(len(src), 'строк; названий черт в справочнике:', len(pn))
    elif cmd == 'in':
        maps = json.load(open(os.path.join(W, f'b{nnn}_map.json'), encoding='utf-8'))
        ru = {}
        for l in open(os.path.join(W, f'b{nnn}_ru.txt'), encoding='utf-8'):
            l = l.rstrip('\n')
            if '|' in l:
                i, t = l.split('|', 1); ru[int(i)] = t
        res = []; bad = 0
        for i, r in enumerate(src):
            if i not in ru:
                if os.environ.get('PARTIAL'): continue
                print('нет перевода', i); bad += 1; continue
            t = ru[i]
            if t == '': continue
            t = fix_cases(expand_names(t))
            t = re.sub(r'⟦(k|i|p|s|t)(\d+)(?::[^⟧]*)?⟧', lambda m: maps[i].get('⟦%s%s⟧' % (m.group(1), m.group(2)), 'ОШИБКА'), t)
            t = t.replace('⟦f⟧', "<FontStyle name='Class_Will'>").replace('⟦/f⟧', '</FontStyle>').replace('¶', '\n')
            if 'ОШИБКА' in t or '⟦' in t: print('токен', i, t[:80]); bad += 1; continue
            res.append({'ns': r['ns'], 'key': r['key'], 'en': r['en'], 'ru': t})
        if bad: sys.exit(1)
        p = os.path.join(ROOT, 'batches', f'{nnn}.json')
        json.dump(res, open(p, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
        r = subprocess.run([X5, 'apply', PRJ, p], capture_output=True, text=True, encoding='utf-8')
        print(r.stdout.strip()[:3000])
