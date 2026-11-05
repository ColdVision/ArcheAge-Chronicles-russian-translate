using System.IO;
using System.Security.Cryptography;
using System.Text;
using System.Text.Json;
using System.Text.Json.Serialization;

namespace X5Translator.Services;

/// <summary>Сборка релиза перевода: файлы для игры + manifest.json для установщика и автообновления.</summary>
public static class Release
{
    public const string LocresPath = "X5/Content/Localization/String/ru/String.locres";

    public sealed class FileEntry
    {
        [JsonPropertyName("path")] public string Path { get; set; } = "";
        [JsonPropertyName("asset")] public string Asset { get; set; } = "";
        [JsonPropertyName("sha256")] public string Sha256 { get; set; } = "";
        [JsonPropertyName("size")] public long Size { get; set; }
    }

    public sealed class Coverage
    {
        [JsonPropertyName("total")] public int Total { get; set; }
        [JsonPropertyName("translated")] public int Translated { get; set; }
        [JsonPropertyName("stale")] public int Stale { get; set; }
    }

    public sealed class Manifest
    {
        [JsonPropertyName("schema_version")] public int SchemaVersion { get; set; } = 1;
        [JsonPropertyName("version")] public string Version { get; set; } = "";
        [JsonPropertyName("steam_app_id")] public long SteamAppId { get; set; }
        /// <summary>Сборка игры (Steam buildid), из которой взят английский оригинал.</summary>
        [JsonPropertyName("game_build")] public long GameBuild { get; set; }
        [JsonPropertyName("built_utc")] public string BuiltUtc { get; set; } = "";
        [JsonPropertyName("coverage")] public Coverage Coverage { get; set; } = new();
        [JsonPropertyName("notes")] public string? Notes { get; set; }
        [JsonPropertyName("files")] public List<FileEntry> Files { get; set; } = new();
    }

    public static string Sha(byte[] b) => Convert.ToHexString(SHA256.HashData(b)).ToLowerInvariant();

    /// <summary>
    /// Пишет в outDir: assets/ (плоский набор для GitHub Releases: файлы + manifest.json)
    /// и package/ (то же в структуре папок игры — для установки вручную).
    /// </summary>
    public static Manifest Make(Project p, string outDir, string version, long gameBuild, long appId, string? notes = null, bool includeStale = true, string variant = "A", Names? names = null, KeepEnglish? keep = null)
    {
        var problems = new List<string>();
        var locres = p.Build(includeStale, variant, names, keep, problems);
        if (problems.Count > 0) throw new InvalidOperationException("Есть неразрешённые маркеры имён:\n  " + string.Join("\n  ", problems.Take(20)));
        var m = new Manifest
        {
            Version = version, SteamAppId = appId, GameBuild = gameBuild, Notes = notes,
            BuiltUtc = DateTime.UtcNow.ToString("yyyy-MM-dd'T'HH:mm:ss'Z'"),
            Coverage = new Coverage
            {
                Total = p.Items.Count,
                Translated = p.Items.Count(i => i.IsDone && (includeStale || !i.Stale)),
                Stale = p.Items.Count(i => i.Stale),
            },
        };
        m.Files.Add(new FileEntry { Path = LocresPath, Asset = System.IO.Path.GetFileName(LocresPath), Sha256 = Sha(locres), Size = locres.Length });

        var assets = System.IO.Path.Combine(outDir, "assets");
        var package = System.IO.Path.Combine(outDir, "package");
        Directory.CreateDirectory(assets);
        File.WriteAllBytes(System.IO.Path.Combine(assets, m.Files[0].Asset), locres);
        var dst = System.IO.Path.Combine(package, LocresPath.Replace('/', '\\'));
        Directory.CreateDirectory(System.IO.Path.GetDirectoryName(dst)!);
        File.WriteAllBytes(dst, locres);

        var json = JsonSerializer.Serialize(m, new JsonSerializerOptions { WriteIndented = true, Encoder = System.Text.Encodings.Web.JavaScriptEncoder.UnsafeRelaxedJsonEscaping });
        File.WriteAllText(System.IO.Path.Combine(assets, "manifest.json"), json, new UTF8Encoding(false));
        File.WriteAllText(System.IO.Path.Combine(package, "release-manifest.json"), json, new UTF8Encoding(false));
        return m;
    }
}
