@echo off
REM Lancement sans installation (necessite Python 3.8+)
cd /d "%~dp0"
where pyw >nul 2>nul
if not errorlevel 1 goto :pyw
start "" pythonw SoNiC_0TAB0.py %*
exit /b
:pyw
start "" pyw -3 SoNiC_0TAB0.py %*
