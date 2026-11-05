using System.IO;
using System.Text;

namespace X5Translator.Services;

public sealed class LocEntry
{
    public uint KeyHash;
    public string Key = "";
    public uint SourceHash;   // хеш исходного текста: движок по нему решает, актуален ли перевод
    public string Text = "";
}

public sealed class LocNamespace
{
    public uint Hash;
    public string Name = "";
    public List<LocEntry> Entries = new();
}

/// <summary>Формат Unreal Engine .locres (версии Compact, Optimized_CRC32, Optimized_CityHash64_UTF16).</summary>
public sealed class LocRes
{
    // FGuid(0x7574140E, 0xFC034A67, 0x9D90154A, 0x1B7F37C3), каждое число little-endian
    static readonly byte[] Magic =
    {
        0x0E, 0x14, 0x74, 0x75, 0x67, 0x4A, 0x03, 0xFC, 0x4A, 0x15, 0x90, 0x9D, 0xC3, 0x37, 0x7F, 0x1B,
    };

    public byte Version = 3;
    public List<LocNamespace> Namespaces = new();

    public int Count => Namespaces.Sum(n => n.Entries.Count);

    public static LocRes Read(byte[] data)
    {
        using var ms = new MemoryStream(data);
        using var r = new BinaryReader(ms, Encoding.UTF8);
        if (data.Length < 17 || !r.ReadBytes(16).AsSpan().SequenceEqual(Magic))
            throw new InvalidDataException("Это не .locres (или очень старый формат без заголовка).");
        var ver = r.ReadByte();
        if (ver > 3) throw new InvalidDataException($"Версия .locres {ver} не поддерживается.");

        var res = new LocRes { Version = ver };
        var strings = Array.Empty<string>();
        if (ver >= 1)
        {
            var offset = r.ReadInt64();
            if (offset != -1)
            {
                var cur = ms.Position;
                ms.Position = offset;
                var n = r.ReadInt32();
                strings = new string[n];
                for (var i = 0; i < n; i++)
                {
                    strings[i] = ReadFString(r);
                    if (ver >= 2) r.ReadInt32(); // число ссылок
                }
                ms.Position = cur;
            }
        }
        if (ver >= 2) r.ReadUInt32(); // общее число записей

        var nsCount = r.ReadUInt32();
        for (var i = 0; i < nsCount; i++)
        {
            var ns = new LocNamespace();
            if (ver >= 2) ns.Hash = r.ReadUInt32();
            ns.Name = ReadFString(r);
            var keyCount = r.ReadUInt32();
            for (var j = 0; j < keyCount; j++)
            {
                var e = new LocEntry();
                if (ver >= 2) e.KeyHash = r.ReadUInt32();
                e.Key = ReadFString(r);
                e.SourceHash = r.ReadUInt32();
                if (ver >= 1)
                {
                    var idx = r.ReadInt32();
                    e.Text = idx >= 0 && idx < strings.Length ? strings[idx] : "";
                }
                else e.Text = ReadFString(r);
                ns.Entries.Add(e);
            }
            res.Namespaces.Add(ns);
        }
        return res;
    }

    public byte[] Write()
    {
        // таблица уникальных строк со счётчиками ссылок
        var index = new Dictionary<string, int>(StringComparer.Ordinal);
        var list = new List<string>();
        var refs = new List<int>();
        int Intern(string s)
        {
            if (!index.TryGetValue(s, out var i)) { i = list.Count; index[s] = i; list.Add(s); refs.Add(0); }
            refs[i]++;
            return i;
        }

        using var ms = new MemoryStream();
        using var w = new BinaryWriter(ms, Encoding.UTF8);
        w.Write(Magic);
        w.Write(Version);
        var offsetPos = ms.Position;
        if (Version >= 1) w.Write(-1L);
        if (Version >= 2) w.Write((uint)Count);

        w.Write((uint)Namespaces.Count);
        foreach (var ns in Namespaces)
        {
            if (Version >= 2) w.Write(ns.Hash);
            WriteFString(w, ns.Name);
            w.Write((uint)ns.Entries.Count);
            foreach (var e in ns.Entries)
            {
                if (Version >= 2) w.Write(e.KeyHash);
                WriteFString(w, e.Key);
                w.Write(e.SourceHash);
                if (Version >= 1) w.Write(Intern(e.Text));
                else WriteFString(w, e.Text);
            }
        }

        if (Version >= 1)
        {
            var arrayPos = ms.Position;
            w.Write(list.Count);
            for (var i = 0; i < list.Count; i++)
            {
                WriteFString(w, list[i]);
                if (Version >= 2) w.Write(refs[i]);
            }
            ms.Position = offsetPos;
            w.Write(arrayPos);
        }
        w.Flush();
        return ms.ToArray();
    }

    static string ReadFString(BinaryReader r)
    {
        var len = r.ReadInt32();
        if (len == 0) return "";
        if (len < 0)
        {
            var n = -len;
            var b = r.ReadBytes(n * 2);
            return Encoding.Unicode.GetString(b, 0, (n - 1) * 2);
        }
        var a = r.ReadBytes(len);
        return Encoding.UTF8.GetString(a, 0, len - 1);
    }

    static void WriteFString(BinaryWriter w, string s)
    {
        if (s.Length == 0) { w.Write(0); return; }
        if (s.All(c => c < 128))
        {
            w.Write(s.Length + 1);
            w.Write(Encoding.ASCII.GetBytes(s));
            w.Write((byte)0);
        }
        else
        {
            w.Write(-(s.Length + 1));
            w.Write(Encoding.Unicode.GetBytes(s));
            w.Write((short)0);
        }
    }
}
