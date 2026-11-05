using System.Text;
using X5Translator.Services;

Console.OutputEncoding = new UTF8Encoding(false);

const string Usage = """
x5tr — рабочий инструмент перевода (сторона разработчика)

  x5tr new     <en.locres> <project.x5tr>                     создать проект из английского оригинала
  x5tr info    <project.x5tr>                                  статистика проекта
  x5tr diff    <old.locres> <new.locres>                       что изменилось между версиями оригинала
  x5tr rebase  <project.x5tr> <new-en.locres> <out.x5tr>      перенести переводы на новую версию игры
  x5tr todo    <project.x5tr> <out.json> [--max N] [--no-stale] [--key REGEX]   пачка строк для перевода
  x5tr apply   <project.x5tr> <batch.json>                     принять переведённую пачку
  x5tr merge   <project.x5tr> <ru.locres> [--overwrite]        подставить переводы из готового .locres
  x5tr export-csv <file.locres> <out.csv>                       выгрузить любой .locres в CSV (UTF-8 с BOM)
  x5tr release <project.x5tr> <outDir> --version V --build B [--app ID] [--notes TEXT] [--skip-stale] [--variant A|B] [--names f.tsv] [--keep f.txt] [--b-kinds loc,item,skill,npc,faction,person]
""";

try { return Run(args); }
catch (Exception ex) { Console.Error.WriteLine("Ошибка: " + ex.Message); return 1; }

static int Run(string[] a)
{
    if (a.Length == 0) { Console.WriteLine(Usage); return 0; }
    string Opt(string name, string def = "") { var i = Array.IndexOf(a, name); return i >= 0 && i + 1 < a.Length ? a[i + 1] : def; }
    bool Flag(string name) => a.Contains(name);

    switch (a[0])
    {
        case "new":
        {
            var p = Project.FromLocRes(File.ReadAllBytes(a[1]));
            p.Save(a[2]);
            Console.WriteLine($"Создан проект: {p.Items.Count:N0} строк, {p.Base.Namespaces.Count} namespace, формат locres v{p.Base.Version}.");
            return 0;
        }
        case "info":
        {
            var p = Project.Load(a[1]);
            var done = p.Items.Count(i => i.IsDone);
            Console.WriteLine($"Всего {p.Items.Count:N0}; переведено {done:N0} ({(p.Items.Count == 0 ? 0 : 100.0 * done / p.Items.Count):0.#}%); устарело {p.Items.Count(i => i.Stale):N0}; с предупреждениями {p.Items.Count(i => i.HasWarning):N0}.");
            return 0;
        }
        case "diff":
        {
            var o = Flat(LocRes.Read(File.ReadAllBytes(a[1])));
            var n = Flat(LocRes.Read(File.ReadAllBytes(a[2])));
            int add = n.Keys.Count(k => !o.ContainsKey(k)), del = o.Keys.Count(k => !n.ContainsKey(k));
            int chg = n.Count(kv => o.TryGetValue(kv.Key, out var h) && h != kv.Value);
            Console.WriteLine($"Новых: {add:N0}; изменённых: {chg:N0}; удалённых: {del:N0}; без изменений: {n.Count - add - chg:N0}.");
            return 0;
        }
        case "rebase":
        {
            var p = Project.Rebase(Project.Load(a[1]), File.ReadAllBytes(a[2]), out var st);
            p.Save(a[3]);
            Console.WriteLine("Готово — " + st);
            return 0;
        }
        case "todo":
        {
            var p = Project.Load(a[1]);
            var n = p.ExportTodo(a[2], int.TryParse(Opt("--max"), out var m) ? m : 0, !Flag("--no-stale"), Opt("--key"));
            Console.WriteLine($"В {a[2]}: {n:N0} строк.");
            return 0;
        }
        case "apply":
        {
            var p = Project.Load(a[1]);
            var (ok, warn, miss) = p.ImportBatch(a[2]);
            p.Save(a[1]);
            Console.WriteLine($"Применено: {ok:N0}; с предупреждениями: {warn:N0}; не найдено в проекте: {miss:N0}.");
            if (warn > 0)
                foreach (var it in p.Items.Where(i => i.HasWarning).Take(15))
                    Console.WriteLine($"  ! {it.Namespace}/{it.Key}: {it.Warning}");
            return warn > 0 ? 2 : 0;
        }
        case "merge":
        {
            var p = Project.Load(a[1]);
            var n = p.MergeTranslation(LocRes.Read(File.ReadAllBytes(a[2])), Flag("--overwrite"));
            p.Save(a[1]);
            Console.WriteLine($"Подставлено: {n:N0}.");
            return 0;
        }
        case "release":
        {
            var p = Project.Load(a[1]);
            var gdir = Path.Combine(Path.GetDirectoryName(Path.GetFullPath(a[1]))!, "..", "glossary");
            var variant = Opt("--variant", "A").ToUpperInvariant();
            var m = Release.Make(p, a[2], Opt("--version", "1"), long.TryParse(Opt("--build"), out var b) ? b : 0,
                long.TryParse(Opt("--app", "5280930"), out var app) ? app : 5280930, Opt("--notes") is { Length: > 0 } nt ? nt : null, !Flag("--skip-stale"),
                variant, LoadNames(Opt("--names", Path.Combine(gdir, "names.tsv")), Opt("--b-kinds")), KeepEnglish.Load(Opt("--keep", Path.Combine(gdir, "variantB-keep.txt"))));
            Console.WriteLine($"Релиз {m.Version}: переведено {m.Coverage.Translated:N0} из {m.Coverage.Total:N0}, устарело {m.Coverage.Stale:N0}. Файлы: {a[2]}/assets, {a[2]}/package");
            return 0;
        }
        case "export-csv":   // x5tr export-csv <file.locres> <out.csv>
        {
            var r = LocRes.Read(File.ReadAllBytes(a[1]));
            static string Q(string t) => "\"" + t.Replace("\"", "\"\"") + "\"";
            using var w = new StreamWriter(a[2], false, new UTF8Encoding(true));
            w.Write("namespace,key,source_hash,text\r\n");
            foreach (var ns in r.Namespaces) foreach (var e in ns.Entries)
                w.Write($"{Q(ns.Name)},{Q(e.Key)},{e.SourceHash},{Q(e.Text)}\r\n");
            Console.WriteLine($"Записано {r.Count:N0} строк в {a[2]}.");
            return 0;
        }
        case "mkbase":   // тестовый оригинал для проверок конвейера: x5tr mkbase <out.locres> [v2]
        {
            var r = new LocRes { Version = 3 };
            var ns = new LocNamespace { Hash = 7, Name = "UI" };
            var v2 = a.Length > 2 && a[2] == "v2";
            ns.Entries.Add(new LocEntry { KeyHash = 1, Key = "Play", SourceHash = 11, Text = "Play" });
            ns.Entries.Add(new LocEntry { KeyHash = 2, Key = "Greet", SourceHash = 12, Text = "Hello, {0}!" });
            ns.Entries.Add(new LocEntry { KeyHash = 3, Key = "Quest", SourceHash = v2 ? 130u : 13, Text = v2 ? "Bring <b>{0}</b> wolf pelts" : "Bring {0} wolf pelts" });
            if (!v2) ns.Entries.Add(new LocEntry { KeyHash = 4, Key = "Old", SourceHash = 14, Text = "Old text" });
            if (v2) ns.Entries.Add(new LocEntry { KeyHash = 5, Key = "Shop", SourceHash = 15, Text = "Shop" });
            r.Namespaces.Add(ns);
            File.WriteAllBytes(a[1], r.Write());
            return 0;
        }
        default: Console.WriteLine(Usage); return 1;
    }
}

static Names LoadNames(string path, string kinds)
{
    var n = Names.Load(path);
    if (kinds.Length > 0) n.EnglishKinds = new HashSet<string>(kinds.Split(','), StringComparer.OrdinalIgnoreCase);
    return n;
}

static Dictionary<(string, string), uint> Flat(LocRes r)
{
    var d = new Dictionary<(string, string), uint>();
    foreach (var ns in r.Namespaces) foreach (var e in ns.Entries) d[(ns.Name, e.Key)] = e.SourceHash;
    return d;
}
