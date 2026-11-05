param(
    [ValidateSet('Install','Update','Disable','Remove','Status')][string]$Action = 'Install',
    [string]$GameRoot = '',
    [string]$ManifestUrl = '',
    [string]$SettingsPath = '',     # для проверок: другой GameUserSettings.ini
    [ValidateSet('','A','B')][string]$Variant = '',   # A — всё на русском, B — названия и имена на английском
    [switch]$Offline,
    [switch]$NoPrompt,
    [switch]$SkipGameCheck          # только для автоматических проверок в песочнице
)
$ErrorActionPreference = 'Stop'
trap { Write-Host ("Ошибка: " + $_.Exception.Message) -ForegroundColor Red; exit 1 }
try { [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12 } catch {}

$PackageRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$Config = [IO.File]::ReadAllText((Join-Path $PSScriptRoot 'config.json')) | ConvertFrom-Json
$StateRel = 'X5\ru-localization.json'

function Say([string]$m) { Write-Host $m }

function Assert-GameClosed {
    if ($SkipGameCheck) { return }
    $run = @(Get-Process -ErrorAction SilentlyContinue | Where-Object {
        $_.ProcessName -eq 'ArcheAgeChronicles' -or $_.ProcessName -like 'X5*' -or $_.ProcessName -like 'xldr_ArcheageChronicles*' })
    if ($run.Count -gt 0) { throw "Закройте игру и лаунчер (запущен процесс $($run[0].ProcessName)) и повторите." }
}

function Test-Game([string]$d) {
    $d -and (Test-Path -LiteralPath $d -PathType Container) -and
    ((Test-Path -LiteralPath (Join-Path $d 'ArcheAgeChronicles.exe')) -or (Test-Path -LiteralPath (Join-Path $d 'X5') -PathType Container))
}

function Find-SteamGame {
    $steam = $null
    try { $steam = (Get-ItemProperty 'HKCU:\Software\Valve\Steam' -ErrorAction Stop).SteamPath } catch {}
    if (-not $steam) { return $null }
    $libs = [Collections.Generic.List[string]]::new(); $libs.Add($steam)
    $vdf = Join-Path $steam 'steamapps\libraryfolders.vdf'
    if (Test-Path $vdf) {
        foreach ($m in [regex]::Matches([IO.File]::ReadAllText($vdf), '"path"\s+"([^"]+)"')) { $libs.Add($m.Groups[1].Value.Replace('\\','\')) }
    }
    foreach ($lib in ($libs | Select-Object -Unique)) {
        foreach ($id in $Config.steam_app_ids) {
            $acf = Join-Path $lib "steamapps\appmanifest_$id.acf"
            if (-not (Test-Path $acf)) { continue }
            $m = [regex]::Match([IO.File]::ReadAllText($acf), '"installdir"\s+"([^"]+)"')
            if (-not $m.Success) { continue }
            $dir = Join-Path $lib "steamapps\common\$($m.Groups[1].Value)"
            if (Test-Game $dir) { return $dir }
        }
    }
    return $null
}

function Get-InstalledBuild([string]$game) {
    # steamapps\common\<папка> -> steamapps\appmanifest_<id>.acf
    $steamapps = Split-Path (Split-Path $game -Parent) -Parent
    foreach ($id in $Config.steam_app_ids) {
        $acf = Join-Path $steamapps "appmanifest_$id.acf"
        if (Test-Path $acf) {
            $m = [regex]::Match([IO.File]::ReadAllText($acf), '"buildid"\s+"(\d+)"')
            if ($m.Success) { return [long]$m.Groups[1].Value }
        }
    }
    return 0
}

function Get-Sha([string]$p) { (Get-FileHash -LiteralPath $p -Algorithm SHA256).Hash.ToLowerInvariant() }

function Compare-Ver([string]$a, [string]$b) {
    $x = 0; $y = 0
    if ([int]::TryParse($a, [ref]$x) -and [int]::TryParse($b, [ref]$y)) { return $x.CompareTo($y) }
    return [string]::Compare($a, $b, $true)
}

function Read-State([string]$game) {
    $p = Join-Path $game $StateRel
    if (Test-Path -LiteralPath $p) { try { return [IO.File]::ReadAllText($p) | ConvertFrom-Json } catch {} }
    return $null
}

function Write-AllBytesAtomic([string]$path, [byte[]]$bytes) {
    $dir = Split-Path $path -Parent
    if (-not (Test-Path -LiteralPath $dir)) { New-Item -ItemType Directory -Force -Path $dir | Out-Null }
    $tmp = "$path.ru-tmp"
    [IO.File]::WriteAllBytes($tmp, $bytes)
    Move-Item -LiteralPath $tmp -Destination $path -Force
}

# --- язык игры: Culture=… в [Internationalization] GameUserSettings.ini, кодировка и переводы строк сохраняются ---
function Get-IniPath {
    if ($SettingsPath) { return $SettingsPath }
    Join-Path $env:LOCALAPPDATA 'X5\Saved\Config\Windows\GameUserSettings.ini'
}

function Set-Culture([string]$Culture) {
    $path = Get-IniPath
    $dir = Split-Path $path -Parent
    if (-not (Test-Path -LiteralPath $dir)) { New-Item -ItemType Directory -Force -Path $dir | Out-Null }
    $raw = if (Test-Path -LiteralPath $path) { [IO.File]::ReadAllBytes($path) } else { [byte[]]@() }
    $bom = 0; $enc = New-Object Text.UTF8Encoding($false)
    if ($raw.Length -ge 3 -and $raw[0] -eq 0xEF -and $raw[1] -eq 0xBB -and $raw[2] -eq 0xBF) { $bom = 3 }
    elseif ($raw.Length -ge 2 -and $raw[0] -eq 0xFF -and $raw[1] -eq 0xFE) { $enc = New-Object Text.UnicodeEncoding($false, $false); $bom = 2 }
    elseif ($raw.Length -ge 2 -and $raw[0] -eq 0xFE -and $raw[1] -eq 0xFF) { $enc = New-Object Text.UnicodeEncoding($true, $false); $bom = 2 }
    elseif ($raw -contains 0) { throw 'GameUserSettings.ini в неизвестной кодировке, правка отменена.' }

    $text = $enc.GetString($raw, $bom, $raw.Length - $bom)
    $nl = if ($text.Length -eq 0 -or $text.Contains("`r`n")) { "`r`n" } else { "`n" }
    $lines = [Collections.Generic.List[string]]::new()
    if ($text.Length -gt 0) { foreach ($l in $text.Replace("`r`n", "`n").Split("`n")) { $lines.Add($l) } }

    $sec = -1
    for ($i = 0; $i -lt $lines.Count; $i++) { if ($lines[$i].Trim() -ieq '[Internationalization]') { $sec = $i; break } }
    if ($sec -lt 0) {
        if ($lines.Count -gt 0 -and $lines[$lines.Count - 1].Length -gt 0) { $lines.Add('') }
        $lines.Add('[Internationalization]'); $lines.Add("Culture=$Culture")
    } else {
        $end = $lines.Count
        for ($i = $sec + 1; $i -lt $lines.Count; $i++) { if ($lines[$i].TrimStart().StartsWith('[')) { $end = $i; break } }
        $first = $true
        for ($i = $sec + 1; $i -lt $end; $i++) {
            if ($lines[$i].TrimStart() -imatch '^Culture=') {
                if ($first) { $lines[$i] = "Culture=$Culture"; $first = $false }
                else { $lines.RemoveAt($i); $i--; $end-- }
            }
        }
        if ($first) {
            $at = $end
            while ($at -gt $sec + 1 -and $lines[$at - 1].Length -eq 0) { $at-- }
            $lines.Insert($at, "Culture=$Culture")
        }
    }
    $body = $enc.GetBytes(($lines -join $nl))
    $out = New-Object byte[] ($bom + $body.Length)
    if ($bom -gt 0) { [Array]::Copy($raw, 0, $out, 0, $bom) }
    [Array]::Copy($body, 0, $out, $bom, $body.Length)
    Write-AllBytesAtomic $path $out
}

# --- манифесты ---
function Get-LocalManifest([string]$v) {
    $names = @("release-manifest-$v.json"); if ($v -eq 'A') { $names += 'release-manifest.json' }
    foreach ($n in $names) {
        $p = Join-Path $PackageRoot $n
        if (Test-Path -LiteralPath $p) { return [IO.File]::ReadAllText($p) | ConvertFrom-Json }
    }
    return $null
}
function Get-LocalSource([string]$v, [string]$rel) {
    $p = Join-Path $PackageRoot "variants\$v\$rel"
    if (Test-Path -LiteralPath $p) { return $p }
    return (Join-Path $PackageRoot $rel)
}
function Select-Variant($st) {
    if ($Variant) { return $Variant }
    if ($st -and $st.variant) { return [string]$st.variant }
    if ($st) { return 'A' }
    if (-not $NoPrompt -and [Environment]::UserInteractive -and $Action -eq 'Install') {
        Say 'Выберите версию перевода:'
        Say '  1 — A: всё на русском (рекомендуется)'
        Say '  2 — B: тексты на русском, а названия предметов, локаций, умений, имена NPC и фракций — на английском'
        $a = Read-Host 'Введите 1 или 2 (Enter — 1)'
        if ($a -eq '2' -or $a -ieq 'B') { return 'B' }
    }
    return 'A'
}
function Name-Variant([string]$v) { if ($v -eq 'B') { 'B (английские названия и имена)' } else { 'A (полностью на русском)' } }

function Get-RemoteManifest([string]$url) {
    $tmp = Join-Path ([IO.Path]::GetTempPath()) ('ru-manifest-' + [guid]::NewGuid().ToString('N') + '.json')
    try {
        Invoke-WebRequest -Uri $url -OutFile $tmp -UseBasicParsing -TimeoutSec 20
        return [IO.File]::ReadAllText($tmp) | ConvertFrom-Json
    } finally { Remove-Item -LiteralPath $tmp -Force -ErrorAction SilentlyContinue }
}

# ================= основная логика =================
$game = $null
foreach ($c in @($GameRoot, (Split-Path $PackageRoot -Parent), $PackageRoot)) { if ($c -and (Test-Game $c)) { $game = (Resolve-Path $c).Path; break } }
if (-not $game) { $game = Find-SteamGame }
if (-not $game) { throw 'Не нашёл папку игры. Положите русификатор в папку игры (рядом с ArcheAgeChronicles.exe) или запустите с параметром -GameRoot "путь".' }

switch ($Action) {
    'Status' {
        $st = Read-State $game
        Say "Папка игры: $game"
        if ($st) { $sv = if ($st.variant) { $st.variant } else { 'A' }; Say "Установлен перевод версии $($st.version), вариант $(Name-Variant $sv)." } else { Say 'Перевод не установлен.' }
        $b = Get-InstalledBuild $game; if ($b) { Say "Сборка игры (Steam buildid): $b" }
        return
    }
    'Disable' {
        Assert-GameClosed
        Set-Culture 'en'
        Say 'Готово. Выбран английский язык; файлы перевода оставлены. Чтобы вернуть русский, запустите «Enable Full Russian.cmd» или «Enable English names.cmd».'
        Say 'Если в параметрах запуска Steam есть -culture=ru, удалите его.'
        return
    }
    'Remove' {
        Assert-GameClosed
        $st = Read-State $game
        if ($st) {
            foreach ($f in $st.files.PSObject.Properties.Name) {
                $t = Join-Path $game ($f.Replace('/', '\'))
                $bk = "$t.ru-backup"
                if (Test-Path -LiteralPath $bk) { Move-Item -LiteralPath $bk -Destination $t -Force }
                elseif (Test-Path -LiteralPath $t) { Remove-Item -LiteralPath $t -Force }
            }
            Remove-Item -LiteralPath (Join-Path $game $StateRel) -Force
        }
        Set-Culture 'en'
        Say 'Перевод удалён из игры, выбран английский язык.'
        return
    }
}

# Install / Update
Assert-GameClosed
$st = Read-State $game
$V = Select-Variant $st
Say "Вариант перевода: $(Name-Variant $V)"
$local = Get-LocalManifest $V
$remote = $null
$online = (-not $Offline) -and ($Action -eq 'Update' -or $true)
$url = $ManifestUrl
if (-not $url -and $Config.repo -and $Config.repo -notmatch 'OWNER') { $url = "https://github.com/$($Config.repo)/releases/latest/download/manifest-$V.json" }
if ($online -and $url) {
    try { $remote = Get-RemoteManifest $url; Say "Последняя версия перевода на сервере: $($remote.version)." }
    catch { Say "Не удалось проверить обновления ($($_.Exception.Message)); использую файлы из папки." }
}

$manifest = $null; $source = ''
if ($local -and $remote) {
    if ((Compare-Ver "$($remote.version)" "$($local.version)") -gt 0) { $manifest = $remote; $source = 'remote' } else { $manifest = $local; $source = 'local' }
} elseif ($remote) { $manifest = $remote; $source = 'remote' }
elseif ($local) { $manifest = $local; $source = 'local' }
if (-not $manifest) { throw 'Нет данных перевода: рядом нет release-manifest.json, а сервер недоступен.' }

$stV = if ($st -and $st.variant) { [string]$st.variant } elseif ($st) { 'A' } else { '' }
if ($Action -eq 'Update' -and $st -and $stV -eq $V -and (Compare-Ver "$($manifest.version)" "$($st.version)") -le 0) {
    Say "Уже установлена актуальная версия перевода ($($st.version))."
    Set-Culture 'ru'
    return
}

$baseUrl = if ($source -eq 'remote') { $url.Substring(0, $url.LastIndexOf('/') + 1) } else { '' }
$newFiles = [ordered]@{}
$staged = @()
try {
    foreach ($f in $manifest.files) {
        if ($f.sha256 -isnot [string] -or $f.sha256 -notmatch '^[0-9a-fA-F]{64}$') { throw 'В манифесте нет корректной контрольной суммы.' }
        $rel = ([string]$f.path).Replace('/', '\')
        if ($rel -match '(^|\\)\.\.(\\|$)' -or [IO.Path]::IsPathRooted($rel)) { throw "Недопустимый путь в манифесте: $($f.path)" }
        $target = Join-Path $game $rel
        $want = ([string]$f.sha256).ToLowerInvariant()
        $newFiles[$f.path] = $want
        if ((Test-Path -LiteralPath $target) -and (Get-Sha $target) -eq $want) { Say "Без изменений: $($f.path)"; continue }

        $tmp = Join-Path ([IO.Path]::GetTempPath()) ('ru-' + [guid]::NewGuid().ToString('N') + '.bin')
        if ($source -eq 'remote') {
            $asset = if ($f.asset) { $f.asset } else { Split-Path $f.path -Leaf }
            Say "Скачиваю $asset ..."
            Invoke-WebRequest -Uri ($baseUrl + [uri]::EscapeDataString($asset)) -OutFile $tmp -UseBasicParsing
        } else {
            $src = Get-LocalSource $V $rel
            if (-not (Test-Path -LiteralPath $src)) { throw "В комплекте нет файла $($f.path). Скопируйте в папку игры всё содержимое архива." }
            Copy-Item -LiteralPath $src -Destination $tmp -Force
        }
        if ((Get-Sha $tmp) -ne $want) { Remove-Item -LiteralPath $tmp -Force; throw "Контрольная сумма не совпала: $($f.path). Файл повреждён или отличается от манифеста." }
        $staged += [pscustomobject]@{ Tmp = $tmp; Target = $target; Path = $f.path }
    }

    # всё проверено — только теперь трогаем игру
    $ours = @(); if ($st) { $ours = @($st.files.PSObject.Properties.Name) }
    foreach ($s in $staged) {
        $dir = Split-Path $s.Target -Parent
        if (-not (Test-Path -LiteralPath $dir)) { New-Item -ItemType Directory -Force -Path $dir | Out-Null }
        $bk = "$($s.Target).ru-backup"
        if ((Test-Path -LiteralPath $s.Target) -and ($ours -notcontains $s.Path) -and -not (Test-Path -LiteralPath $bk)) { Copy-Item -LiteralPath $s.Target -Destination $bk }
        Move-Item -LiteralPath $s.Tmp -Destination ($s.Target + '.ru-tmp') -Force
        Move-Item -LiteralPath ($s.Target + '.ru-tmp') -Destination $s.Target -Force
        Say "Установлено: $($s.Path)"
    }
} finally {
    foreach ($s in $staged) { if (Test-Path -LiteralPath $s.Tmp) { Remove-Item -LiteralPath $s.Tmp -Force -ErrorAction SilentlyContinue } }
}

Set-Culture 'ru'
# файлы прежней установки, которых нет в новой, убираем (смена версии не оставляет мусора)
if ($st) {
    foreach ($f in $st.files.PSObject.Properties.Name) {
        if ($newFiles.Contains($f)) { continue }
        $t = Join-Path $game ($f.Replace('/', '\')); $bk = "$t.ru-backup"
        if (Test-Path -LiteralPath $bk) { Move-Item -LiteralPath $bk -Destination $t -Force } elseif (Test-Path -LiteralPath $t) { Remove-Item -LiteralPath $t -Force }
    }
}
$state = [ordered]@{ version = "$($manifest.version)"; variant = $V; installed_utc = (Get-Date).ToUniversalTime().ToString('s') + 'Z'; files = $newFiles }
Write-AllBytesAtomic (Join-Path $game $StateRel) ([Text.UTF8Encoding]::new($false).GetBytes(($state | ConvertTo-Json -Depth 5)))

Say ''
Say "Готово! Перевод версии $($manifest.version) установлен (вариант $(Name-Variant $V)), язык игры: русский."
if ($manifest.coverage) {
    $pct = if ($manifest.coverage.total) { [math]::Round(100.0 * $manifest.coverage.translated / $manifest.coverage.total, 1) } else { 0 }
    Say "Переведено строк: $($manifest.coverage.translated) из $($manifest.coverage.total) ($pct%)."
}
$have = Get-InstalledBuild $game
if ($manifest.game_build -and $have -and [long]$manifest.game_build -ne $have) {
    Say ''
    Say "Внимание: перевод собран для сборки игры $($manifest.game_build), у вас $have."
    if ([long]$manifest.game_build -gt $have) { Say 'Ваша игра старее, чем та, под которую сделан перевод: обновите игру в Steam. Часть строк пока может отображаться неверно.' }
    else { Say 'Часть строк, изменившихся в игре, может остаться на английском. Время от времени запускайте Update-Russian.cmd — перевод обновится, когда выйдет подходящая версия.' }
}
Say 'Если игра осталась на английском, добавьте в параметры запуска Steam: -culture=ru'
