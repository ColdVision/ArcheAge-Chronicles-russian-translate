using System.Diagnostics;
using System.IO;
using System.Text;
using System.Text.RegularExpressions;
using Microsoft.Win32;

namespace X5Translator.Services;

/// <summary>Поиск игры и установка/удаление перевода (String.locres + язык в GameUserSettings.ini).</summary>
public static class GameInstall
{
    public const string SteamAppId = "5280930";
    public const string LocresRel = @"X5\Content\Localization\String\ru\String.locres";
    const string BackupSuffix = ".x5tr-backup";

    static string IniPath => Path.Combine(
        Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData), "X5", "Saved", "Config", "Windows", "GameUserSettings.ini");

    public static bool LooksLikeGame(string dir) =>
        Directory.Exists(dir) && (File.Exists(Path.Combine(dir, "ArcheAgeChronicles.exe")) || Directory.Exists(Path.Combine(dir, "X5")));

    /// <summary>Ищет игру в библиотеках Steam по номеру приложения.</summary>
    public static string? FindGame()
    {
        try
        {
            var steam = Registry.CurrentUser.OpenSubKey(@"Software\Valve\Steam")?.GetValue("SteamPath") as string;
            if (string.IsNullOrEmpty(steam)) return null;
            var libs = new List<string> { steam };
            var vdf = Path.Combine(steam, "steamapps", "libraryfolders.vdf");
            if (File.Exists(vdf))
                foreach (Match m in Regex.Matches(File.ReadAllText(vdf), "\"path\"\\s+\"([^\"]+)\""))
                    libs.Add(m.Groups[1].Value.Replace(@"\\", @"\"));
            foreach (var lib in libs.Distinct(StringComparer.OrdinalIgnoreCase))
            {
                var acf = Path.Combine(lib, "steamapps", $"appmanifest_{SteamAppId}.acf");
                if (!File.Exists(acf)) continue;
                var m = Regex.Match(File.ReadAllText(acf), "\"installdir\"\\s+\"([^\"]+)\"");
                if (!m.Success) continue;
                var dir = Path.Combine(lib, "steamapps", "common", m.Groups[1].Value);
                if (LooksLikeGame(dir)) return dir;
            }
        }
        catch { }
        return null;
    }

    static void EnsureNotRunning()
    {
        var run = Process.GetProcesses().Select(p => p.ProcessName)
            .FirstOrDefault(n => n.Equals("ArcheAgeChronicles", StringComparison.OrdinalIgnoreCase) || n.StartsWith("X5", StringComparison.OrdinalIgnoreCase)
                                 || n.StartsWith("xldr_ArcheageChronicles", StringComparison.OrdinalIgnoreCase));
        if (run != null) throw new InvalidOperationException($"Закройте игру и лаунчер (запущен процесс {run}).");
    }

    public static string Install(string gameDir, byte[] locres)
    {
        if (!LooksLikeGame(gameDir)) throw new DirectoryNotFoundException("В этой папке не найдена игра (нужен ArcheAgeChronicles.exe или папка X5).");
        EnsureNotRunning();
        var target = Path.Combine(gameDir, LocresRel);
        Directory.CreateDirectory(Path.GetDirectoryName(target)!);
        var backup = target + BackupSuffix;
        if (File.Exists(target) && !File.Exists(backup)) File.Copy(target, backup);   // сохраняем чужой перевод один раз
        var tmp = target + ".tmp";
        File.WriteAllBytes(tmp, locres);
        File.Move(tmp, target, true);
        SetCulture("ru");
        return target;
    }

    public static string Uninstall(string gameDir)
    {
        EnsureNotRunning();
        var target = Path.Combine(gameDir, LocresRel);
        var backup = target + BackupSuffix;
        string msg;
        if (File.Exists(backup)) { File.Move(backup, target, true); msg = "Восстановлен прежний файл перевода."; }
        else if (File.Exists(target)) { File.Delete(target); msg = "Файл перевода удалён."; }
        else msg = "Файла перевода в игре не было.";
        SetCulture("en");
        return msg + " Язык игры переключён на английский.";
    }

    public static bool IsInstalled(string gameDir) => File.Exists(Path.Combine(gameDir, LocresRel));

    /// <summary>Пишет Culture=… в [Internationalization] GameUserSettings.ini, сохраняя кодировку и переводы строк.</summary>
    static void SetCulture(string culture)
    {
        var path = IniPath;
        Directory.CreateDirectory(Path.GetDirectoryName(path)!);
        byte[] raw = File.Exists(path) ? File.ReadAllBytes(path) : [];

        Encoding enc; int bom;
        if (raw.Length >= 3 && raw[0] == 0xEF && raw[1] == 0xBB && raw[2] == 0xBF) { enc = new UTF8Encoding(false); bom = 3; }
        else if (raw.Length >= 2 && raw[0] == 0xFF && raw[1] == 0xFE) { enc = new UnicodeEncoding(false, false); bom = 2; }
        else if (raw.Length >= 2 && raw[0] == 0xFE && raw[1] == 0xFF) { enc = new UnicodeEncoding(true, false); bom = 2; }
        else
        {
            if (raw.Contains((byte)0)) throw new InvalidDataException("GameUserSettings.ini в неизвестной кодировке, правка отменена.");
            enc = new UTF8Encoding(false); bom = 0;
        }

        var text = enc.GetString(raw, bom, raw.Length - bom);
        var nl = text.Contains("\r\n") || text.Length == 0 ? "\r\n" : "\n";
        var lines = text.Length == 0 ? new List<string>() : text.Replace("\r\n", "\n").Split('\n').ToList();

        var sec = lines.FindIndex(l => l.Trim().Equals("[Internationalization]", StringComparison.OrdinalIgnoreCase));
        if (sec < 0)
        {
            if (lines.Count > 0 && lines[^1].Length > 0) lines.Add("");
            lines.Add("[Internationalization]");
            lines.Add("Culture=" + culture);
        }
        else
        {
            var end = lines.FindIndex(sec + 1, l => l.TrimStart().StartsWith('['));
            if (end < 0) end = lines.Count;
            var first = true;
            for (var i = sec + 1; i < end; i++)
            {
                if (!lines[i].TrimStart().StartsWith("Culture=", StringComparison.OrdinalIgnoreCase)) continue;
                if (first) { lines[i] = "Culture=" + culture; first = false; }
                else { lines.RemoveAt(i); i--; end--; }
            }
            if (first)
            {
                var at = end;
                while (at > sec + 1 && lines[at - 1].Length == 0) at--;
                lines.Insert(at, "Culture=" + culture);
            }
        }

        var body = enc.GetBytes(string.Join(nl, lines));
        var pre = raw.Take(bom).ToArray();
        var tmp = path + ".x5tr.tmp";
        File.WriteAllBytes(tmp, pre.Concat(body).ToArray());
        File.Move(tmp, path, true);
    }
}
