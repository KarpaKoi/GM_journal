@echo off
rem Costruisce GM Journal per Windows. Si lancia con un doppio clic (serve Python 3.11 o piu' recente).
rem   1) programma pronto:   installer\out\dist\GMJournal\GMJournal.exe
rem   2) installer Setup.exe: installer\out\GMJournal-Setup-<versione>.exe   (solo se e' installato Inno Setup 6)
setlocal
cd /d "%~dp0\.."

where py >nul 2>nul && (set PY=py -3) || (set PY=python)
%PY% --version >nul 2>nul || (echo Python non trovato: installalo da python.org e riprova. & pause & exit /b 1)

echo [1/3] Installo gli strumenti necessari...
%PY% -m pip install --quiet --upgrade pyinstaller -r requirements.txt || goto :errore

echo [2/3] Costruisco il programma (ci vuole qualche minuto)...
%PY% -m PyInstaller --noconfirm --clean --distpath installer\out\dist --workpath installer\out\build installer\gmjournal.spec || goto :errore

for /f %%v in ('%PY% -c "import gmjournal; print(gmjournal.__version__)"') do set VERSION=%%v

set ISCC=
for %%p in ("%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe" "%ProgramFiles%\Inno Setup 6\ISCC.exe" "%LOCALAPPDATA%\Programs\Inno Setup 6\ISCC.exe") do if exist %%p set ISCC=%%~p
if not defined ISCC (
    echo.
    echo Programma pronto: installer\out\dist\GMJournal\GMJournal.exe
    echo Per creare anche il Setup.exe installa "Inno Setup 6" ^(gratuito, jrsoftware.org/isdl.php^) e rilancia questo file.
    pause & exit /b 0
)

echo [3/3] Creo l'installer...
"%ISCC%" /Qp /DAppVersion=%VERSION% installer\gmjournal.iss || goto :errore
echo.
echo Fatto: installer\out\GMJournal-Setup-%VERSION%.exe
pause & exit /b 0

:errore
echo.
echo Qualcosa e' andato storto: copia il messaggio qui sopra e mandalo a Claude.
pause & exit /b 1
