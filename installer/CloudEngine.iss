#ifndef EngineSource
  #define EngineSource "..\releases\Current\CloudEngine.exe"
#endif
#ifndef SetupOutput
  #define SetupOutput "..\releases\Current"
#endif
#define EngineVersion "1.2.0.7"

[Setup]
AppId={{FADCE49D-AC51-4763-BA71-83FC00605FB3}
AppName=Cloud Engine
AppVersion={#EngineVersion}
AppVerName=Cloud Engine {#EngineVersion}
AppPublisher=Cloud Team
VersionInfoVersion=1.2.0.7
VersionInfoProductName=Cloud Engine
VersionInfoProductVersion=1.2.0.7
VersionInfoProductTextVersion={#EngineVersion}
DefaultDirName={localappdata}\Programs\Cloud Engine
DefaultGroupName=Cloud Engine
DisableDirPage=no
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0
OutputDir={#SetupOutput}
#ifndef VerifyInstaller
OutputBaseFilename=CloudEngine-{#EngineVersion}-Setup
#endif
SetupIconFile=..\assets\engine_icon.ico
UninstallDisplayIcon={app}\CloudEngine.exe
UninstallDisplayName=Cloud Engine {#EngineVersion}
Compression=lzma2/fast
SolidCompression=yes
WizardStyle=modern
WizardSizePercent=110
SetupLogging=yes
CloseApplications=no
RestartApplications=no
CreateUninstallRegKey=no
#ifdef VerifyInstaller
OutputBaseFilename=CloudEngine-Installer-Verification
#endif

[Languages]
Name: "russian"; MessagesFile: "compiler:Languages\Russian.isl"
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"
Name: "startmenuicon"; Description: "Ярлык в меню Пуск"; GroupDescription: "{cm:AdditionalIcons}"

[Files]
Source: "{#EngineSource}"; DestDir: "{app}"; DestName: "CloudEngine.exe"; Flags: ignoreversion

[Registry]
; Registry integration is optional. A denied HKCU must never roll back the engine.
#ifdef VerifyInstaller
#define UninstallKey "Software\CloudEngineInstallerQA\Uninstall"
#else
#define UninstallKey "Software\Microsoft\Windows\CurrentVersion\Uninstall\CloudEngine"
#endif
Root: HKCU; Subkey: "{#UninstallKey}"; ValueType: string; ValueName: "DisplayName"; ValueData: "Cloud Engine {#EngineVersion}"; Flags: noerror uninsdeletekey
Root: HKCU; Subkey: "{#UninstallKey}"; ValueType: string; ValueName: "DisplayVersion"; ValueData: "{#EngineVersion}"; Flags: noerror
Root: HKCU; Subkey: "{#UninstallKey}"; ValueType: string; ValueName: "Publisher"; ValueData: "Cloud Team"; Flags: noerror
Root: HKCU; Subkey: "{#UninstallKey}"; ValueType: string; ValueName: "InstallLocation"; ValueData: "{app}"; Flags: noerror
Root: HKCU; Subkey: "{#UninstallKey}"; ValueType: string; ValueName: "DisplayIcon"; ValueData: "{app}\CloudEngine.exe"; Flags: noerror
Root: HKCU; Subkey: "{#UninstallKey}"; ValueType: string; ValueName: "UninstallString"; ValueData: """{uninstallexe}"""; Flags: noerror
Root: HKCU; Subkey: "{#UninstallKey}"; ValueType: string; ValueName: "QuietUninstallString"; ValueData: """{uninstallexe}"" /VERYSILENT /SUPPRESSMSGBOXES /NORESTART"; Flags: noerror
Root: HKCU; Subkey: "{#UninstallKey}"; ValueType: dword; ValueName: "NoModify"; ValueData: "1"; Flags: noerror
Root: HKCU; Subkey: "{#UninstallKey}"; ValueType: dword; ValueName: "NoRepair"; ValueData: "1"; Flags: noerror

[UninstallDelete]
Type: files; Name: "{app}\Cloud Engine {#EngineVersion}.lnk"
Type: files; Name: "{app}\InstallationReport.txt"

[Run]
Filename: "{app}\CloudEngine.exe"; Description: "{cm:LaunchProgram,Cloud Engine}"; Flags: nowait postinstall skipifsilent unchecked

; Only files installed by Setup are removed. User projects and settings remain.

[Code]
function WritableFolder(Path: String): Boolean;
var Probe: String;
begin
  try
  Result := ForceDirectories(Path);
  Log('Cloud folder probe: ' + Path + ' created=' + IntToStr(Ord(Result)));
  if Result then begin
    Probe := AddBackslash(Path) + '.cloud-write-probe-' + GetDateTimeString('yyyymmddhhnnsszzz', '-', ':') + '.tmp';
    if FileExists(Probe) then begin Result := False; Exit; end;
    Result := SaveStringToFile(Probe, 'test', False);
    Log('Cloud write probe: ' + Probe + ' writable=' + IntToStr(Ord(Result)));
    if Result then DeleteFile(Probe);
  end;
  except
    Log('Cloud folder exception: ' + GetExceptionMessage);
    Result := False;
  end;
end;
function FallbackFolder: String;
begin
#ifdef VerifyInstaller
  Result := AddBackslash(ExtractFileDir(GetEnv('CLOUDENGINE_LAUNCHER_PATH'))) + 'Fallback Installation';
#else
  Result := ExpandConstant('{userdocs}\Cloud Engine');
#endif
end;
function NextButtonClick(CurPageID: Integer): Boolean;
var Fallback: String;
begin
  Result := True;
  if CurPageID = wpSelectDir then begin
    if not WritableFolder(WizardDirValue) then begin
      Fallback := FallbackFolder;
      if not WritableFolder(Fallback) then Fallback := ExpandConstant('{src}\Cloud Engine');
      WizardForm.DirEdit.Text := Fallback;
      if not WizardSilent then
        MsgBox('Нет доступа к выбранной папке. Указан другой путь. Проверьте его или выберите свою папку.', mbInformation, MB_OK);
      Result := WizardSilent and WritableFolder(Fallback);
    end;
  end;
end;
function PrepareToInstall(var NeedsRestart: Boolean): String;
begin
  Result := '';
  if not WritableFolder(WizardDirValue) then
    Result := 'Нет прав на запись в выбранную папку. Вернитесь назад и выберите другую папку установки.';
end;

procedure InitializeWizard;
var Candidate: String;
begin
  if not WritableFolder(WizardDirValue) then begin
    Candidate := FallbackFolder;
    if not WritableFolder(Candidate) then Candidate := ExpandConstant('{src}\Cloud Engine');
    if WritableFolder(Candidate) then WizardForm.DirEdit.Text := Candidate;
  end;
end;

function ShellFolder(Desktop: Boolean): String;
begin
#ifdef VerifyInstaller
  if ExpandConstant('{param:CloudTestBlockedShell|0}') = '1' then begin
    Result := ExpandConstant('{app}\BlockedShell');
    Exit;
  end;
  if Desktop then Result := ExpandConstant('{app}\Verification Desktop')
  else Result := ExpandConstant('{app}\Verification Start Menu');
#else
  if Desktop then Result := ExpandConstant('{userdesktop}')
  else Result := ExpandConstant('{userprograms}\Cloud Engine');
#endif
end;

function SafeShortcut(Folder: String): Boolean;
var Link: String;
begin
  Result := False;
  try
    if not WritableFolder(Folder) then begin
      Log('Cloud optional shortcut skipped (folder denied): ' + Folder);
      Exit;
    end;
    Link := AddBackslash(Folder) + 'Cloud Engine {#EngineVersion}.lnk';
    CreateShellLink(Link, 'Cloud Engine {#EngineVersion}', ExpandConstant('{app}\CloudEngine.exe'), '', ExpandConstant('{app}'), ExpandConstant('{app}\CloudEngine.exe'), 0, SW_SHOWNORMAL);
    Result := FileExists(Link);
    if Result then Log('Cloud optional shortcut created: ' + Link);
  except
    Log('Cloud optional shortcut skipped: ' + Folder + ': ' + GetExceptionMessage);
  end;
end;

procedure CurStepChanged(CurStep: TSetupStep);
var DesktopOK, StartOK, LocalOK, Registered: Boolean; Summary: String;
begin
  if CurStep = ssPostInstall then begin
    DesktopOK := False;
    StartOK := False;
    if WizardIsTaskSelected('desktopicon') then DesktopOK := SafeShortcut(ShellFolder(True));
    if WizardIsTaskSelected('startmenuicon') then StartOK := SafeShortcut(ShellFolder(False));
    LocalOK := SafeShortcut(ExpandConstant('{app}'));
    Registered := RegValueExists(HKCU, '{#UninstallKey}', 'UninstallString');
    Summary := 'Cloud Engine {#EngineVersion}' + #13#10 + 'Installation completed.' + #13#10;
    Summary := Summary + 'Desktop shortcut: ' + IntToStr(Ord(DesktopOK)) + #13#10;
    Summary := Summary + 'Start Menu shortcut: ' + IntToStr(Ord(StartOK)) + #13#10;
    Summary := Summary + 'Local shortcut: ' + IntToStr(Ord(LocalOK)) + #13#10;
    Summary := Summary + 'Windows uninstall registration: ' + IntToStr(Ord(Registered)) + #13#10;
    Summary := Summary + 'Launch: ' + ExpandConstant('{app}\CloudEngine.exe') + #13#10;
    Summary := Summary + 'Uninstall: ' + ExpandConstant('{uninstallexe}') + #13#10;
    try
      SaveStringToFile(ExpandConstant('{app}\InstallationReport.txt'), Summary, False);
    except
      Log('Cloud installation report could not be written: ' + GetExceptionMessage);
    end;
    Log(Summary);
    if (WizardIsTaskSelected('desktopicon') and (not DesktopOK)) or (WizardIsTaskSelected('startmenuicon') and (not StartOK)) or (not Registered) then
      WizardForm.FinishedLabel.Caption := 'Cloud Engine установлен.' + #13#10 + 'Часть системных папок или реестр недоступны. Это не мешает запуску движка.' + #13#10 + 'Откройте CloudEngine.exe в выбранной папке. Там также находятся ярлык и программа удаления.';
  end;
end;

procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
begin
  if CurUninstallStep = usPostUninstall then begin
    try
      DeleteFile(AddBackslash(ShellFolder(True)) + 'Cloud Engine {#EngineVersion}.lnk');
      DeleteFile(AddBackslash(ShellFolder(False)) + 'Cloud Engine {#EngineVersion}.lnk');
    except
      Log('Cloud optional shortcut cleanup skipped: ' + GetExceptionMessage);
    end;
  end;
end;
