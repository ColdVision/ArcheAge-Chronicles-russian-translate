# Загрузка репозитория и релиза на GitHub.
# По умолчанию — только проверка (dry-run): собирает содержимое репозитория во временную папку, проверяет на запрещённые файлы,
# показывает, что будет залито, и НИЧЕГО не отправляет. Реальная отправка — только с -Publish и подтверждением.
#   powershell -ExecutionPolicy Bypass -File scripts\publish_github.ps1 -Version 0.1.0
#   powershell -ExecutionPolicy Bypass -File scripts\publish_github.ps1 -Version 0.1.0 -Publish
param(
    [string]$Version = '',          # пусто = самая новая папка в releases\
    [string]$Repo = 'ColdVision/ArcheAge-Chronicles-russian-translate',
    [switch]$Publish,
    [switch]$Yes,                # пользователь уже подтвердил публикацию в чате: не спрашивать ДА
    [switch]$SkipRepoPush        # только релиз, без пуша содержимого репозитория
)
$ErrorActionPreference = 'Stop'
$tr = Split-Path $PSScriptRoot -Parent          # ru-translation
if (-not $Version) { $Version = (Get-ChildItem (Join-Path $tr 'releases') -Directory | Where-Object { $_.Name -match '^\d+(\.\d+)*$' -and (Test-Path (Join-Path $_.FullName 'github')) } | Sort-Object { [version]$_.Name } | Select-Object -Last 1).Name }
$at = Split-Path $tr -Parent                     # aa-tools
$assetsDir = Join-Path $tr "releases\$Version\github"
$stage = Join-Path $env:TEMP "aa-ru-repo-$Version"

function Find-Exe($name, $extra) {
    $c = Get-Command $name -ErrorAction SilentlyContinue
    if ($c) { return $c.Source }
    foreach ($p in $extra) { if (Test-Path $p) { return $p } }
    return $null
}
$gh = Find-Exe 'gh' @('C:\Program Files\GitHub CLI\gh.exe', "$env:LOCALAPPDATA\Programs\GitHub CLI\gh.exe")
$git = Find-Exe 'git' @('C:\Program Files\Git\cmd\git.exe')

# ---------- 1. содержимое репозитория (белый список) ----------
Remove-Item $stage -Recurse -Force -ErrorAction SilentlyContinue; New-Item -ItemType Directory $stage | Out-Null
function Put($src, $dst, [string[]]$excludeDirs = @('bin', 'obj')) {
    if (-not (Test-Path $src)) { throw "нет $src" }
    $d = Join-Path $stage $dst
    if ((Get-Item $src).PSIsContainer) {
        Get-ChildItem $src -Recurse -File | Where-Object {
            $rel = $_.FullName.Substring($src.Length).TrimStart('\'); -not ($rel.Split('\') | Where-Object { $excludeDirs -contains $_ })
        } | ForEach-Object {
            $rel = $_.FullName.Substring($src.Length).TrimStart('\'); $to = Join-Path $d $rel
            New-Item -ItemType Directory (Split-Path $to) -Force | Out-Null; Copy-Item $_.FullName $to
        }
    } else { New-Item -ItemType Directory (Split-Path $d) -Force | Out-Null; Copy-Item $src $d }
}
Put (Join-Path $tr 'README.md') 'README.md'
Put (Join-Path $at 'ru-installer') 'ru-installer'
Put (Join-Path $tr 'glossary') 'translation\glossary'
Put (Join-Path $tr 'scripts') 'translation\scripts'
Put (Join-Path $tr 'release-docs') 'translation\release-docs'
foreach ($f in 'WORKFLOW.md', 'PLAN.md', 'TODO-review.md') { if (Test-Path (Join-Path $tr $f)) { Put (Join-Path $tr $f) "translation\$f" } }
Put (Join-Path $at 'X5Translator') 'tools-src\X5Translator'
Put (Join-Path $at 'X5Tr.Cli') 'tools-src\X5Tr.Cli'
@'
# файлы игры и всё, что из неё извлечено, в репозиторий не попадает
*.locres
*.pak
*.utoc
*.ucas
*.usmap
*.x5tr
*.exe
*.dll
*.zip
bin/
obj/
game-data/
dump/
work/
batches/
releases/
project/
*aes*
*key-result*
'@ | Set-Content (Join-Path $stage '.gitignore') -Encoding UTF8

# ---------- 2. проверка на запрещённые файлы ----------
$bad = @()
$badExt = '.locres', '.pak', '.utoc', '.ucas', '.usmap', '.x5tr', '.exe', '.dll', '.zip', '.sig', '.bin'
foreach ($f in Get-ChildItem $stage -Recurse -File -Force) {
    $rel = $f.FullName.Substring($stage.Length + 1)
    if ($badExt -contains $f.Extension.ToLower()) { $bad += "$rel — файл игры/бинарник" }
    elseif ($rel -match '(?i)aes|key-result|game-data|dump|String\.locres') { $bad += "$rel — запрещённое имя" }
    elseif ($f.Length -gt 3MB) { $bad += "$rel — слишком большой ($([math]::Round($f.Length/1MB,1)) МБ)" }
    elseif ($f.Length -lt 3MB -and (Select-String -LiteralPath $f.FullName -Pattern '0x[0-9A-Fa-f]{64}\b' -Quiet -ErrorAction SilentlyContinue)) { $bad += "$rel — похоже на AES-ключ" }
}

# ---------- 3. файлы релиза ----------
$assetNames = ('ArcheAge-Chronicles-RU-' + $Version + '.zip'), 'String-A.locres', 'String-B.locres', 'manifest-A.json', 'manifest-B.json', 'manifest.json', 'SHA256SUMS.txt'
$assets = @()
foreach ($n in $assetNames) { $p = Join-Path $assetsDir $n; if (-not (Test-Path $p)) { $bad += "нет файла релиза $n (соберите: python scripts\make_release.py $Version)" } else { $assets += Get-Item $p } }
if (Test-Path (Join-Path $assetsDir 'SHA256SUMS.txt')) {
    foreach ($l in Get-Content (Join-Path $assetsDir 'SHA256SUMS.txt')) { $h, $n = $l -split '  ', 2; if ((Get-FileHash (Join-Path $assetsDir $n) -Algorithm SHA256).Hash.ToLower() -ne $h) { $bad += "контрольная сумма не сходится: $n" } }
}
$notes = Join-Path $tr 'release-docs\RELEASE-NOTES.md'

# ---------- отчёт ----------
$files = Get-ChildItem $stage -Recurse -File -Force
''
"Репозиторий: https://github.com/$Repo"
"Содержимое репозитория (собрано в $stage): $($files.Count) файлов, $([math]::Round(($files | Measure-Object Length -Sum).Sum / 1KB)) КБ"
$files | Group-Object { $_.FullName.Substring($stage.Length + 1).Split('\')[0..1] -join '\' } | Sort-Object Name | ForEach-Object {
    '  {0,-40} {1,4} файлов  {2,8} КБ' -f $_.Name, $_.Count, [math]::Round(($_.Group | Measure-Object Length -Sum).Sum / 1KB)
}
''
"Релиз v$Version (файлы из $assetsDir):"
$assets | ForEach-Object { '  {0,-40} {1,10} КБ' -f $_.Name, [math]::Round($_.Length / 1KB) }
"  итого: $([math]::Round(($assets | Measure-Object Length -Sum).Sum / 1MB, 1)) МБ; описание: $notes"
''
"gh: $(if ($gh) { $gh } else { 'НЕ УСТАНОВЛЕН — установите GitHub CLI (https://cli.github.com, или: winget install --id GitHub.cli) и выполните gh auth login' })"
"git: $(if ($git) { $git } else { 'НЕ УСТАНОВЛЕН' })"
if ($gh) { & $gh auth status 2>&1 | Select-Object -First 4 | ForEach-Object { "  $_" } }
''
if ($bad.Count) { 'НАЙДЕНЫ ПРОБЛЕМЫ (отправка запрещена):'; $bad | ForEach-Object { "  - $_" }; exit 1 }
'Проверка на запрещённые файлы: OK (нет файлов игры, ключей, дампов, оригинального String.locres).'

if (-not $Publish) { ''; 'DRY-RUN: ничего не отправлено. Для реальной отправки запустите с флагом -Publish.'; exit 0 }

# ---------- 4. реальная отправка ----------
if (-not $gh) { throw 'GitHub CLI (gh) не установлен.' }
if (-not $git) { throw 'git не установлен.' }
& $gh auth status *> $null; if ($LASTEXITCODE) { throw 'gh не авторизован: выполните gh auth login.' }
''
"Будет выполнено: $(if (-not $SkipRepoPush) { "пуш содержимого репозитория в $Repo (ветка main), " })создание релиза v$Version и загрузка $($assets.Count) файлов."
if (-not $Yes) { $ans = Read-Host 'Чтобы продолжить, введите ДА'; if ($ans -ne 'ДА') { 'Отменено.'; exit 0 } }

$exists = $true; & $gh repo view $Repo *> $null; if ($LASTEXITCODE) { $exists = $false }
if (-not $exists) {
    $ans2 = Read-Host "Репозиторий $Repo не найден. Создать публичный репозиторий? Введите ДА"
    if ($ans2 -ne 'ДА') { 'Отменено.'; exit 0 }
    & $gh repo create $Repo --public --description 'Неофициальный русский перевод ArcheAge Chronicles'; if ($LASTEXITCODE) { throw 'не удалось создать репозиторий' }
}
if (-not $SkipRepoPush) {
    Push-Location $stage
    try {
        & $git init -b main | Out-Null
        & $git add -A; & $git commit -m "Русский перевод $Version" | Out-Null
        & $git remote add origin "https://github.com/$Repo.git"
        & $git push -u origin main; if ($LASTEXITCODE) { throw 'git push не удался (если в репозитории уже есть история — залейте изменения вручную или запустите с -SkipRepoPush).' }
    } finally { Pop-Location }
}
& $gh release create "v$Version" --repo $Repo --title "Русский перевод $Version (ранняя версия)" --notes-file $notes --latest @($assets | ForEach-Object { $_.FullName })
if ($LASTEXITCODE) { throw 'gh release create не удался' }
"Готово: https://github.com/$Repo/releases/tag/v$Version"
