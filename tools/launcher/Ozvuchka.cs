// Озвучка.exe, the program's launcher (ADR-0001, ADR-0003). Built by tools\build.ps1 release with the C# compiler
// of .NET Framework 4, which every Windows 10 and 11 has.
//
// It starts runtime\pythonw.exe from its own folder (no console window, no absolute paths) with
// "-m ozvuchka --app" and its own arguments; the program opens the Edge window itself. A second start ends at once
// with code 0 after opening the window of the program already running.
// It waits for the program to end, so a start that fails is shown to the teacher instead of passing silently.

using System;
using System.Diagnostics;
using System.IO;
using System.Linq;
using System.Text;
using System.Windows.Forms;

static class Launcher
{
    const string Title = "Озвучка";
    const int MaxOutput = 64 * 1024;  // what the program prints before its log exists; the rest is not kept
    static bool quiet;  // --no-window (the smoke test): nobody is there to close a message box

    [STAThread]
    static int Main(string[] args)
    {
        quiet = args.Contains("--no-window");
        string folder = AppDomain.CurrentDomain.BaseDirectory;
        string python = Path.Combine(folder, "runtime", "pythonw.exe");
        if (!File.Exists(python))
        {
            Fail("Не найден файл runtime\\pythonw.exe рядом с Озвучка.exe.\n\n" +
                 "Распакуйте архив программы целиком и запускайте Озвучка.exe из распакованной папки.");
            return 1;
        }
        // pythonw has no console: what it prints before the log starts is kept here, to be written into data\ on a failure
        var start = new ProcessStartInfo(python, "-X utf8 -m ozvuchka --app " + string.Join(" ", args.Select(Quote)))
        {
            WorkingDirectory = folder,
            UseShellExecute = false,
            RedirectStandardOutput = true,
            RedirectStandardError = true,
            StandardOutputEncoding = Encoding.UTF8,
            StandardErrorEncoding = Encoding.UTF8,
        };
        try
        {
            DateTime started = DateTime.Now;
            var output = new StringBuilder();
            using (Process program = Process.Start(start))
            {
                program.OutputDataReceived += (sender, line) => Keep(output, line.Data);
                program.ErrorDataReceived += (sender, line) => Keep(output, line.Data);
                program.BeginOutputReadLine();
                program.BeginErrorReadLine();
                program.WaitForExit();
                if (program.ExitCode != 0)
                {
                    Fail(FailureMessage(folder, program.ExitCode, started, output.ToString()));
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

    static void Keep(StringBuilder output, string line)
    {
        if (line == null) return;
        lock (output)
        {
            if (output.Length < MaxOutput) output.AppendLine(line);
        }
    }

    // Only a log written by this start counts: an older one is not the diagnostics of this failure.
    static string FailureMessage(string folder, int exitCode, DateTime started, string output)
    {
        string dataFolder = Path.Combine(folder, "data");
        string log = Path.Combine(dataFolder, "ozvuchka.log");
        string head = "Озвучка закрылась из-за ошибки (код " + exitCode + ").\n\n";
        // FAT on a flash drive keeps file times to 2 s, so a log written just after the start may look older.
        if (File.Exists(log) && new FileInfo(log).Length > 0 && File.GetLastWriteTime(log) >= started.AddSeconds(-2))
        {
            return head + "Подробности — в файле data\\ozvuchka.log в папке программы.";
        }
        string unwritable = head + "Журнал не записан: папка data\\ в папке программы не создаётся или недоступна для записи. " +
                            "Распакуйте архив целиком в обычную папку на диске, где можно создавать файлы, и запустите программу снова.";
        if (!CanWriteTo(dataFolder))
        {
            return unwritable;
        }
        if (output.Length == 0)
        {
            return head + "Подробностей об ошибке нет: программа закрылась до начала записи журнала и ничего не вывела. " +
                   "Код ошибки можно передать разработчику.";
        }
        try
        {
            File.WriteAllText(Path.Combine(dataFolder, "startup-output.txt"), output, new UTF8Encoding(false));
        }
        catch (Exception)
        {
            return unwritable;
        }
        return head + "Программа закрылась до начала записи журнала. Что она вывела — в файле data\\startup-output.txt в папке программы.";
    }

    static bool CanWriteTo(string folder)
    {
        try
        {
            Directory.CreateDirectory(folder);
            string probe = Path.Combine(folder, "write-test.tmp");
            File.WriteAllText(probe, "");
            File.Delete(probe);
            return true;
        }
        catch (Exception)
        {
            return false;
        }
    }

    static void Fail(string message)
    {
        if (quiet)
        {
            // the smoke test reads it instead of a message box; no console here, so the encoding is set on the stream
            using (var error = new StreamWriter(Console.OpenStandardError(), new UTF8Encoding(false)))
            {
                error.WriteLine(message);
            }
            return;
        }
        MessageBox.Show(message, Title, MessageBoxButtons.OK, MessageBoxIcon.Error);
    }
}
