# Проверки локального релиза без игры (обе версии A и B). Запуск: powershell -ExecutionPolicy Bypass -File scripts\verify_release.ps1 -Version 0.1.0
param([string]$Version = '0.1.0')
$ErrorActionPreference = 'Stop'
$root = Split-Path $PSScriptRoot -Parent
$at = Split-Path $root -Parent
$x = Join-Path $at 'X5Tr.Cli\bin\Release\net10.0\x5tr.exe'
$rel = Join-Path $root "releases\$Version"
$en = Join-Path $at 'game-data\X5\Content\Localization\String\en\String.locres'
$fail = 0
function Check($name, $ok) { if ($ok) { "OK   $name" } else { "FAIL $name"; $script:fail++ } }
$t = Join-Path $env:TEMP "ru-verify-$Version"; Remove-Item $t -Recurse -Force -ErrorAction SilentlyContinue; New-Item -ItemType Directory $t | Out-Null

& $x export-csv $en "$t\en.csv" | Out-Null
$ENR = Import-Csv "$t\en.csv" -Encoding UTF8 -Header ns,key,hash,text
$enHash = @{}; $enText = @{}
foreach ($row in $ENR) { $enHash["$($row.ns)/$($row.key)"] = $row.hash; $enText["$($row.ns)/$($row.key)"] = $row.text }
$data = @{}

foreach ($v in 'A', 'B') {
    "--- версия $v"
    $file = Join-Path $rel "github\String-$v.locres"
    & $x export-csv $file "$t\ru$v.csv" | Out-Null
    Check "$v`: String.locres читается LocRes-ридером" ($LASTEXITCODE -eq 0 -and (Test-Path "$t\ru$v.csv"))
    $RU = Import-Csv "$t\ru$v.csv" -Encoding UTF8 -Header ns,key,hash,text
    $data[$v] = $RU
    Check "$v`: число строк совпадает ($($ENR.Count))" ($ENR.Count -eq $RU.Count)
    $bad = 0; foreach ($row in $RU) { if ($enHash["$($row.ns)/$($row.key)"] -ne $row.hash) { $bad++ } }
    Check "$v`: ключи и SourceHash совпадают с en (расхождений: $bad)" ($bad -eq 0)
    $mk = @($RU | Where-Object { $_.text -match '\{\{' }).Count
    Check "$v`: нет необработанных маркеров {{...}} (найдено: $mk)" ($mk -eq 0)
    $cyr = @($RU | Where-Object { $_.text -match '[Ѐ-ӿ]' }).Count
    Check "$v`: строк с кириллицей: $cyr" ($cyr -gt 35000)
    $m = Get-Content (Join-Path $rel "github\manifest-$v.json") -Raw -Encoding UTF8 | ConvertFrom-Json
    Check "$v`: manifest — buildid 26404487, AppID 3218230, вариант $v" ($m.game_build -eq 26404487 -and $m.steam_app_id -eq 3218230 -and $m.variant -eq $v)
    Check "$v`: manifest sha256 = String-$v.locres" ($m.files[0].sha256 -eq (Get-FileHash $file -Algorithm SHA256).Hash.ToLower())
}

"--- только B"
# строки из списка variantB-keep (названия предметов, зон, умений, статусов, рецептов, имена NPC, групп и т. д.) — английские как в оригинале
$keep = @(Get-Content (Join-Path $root 'glossary\variantB-keep.txt') -Encoding UTF8 | Where-Object { $_ -and -not $_.StartsWith('#') })
$keepRx = [regex]('(' + ($keep -join ')|(') + ')')
$kb = 0; $kn = 0
foreach ($row in $data['B']) { if ($keepRx.IsMatch($row.key)) { $kn++; if ($row.text -ne $enText["$($row.ns)/$($row.key)"]) { $kb++ } } }
Check "B: названия предметов/зон/умений/статусов/NPC/групп английские ($kn строк, отличий: $kb)" ($kn -gt 3000 -and $kb -eq 0)
# русские формы имён из names.tsv (кроме терминов sp/end/con) не встречаются
$forms = [Collections.Generic.HashSet[string]]::new()
foreach ($l in Get-Content (Join-Path $root 'glossary\names.tsv') -Encoding UTF8) {
    if ($l.StartsWith('#')) { continue }; $p = $l.Split("`t"); if ($p.Count -lt 9 -or $p[1] -notin @('npc', 'loc', 'faction', 'item')) { continue }
    foreach ($f in $p[3..8]) { if ($f.Length -ge 4) { [void]$forms.Add($f) } }
}
$frx = [regex]('(?<![\p{L}])(' + (($forms | Sort-Object Length -Descending | ForEach-Object { [regex]::Escape($_) }) -join '|') + ')(?![\p{L}])')
$hits = @{}
foreach ($row in $data['B']) { foreach ($mm in $frx.Matches($row.text)) { $hits[$mm.Value] = 1 + [int]$hits[$mm.Value] } }
$top = ($hits.GetEnumerator() | Sort-Object Value -Descending | Select-Object -First 8 | ForEach-Object { "$($_.Key)×$($_.Value)" }) -join ', '
Check "B: русские формы имён из names.tsv не встречаются (найдено: $($hits.Count) форм$(if ($top) { ': ' + $top }))" ($hits.Count -eq 0)
$aur = @($data['B'] | Where-Object { $_.text -cmatch 'Аврори[яиюе]' }).Count
Check "B: «Аврория» не встречается (строк: $aur), Auroria есть" ($aur -eq 0 -and @($data['B'] | Where-Object { $_.text -match 'Auroria' }).Count -gt 0)
$diff = 0; for ($i = 0; $i -lt $data['A'].Count; $i++) { if ($data['A'][$i].text -ne $data['B'][$i].text) { $diff++ } }
Check "A и B различаются ($diff строк)" ($diff -gt 3000)

"--- контрольные суммы"
$sumOk = $true
foreach ($l in Get-Content (Join-Path $rel 'github\SHA256SUMS.txt')) { $h, $n = $l -split '  ', 2; if ((Get-FileHash (Join-Path $rel "github\$n") -Algorithm SHA256).Hash.ToLower() -ne $h) { $sumOk = $false } }
Check 'SHA256SUMS.txt сходится' $sumOk

"--- установщик (песочница)"
$shaA = (Get-Content (Join-Path $rel 'github\manifest-A.json') -Raw | ConvertFrom-Json).files[0].sha256
$shaB = (Get-Content (Join-Path $rel 'github\manifest-B.json') -Raw | ConvertFrom-Json).files[0].sha256
$game = Join-Path $t 'game'; New-Item -ItemType Directory "$game\X5\Content\Localization\String\en" -Force | Out-Null
Set-Content "$game\ArcheAgeChronicles.exe" 'x'; Copy-Item $en "$game\X5\Content\Localization\String\en\String.locres"
$ini = Join-Path $t 'GameUserSettings.ini'; [IO.File]::WriteAllText($ini, "[/Script/Engine.GameUserSettings]`r`nbUseVSync=False`r`n")
Expand-Archive (Join-Path $rel "ArcheAge-Chronicles-RU-$Version.zip") "$t\pkg"
$tool = Join-Path $t "pkg\tools\ru-tool.ps1"
$target = "$game\X5\Content\Localization\String\ru\String.locres"
$stp = "$game\X5\ru-localization.json"
function Run($a, $v = '') {
    $args2 = @('-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', $tool, '-Action', $a, '-GameRoot', $game, '-SettingsPath', $ini, '-Offline', '-NoPrompt', '-SkipGameCheck')
    if ($v) { $args2 += @('-Variant', $v) }
    & powershell @args2 *> "$t\$a$v.log"; $LASTEXITCODE
}
function Sha($p) { (Get-FileHash $p -Algorithm SHA256).Hash.ToLower() }
function St { Get-Content $stp -Raw | ConvertFrom-Json }
function Files { @(Get-ChildItem $game -Recurse -File | Where-Object { $_.FullName -notmatch '\\en\\|ArcheAgeChronicles.exe' } | ForEach-Object { $_.FullName.Substring($game.Length) }) -join ';' }
New-Item -ItemType Directory (Split-Path $target) -Force | Out-Null; Set-Content $target 'OLD'
Check 'Install (без выбора, -NoPrompt) ставит A' ((Run 'Install') -eq 0 -and (Sha $target) -eq $shaA -and (St).variant -eq 'A')
Check 'Install: чужой файл сохранён в .ru-backup, Culture=ru, прочие настройки целы' ((Test-Path "$target.ru-backup") -and (Get-Content $ini -Raw) -match 'Culture=ru' -and (Get-Content $ini -Raw) -match 'bUseVSync=False')
$before = (St).installed_utc
Check 'Update A: актуальная версия, переустановки нет' ((Run 'Update') -eq 0 -and (St).installed_utc -eq $before -and (Sha $target) -eq $shaA)
$filesA = Files
Check 'Смена на B (Install -Variant B): файл = B, состояние B' ((Run 'Install' 'B') -eq 0 -and (Sha $target) -eq $shaB -and (St).variant -eq 'B')
Check 'Смена версии не оставляет мусора (тот же набор файлов)' ((Files) -eq $filesA)
Check 'Update после смены держит B' ((Run 'Update') -eq 0 -and (Sha $target) -eq $shaB -and (St).variant -eq 'B')
Check 'Install без -Variant при установленной B оставляет B' ((Run 'Install') -eq 0 -and (Sha $target) -eq $shaB)
Set-Content $target 'BROKEN'
Check 'Install повторно чинит повреждённый файл (B)' ((Run 'Install') -eq 0 -and (Sha $target) -eq $shaB)
Check 'Обратно на A' ((Run 'Install' 'A') -eq 0 -and (Sha $target) -eq $shaA -and (St).variant -eq 'A')
Check 'Status: код 0' ((Run 'Status') -eq 0)
Check 'Disable: Culture=en, файл остаётся' ((Run 'Disable') -eq 0 -and (Get-Content $ini -Raw) -match 'Culture=en' -and (Test-Path $target))
Check 'Remove: прежний файл возвращён, бэкап и состояние убраны' ((Run 'Remove') -eq 0 -and (Get-Content $target) -eq 'OLD' -and -not (Test-Path "$target.ru-backup") -and -not (Test-Path $stp))
Check 'en-оригинал не тронут' ((Sha "$game\X5\Content\Localization\String\en\String.locres") -eq (Sha $en))
Remove-Item $target -Force
Check 'Install B на чистую игру' ((Run 'Install' 'B') -eq 0 -and (Sha $target) -eq $shaB)
'{"version":"0.0.1","files":{"X5/Content/Localization/String/ru/String.locres":"00"}}' | Set-Content $stp -Encoding ASCII
Check 'Update со старым состоянием (без variant) обновляет до текущей A' ((Run 'Update') -eq 0 -and (St).version -eq $Version -and (Sha $target) -eq $shaA)
Check 'Remove после чистой установки: файла ru нет' ((Run 'Remove') -eq 0 -and -not (Test-Path $target))

"--- файлы игрока (.cmd) в папке игры с пробелами в пути"
$game2 = Join-Path $t 'Steam Library\ArcheAge Chronicles'; New-Item -ItemType Directory "$game2\X5\Content\Localization\String\en" -Force | Out-Null
Set-Content "$game2\ArcheAgeChronicles.exe" 'x'
$ini2 = Join-Path $t 'Game User Settings.ini'; [IO.File]::WriteAllText($ini2, "[Internationalization]`r`nCulture=en`r`n")
Expand-Archive (Join-Path $rel "ArcheAge-Chronicles-RU-$Version.zip") $game2
$pkg2 = $game2
$target2 = "$game2\X5\Content\Localization\String\ru\String.locres"; $stp2 = "$game2\X5\ru-localization.json"
foreach ($n in 'Enable Full Russian.cmd', 'Enable English names.cmd', 'Update-Russian.cmd', 'Remove-Russian.cmd') { Check "в архиве есть «$n»" (Test-Path (Join-Path $pkg2 $n)) }
Check 'в архиве нет старых Install-Russian*.cmd и Disable-Russian.cmd' (-not (Get-ChildItem $pkg2 -Filter 'Install-Russian*.cmd') -and -not (Test-Path (Join-Path $pkg2 'Disable-Russian.cmd')))
function RunCmd($n) { '' | & cmd.exe /c "`"$(Join-Path $pkg2 $n)`" -SettingsPath `"$ini2`" -Offline -SkipGameCheck" *> "$t\cmd-$($n -replace ' ','_').log"; $LASTEXITCODE }
function St2 { Get-Content $stp2 -Raw | ConvertFrom-Json }
Check '«Enable Full Russian.cmd»: версия A, Culture=ru' ((RunCmd 'Enable Full Russian.cmd') -eq 0 -and (Sha $target2) -eq $shaA -and (St2).variant -eq 'A' -and (Get-Content $ini2 -Raw) -match 'Culture=ru')
$f1 = @(Get-ChildItem "$game2\X5" -Recurse -File).Count
Check '«Enable English names.cmd»: переключение на B' ((RunCmd 'Enable English names.cmd') -eq 0 -and (Sha $target2) -eq $shaB -and (St2).variant -eq 'B')
Check 'после переключения лишних файлов нет' (@(Get-ChildItem "$game2\X5" -Recurse -File).Count -eq $f1)
Check '«Update-Russian.cmd» держит B' ((RunCmd 'Update-Russian.cmd') -eq 0 -and (Sha $target2) -eq $shaB -and (St2).variant -eq 'B')
Check '«Enable Full Russian.cmd»: обратно на A' ((RunCmd 'Enable Full Russian.cmd') -eq 0 -and (Sha $target2) -eq $shaA -and (St2).variant -eq 'A')
Check '«Enable English names.cmd» снова: B, Culture=ru' ((RunCmd 'Enable English names.cmd') -eq 0 -and (Sha $target2) -eq $shaB -and (Get-Content $ini2 -Raw) -match 'Culture=ru')
Check '«Remove-Russian.cmd»: файл ru и состояние удалены, Culture=en' ((RunCmd 'Remove-Russian.cmd') -eq 0 -and -not (Test-Path $target2) -and -not (Test-Path $stp2) -and (Get-Content $ini2 -Raw) -match 'Culture=en')

''
if ($fail) { "ПРОВАЛЕНО проверок: $fail (логи: $t)"; exit 1 } else { 'Все проверки пройдены.' }
