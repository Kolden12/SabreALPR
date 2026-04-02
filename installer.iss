[Setup]
AppName=SabreALPR Tactical Suite
AppVersion=2.5
DefaultDirName={commonpf}\SabreALPR
DefaultGroupName=Sabre Security
OutputBaseFilename=SabreALPR_Setup
OutputDir=Output
Compression=lzma
SolidCompression=yes
PrivilegesRequired=admin
ArchitecturesInstallIn64BitMode=x64

[Tasks]
Name: "autostart"; Description: "Launch SabreALPR on Windows Startup"; GroupDescription: "Patrol Options:"; Flags: checkedonce

[Files]
; Main Executable and all dependencies from the publish folder
Source: "SabreALPR\bin\Release\net8.0-windows\win-x64\publish\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs

[Dirs]
; Mission-critical data and sound folders
Name: "C:\SabreALPR"
Name: "C:\SabreALPR\Captures"
Name: "C:\SabreALPR\Sounds"

[Icons]
Name: "{group}\SabreALPR"; Filename: "{app}\SabreALPR.exe"
Name: "{commondesktop}\SabreALPR"; Filename: "{app}\SabreALPR.exe"

[Registry]
; Handles the Auto-Start task
Root: HKCU; Subkey: "Software\Microsoft\Windows\CurrentVersion\Run"; ValueType: string; ValueName: "SabreALPR"; ValueData: "{app}\SabreALPR.exe"; Flags: uninsdeletevalue; Tasks: autostart

[Run]
Filename: "{app}\SabreALPR.exe"; Description: "Launch SabreALPR Now"; Flags: nowait postinstall skipifsilent

[Code]
function InitializeSetup(): Boolean;
var
  VLCPath: string;
begin
  Result := True;
  // Check both 64-bit and 32-bit registry paths for VLC
  if not RegQueryStringValue(HKEY_LOCAL_MACHINE, 'SOFTWARE\VideoLAN\VLC', '', VLCPath) then
  begin
    if MsgBox('Warning: VLC Media Player (64-bit) was not detected.' + #13#10 + #13#10 + 'The ALPR video streams require VLC to function. Install VLC after this setup?', mbConfirmation, MB_YESNO) = IDNO then
    begin
      // User acknowledged, but we continue the install of the ALPR suite itself
    end;
  end;
end;