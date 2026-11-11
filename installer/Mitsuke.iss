; Mitsuke installer (Inno Setup 6). Installs for the current user only — no administrator rights — into
; %LOCALAPPDATA%\Programs\Mitsuke, so the built-in updater can replace the files later.
; Build: iscc /DAppVersion=2.5 installer\Mitsuke.iss   (after PyInstaller has produced dist\Mitsuke)
; Silent install: MitsukeSetup-2.5.exe /VERYSILENT   (add /NOLAUNCH to leave it closed)
; Settings, saved words and the dictionary live in %APPDATA%\Mitsuke and survive uninstalling.

#ifndef AppVersion
  #define AppVersion "0.0"
#endif

[Setup]
AppId=Mitsuke
AppName=Mitsuke
AppVersion={#AppVersion}
AppVerName=Mitsuke {#AppVersion}
AppPublisher=Berneyw
AppPublisherURL=https://github.com/Berneyw/mitsuke
AppSupportURL=https://github.com/Berneyw/mitsuke/issues
AppUpdatesURL=https://github.com/Berneyw/mitsuke/releases
DefaultDirName={localappdata}\Programs\Mitsuke
DisableDirPage=auto
DisableProgramGroupPage=yes
DisableReadyPage=yes
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0.17763
OutputDir=..\dist
OutputBaseFilename=MitsukeSetup-{#AppVersion}
SetupIconFile=..\assets\icon.ico
UninstallDisplayIcon={app}\Mitsuke.exe
UninstallDisplayName=Mitsuke
WizardStyle=modern
WizardSizePercent=100
Compression=lzma2/max
SolidCompression=yes
CloseApplications=no
RestartApplications=no

[Languages]
Name: "en"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "Create a &desktop shortcut"; Flags: unchecked

[InstallDelete]
; files of the previous version that the new one no longer ships
Type: filesandordirs; Name: "{app}\_internal"

[Files]
Source: "..\dist\Mitsuke\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{userprograms}\Mitsuke"; Filename: "{app}\Mitsuke.exe"
Name: "{userdesktop}\Mitsuke"; Filename: "{app}\Mitsuke.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\Mitsuke.exe"; Description: "Start Mitsuke"; Flags: nowait postinstall skipifsilent
Filename: "{app}\Mitsuke.exe"; Flags: nowait; Check: SilentLaunch

[UninstallRun]
Filename: "{sys}\taskkill.exe"; Parameters: "/F /IM Mitsuke.exe"; Flags: runhidden; RunOnceId: "StopMitsuke"

[Registry]
; the "Start with Windows" entry the app writes; removed on uninstall
Root: HKCU; Subkey: "Software\Microsoft\Windows\CurrentVersion\Run"; ValueName: "Mitsuke"; ValueType: none; Flags: uninsdeletevalue

[Code]
function SilentLaunch: Boolean;
begin
  Result := WizardSilent and (Pos('/NOLAUNCH', Uppercase(GetCmdTail)) = 0);
end;

function PrepareToInstall(var NeedsRestart: Boolean): String;
var
  Code: Integer;
begin
  // a running copy holds its files open; it keeps nothing unsaved (settings and words are written at once)
  Exec(ExpandConstant('{sys}\taskkill.exe'), '/F /IM Mitsuke.exe', '', SW_HIDE, ewWaitUntilTerminated, Code);
  Sleep(400);
  Result := '';
end;
