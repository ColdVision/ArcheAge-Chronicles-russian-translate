using System.IO;
using System.Windows;
using X5Translator.Services;

namespace X5Translator;

public partial class App : Application
{
    protected override void OnStartup(StartupEventArgs e)
    {
        var i = Array.IndexOf(e.Args, "--selftest");
        if (i >= 0 && i + 1 < e.Args.Length)
        {
            File.WriteAllText(e.Args[i + 1], SelfTest.Run());
            Shutdown();
            return;
        }
        base.OnStartup(e);
        new MainWindow().Show();
    }

    public App()
    {
        DispatcherUnhandledException += (_, ex) =>
        {
            MessageBox.Show(ex.Exception.Message, "X5 Translator", MessageBoxButton.OK, MessageBoxImage.Error);
            ex.Handled = true;
        };
    }
}
