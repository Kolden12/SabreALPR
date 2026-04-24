[Setup]
AppName=Sabre Patrol LPR Windows Suite
AppVersion=1.0
DefaultDirName={pf}\SabrePatrolLPR
DefaultGroupName=Sabre Patrol LPR
OutputDir=.\Output
OutputBaseFilename=SabrePatrolLPR_Setup
Compression=lzma
SolidCompression=yes
ArchitecturesAllowed=x64
ArchitecturesInstallIn64BitMode=x64

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
Source: "dist\SabrePatrolLPR.exe"; DestDir: "{app}"; Flags: ignoreversion
Source: "assets\*"; DestDir: "{app}\assets"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "watchlist.csv"; DestDir: "{app}"; Flags: ignoreversion skipifsourcedoesntexist

[Icons]
Name: "{group}\Sabre Patrol LPR"; Filename: "{app}\SabrePatrolLPR.exe"
Name: "{commondesktop}\Sabre Patrol LPR"; Filename: "{app}\SabrePatrolLPR.exe"; Tasks: desktopicon

[Run]
Filename: "cmd.exe"; Parameters: "/c if not exist Z:\ echo Warning: Z: drive is not currently mapped. The LPR engine requires Z:\ to function properly. && pause"; Description: "Verify Z: Drive Connectivity"; Flags: nowait postinstall skipifsilent
Filename: "{app}\SabrePatrolLPR.exe"; Description: "{cm:LaunchProgram,Sabre Patrol LPR}"; Flags: nowait postinstall skipifsilent
