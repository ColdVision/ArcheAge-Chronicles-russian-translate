# Русификатор ArcheAge Chronicles — установщик (cmd + PowerShell)

Игроку нужно положить содержимое архива в папку игры и запустить:

- `Enable Full Russian.cmd` — установить и включить версию A (полный перевод).
- `Enable English names.cmd` — установить и включить версию B (английские названия предметов, локаций, умений, имена NPC и фракций).
  Оба файла при наличии интернета сначала проверяют, нет ли версии новее; запуск другого файла переключает версию.
- `Update-Russian.cmd` — только обновление до последней версии с GitHub.
- `Remove-Russian.cmd` — удалить перевод и вернуть прежние файлы.

Что делает `tools/ru-tool.ps1`: находит игру (папка скрипта или Steam), проверяет что игра закрыта, читает манифест
(локальный `release-manifest.json` и последний релиз с GitHub), скачивает только изменившиеся файлы, сверяет SHA256
до записи в игру, ставит `Culture=ru` в `GameUserSettings.ini` (кодировка и переводы строк сохраняются)
и сообщает, если сборка игры (Steam buildid) отличается от той, под которую сделан перевод.

Репозиторий проекта: https://github.com/ColdVision/ArcheAge-Chronicles-russian-translate (прописан в `tools/config.json`).

## Ссылки

- Telegram: https://t.me/ucolda
- ВКонтакте: https://vk.ru/archeagechronicles
- YouTube: https://www.youtube.com/@ycolda

## Формат релиза на GitHub

Собирается локально скриптом `ru-translation/scripts/make_release.py <версия>` в `ru-translation/releases/<версия>/github/`:
`String-A.locres`, `manifest-A.json` (его читает установщик: `releases/latest/download/manifest-A.json`), `manifest.json` (копия для старых установщиков),
архив игрока `ArcheAge-Chronicles-RU-<версия>.zip` и `SHA256SUMS.txt`.
Манифест: `version`, `variant`, `steam_app_id`, `game_build`, `coverage`, `files[{path, asset, sha256, size}]`.
Локально установщик берёт `release-manifest-A.json` и файл из `variants/A/X5/...` (для совместимости — и `release-manifest.json` с файлом по прямому пути).
