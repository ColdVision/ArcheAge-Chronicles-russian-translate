"""Рабочие пачки перевода.
  python scripts/batch.py out <NNN> <regex> <N>   выгрузить N непереведённых строк по ключу в work/bNNN_src.txt
  python scripts/batch.py in  <NNN>               собрать batches/NNN.json из work/bNNN_ru.txt и применить к проекту
Формат txt: «номер|текст», перенос строки записан как ¶. Служебные строки (пустые, DO NOT TRANSLATE, корейские, тестовые)
не выгружаются, а попадают в work/skipped.tsv — в варианте B и A они остаются оригинальными.
"""
import json, os, re, subprocess, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
X5 = os.path.join(ROOT, '..', 'X5Tr.Cli', 'bin', 'Release', 'net10.0', 'x5tr.exe')
PRJ = os.path.join(ROOT, 'project', 'aa.x5tr')
W = os.path.join(ROOT, 'work')
SKIP = re.compile(r'DO NOT TRANSLATE|^\s*PC\s*:|^\s*[(]\s*(Чит|Cheat)|\bTest\b|^[\s\W\d_]*$')
TECH = re.compile(r'^(\d+ FPS|FPS|DLAA|DLSS|FSR|TSR|XeSS|Xess|XeLL|VRS|HDR|Reflex|Anti-Lag 2|GM|FX|Num .|Num Lock|Backspace|Caps Lock|Delete\*?|End|Enter|Esc|Home|Insert|Page Down|Page Up|Pause|Scroll Lock|Tab|Etc)$|^[A-Za-z0-9]+(_[A-Za-z0-9]+)+$')
HANGUL = re.compile('[가-힣]')


def out(nnn, rx, n):
    tmp = os.path.join(W, f'b{nnn}_todo.json')
    subprocess.run([X5, 'todo', PRJ, tmp, '--max', str(n * 3), '--key', rx], check=True, stdout=subprocess.DEVNULL)
    rows = json.load(open(tmp, encoding='utf-8'))
    keep, skipped = [], []
    for r in rows:
        t = r['en']
        (skipped if SKIP.search(t) or TECH.search(t) or HANGUL.search(t) or not re.search('[A-Za-z]{2}', t) else keep).append(r)
    keep = keep[:n]
    json.dump(keep, open(os.path.join(W, f'b{nnn}_src.json'), 'w', encoding='utf-8'), ensure_ascii=False)
    with open(os.path.join(W, 'skipped.tsv'), 'a', encoding='utf-8') as f:
        for r in skipped:
            f.write(f"{r['ns']}\t{r['key']}\t{r['en'][:60]!r}\n")
    with open(os.path.join(W, f'b{nnn}_src.txt'), 'w', encoding='utf-8') as f:
        for i, r in enumerate(keep):
            f.write(f"{i}|{r['key'].replace('TXT_', '')}|{r['en'].replace(chr(10), '¶')}\n")
    print(len(keep), 'строк,', sum(len(r['en']) for r in keep), 'знаков; пропущено служебных', len(skipped))


def inn(nnn):
    src = json.load(open(os.path.join(W, f'b{nnn}_src.json'), encoding='utf-8'))
    ru = {}
    for l in open(os.path.join(W, f'b{nnn}_ru.txt'), encoding='utf-8'):
        l = l.rstrip(chr(10))
        if '|' in l:
            i, t = l.split('|', 1)
            ru[int(i)] = t.replace('¶', chr(10))
    for i in list(ru):
        if ru[i] == '': del ru[i]; ru[i] = None
    miss = [i for i in range(len(src)) if i not in ru]
    if miss:
        print('нет перевода для', miss[:20], '...' if len(miss) > 20 else ''); sys.exit(1)
    res = [{'ns': s['ns'], 'key': s['key'], 'en': s['en'], 'ru': ru[i]} for i, s in enumerate(src) if ru[i] is not None]
    p = os.path.join(ROOT, 'batches', f'{nnn}.json')
    json.dump(res, open(p, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    r = subprocess.run([X5, 'apply', PRJ, p], capture_output=True, text=True, encoding='utf-8')
    print(r.stdout.strip()[:3000])


if __name__ == '__main__':
    a = sys.argv
    out(a[2], a[3], int(a[4])) if a[1] == 'out' else inn(a[2])
