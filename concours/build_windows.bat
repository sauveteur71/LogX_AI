@echo off
REM ============================================================
REM  RadioContest AI - Construction de l'executable Windows
REM  Produit : dist\RadioContestAI.exe (autonome, sans Python)
REM ============================================================
setlocal
cd /d "%~dp0"

echo [1/2] Installation de PyInstaller si necessaire...
python -m pip install --quiet --upgrade pyinstaller

echo [2/2] Construction de l'executable...
python -m PyInstaller --noconfirm --clean radiocontest.spec

echo.
if exist "dist\RadioContestAI.exe" (
  echo  ============================================================
  echo   OK ! Executable pret : dist\RadioContestAI.exe
  echo   Double-clique dessus pour lancer RadioContest AI.
  echo  ============================================================
) else (
  echo  [ERREUR] La construction a echoue. Verifie les messages ci-dessus.
)
pause
