[Setup]
AppName=SabreALPR Tactical Suite
AppVersion=2.0
DefaultDirName={commonpf}\SabreALPR
DefaultGroupName=Sabre Security
; This matches the 'path' in the Upload step above
OutputBaseFilename=SabreALPR_Setup
OutputDir=Output
Compression=lzma
SolidCompression=yes
PrivilegesRequired=adminin

[Files]
; The main executable from your build folder
Source: "SabreALPR\bin\Release\net8.0-windows\win-x64\publish\SabreALPR.exe"; DestDir: "{app}"; Flags: ignoreversion
; Include any supporting DLLs
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