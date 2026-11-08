# Публикация на GitHub — только по прямому «да» пользователя

Репозиторий: https://github.com/ColdVision/ArcheAge-Chronicles-russian-translate

## 1. Собрать релиз и проверить (локально, без игры)
```
cd D:\Claude\aa-tools\ru-translation
python scripts\make_release.py 0.1.3
powershell -ExecutionPolicy Bypass -File scripts\verify_release.ps1 -Version 0.1.3
```

## 2. Посмотреть, что будет залито (dry-run, ничего не отправляет)
```
powershell -ExecutionPolicy Bypass -File scripts\publish_github.ps1 -Version 0.1.3
```
Скрипт собирает содержимое репозитория во временную папку `%TEMP%\aa-ru-repo-0.1.3` по белому списку:
- `README.md`;
- `ru-installer/`;
- `translation/glossary`, `translation/scripts`, `translation/release-docs` и md-файлы;
- исходники `tools-src/X5Translator` и `tools-src/X5Tr.Cli` без `bin/obj`.

Затем проверяет, что внутри нет файлов игры (`.locres/.pak/.utoc/.ucas/.usmap/.x5tr`), бинарников, AES-ключей, дампов и `game-data`, сверяет `SHA256SUMS.txt` и печатает список файлов с размерами.

Не входят в репозиторий:
- рабочий проект `aa.x5tr` (в нём оригинальный английский файл игры);
- `batches/`, `work/` (там английские тексты игры);
- `releases/`, `game-data`, ключи, дампы.

## 3. Подготовка (один раз)
- Установить GitHub CLI: https://cli.github.com (или `winget install --id GitHub.cli`).
- Войти: `gh auth login`, проверить: `gh auth status`.

## 4. Реальная отправка
```
powershell -ExecutionPolicy Bypass -File scripts\publish_github.ps1 -Version 0.1.3 -Publish
```
Скрипт повторит все проверки и попросит ввести «ДА». Если репозитория нет, он спросит, создавать ли его. Затем:
1. Пушит содержимое в ветку `main`. Шаг можно пропустить флагом `-SkipRepoPush`, если репозиторий уже заполнен.
2. Создаёт релиз `v0.1.3`, помеченный Latest, с описанием `release-docs/RELEASE-NOTES.md`.
3. Загружает файлы релиза: `ArcheAge-Chronicles-RU-0.1.3.zip`, `String-A.locres`, `String-B.locres`, `manifest-A.json`, `manifest-B.json`, `manifest.json`, `SHA256SUMS.txt`.

Установщик проверяет обновления по `releases/latest/download/manifest-A.json` или `manifest-B.json`, поэтому все файлы должны быть в одном релизе с пометкой Latest.

## 5. Проверка после публикации
`gh release view v0.1.3 --repo ColdVision/ArcheAge-Chronicles-russian-translate`. Затем `Update-Russian.cmd` на тестовой машине должен написать «Последняя версия перевода на сервере: 0.1.3».
