@echo off
cd /d "%~dp0"
set PY=
where py >nul 2>nul && set PY=py -3
if not defined PY where python >nul 2>nul && set PY=python
if not defined PY (
    echo Python non e' installato su questo computer.
    echo Scaricalo da https://www.python.org/downloads/ e, durante l'installazione,
    echo spunta la casella "Add python.exe to PATH". Poi rilancia questo file.
    pause
    exit /b 1
)
rem Installa le librerie (PySide6 e spylls) solo se ne manca una: la prima volta, o quando ne arriva una nuova.
%PY% -c "import PySide6, spylls" >nul 2>nul || (
    echo Installo le librerie che mancano, ci vuole al massimo un minuto...
    %PY% -m pip install -q --disable-pip-version-check --no-warn-script-location -r requirements.txt
)
%PY% main.py
if errorlevel 1 pause
