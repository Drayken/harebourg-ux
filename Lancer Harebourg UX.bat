@echo off
setlocal
chcp 65001 >nul
title Harebourg UX
set "DOWNLOAD=https://www.python.org/downloads/windows/"

where py >nul 2>nul || goto :no_launcher

set "FOUND="
for /f "delims=" %%v in ('py -3 --version 2^>nul') do set "FOUND=%%v"
if not defined FOUND goto :no_python

py -3 -c "import sys; sys.exit(sys.version_info < (3, 14))" >nul 2>nul || goto :old_python

if not exist "%~dp0harebourg.pyw" goto :missing_file

start "" pyw -3 "%~dp0harebourg.pyw" || goto :start_failed
exit /b 0

:no_launcher
echo [ERREUR] Le lanceur Python (py) est introuvable.
echo.
echo  1. Installez Python 3.14 ou plus récent.
echo  2. Cochez « py launcher » pendant l'installation.
echo  3. Relancez ce fichier.
goto :offer_download

:no_python
echo [ERREUR] Le lanceur Python est installé, mais aucun Python 3 n'a été trouvé.
echo.
echo  Installez Python 3.14 ou plus récent, puis relancez ce fichier.
goto :offer_download

:old_python
echo [ERREUR] Python 3.14 ou plus récent est requis. Trouvé : %FOUND%.
echo.
echo  Installez Python 3.14 ou plus récent, puis relancez ce fichier.
goto :offer_download

:missing_file
echo [ERREUR] harebourg.pyw est introuvable à côté de ce fichier.
echo.
echo  Gardez « Lancer Harebourg UX.bat » dans le dossier de Harebourg UX.
goto :fail

:start_failed
echo [ERREUR] Impossible de démarrer pyw.exe.
echo.
echo  Réinstallez Python en cochant « py launcher ».
goto :offer_download

:offer_download
echo.
choice /c ON /n /m "Ouvrir la page de téléchargement de Python ? [O/N] "
if errorlevel 2 exit /b 1
start "" "%DOWNLOAD%"
exit /b 1

:fail
echo.
pause
exit /b 1
