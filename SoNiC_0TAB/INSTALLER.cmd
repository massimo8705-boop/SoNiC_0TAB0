@echo off
setlocal EnableExtensions
cd /d "%~dp0"
title Installation de SoNiC_0TAB0
echo.
echo  ===== Installation de SoNiC_0TAB0 =====
echo.

if not exist "td_win.py" goto :nofiles

set "PY="
py -3 -c "import tkinter,sys;sys.exit(0 if sys.version_info>=(3,8) else 1)" >nul 2>nul
if not errorlevel 1 set "PY=py -3"
if defined PY goto :run
python -c "import tkinter,sys;sys.exit(0 if sys.version_info>=(3,8) else 1)" >nul 2>nul
if not errorlevel 1 set "PY=python"
if defined PY goto :run
if exist "%LOCALAPPDATA%\Programs\Python\Python312\python.exe" goto :trylocal
goto :nopython

:trylocal
"%LOCALAPPDATA%\Programs\Python\Python312\python.exe" -c "import tkinter" >nul 2>nul
if errorlevel 1 goto :nopython
set PY="%LOCALAPPDATA%\Programs\Python\Python312\python.exe"
goto :run

:nopython
echo  Python 3 (avec Tkinter) est introuvable sur ce PC. SoNiC_0TAB0 en a besoin.
echo  Je peux installer Python 3.12 automatiquement (gratuit, pour votre compte seulement).
echo.
choice /c ON /m "Installer Python maintenant (O = oui, N = non)"
if errorlevel 2 goto :end
where winget >nul 2>nul
if errorlevel 1 goto :download
winget install -e --id Python.Python.3.12 --scope user --accept-package-agreements --accept-source-agreements
goto :afterinstall

:download
echo  Telechargement de Python depuis python.org ...
powershell -NoProfile -ExecutionPolicy Bypass -Command "[Net.ServicePointManager]::SecurityProtocol=[Net.SecurityProtocolType]::Tls12; Invoke-WebRequest 'https://www.python.org/ftp/python/3.12.8/python-3.12.8-amd64.exe' -OutFile ($env:TEMP + '\python-setup.exe')"
if not exist "%TEMP%\python-setup.exe" goto :dlfail
"%TEMP%\python-setup.exe" /quiet InstallAllUsers=0 PrependPath=1 Include_tcltk=1 Include_launcher=1 Include_test=0

:afterinstall
if not exist "%LOCALAPPDATA%\Programs\Python\Python312\python.exe" goto :pyfail
set PY="%LOCALAPPDATA%\Programs\Python\Python312\python.exe"
goto :run

:run
echo  Python detecte. Ouverture de l'assistant d'installation...
echo  (la fenetre de l'assistant peut apparaitre derriere celle-ci)
echo.
%PY% installer.py
if errorlevel 1 goto :fail
goto :end

:nofiles
echo  Les fichiers de SoNiC_0TAB0 sont incomplets : vous avez probablement lance ce fichier
echo  depuis l'interieur du zip. Faites un clic droit sur SoNiC_0TAB0.zip, puis
echo  "Extraire tout...", et relancez INSTALLER.cmd depuis le dossier extrait.
goto :fail

:dlfail
echo  Telechargement impossible. Installez Python 3.12 depuis https://www.python.org/downloads/
echo  (cochez "Add python.exe to PATH"), puis relancez INSTALLER.cmd.
goto :fail

:pyfail
echo  L'installation de Python a echoue. Installez-le manuellement depuis
echo  https://www.python.org/downloads/ (cochez "Add python.exe to PATH"), puis relancez INSTALLER.cmd.
goto :fail

:fail
echo.
echo  L'installation n'a pas abouti. Journal : %TEMP%\sonic_0tab0_install.log
echo.
pause
exit /b 1

:end
endlocal
