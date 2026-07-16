@echo off
title RadioContest AI — Lanceur
color 0A

echo.
echo  ================================================
echo    RadioContest AI v3.0
echo    Logiciel de concours radioamateur
echo  ================================================
echo.

:: Dossier du .bat (fonctionne peu importe ou le zip est extrait)
set "DOSSIER=%~dp0concours"

:: Verifier si Python est installe
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo  [ERREUR] Python n'est pas installe !
    echo.
    echo  Telecharge Python sur https://www.python.org/downloads/
    echo  Coche bien "Add Python to PATH" lors de l'installation.
    echo.
    pause
    exit /b 1
)

:: Verifier si le serveur tourne deja
curl -s --max-time 1 http://localhost:8080/ >nul 2>&1
if %errorlevel% == 0 (
    echo  [OK] Serveur deja en route sur localhost:8080
    goto ouvre_browser
)

:: Lancer le serveur depuis le bon dossier (chemin relatif)
echo  [..] Lancement du serveur Python...
start "RadioContest Serveur" /MIN cmd /k "cd /d ""%DOSSIER%"" && python radiocontest_serveur.py"

:: Attendre que le serveur demarre
echo  [..] Attente demarrage (3 secondes)...
timeout /t 3 /nobreak >nul

:ouvre_browser
echo  [OK] Ouverture du navigateur...
echo.
echo  -> http://localhost:8080/radiocontest_logbook.html
echo  -> http://localhost:8080/radiocontest_configuration.html
echo.

:: Ouvrir dans le navigateur par defaut (Chrome ou autre)
start "" "http://localhost:8080/radiocontest_configuration.html"
timeout /t 1 /nobreak >nul
start "" "http://localhost:8080/radiocontest_logbook.html"

echo  ================================================
echo    Logiciel ouvert ! Bonne chance pour le concours
echo  ================================================
echo.
pause
