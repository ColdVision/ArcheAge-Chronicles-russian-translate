# Проверка конвейера на тестовом оригинале (4 строки, v1 -> v2). Запуск: powershell -File scripts\selftest.ps1
$ErrorActionPreference = 'Stop'
$x = Join-Path $PSScriptRoot '..\..\X5Tr.Cli\bin\Release\net10.0\x5tr.exe'
$t = Join-Path $env:TEMP 'x5tr-selftest'; Remove-Item $t -Recurse -Force -ErrorAction SilentlyContinue; New-Item -ItemType Directory $t | Out-Null
$fail = 0
function Check($name, $cond) { if ($cond) { "OK   $name" } else { "FAIL $name"; $script:fail++ } }
function J($o, $p) { [IO.File]::WriteAllText($p, ($o | ConvertTo-Json -Depth 5), [Text.UTF8Encoding]::new($false)) }

& $x mkbase "$t\en1.locres"; & $x mkbase "$t\en2.locres" v2
& $x new "$t\en1.locres" "$t\p.x5tr" | Out-Null
& $x todo "$t\p.x5tr" "$t\todo.json" | Out-Null
$todo = Get-Content "$t\todo.json" -Raw -Encoding UTF8 | ConvertFrom-Json
Check 'todo: 4 строки' ($todo.Count -eq 4)

# пачка: Greet намеренно без {0} — должно дать предупреждение
$tr = @{ Play='Играть'; Greet='Привет!'; Quest='Принеси волчьих шкур: {0}'; Old='Старый текст' }
foreach ($i in $todo) { $i.ru = $tr[$i.key] }
J $todo "$t\batch.json"
& $x apply "$t\p.x5tr" "$t\batch.json" | Out-Null
Check 'apply: предупреждение о потерянном {0} (код 2)' ($LASTEXITCODE -eq 2)

# исправляем
foreach ($i in $todo) { if ($i.key -eq 'Greet') { $i.ru = 'Привет, {0}!' } }
J $todo "$t\batch.json"
& $x apply "$t\p.x5tr" "$t\batch.json" | Out-Null
Check 'apply: после исправления без предупреждений' ($LASTEXITCODE -eq 0)

& $x release "$t\p.x5tr" "$t\rel1" --version 0.1.0 --build 1 | Out-Null
Check 'release v1: String.locres' (Test-Path "$t\rel1\assets\String.locres")
Check 'release v1: manifest.json' (Test-Path "$t\rel1\assets\manifest.json")

& $x diff "$t\en1.locres" "$t\en2.locres"
& $x rebase "$t\p.x5tr" "$t\en2.locres" "$t\p2.x5tr" | Out-Null
$info = & $x info "$t\p2.x5tr"; $info
Check 'rebase: устарела 1 строка (Quest)' ($info -match 'устарело 1;')
& $x todo "$t\p2.x5tr" "$t\todo2.json" | Out-Null
$todo2 = Get-Content "$t\todo2.json" -Raw -Encoding UTF8 | ConvertFrom-Json
Check 'todo после rebase: Quest + Shop' ($todo2.Count -eq 2)
foreach ($i in $todo2) { $i.ru = if ($i.key -eq 'Shop') { 'Магазин' } else { 'Принеси <b>{0}</b> волчьих шкур' } }
J $todo2 "$t\batch2.json"; & $x apply "$t\p2.x5tr" "$t\batch2.json" | Out-Null
Check 'apply v2 без предупреждений' ($LASTEXITCODE -eq 0)
& $x release "$t\p2.x5tr" "$t\rel2" --version 0.2.0 --build 2 | Out-Null
Check 'release v2: String.locres' (Test-Path "$t\rel2\assets\String.locres")
$m = Get-Content "$t\rel2\assets\manifest.json" -Raw | ConvertFrom-Json
Check 'manifest: переведены все 4 строки v2' ($m.Coverage.Translated -eq 4)
if ($fail) { "ПРОВАЛЕНО: $fail"; exit 1 } else { 'Конвейер в порядке.' }
