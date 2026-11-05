# Что делать

`x5tr` = `D:\Claude\aa-tools\X5Tr.Cli\bin\Release\net10.0\x5tr.exe`
(пересборка: `$env:DOTNET_ROOT='D:\Claude\aa-tools\.dotnet10'; D:\Claude\aa-tools\.dotnet10\dotnet.exe build -c Release` в `X5Tr.Cli`).

## 0. Проверка конвейера
`powershell -File scripts\selftest.ps1` — должно закончиться «Конвейер в порядке».

## 1. Выход игры (первый перевод)
1. Получить английский `X5\Content\Localization\String\en\String.locres` (из полной версии; кладём вне репозитория, например `D:\Claude\aa-tools\orig\1.0\String.locres`).
2. `x5tr new <en.locres> project\aa.x5tr` и `x5tr info project\aa.x5tr`.
3. Сначала собрать глоссарий: просмотреть строки, выписать классы, навыки, фракции, локации в `glossary\glossary.tsv`.
4. Цикл пачками:
   - `x5tr todo project\aa.x5tr batches\NNN.json --max 200`
   - перевести поле `ru` (поле `tokens` показывает подстановки, которые обязаны остаться),
   - `x5tr apply project\aa.x5tr batches\NNN.json` — код 2 = есть предупреждения (подстановки `{0}`, теги `<..>`, `%s`, переносы). Исправить и применить снова.
5. Релиз: `x5tr release project\aa.x5tr releases\V --version V --build <Steam buildid> --app 5280930`
   - в `releases\V\assets\` — `String.locres` + `manifest.json` для GitHub Releases,
   - в `releases\V\package\` — структура папок игры.
6. SourceHash не трогаем: сборщик сохраняет хэши оригинала, иначе движок игнорирует перевод.

## 2. Обновление игры
1. Новый английский `String.locres` + узнать новый Steam buildid.
2. `x5tr diff <old-en.locres> <new-en.locres>` — оценить объём.
3. `x5tr rebase project\aa.x5tr <new-en.locres> project\aa.x5tr.new`, проверить `x5tr info`, заменить файл проекта (старый оставить как `aa.x5tr.bak`).
4. `x5tr todo` (по умолчанию включает устаревшие строки; `--no-stale` — только новые) → перевод → `apply`.
5. Новый релиз с новым `--build`; установщик игроков сверяет buildid и покажет, нужен ли `Update-Russian.cmd`.

## 3. Публикация (только по явной команде пользователя)
Заменить `OWNER/REPO` в `D:\Claude\aa-tools\ru-installer\tools\config.json`, создать репозиторий, залить `ru-translation` и `ru-installer`, приложить `assets\*` к релизу. Ничего не публиковать без разрешения.

## 4. Проверка в игре
Установщик ставит `Culture=ru` в `GameUserSettings.ini`; если строки остаются английскими — проверить, что locres лежит по пути `X5\Content\Localization\String\ru\String.locres` и что buildid совпадает.
