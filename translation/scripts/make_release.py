"""Локальная сборка релиза (ничего не публикует).
  python scripts/make_release.py 0.1.0 [buildid] [appid]
Результат: releases/<версия>/
  A/, B/                — вывод `x5tr release` (assets/ + package/ с раскладкой X5/Content/Localization/String/ru/String.locres)
  github/               — файлы для GitHub Release: String-A.locres, String-B.locres, manifest-A.json, manifest-B.json, manifest.json (= A),
                          ArcheAge-Chronicles-RU-<v>.zip, SHA256SUMS.txt
  ArcheAge-Chronicles-RU-<v>.zip — архив для игроков (установщик + обе версии)"""
import hashlib, json, os, shutil, subprocess, sys, zipfile
sys.stdout.reconfigure(encoding='utf-8')
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
AT = os.path.dirname(ROOT)
X5 = os.path.join(AT, 'X5Tr.Cli', 'bin', 'Release', 'net10.0', 'x5tr.exe')
INST = os.path.join(AT, 'ru-installer')
ver = sys.argv[1]; build = sys.argv[2] if len(sys.argv) > 2 else '26404487'; app = sys.argv[3] if len(sys.argv) > 3 else '3218230'
out = os.path.join(ROOT, 'releases', ver)
if os.path.exists(out): shutil.rmtree(out)
os.makedirs(out)
sha = lambda p: hashlib.sha256(open(p, 'rb').read()).hexdigest()
REL = 'X5/Content/Localization/String/ru/String.locres'
gh = os.path.join(out, 'github'); os.makedirs(gh)
mans = {}
for v in 'AB':
    d = os.path.join(out, v)
    r = subprocess.run([X5, 'release', os.path.join(ROOT, 'project', 'aa.x5tr'), d, '--version', ver, '--build', build, '--app', app, '--variant', v],
                       capture_output=True, text=True, encoding='utf-8')
    print(v, r.stdout.strip().splitlines()[-1] if r.stdout.strip() else r.stderr[-500:])
    if r.returncode: sys.exit(1)
    m = json.load(open(os.path.join(d, 'assets', 'manifest.json'), encoding='utf-8'))
    m['variant'] = v
    m['files'][0]['asset'] = f'String-{v}.locres'
    shutil.copy(os.path.join(d, 'assets', 'String.locres'), os.path.join(gh, f'String-{v}.locres'))
    assert sha(os.path.join(gh, f'String-{v}.locres')) == m['files'][0]['sha256']
    json.dump(m, open(os.path.join(gh, f'manifest-{v}.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=2)
    mans[v] = m
shutil.copy(os.path.join(gh, 'manifest-A.json'), os.path.join(gh, 'manifest.json'))

# архив для игроков: установщик + обе версии
zname = f'ArcheAge-Chronicles-RU-{ver}.zip'
zp = os.path.join(out, zname)
with zipfile.ZipFile(zp, 'w', zipfile.ZIP_DEFLATED) as z:
    top = ''
    for f in sorted(os.listdir(INST)):
        p = os.path.join(INST, f)
        if os.path.isfile(p) and f != 'README.md': z.write(p, top + f)
    for f in sorted(os.listdir(os.path.join(INST, 'tools'))):
        z.write(os.path.join(INST, 'tools', f), top + 'tools/' + f)
    for v in 'AB':
        z.writestr(top + f'release-manifest-{v}.json', json.dumps(mans[v], ensure_ascii=False, indent=2))
        z.write(os.path.join(out, v, 'package', *REL.split('/')), top + f'variants/{v}/' + REL)
    for f in ('README.md', 'RELEASE-NOTES.md'):
        p = os.path.join(ROOT, 'release-docs', f)
        if os.path.exists(p): z.write(p, top + f)
shutil.copy(zp, os.path.join(gh, zname))
with open(os.path.join(gh, 'SHA256SUMS.txt'), 'w', encoding='utf-8', newline='\n') as f:
    for n in sorted(os.listdir(gh)):
        if n != 'SHA256SUMS.txt': f.write(f'{sha(os.path.join(gh, n))}  {n}\n')
print('готово:', out)
for f in ('TEST-CHECKLIST.md', 'PUBLISH.md'):
    p = os.path.join(ROOT, 'release-docs', f)
    if os.path.exists(p): shutil.copy(p, os.path.join(out, f))
