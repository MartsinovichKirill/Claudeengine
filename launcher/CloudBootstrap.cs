// Single-file Windows bootstrap. Selects a writable private runtime directory
// before starting the embedded PyInstaller application. No Python install.
using System;
using System.IO;
using System.Reflection;
using System.Diagnostics;
using System.Text;
using System.Windows.Forms;
using System.Security.Cryptography;

class CloudBootstrap {
    static string Quote(string value) {
        StringBuilder result=new StringBuilder("\""); int slashes=0;
        foreach(char c in value) {
            if(c=='\\') { slashes++; continue; }
            if(c=='\"') { result.Append('\\',slashes*2+1); result.Append(c); }
            else { result.Append('\\',slashes);result.Append(c); }
            slashes=0;
        }
        result.Append('\\',slashes*2);result.Append('"');return result.ToString();
    }
    static string ChooseDirectory() {
        string[] candidates={
            Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData),"CloudEngine","Runtime"),
            Path.Combine(Path.GetDirectoryName(Assembly.GetExecutingAssembly().Location),".cloudengine-runtime"),
            Path.Combine(Path.GetTempPath(),"CloudEngineRuntime")
        };
        StringBuilder errors=new StringBuilder();
        foreach(string candidate in candidates) {
            string test=null;
            try {
                Directory.CreateDirectory(candidate);
                test=Path.Combine(candidate,"probe-"+Guid.NewGuid().ToString("N"));
                using(FileStream stream=new FileStream(test,FileMode.CreateNew,FileAccess.Write,FileShare.None)) { stream.WriteByte(1); }
                File.Delete(test);
                return candidate;
            } catch(Exception error) { errors.AppendLine(candidate+": "+error.Message); }
            finally { try { if(test!=null && File.Exists(test))File.Delete(test); }catch{} }
        }
        throw new IOException("No writable runtime folder. Move the EXE to a writable folder.\n"+errors.ToString());
    }
    [STAThread]
    static int Main(string[] args) {
        string run=null;
        try {
            string root=ChooseDirectory();
            run=Path.Combine(root,"run-"+Guid.NewGuid().ToString("N"));Directory.CreateDirectory(run);
            // Keep the application path stable: the editor may store project
            // history and default project paths relative to its executable.
            string application=Path.Combine(root,"Application-PAYLOAD_HASH");Directory.CreateDirectory(application);
            string payload=Path.Combine(application,"CloudEngineRuntime.exe");
            string expected="PAYLOAD_HASH";
            bool valid=false;
            if(File.Exists(payload)) {
                using(SHA256 hash=SHA256.Create()) using(FileStream input=File.OpenRead(payload)) {
                    valid=BitConverter.ToString(hash.ComputeHash(input)).Replace("-", "").ToLowerInvariant()==expected;
                }
            }
            if(!valid) {
                string staging=Path.Combine(run,"payload.new");
                using(Stream source=Assembly.GetExecutingAssembly().GetManifestResourceStream("CloudEnginePayload"))
                using(FileStream output=new FileStream(staging,FileMode.CreateNew,FileAccess.Write,FileShare.None)) { source.CopyTo(output); }
                if(File.Exists(payload))File.Delete(payload);
                File.Move(staging,payload);
            }
            ProcessStartInfo start=new ProcessStartInfo(payload);
            StringBuilder command=new StringBuilder();foreach(string arg in args) { if(command.Length>0)command.Append(' ');command.Append(Quote(arg)); }
            start.Arguments=command.ToString();start.UseShellExecute=false;start.CreateNoWindow=true;
            start.WorkingDirectory=Environment.CurrentDirectory;
            foreach(string key in new string[]{"QT_PLUGIN_PATH","QT_QPA_PLATFORM_PLUGIN_PATH","QT_QPA_PLATFORMTHEME","QT_STYLE_OVERRIDE","QML_IMPORT_PATH","QML2_IMPORT_PATH"})start.EnvironmentVariables.Remove(key);
            string logs=Path.Combine(root,"Logs");Directory.CreateDirectory(logs);
            start.EnvironmentVariables["CLOUDENGINE_LOG_DIR"]=logs;
            start.EnvironmentVariables["TEMP"]=run;start.EnvironmentVariables["TMP"]=run;
            start.EnvironmentVariables["CLOUDENGINE_LAUNCHER_PATH"]=Assembly.GetExecutingAssembly().Location;
            start.EnvironmentVariables["PYINSTALLER_RESET_ENVIRONMENT"]="1";
            using(Process child=Process.Start(start)) { child.WaitForExit();return child.ExitCode; }
        } catch(Exception error) {
            MessageBox.Show("Cloud Engine could not start.\n\n"+error.Message,"Cloud Engine",MessageBoxButtons.OK,MessageBoxIcon.Error);return 1;
        } finally {
            if(run!=null) { try {Directory.Delete(run,true);}catch{} }
        }
    }
}
