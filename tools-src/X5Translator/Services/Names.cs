using System.IO;
using System.Text;
using System.Text.RegularExpressions;

namespace X5Translator.Services;

/// <summary>
/// Глоссарий имён для двух вариантов перевода. В тексте имя записано маркером {{n:id|падеж}}
/// (падежи: nom gen dat acc ins prep); сборщик подставляет русскую форму (вариант A) или английское имя (вариант B).
/// Файл names.tsv: id, kind, en, nom, gen, dat, acc, ins, prep (строки с # пропускаются).
/// </summary>
public sealed class Names
{
    public sealed record Entry(string Id, string Kind, string En, string[] Forms);   // Forms: nom gen dat acc ins prep

    public static readonly string[] Cases = ["nom", "gen", "dat", "acc", "ins", "prep"];
    public static readonly Regex Marker = new(@"\{\{n:([^|{}]+)(?:\|([A-Za-z]+))?\}\}", RegexOptions.Compiled);

    /// <summary>Виды имён, которые в варианте B остаются английскими.</summary>
    public HashSet<string> EnglishKinds = new(StringComparer.OrdinalIgnoreCase) { "loc", "item", "skill", "npc", "faction", "person" };

    public Dictionary<string, Entry> ById = new(StringComparer.OrdinalIgnoreCase);

    public static Names Load(string path)
    {
        var n = new Names();
        if (!File.Exists(path)) return n;
        foreach (var line in File.ReadLines(path, Encoding.UTF8))
        {
            if (line.Length == 0 || line[0] == '#') continue;
            var c = line.Split('\t');
            if (c.Length < 4 || c[0] == "id") continue;
            var forms = new string[6];
            for (int i = 0; i < 6; i++) forms[i] = 3 + i < c.Length && c[3 + i].Length > 0 ? c[3 + i] : c[3];   // нет формы — берём именительный
            n.ById[c[0]] = new Entry(c[0], c[1], c[2], forms);
        }
        return n;
    }

    /// <summary>Подставляет имена. english=true — вариант B (английские названия). Неизвестные id остаются в тексте и попадут в отчёт.</summary>
    public string Resolve(string text, bool english, List<string>? unknown = null)
        => Marker.Replace(text, m =>
        {
            if (!ById.TryGetValue(m.Groups[1].Value, out var e)) { unknown?.Add(m.Value); return m.Value; }
            if (english && EnglishKinds.Contains(e.Kind)) return e.En;
            var cs = m.Groups[2].Success ? m.Groups[2].Value : "nom";
            var ci = Array.IndexOf(Cases, cs.ToLowerInvariant());
            var r = e.Forms[ci < 0 ? 0 : ci];
            return cs.Length > 0 && char.IsUpper(cs[0]) && r.Length > 0 ? char.ToUpperInvariant(r[0]) + r[1..] : r;   // «Nom» — с заглавной
        });

    public static string Strip(string text) => Marker.Replace(text, "§");
}

/// <summary>Правила варианта B: ключи, у которых целиком остаётся английский текст (названия предметов, локаций, умений).</summary>
public sealed class KeepEnglish
{
    readonly List<Regex> _rx = new();
    public static KeepEnglish Load(string path)
    {
        var k = new KeepEnglish();
        if (File.Exists(path))
            foreach (var l in File.ReadLines(path, Encoding.UTF8))
                if (l.Trim() is { Length: > 0 } t && t[0] != '#') k._rx.Add(new Regex(t, RegexOptions.Compiled));
        return k;
    }
    public bool Matches(string key) => _rx.Any(r => r.IsMatch(key));
}
