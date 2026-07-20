@echo off
REM ============================================================
REM  LogX AI - Construction de l'executable Windows
REM  Produit : dist\LogXAI.exe (autonome, sans Python)
REM ============================================================
setlocal
cd /d "%~dp0"

echo [1/2] Installation de PyInstaller si necessaire...
python -m pip install --quiet --upgrade pyinstaller

echo [2/2] Construction de l'executable...
python -m PyInstaller --noconfirm --clean logx.spec

echo.
if exist "dist\LogXAI.exe" (
  echo  ============================================================
  echo   OK ! Executable pret : dist\LogXAI.exe
  echo   Double-clique dessus pour lancer LogX AI.
  echo  ============================================================
) else (
  echo  [ERREUR] La construction a echoue. Verifie les messages ci-dessus.
)
pause
