#!/bin/bash
# ============================================================
#  LogX AI - Construction de l'application macOS
#  Produit : dist/LogXAI (autonome, sans Python)
#  À LANCER SUR UN MAC (PyInstaller ne cross-compile pas).
# ============================================================
set -e
cd "$(dirname "$0")"

echo "[1/3] Vérification de Python 3..."
command -v python3 >/dev/null 2>&1 || { echo "Python 3 requis : https://www.python.org/downloads/macos/"; exit 1; }

echo "[2/4] Installation des dépendances (requirements.txt)..."
# Indispensable AVANT PyInstaller : il n'embarque que les bibliothèques
# importables au moment du build. Sans cette étape, un poste frais produit
# une app sans CAT série, sans keyer vocal, sans EME — silencieusement.
python3 -m pip install --quiet -r requirements.txt

echo "[3/4] Installation de PyInstaller si nécessaire..."
python3 -m pip install --quiet --upgrade pyinstaller

echo "[4/4] Construction de l'application..."
python3 -m PyInstaller --noconfirm --clean logx.spec

echo
if [ -f "dist/LogXAI" ]; then
  chmod +x dist/LogXAI
  echo "============================================================"
  echo "  OK ! Application prête : dist/LogXAI"
  echo "  Lance-la par double-clic (ou ./dist/LogXAI)."
  echo
  echo "  Note macOS : au 1er lancement, clic droit → Ouvrir"
  echo "  (Gatekeeper bloque les apps non signées par défaut)."
  echo "============================================================"
else
  echo "[ERREUR] La construction a échoué. Vérifie les messages ci-dessus."
fi
