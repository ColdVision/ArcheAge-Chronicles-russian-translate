using System.ComponentModel;
using System.IO;
using System.Text;
using System.Text.Json;
using System.Text.RegularExpressions;

namespace X5Translator.Services;

public sealed class Item : INotifyPropertyChanged
{
    public string Namespace { get; init; } = "";
    public string Key { get; init; } = "";
    public string Original { get; init; } = "";
    public uint KeyHash { get; init; }
    public uint NsHash { get; init; }
    public uint SourceHash { get; init; }

    string _tr = "";
    public string Translation
    {
        get => _tr;
        set
        {
            if (_tr == value) return;
            _tr = value;
            _cmp = Checks.Compare(Original, value);
            Stale = false;   // правка перевода снимает пометку «оригинал изменился»
            Raise(nameof(Translation)); Raise(nameof(Warning)); Raise(nameof(HasWarning)); Raise(nameof(WarnMark)); Raise(nameof(IsDone)); Raise(nameof(Stale));
        }
    }
    string _cmp = "";

    /// <summary>Оригинал изменился после обновления игры, а перевод остался от прошлой версии.</summary>
    public bool Stale { get; private set; }
    public void MarkStale()
    {
        if (Stale || !IsDone) return;
        Stale = true;
        Raise(nameof(Stale)); Raise(nameof(Warning)); Raise(nameof(HasWarning)); Raise(nameof(WarnMark));
    }

    public string Warning => Stale ? "Оригинал изменился в новой версии игры — проверьте перевод" : _cmp;
    public bool HasWarning => Warning.Length > 0;
    public string WarnMark => HasWarning ? "⚠" : "";
    public bool IsDone => !string.IsNullOrWhiteSpace(_tr);

    public event PropertyChangedEventHandler? PropertyChanged;
    void Raise(string n) => PropertyChanged?.Invoke(this, new PropertyChangedEventArgs(n));
}

public static class Checks
{
    static readonly Regex Tokens = new(@"\{[^{}]*\}|<[^<>]*>|%[sdif]|\\n|\r?\n", RegexOptions.Compiled);

    /// <summary>Сверяет служебные элементы (подстановки {0}, теги, %s, переносы) в оригинале и переводе.</summary>
    public static List<string> TokensOf(string s) => Tokens.Matches(s).Select(m => m.Value.Replace("\r\n", "\n")).OrderBy(x => x, StringComparer.Ordinal).ToList();

    public static string Compare(string original, string translation)
    {
        if (string.IsNullOrWhiteSpace(translation)) return "";
        var a = TokensOf(original);
        var b = TokensOf(Names.Marker.Replace(translation, "§"));
        return a.SequenceEqual(b) ? "" : "Не совпадают служебные элементы: " + string.Join(" ", a);
    }
}

/// <summary>Проект: основа (.locres оригинала) + переводы. Хранится одним JSON-файлом.</summary>
public sealed class Project
{
    public byte[] BaseBytes = [];
    public LocRes Base = new();
    public List<Item> Items = new();

    class Saved
    {
        public string Base { get; set; } = "";
        public List<string[]> Tr { get; set; } = new();   // [namespace, key, перевод]
        public List<string[]> Stale { get; set; } = new(); // [namespace, key] — перевод от прошлой версии оригинала
    }

    public static Project FromLocRes(byte[] bytes)
    {
        var p = new Project { BaseBytes = bytes, Base = LocRes.Read(bytes) };
        foreach (var ns in p.Base.Namespaces)
            foreach (var e in ns.Entries)
                p.Items.Add(new Item { Namespace = ns.Name, Key = e.Key, Original = e.Text, KeyHash = e.KeyHash, NsHash = ns.Hash, SourceHash = e.SourceHash });
        return p;
    }

    /// <summary>Подставляет переводы из готового .locres (по паре namespace+key). Возвращает число подставленных.</summary>
    public int MergeTranslation(LocRes tr, bool overwrite)
    {
        var map = new Dictionary<(string, string), string>();
        foreach (var ns in tr.Namespaces) foreach (var e in ns.Entries) map[(ns.Name, e.Key)] = e.Text;
        var n = 0;
        foreach (var it in Items)
            if (map.TryGetValue((it.Namespace, it.Key), out var t) && !string.IsNullOrWhiteSpace(t) && (overwrite || !it.IsDone) && t != it.Original)
            { it.Translation = t; n++; }
        return n;
    }

    public sealed record RebaseStats(int Kept, int Stale, int New, int Removed)
    {
        public override string ToString() => $"перенесено: {Kept:N0}, из них устарело (оригинал изменился): {Stale:N0}, новых строк: {New:N0}, удалённых из игры: {Removed:N0}";
    }

    /// <summary>
    /// Переносит переводы на новую версию оригинала. Пара namespace+key находит строку,
    /// несовпадение SourceHash помечает перевод как устаревший (в игре он останется, пока его не проверят).
    /// </summary>
    public static Project Rebase(Project old, byte[] newBytes, out RebaseStats stats)
    {
        var p = FromLocRes(newBytes);
        var prev = old.Items.ToDictionary(i => (i.Namespace, i.Key));
        int kept = 0, stale = 0, added = 0;
        foreach (var it in p.Items)
        {
            if (!prev.TryGetValue((it.Namespace, it.Key), out var o)) { added++; continue; }
            if (!o.IsDone) continue;
            it.Translation = o.Translation;
            kept++;
            if (o.SourceHash != it.SourceHash || o.Stale) { it.MarkStale(); stale++; }
        }
        var now = p.Items.Select(i => (i.Namespace, i.Key)).ToHashSet();
        var removed = old.Items.Count(i => i.IsDone && !now.Contains((i.Namespace, i.Key)));
        stats = new RebaseStats(kept, stale, added, removed);
        return p;
    }

    /// <summary>Список для перевода: непереведённые и (по желанию) устаревшие строки. JSON, который удобно отдать на перевод пачкой.</summary>
    public int ExportTodo(string path, int max, bool includeStale = true, string? keyRegex = null)
    {
        var rx = keyRegex is { Length: > 0 } ? new Regex(keyRegex) : null;
        var rows = Items.Where(i => (!i.IsDone || includeStale && i.Stale) && (rx == null || rx.IsMatch(i.Key))).Take(max <= 0 ? int.MaxValue : max)
            .Select(i => new Dictionary<string, string?>
            {
                ["ns"] = i.Namespace, ["key"] = i.Key, ["en"] = i.Original,
                ["ru"] = i.Stale ? i.Translation : null,
                ["tokens"] = string.Join(" ", Checks.TokensOf(i.Original)),
            }).ToList();
        File.WriteAllText(path, JsonSerializer.Serialize(rows, new JsonSerializerOptions { WriteIndented = true, Encoder = System.Text.Encodings.Web.JavaScriptEncoder.UnsafeRelaxedJsonEscaping }), new UTF8Encoding(false));
        return rows.Count;
    }

    /// <summary>Принимает пачку переводов [{ns,key,ru}]. Возвращает (применено, с предупреждениями, не найдено).</summary>
    public (int Applied, int Warned, int Missing) ImportBatch(string path)
    {
        var rows = JsonSerializer.Deserialize<List<Dictionary<string, string?>>>(File.ReadAllText(path)) ?? [];
        var map = Items.ToDictionary(i => (i.Namespace, i.Key));
        int ok = 0, warn = 0, miss = 0;
        foreach (var r in rows)
        {
            r.TryGetValue("ns", out var ns); r.TryGetValue("key", out var key); r.TryGetValue("ru", out var ru);
            if (!map.TryGetValue((ns ?? "", key ?? ""), out var it)) { miss++; continue; }
            if (string.IsNullOrWhiteSpace(ru)) continue;
            it.Translation = ru; ok++;
            if (it.HasWarning) warn++;
        }
        return (ok, warn, miss);
    }

    /// <summary>Собирает .locres: переведённые строки заменяются, остальные остаются оригинальными.
    /// variant "A" — полный перевод; "B" — ключи из keep остаются английскими, имена в маркерах — английские.</summary>
    public byte[] Build(bool includeStale = true, string variant = "A", Names? names = null, KeepEnglish? keep = null, List<string>? problems = null)
    {
        bool b = variant == "B";
        names ??= new Names();
        var map = new Dictionary<(string, string), string>();
        foreach (var i in Items.Where(i => i.IsDone && (includeStale || !i.Stale)))
        {
            if (b && keep != null && keep.Matches(i.Key)) continue;   // остаётся оригинал
            var unknown = new List<string>();
            var t = names.Resolve(i.Translation, b, unknown);
            if (unknown.Count > 0) problems?.Add($"{i.Namespace}/{i.Key}: неизвестное имя {string.Join(" ", unknown)}");
            map[(i.Namespace, i.Key)] = t;
        }
        var copy = LocRes.Read(BaseBytes);
        foreach (var ns in copy.Namespaces)
            foreach (var e in ns.Entries)
                if (map.TryGetValue((ns.Name, e.Key), out var t)) e.Text = t;
        return copy.Write();
    }

    public void Save(string path)
    {
        var s = new Saved { Base = Convert.ToBase64String(BaseBytes) };
        foreach (var i in Items.Where(i => i.IsDone)) s.Tr.Add([i.Namespace, i.Key, i.Translation]);
        foreach (var i in Items.Where(i => i.Stale)) s.Stale.Add([i.Namespace, i.Key]);
        var tmp = path + ".tmp";
        File.WriteAllText(tmp, JsonSerializer.Serialize(s), new UTF8Encoding(false));
        File.Move(tmp, path, true);
    }

    public static Project Load(string path)
    {
        var s = JsonSerializer.Deserialize<Saved>(File.ReadAllText(path)) ?? throw new InvalidDataException("Пустой проект");
        var p = FromLocRes(Convert.FromBase64String(s.Base));
        var map = s.Tr.ToDictionary(t => (t[0], t[1]), t => t[2]);
        foreach (var it in p.Items) if (map.TryGetValue((it.Namespace, it.Key), out var t)) it.Translation = t;
        var stale = s.Stale.Select(t => (t[0], t[1])).ToHashSet();
        foreach (var it in p.Items) if (stale.Contains((it.Namespace, it.Key))) it.MarkStale();
        return p;
    }

    // ---- CSV (UTF-8 с BOM, открывается в Excel) ----

    public void ExportCsv(string path)
    {
        var sb = new StringBuilder();
        sb.Append("namespace,key,original,translation\r\n");
        foreach (var i in Items) sb.Append(Q(i.Namespace)).Append(',').Append(Q(i.Key)).Append(',').Append(Q(i.Original)).Append(',').Append(Q(i.Translation)).Append("\r\n");
        File.WriteAllText(path, sb.ToString(), new UTF8Encoding(true));
    }

    public int ImportCsv(string path)
    {
        var rows = ParseCsv(File.ReadAllText(path, Encoding.UTF8));
        var map = new Dictionary<(string, string), string>();
        foreach (var r in rows.Skip(1)) if (r.Count >= 4) map[(r[0], r[1])] = r[3];
        var n = 0;
        foreach (var it in Items)
            if (map.TryGetValue((it.Namespace, it.Key), out var t) && t != it.Translation) { it.Translation = t; n++; }
        return n;
    }

    static string Q(string s) => "\"" + s.Replace("\"", "\"\"") + "\"";

    static List<List<string>> ParseCsv(string t)
    {
        var rows = new List<List<string>>();
        var row = new List<string>();
        var sb = new StringBuilder();
        var q = false;
        for (var i = 0; i < t.Length; i++)
        {
            var c = t[i];
            if (q)
            {
                if (c == '"') { if (i + 1 < t.Length && t[i + 1] == '"') { sb.Append('"'); i++; } else q = false; }
                else sb.Append(c);
            }
            else if (c == '"') q = true;
            else if (c == ',') { row.Add(sb.ToString()); sb.Clear(); }
            else if (c == '\r') { }
            else if (c == '\n') { row.Add(sb.ToString()); sb.Clear(); rows.Add(row); row = new(); }
            else sb.Append(c);
        }
        if (sb.Length > 0 || row.Count > 0) { row.Add(sb.ToString()); rows.Add(row); }
        return rows;
    }
}
