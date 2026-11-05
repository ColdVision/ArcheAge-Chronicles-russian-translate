using System.ComponentModel;
using System.IO;
using System.Text.Json;
using System.Windows;
using System.Windows.Controls;
using System.Windows.Data;
using System.Windows.Threading;
using Microsoft.Win32;
using X5Translator.Services;

namespace X5Translator;

public partial class MainWindow : Window
{
    Project? _proj;
    string? _projPath;
    bool _dirty;
    ICollectionView? _view;
    readonly DispatcherTimer _autosave = new() { Interval = TimeSpan.FromSeconds(30) };
    readonly DispatcherTimer _filterTimer = new() { Interval = TimeSpan.FromMilliseconds(250) };

    static string SettingsFile => Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.ApplicationData), "X5Translator", "settings.json");

    public MainWindow()
    {
        InitializeComponent();
        GameDirBox.Text = LoadGameDir() ?? GameInstall.FindGame() ?? "";
        _autosave.Tick += (_, _) => SaveIfDirty();
        _autosave.Start();
        _filterTimer.Tick += (_, _) => { _filterTimer.Stop(); _view?.Refresh(); UpdateCount(); };
        Closing += MainWindow_Closing;
    }

    // ---------- настройки ----------

    static string? LoadGameDir()
    {
        try { return JsonSerializer.Deserialize<Dictionary<string, string>>(File.ReadAllText(SettingsFile))?.GetValueOrDefault("gameDir"); }
        catch { return null; }
    }

    void SaveGameDir()
    {
        try
        {
            Directory.CreateDirectory(Path.GetDirectoryName(SettingsFile)!);
            File.WriteAllText(SettingsFile, JsonSerializer.Serialize(new Dictionary<string, string> { ["gameDir"] = GameDirBox.Text }));
        }
        catch { }
    }

    // ---------- открытие и сохранение ----------

    void SetProject(Project p, string? path)
    {
        _proj = p; _projPath = path; _dirty = false;
        _view = CollectionViewSource.GetDefaultView(p.Items);
        _view.Filter = FilterItem;
        Grid.ItemsSource = _view;
        foreach (var b in new[] { BtnMerge, BtnSave, BtnImportCsv, BtnExportCsv, BtnBuild, BtnInstall }) b.IsEnabled = true;
        Title = "X5 Translator — " + (path != null ? Path.GetFileName(path) : "новый проект");
        UpdateCount();
    }

    void BtnOpenBase_Click(object sender, RoutedEventArgs e)
    {
        var dlg = new OpenFileDialog { Filter = "Localization (*.locres)|*.locres|все файлы|*.*", Title = "Оригинальный String.locres (английский)" };
        if (dlg.ShowDialog(this) != true) return;
        if (!ConfirmDiscard()) return;
        try
        {
            var p = Project.FromLocRes(File.ReadAllBytes(dlg.FileName));
            SetProject(p, null);
            Status($"Загружено {p.Items.Count:N0} записей из {Path.GetFileName(dlg.FileName)}. Сохраните проект, чтобы не потерять работу.");
        }
        catch (Exception ex) { Error(ex); }
    }

    void BtnMerge_Click(object sender, RoutedEventArgs e)
    {
        var dlg = new OpenFileDialog { Filter = "Localization (*.locres)|*.locres", Title = "Готовый перевод (.locres)" };
        if (_proj == null || dlg.ShowDialog(this) != true) return;
        try
        {
            var overwrite = MessageBox.Show(this, "Заменять уже введённые переводы значениями из файла?\n\nДа — заменять, Нет — только пустые.",
                "Подгрузить перевод", MessageBoxButton.YesNo, MessageBoxImage.Question) == MessageBoxResult.Yes;
            var n = _proj.MergeTranslation(LocRes.Read(File.ReadAllBytes(dlg.FileName)), overwrite);
            _dirty = true; _view?.Refresh(); UpdateCount();
            Status($"Подставлено переводов: {n:N0}.");
        }
        catch (Exception ex) { Error(ex); }
    }

    void BtnOpenProject_Click(object sender, RoutedEventArgs e)
    {
        var dlg = new OpenFileDialog { Filter = "Проект перевода (*.x5tr)|*.x5tr" };
        if (dlg.ShowDialog(this) != true || !ConfirmDiscard()) return;
        try { SetProject(Project.Load(dlg.FileName), dlg.FileName); Status("Проект открыт."); }
        catch (Exception ex) { Error(ex); }
    }

    void BtnSave_Click(object sender, RoutedEventArgs e) => SaveProject(true);

    bool SaveProject(bool askPath)
    {
        if (_proj == null) return true;
        if (_projPath == null || askPath && _projPath == null)
        {
            var dlg = new SaveFileDialog { Filter = "Проект перевода (*.x5tr)|*.x5tr", FileName = "ru-translation.x5tr" };
            if (dlg.ShowDialog(this) != true) return false;
            _projPath = dlg.FileName;
        }
        try
        {
            _proj.Save(_projPath);
            _dirty = false;
            Title = "X5 Translator — " + Path.GetFileName(_projPath);
            Status("Проект сохранён: " + _projPath);
            return true;
        }
        catch (Exception ex) { Error(ex); return false; }
    }

    void SaveIfDirty() { if (_dirty && _proj != null && _projPath != null) { try { _proj.Save(_projPath); _dirty = false; } catch { } } }

    bool ConfirmDiscard()
    {
        if (_proj == null || !_dirty) return true;
        var r = MessageBox.Show(this, "Есть несохранённые изменения. Сохранить проект?", "X5 Translator", MessageBoxButton.YesNoCancel, MessageBoxImage.Question);
        if (r == MessageBoxResult.Cancel) return false;
        return r != MessageBoxResult.Yes || SaveProject(false);
    }

    void MainWindow_Closing(object? sender, CancelEventArgs e)
    {
        if (!ConfirmDiscard()) e.Cancel = true;
    }

    // ---------- CSV и сборка ----------

    void BtnExportCsv_Click(object sender, RoutedEventArgs e)
    {
        var dlg = new SaveFileDialog { Filter = "CSV (*.csv)|*.csv", FileName = "translation.csv" };
        if (_proj == null || dlg.ShowDialog(this) != true) return;
        try { _proj.ExportCsv(dlg.FileName); Status("CSV сохранён: " + dlg.FileName); } catch (Exception ex) { Error(ex); }
    }

    void BtnImportCsv_Click(object sender, RoutedEventArgs e)
    {
        var dlg = new OpenFileDialog { Filter = "CSV (*.csv)|*.csv" };
        if (_proj == null || dlg.ShowDialog(this) != true) return;
        try { var n = _proj.ImportCsv(dlg.FileName); _dirty = true; _view?.Refresh(); UpdateCount(); Status($"Из CSV обновлено строк: {n:N0}."); }
        catch (Exception ex) { Error(ex); }
    }

    void BtnBuild_Click(object sender, RoutedEventArgs e)
    {
        var dlg = new SaveFileDialog { Filter = "Localization (*.locres)|*.locres", FileName = "String.locres" };
        if (_proj == null || dlg.ShowDialog(this) != true) return;
        try { File.WriteAllBytes(dlg.FileName, _proj.Build()); Status("Файл перевода сохранён: " + dlg.FileName); }
        catch (Exception ex) { Error(ex); }
    }

    // ---------- установка в игру ----------

    void BtnBrowseGame_Click(object sender, RoutedEventArgs e)
    {
        var dlg = new OpenFolderDialog { Title = "Папка игры (рядом с ArcheAgeChronicles.exe)" };
        if (dlg.ShowDialog(this) == true) { GameDirBox.Text = dlg.FolderName; SaveGameDir(); }
    }

    string? GameDir()
    {
        var d = GameDirBox.Text.Trim();
        if (GameInstall.LooksLikeGame(d)) { SaveGameDir(); return d; }
        MessageBox.Show(this, "Укажите папку игры (где лежит ArcheAgeChronicles.exe).", "X5 Translator", MessageBoxButton.OK, MessageBoxImage.Information);
        return null;
    }

    void BtnInstall_Click(object sender, RoutedEventArgs e)
    {
        if (_proj == null || GameDir() is not { } dir) return;
        var done = _proj.Items.Count(i => i.IsDone);
        if (done == 0 && MessageBox.Show(this, "Ни одной строки не переведено — в игре останется оригинальный текст. Продолжить?", "Установка",
                MessageBoxButton.YesNo, MessageBoxImage.Question) != MessageBoxResult.Yes) return;
        try
        {
            var target = GameInstall.Install(dir, _proj.Build());
            Status($"Перевод установлен ({done:N0} строк). Файл: {target}. Язык игры: ru.");
            MessageBox.Show(this, "Готово. Запустите игру. Если она осталась на английском, добавьте в параметры запуска Steam: -culture=ru",
                "Установка", MessageBoxButton.OK, MessageBoxImage.Information);
        }
        catch (Exception ex) { Error(ex); }
    }

    void BtnUninstall_Click(object sender, RoutedEventArgs e)
    {
        if (GameDir() is not { } dir) return;
        try { Status(GameInstall.Uninstall(dir)); }
        catch (Exception ex) { Error(ex); }
    }

    // ---------- таблица ----------

    bool FilterItem(object o)
    {
        var it = (Item)o;
        switch (FilterMode.SelectedIndex)
        {
            case 1: if (it.IsDone) return false; break;
            case 2: if (!it.IsDone) return false; break;
            case 3: if (!it.HasWarning) return false; break;
        }
        var q = FilterBox.Text.Trim();
        if (q.Length == 0) return true;
        return it.Key.Contains(q, StringComparison.OrdinalIgnoreCase) || it.Original.Contains(q, StringComparison.OrdinalIgnoreCase)
               || it.Translation.Contains(q, StringComparison.OrdinalIgnoreCase) || it.Namespace.Contains(q, StringComparison.OrdinalIgnoreCase);
    }

    void Filter_Changed(object sender, EventArgs e)
    {
        if (!IsLoaded) return;
        _filterTimer.Stop(); _filterTimer.Start();
    }

    void Grid_CellEditEnding(object sender, DataGridCellEditEndingEventArgs e)
    {
        if (e.EditAction != DataGridEditAction.Commit) return;
        _dirty = true;
        Dispatcher.BeginInvoke(UpdateCount, DispatcherPriority.Background);
    }

    void UpdateCount()
    {
        if (_proj == null) { CountText.Text = ""; return; }
        var total = _proj.Items.Count;
        var done = _proj.Items.Count(i => i.IsDone);
        var warn = _proj.Items.Count(i => i.HasWarning);
        var shown = _view?.Cast<object>().Count() ?? total;
        CountText.Text = $"Переведено {done:N0} из {total:N0} ({(total == 0 ? 0 : 100.0 * done / total):0.#}%)" +
                         (warn > 0 ? $" · предупреждений: {warn:N0}" : "") + (shown != total ? $" · показано: {shown:N0}" : "");
    }

    void Status(string s) => StatusText.Text = s;
    void Error(Exception ex) { StatusText.Text = "Ошибка: " + ex.Message; MessageBox.Show(this, ex.Message, "X5 Translator", MessageBoxButton.OK, MessageBoxImage.Error); }
}
