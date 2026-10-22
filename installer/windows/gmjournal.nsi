; Ricetta di NSIS: crea GMJournal-Setup-<versione>.exe a partire dalla cartella preparata da build_package.py.
; Parametri (passati da build_package.py con -D): VERSION, VERSION_NUMS (1.0.0.0), STAGE (cartella da installare), ICON, OUTFILE.
Unicode true
RequestExecutionLevel user                       ; installazione solo per l'utente: nessun permesso di amministratore

!define APP "GM Journal"
!define UNINSTALL_KEY "Software\Microsoft\Windows\CurrentVersion\Uninstall\GMJournal"

Name "${APP}"
OutFile "${OUTFILE}"
InstallDir "$LOCALAPPDATA\Programs\${APP}"
InstallDirRegKey HKCU "Software\${APP}" "InstallDir"
SetCompressor /SOLID lzma
SetCompressorDictSize 64
ShowInstDetails nevershow
ShowUninstDetails nevershow

VIProductVersion "${VERSION_NUMS}"
VIAddVersionKey /LANG=1040 "ProductName" "${APP}"
VIAddVersionKey /LANG=1040 "FileDescription" "Installazione di ${APP}"
VIAddVersionKey /LANG=1040 "FileVersion" "${VERSION}"
VIAddVersionKey /LANG=1040 "ProductVersion" "${VERSION}"
VIAddVersionKey /LANG=1040 "LegalCopyright" "${APP}"

!include MUI2.nsh
!include WinVer.nsh
!include x64.nsh

!define MUI_ICON "${ICON}"
!define MUI_UNICON "${ICON}"
!define MUI_ABORTWARNING
!define MUI_FINISHPAGE_RUN "$INSTDIR\GMJournal.exe"
!define MUI_FINISHPAGE_RUN_TEXT "Avvia ${APP}"

!insertmacro MUI_PAGE_DIRECTORY
!insertmacro MUI_PAGE_COMPONENTS
!insertmacro MUI_PAGE_INSTFILES
!insertmacro MUI_PAGE_FINISH
!insertmacro MUI_UNPAGE_CONFIRM
!insertmacro MUI_UNPAGE_INSTFILES
!insertmacro MUI_LANGUAGE "Italian"

Function .onInit
    ; Qt 6 usa le librerie ICU di sistema, presenti da Windows 10 versione 1903 (build 18362) in poi.
    ${IfNot} ${RunningX64}
    ${OrIfNot} ${AtLeastBuild} 18362
        MessageBox MB_OK|MB_ICONSTOP "${APP} richiede Windows 10 (versione 1903 o successiva) o Windows 11, a 64 bit."
        Abort
    ${EndIf}
FunctionEnd

Section "${APP}" SecApp
    SectionIn RO
    SetOutPath "$INSTDIR"

    ; Se il programma e' aperto non si puo' sostituire: lo si dice invece di lasciare un'installazione a meta'.
    ClearErrors
    IfFileExists "$INSTDIR\GMJournal.exe" 0 free
    Delete "$INSTDIR\GMJournal.exe"
    IfFileExists "$INSTDIR\GMJournal.exe" 0 free
        MessageBox MB_OK|MB_ICONSTOP "${APP} e' aperto. Chiudilo e rilancia l'installazione."
        Abort
    free:

    ; Aggiornamento pulito: via le vecchie cartelle del programma (le campagne stanno in Documenti, non qui).
    RMDir /r "$INSTDIR\app"
    RMDir /r "$INSTDIR\lib"
    RMDir /r "$INSTDIR\runtime"
    RMDir /r "$INSTDIR\licenses"

    File /r "${STAGE}\*.*"
    WriteUninstaller "$INSTDIR\Uninstall.exe"

    CreateShortcut "$SMPROGRAMS\${APP}.lnk" "$INSTDIR\GMJournal.exe"
    WriteRegStr HKCU "Software\${APP}" "InstallDir" "$INSTDIR"
    WriteRegStr HKCU "${UNINSTALL_KEY}" "DisplayName" "${APP}"
    WriteRegStr HKCU "${UNINSTALL_KEY}" "DisplayVersion" "${VERSION}"
    WriteRegStr HKCU "${UNINSTALL_KEY}" "DisplayIcon" "$INSTDIR\GMJournal.exe"
    WriteRegStr HKCU "${UNINSTALL_KEY}" "InstallLocation" "$INSTDIR"
    WriteRegStr HKCU "${UNINSTALL_KEY}" "UninstallString" '"$INSTDIR\Uninstall.exe"'
    WriteRegStr HKCU "${UNINSTALL_KEY}" "QuietUninstallString" '"$INSTDIR\Uninstall.exe" /S'
    WriteRegDWORD HKCU "${UNINSTALL_KEY}" "NoModify" 1
    WriteRegDWORD HKCU "${UNINSTALL_KEY}" "NoRepair" 1
    SectionGetSize ${SecApp} $0
    WriteRegDWORD HKCU "${UNINSTALL_KEY}" "EstimatedSize" $0
SectionEnd

Section /o "Icona sul desktop" SecDesktop
    CreateShortcut "$DESKTOP\${APP}.lnk" "$INSTDIR\GMJournal.exe"
SectionEnd

LangString DESC_App ${LANG_ITALIAN} "Il programma."
LangString DESC_Desktop ${LANG_ITALIAN} "Aggiunge l'icona di ${APP} sul desktop."
!insertmacro MUI_FUNCTION_DESCRIPTION_BEGIN
    !insertmacro MUI_DESCRIPTION_TEXT ${SecApp} $(DESC_App)
    !insertmacro MUI_DESCRIPTION_TEXT ${SecDesktop} $(DESC_Desktop)
!insertmacro MUI_FUNCTION_DESCRIPTION_END

; Disinstallazione: toglie solo cio' che l'installazione ha messo. Le campagne (Documenti\GM Journal) non si toccano.
Section "Uninstall"
    RMDir /r "$INSTDIR\app"
    RMDir /r "$INSTDIR\lib"
    RMDir /r "$INSTDIR\runtime"
    RMDir /r "$INSTDIR\licenses"
    Delete "$INSTDIR\GMJournal.exe"
    Delete "$INSTDIR\Uninstall.exe"
    RMDir "$INSTDIR"                             ; solo se e' vuota

    Delete "$SMPROGRAMS\${APP}.lnk"
    Delete "$DESKTOP\${APP}.lnk"
    DeleteRegKey HKCU "${UNINSTALL_KEY}"
    DeleteRegKey HKCU "Software\${APP}"
SectionEnd
