; Ricetta di Inno Setup: crea GMJournal-Setup-<versione>.exe a partire dalla cartella costruita da PyInstaller.
; Si lancia da build_windows.bat (che passa la versione con /DAppVersion=...).
#ifndef AppVersion
  #define AppVersion "1.0.0"
#endif

[Setup]
AppId={{6F1B7A52-3C0D-4E8B-9A41-5D2E7C9B1F30}
AppName=GM Journal
AppVersion={#AppVersion}
DefaultDirName={autopf}\GM Journal
DefaultGroupName=GM Journal
; installazione solo per l'utente corrente: non servono i permessi di amministratore
PrivilegesRequired=lowest
SetupIconFile=gmjournal.ico
UninstallDisplayIcon={app}\GMJournal.exe
OutputDir=out
OutputBaseFilename=GMJournal-Setup-{#AppVersion}
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
DisableProgramGroupPage=yes

[Languages]
Name: "italian"; MessagesFile: "compiler:Languages\Italian.isl"

[Tasks]
Name: "desktopicon"; Description: "Crea un'icona sul desktop"; Flags: unchecked

[Files]
Source: "out\dist\GMJournal\*"; DestDir: "{app}"; Flags: recursesubdirs ignoreversion

[Icons]
Name: "{autoprograms}\GM Journal"; Filename: "{app}\GMJournal.exe"
Name: "{autodesktop}\GM Journal"; Filename: "{app}\GMJournal.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\GMJournal.exe"; Description: "Avvia GM Journal"; Flags: nowait postinstall skipifsilent

; Le campagne stanno in Documenti\GM Journal e la disinstallazione NON le tocca.
