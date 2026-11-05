// Озвучка.exe, the program's launcher (ADR-0001, ADR-0003). Built by tools\build.ps1 release with the C# compiler
// of .NET Framework 4, which every Windows 10 and 11 has.
//
// It starts runtime\python.exe from its own folder (no console window, no absolute paths) with
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
    static bool quiet;  // --no-window (the smoke test): nobody is there to close a message box

    [STAThread]
    static int Main(string[] args)
    {
        quiet = args.Contains("--no-window");
        if (quiet) Console.SetError(new StreamWriter(Console.OpenStandardError(), new UTF8Encoding(false))
        {
            AutoFlush = true,
        });
        string folder = AppDomain.CurrentDomain.BaseDirectory;
        string python = Path.Combine(folder, "runtime", "python.exe");
        if (!File.Exists(python))
        {
            Fail("Не найден файл runtime\\python.exe рядом с Озвучка.exe.\n\n" +
                 "Распакуйте архив программы целиком и запускайте Озвучка.exe из распакованной папки.");
            return 1;
        }
        var start = new ProcessStartInfo(python, "-X utf8 -m ozvuchka --app " + string.Join(" ", args.Select(Quote)))
        {
            WorkingDirectory = folder,
            UseShellExecute = false,
            CreateNoWindow = true,
            RedirectStandardError = true,
            RedirectStandardOutput = true,
            StandardErrorEncoding = Encoding.UTF8,
            StandardOutputEncoding = Encoding.UTF8,
        };
        // Python sends ordinary output to its rotating log after initialization. These pipes retain
        // pre-initialization output and the current uncaught traceback, independently of any old log.
        start.EnvironmentVariables["OZVUCHKA_LAUNCHER"] = "1";
        try
        {
            using (Process program = Process.Start(start))
            {
                var stderr = program.StandardError.ReadToEndAsync();
                var stdout = program.StandardOutput.ReadToEndAsync();
                program.WaitForExit();
                if (program.ExitCode != 0)
                {
                    Fail(FailureDetails(folder, program.ExitCode, stderr.Result + stdout.Result));
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

    static string FailureDetails(string folder, int code, string output)
    {
        string message = "Озвучка закрылась из-за ошибки. Код завершения Python: " + code + ".\n\n";
        if (string.IsNullOrWhiteSpace(output))
            return message + "Python не вывел сведений об ошибке. Диагностический файл этого запуска не создан.\n" +
                   "Попробуйте распаковать архив программы заново в отдельную папку.";
        string name = "startup-" + Guid.NewGuid().ToString("N") + ".log";
        string path = Path.Combine(folder, "data", name);
        string temporary = path + ".tmp";
        try
        {
            Directory.CreateDirectory(Path.GetDirectoryName(path));
            File.WriteAllText(temporary, "Python exit code: " + code + "\n" + output, new UTF8Encoding(false));
            File.Move(temporary, path);
            return message + "Подробности — в файле data\\" + name + " в папке программы.";
        }
        catch (Exception error)
        {
            return message + "Не удалось сохранить сведения об ошибке в папке data: " + error.Message +
                   "\nПроверьте, что папка программы доступна для записи и на диске есть свободное место, " +
                   "или распакуйте архив в новую папку.\n\nВывод Python:\n" + output;
        }
        finally
        {
            try { if (File.Exists(temporary)) File.Delete(temporary); }
            catch (IOException) { }
            catch (UnauthorizedAccessException) { }
        }
    }

    static string Quote(string arg)
    {
        return arg.Length > 0 && arg.IndexOfAny(new[] { ' ', '\t', '"' }) < 0 ? arg : "\"" + arg.Replace("\"", "\\\"") + "\"";
    }

    static void Fail(string message)
    {
        if (quiet)
        {
            Console.Error.WriteLine(message);
            return;
        }
        MessageBox.Show(message, Title, MessageBoxButtons.OK, MessageBoxIcon.Error);
    }
}
