#define MyAppName "NEXLINK"
#define MyAppVersion "2.1.0"
#define MyAppPublisher "NEXLINK"
#define MyAppExeName "NEXLINK-Server.exe"

[Setup]
AppId={{D2A0C8F5-1F16-4E56-9B7D-7A9D0A8A0C12}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={autopf}\NEXLINK
DefaultGroupName=NEXLINK
OutputDir=installer-output
OutputBaseFilename=NEXLINK-Setup
Compression=lzma2
SolidCompression=yes
ArchitecturesInstallIn64BitMode=x64
PrivilegesRequired=admin
WizardStyle=modern
UninstallDisplayName=NEXLINK

[Files]
Source: "..\dist\NEXLINK-Server.exe"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\dist\client\NEXLINK-Client.exe"; DestDir: "{app}\client"; Flags: ignoreversion
Source: "..\deployment-compose.server.yml"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\scripts\nexlink-server-bootstrap.ps1"; DestDir: "{app}\scripts"; Flags: ignoreversion

[Icons]
Name: "{group}\NEXLINK Server"; Filename: "{app}\NEXLINK-Server.exe"
Name: "{group}\NEXLINK Client"; Filename: "{app}\client\NEXLINK-Client.exe"
Name: "{commondesktop}\NEXLINK Server"; Filename: "{app}\NEXLINK-Server.exe"; Tasks: desktopicon

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut for NEXLINK Server"; GroupDescription: "Shortcuts:"
Name: "autostart"; Description: "Start NEXLINK Server automatically with Windows"; GroupDescription: "Server startup:"

[Run]
Filename: "powershell.exe"; Parameters: "-NoProfile -ExecutionPolicy Bypass -File \"{app}\scripts\nexlink-server-bootstrap.ps1\" -InstallPath \"{app}\""; StatusMsg: "Preparing NEXLINK infrastructure..."; Flags: waituntilterminated runhidden
Filename: "{app}\NEXLINK-Server.exe"; Description: "Launch NEXLINK Server"; Flags: nowait postinstall skipifsilent
Filename: "schtasks.exe"; Parameters: "/Create /TN "NEXLINK Server" /SC ONLOGON /RL HIGHEST /TR "\"{app}\NEXLINK-Server.exe\"" /F"; Tasks: autostart; Flags: runhidden waituntilterminated

[UninstallRun]
Filename: "powershell.exe"; Parameters: "-NoProfile -ExecutionPolicy Bypass -Command \"Get-ScheduledTask -TaskName 'NEXLINK Server' -ErrorAction SilentlyContinue | Unregister-ScheduledTask -Confirm:$false\""; Flags: runhidden
