@echo off
REM Compile SoNiC_0TAB0 en .exe + installateur autonome (necessite Python + : pip install pyinstaller)
cd /d "%~dp0"
pyinstaller --noconsole --onefile --icon assets\tabdock.ico --add-data "assets;assets" --add-data "firefox_extension;firefox_extension" --name SoNiC_0TAB0 SoNiC_0TAB0.py
if errorlevel 1 exit /b 1
REM Variante toujours-administrateur (UAC a chaque lancement) :
REM pyinstaller --noconsole --onefile --uac-admin --icon assets\tabdock.ico --add-data "assets;assets" --name SoNiC_0TAB0-Admin SoNiC_0TAB0.py
pyinstaller --noconsole --onefile --icon assets\tabdock.ico --add-data "assets;assets" --add-data "firefox_extension;firefox_extension" --add-data "dist\SoNiC_0TAB0.exe;payload" --name SoNiC_0TAB0-Setup installer.py
echo.
echo Termine : dist\SoNiC_0TAB0-Setup.exe est l'installateur (a double-cliquer).
pause
