#!/bin/bash
# ============================================================
#  RadioContest AI - Construction de l'application macOS
#  Produit : dist/RadioContestAI (autonome, sans Python)
#  À LANCER SUR UN MAC (PyInstaller ne cross-compile pas).
# ============================================================
set -e
cd "$(dirname "$0")"

echo "[1/3] Vérification de Python 3..."
command -v python3 >/dev/null 2>&1 || { echo "Python 3 requis : https://www.python.org/downloads/macos/"; exit 1; }

echo "[2/3] Installation de PyInstaller si nécessaire..."
python3 -m pip install --quiet --upgrade pyinstaller

echo "[3/3] Construction de l'application..."
python3 -m PyInstaller --noconfirm --clean radiocontest.spec

echo
if [ -f "dist/RadioContestAI" ]; then
  chmod +x dist/RadioContestAI
  echo "============================================================"
  echo "  OK ! Application prête : dist/RadioContestAI"
  echo "  Lance-la par double-clic (ou ./dist/RadioContestAI)."
  echo
  echo "  Note macOS : au 1er lancement, clic droit → Ouvrir"
  echo "  (Gatekeeper bloque les apps non signées par défaut)."
  echo "============================================================"
else
  echo "[ERREUR] La construction a échoué. Vérifie les messages ci-dessus."
fi
