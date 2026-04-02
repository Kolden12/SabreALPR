[Setup]
AppName=SabreALPR Tactical Suite
AppVersion=2.0
DefaultDirName={commonpf}\SabreALPR
DefaultGroupName=Sabre Security
OutputBaseFilename=SabreALPR_Setup
OutputDir=Output
Compression=lzma
SolidCompression=yes
; Fix for the Privileges error
PrivilegesRequired=admin
; Ensures it installs as a 64-bit app on the Toughbook
ArchitecturesInstallIn64BitMode=x64

[Files]
; Main EXE
Source: "SabreALPR\bin\Release\net8.0-windows\win-x64\publish\SabreALPR.exe"; DestDir: "{app}"; Flags: ignoreversion
; All supporting DLLs and JSON configs
Source: "SabreALPR\bin\Release\net8.0-windows\win-x64\publish\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs

[Dirs]
; Create the mission-critical folders on the car's C: drive
Name: "C:\SabreALPR"
Name: "C:\SabreALPR\Captures"
Name: "C:\SabreALPR\Sounds"

[Icons]
Name: "{group}\SabreALPR"; Filename: "{app}\SabreALPR.exe"
Name: "{commondesktop}\SabreALPR"; Filename: "{app}\SabreALPR.exe"

[Run]
Filename: "{app}\SabreALPR.exe"; Description: "Launch SabreALPR"; Flags: nowait postinstall skipifsilent