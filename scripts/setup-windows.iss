; gaokao-analyzer Windows 安装程序 (Inno Setup)
; 使用 Inno Setup 6+ 编译: iscc setup-windows.iss

#define MyAppName "高考模拟卷智能分析系统"
#define MyAppVersion "6.0.0"
#define MyAppPublisher "gaokao-analyzer"
#define MyAppURL "https://github.com/shuangzhebai/gaokao-analyzer"
#define MyAppExeName "启动系统.bat"

[Setup]
AppId={{B4A2C8E1-8F5A-4A6D-9C3E-2F1D7E5B8A0C}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
DefaultDirName={autopf}\gaokao-analyzer
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
OutputDir=..\dist\packages
OutputBaseFilename=gaokao-analyzer-Setup-{#MyAppVersion}
Compression=lzma2/ultra64
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=admin
DisableWelcomePage=no
SetupIconFile=..\frontend\public\favicon.ico
UninstallDisplayIcon={app}\启动系统.bat
UninstallDisplayName={#MyAppName}

[Languages]
Name: "chinesesimplified"; MessagesFile: "compiler:Languages\ChineseSimplified.isl"
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "创建桌面快捷方式"; GroupDescription: "快捷方式："

[Files]
Source: "..\一键启动.bat"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\Docker一键启动.bat"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\*.py"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs
Source: "..\requirements.txt"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\config.py"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\app.py"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\models.py"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\deps.py"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\lifespan.py"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\errors.py"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\celery_app.py"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\region_validator.py"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\locales\*"; DestDir: "{app}\locales"; Flags: ignoreversion recursesubdirs
Source: "..\routes\*.py"; DestDir: "{app}\routes"; Flags: ignoreversion
Source: "..\services\*.py"; DestDir: "{app}\services"; Flags: ignoreversion
Source: "..\repositories\*.py"; DestDir: "{app}\repositories"; Flags: ignoreversion
Source: "..\engines\*.py"; DestDir: "{app}\engines"; Flags: ignoreversion
Source: "..\analyzers\*.py"; DestDir: "{app}\analyzers"; Flags: ignoreversion
Source: "..\tasks\*.py"; DestDir: "{app}\tasks"; Flags: ignoreversion
Source: "..\static\*"; DestDir: "{app}\static"; Flags: ignoreversion recursesubdirs
Source: "..\frontend\dist\*"; DestDir: "{app}\frontend\dist"; Flags: ignoreversion recursesubdirs
Source: "..\data\.gitkeep"; DestDir: "{app}\data"; Flags: ignoreversion

[Dirs]
Name: "{app}\data"; Permissions: users-modify

[Icons]
Name: "{group}\启动系统"; Filename: "{app}\一键启动.bat"; WorkingDir: "{app}"; Comment: "启动高考模拟卷智能分析系统"
Name: "{group}\Docker启动"; Filename: "{app}\Docker一键启动.bat"; WorkingDir: "{app}"
Name: "{group}\卸载系统"; Filename: "{uninstallexe}"
Name: "{commondesktop}\高考分析系统"; Filename: "{app}\一键启动.bat"; WorkingDir: "{app}"; Tasks: desktopicon

[Run]
Filename: "{app}\一键启动.bat"; Description: "立即启动系统"; Flags: postinstall nowait skipifsilent shellexec unchecked

[UninstallRun]
Filename: "{cmd}"; Parameters: "/c taskkill /f /im python.exe /im uvicorn.exe 2>nul"; Flags: runhidden

[Code]
function InitializeSetup: Boolean;
begin
  Result := True;
end;
