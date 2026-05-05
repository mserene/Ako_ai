#define MyAppName "Ako"
#define MyAppVersion "0.1.0"
#define MyAppPublisher "mserene"
#define MyAppExeName "Ako-ai.exe"
#define MyAppLauncherName "Ako-ai_launcher.bat"
#define PythonEmbedZip "python-3.12.10-embed-amd64.zip"

[Setup]
AppId={{5E2E5C71-35B1-4629-8C4F-71A987F07B90}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={autopf}\Ako
DefaultGroupName=Ako
DisableProgramGroupPage=yes
OutputDir=..\installer_output
OutputBaseFilename=AkoSetup-{#MyAppVersion}
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
UninstallDisplayIcon={app}\{#MyAppExeName}
PrivilegesRequired=lowest
ArchitecturesInstallIn64BitMode=x64

[Languages]
Name: "korean"; MessagesFile: "compiler:Languages\Korean.isl"

[Tasks]
Name: "desktopicon"; Description: "바탕화면 바로가기 만들기"; GroupDescription: "추가 옵션:"; Flags: unchecked

[Files]
Source: "..\dist\Ako-ai\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "..\installer_assets\{#PythonEmbedZip}"; DestDir: "{app}\runtime_assets"; Flags: ignoreversion

[Icons]
Name: "{autoprograms}\Ako"; Filename: "{app}\Ako-ai_launcher.bat"; WorkingDir: "{app}"
Name: "{autodesktop}\Ako"; Filename: "{app}\Ako-ai_launcher.bat"; WorkingDir: "{app}"; Tasks: desktopicon

[Run]
Filename: "{app}\bootstrap_runtime.bat"; Parameters: "--no-pause"; Flags: waituntilterminated
Filename: "{app}\{#MyAppLauncherName}"; Description: "Ako 실행하기"; Flags: nowait postinstall skipifsilent
