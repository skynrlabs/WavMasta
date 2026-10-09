; Inno Setup script for the Windows installer.
; Built by packaging\build.ps1 after PyInstaller has produced dist\WavMasta.

#ifndef AppVersion
  #define AppVersion "0.0.0"
#endif

[Setup]
AppId={{3A1CFDD7-AC27-4FB8-BB72-D4CCC3AF4555}
AppName=WavMasta
AppVersion={#AppVersion}
AppVerName=WavMasta {#AppVersion}
AppPublisher=Skynr Labs
AppPublisherURL=https://github.com/skynrlabs
AppSupportURL=https://github.com/skynrlabs/WavMasta/issues
AppUpdatesURL=https://skynrlabs.itch.io/wavmasta
DefaultDirName={autopf}\WavMasta
DefaultGroupName=WavMasta
DisableProgramGroupPage=yes
; Installs for the current user without needing admin rights (users can still choose "all users").
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
LicenseFile=..\LICENSE
OutputDir=..\dist\installer
OutputBaseFilename=WavMasta-Setup-{#AppVersion}
SetupIconFile=..\wavmasta\assets\wavmasta.ico
UninstallDisplayIcon={app}\WavMasta.exe
UninstallDisplayName=WavMasta
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"

[Files]
Source: "..\dist\WavMasta\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autoprograms}\WavMasta"; Filename: "{app}\WavMasta.exe"
Name: "{autodesktop}\WavMasta"; Filename: "{app}\WavMasta.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\WavMasta.exe"; Description: "{cm:LaunchProgram,WavMasta}"; Flags: nowait postinstall skipifsilent
