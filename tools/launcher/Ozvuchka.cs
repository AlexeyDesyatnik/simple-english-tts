// Озвучка.exe, the program's launcher (ADR-0001, ADR-0003). Built by tools\build.ps1 release with the C# compiler
// of .NET Framework 4, which every Windows 10 and 11 has.
//
// It starts runtime\pythonw.exe from its own folder (no console window, no absolute paths) with
// "-m ozvuchka --app" and its own arguments; the program opens the Edge window itself once Kokoro is loaded.
// It waits for the program to end, so a start that fails is shown to the teacher instead of passing silently.

using System;
using System.Diagnostics;
using System.IO;
using System.Linq;
using System.Windows.Forms;

static class Launcher
{
    const string Title = "Озвучка";

    [STAThread]
    static int Main(string[] args)
    {
        string folder = AppDomain.CurrentDomain.BaseDirectory;
        string python = Path.Combine(folder, "runtime", "pythonw.exe");
        if (!File.Exists(python))
        {
            Fail("Не найден файл runtime\\pythonw.exe рядом с Озвучка.exe.\n\n" +
                 "Распакуйте архив программы целиком и запускайте Озвучка.exe из распакованной папки.");
            return 1;
        }
        var start = new ProcessStartInfo(python, "-X utf8 -m ozvuchka --app " + string.Join(" ", args.Select(Quote)))
        {
            WorkingDirectory = folder,
            UseShellExecute = false,
        };
        try
        {
            using (Process program = Process.Start(start))
            {
                program.WaitForExit();
                if (program.ExitCode != 0)
                {
                    Fail("Озвучка закрылась из-за ошибки.\n\n" +
                         "Подробности — в файле data\\ozvuchka.log в папке программы.");
                }
                return program.ExitCode;
            }
        }
        catch (Exception error)
        {
            Fail("Не удалось запустить Озвучку: " + error.Message);
            return 1;
        }
    }

    static string Quote(string arg)
    {
        return arg.Length > 0 && arg.IndexOfAny(new[] { ' ', '\t', '"' }) < 0 ? arg : "\"" + arg.Replace("\"", "\\\"") + "\"";
    }

    static void Fail(string message)
    {
        MessageBox.Show(message, Title, MessageBoxButtons.OK, MessageBoxIcon.Error);
    }
}
