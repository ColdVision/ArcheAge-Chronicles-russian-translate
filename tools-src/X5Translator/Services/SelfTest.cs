using System.IO;
using System.Text;

namespace X5Translator.Services;

/// <summary>Проверка без окна: круговая запись .locres, сборка перевода, CSV, проект, проверка тегов.</summary>
public static class SelfTest
{
    public static string Run()
    {
        var sb = new StringBuilder();
        bool ok = true;
        void Check(string name, bool cond) { sb.AppendLine((cond ? "OK   " : "FAIL ") + name); ok &= cond; }

        foreach (byte ver in new byte[] { 1, 2, 3 })
        {
            var src = new LocRes { Version = ver };
            var ns = new LocNamespace { Hash = 11, Name = "UI" };
            ns.Entries.Add(new LocEntry { KeyHash = 1, Key = "A", SourceHash = 100, Text = "Hello {0}" });
            ns.Entries.Add(new LocEntry { KeyHash = 2, Key = "B", SourceHash = 101, Text = "Hello {0}" });   // та же строка: общий индекс
            ns.Entries.Add(new LocEntry { KeyHash = 3, Key = "C", SourceHash = 102, Text = "Привет, мир" });
            src.Namespaces.Add(ns);
            src.Namespaces.Add(new LocNamespace { Hash = 12, Name = "" });
            var bytes = src.Write();
            var back = LocRes.Read(bytes);
            Check($"v{ver}: круговая запись", back.Count == 3 && back.Namespaces[0].Entries[2].Text == "Привет, мир"
                && back.Namespaces[0].Entries[1].Text == "Hello {0}" && back.Namespaces[0].Entries[0].SourceHash == 100
                && (ver < 2 || back.Namespaces[0].Entries[1].KeyHash == 2));
            Check($"v{ver}: повторная запись идентична", back.Write().AsSpan().SequenceEqual(bytes));
        }

        var proj = Project.FromLocRes(MakeBase());
        Check("проект: 3 записи", proj.Items.Count == 3);
        proj.Items[0].Translation = "Привет, {0}";
        proj.Items[1].Translation = "Привет";                 // потерян {0}
        Check("проверка подстановок: ок", proj.Items[0].Warning == "");
        Check("проверка подстановок: предупреждение", proj.Items[1].Warning != "");

        var built = LocRes.Read(proj.Build());
        Check("сборка: перевод применён", built.Namespaces[0].Entries[0].Text == "Привет, {0}");
        Check("сборка: непереведённое осталось оригиналом", built.Namespaces[0].Entries[2].Text == "Third");
        Check("сборка: хеши сохранены", built.Namespaces[0].Entries[0].SourceHash == 100 && built.Namespaces[0].Entries[0].KeyHash == 1);

        var tmp = Path.Combine(Path.GetTempPath(), "x5tr-selftest");
        Directory.CreateDirectory(tmp);
        var pf = Path.Combine(tmp, "p.x5tr");
        proj.Save(pf);
        var p2 = Project.Load(pf);
        Check("проект: сохранение и загрузка", p2.Items[0].Translation == "Привет, {0}" && p2.Items[2].Translation == "");

        var csv = Path.Combine(tmp, "t.csv");
        proj.Items[2].Translation = "Третий, \"в кавычках\"\nс переносом";
        proj.ExportCsv(csv);
        var p3 = Project.FromLocRes(MakeBase());
        var n = p3.ImportCsv(csv);
        Check("CSV: импорт 3 строк с кавычками и переносом", n == 3 && p3.Items[2].Translation == proj.Items[2].Translation);

        sb.AppendLine(ok ? "ВСЕ ПРОВЕРКИ ПРОЙДЕНЫ" : "ЕСТЬ ОШИБКИ");
        return sb.ToString();
    }

    static byte[] MakeBase()
    {
        var src = new LocRes { Version = 3 };
        var ns = new LocNamespace { Hash = 11, Name = "UI" };
        ns.Entries.Add(new LocEntry { KeyHash = 1, Key = "A", SourceHash = 100, Text = "Hello {0}" });
        ns.Entries.Add(new LocEntry { KeyHash = 2, Key = "B", SourceHash = 101, Text = "Hello {0}" });
        ns.Entries.Add(new LocEntry { KeyHash = 3, Key = "C", SourceHash = 102, Text = "Third" });
        src.Namespaces.Add(ns);
        return src.Write();
    }
}
