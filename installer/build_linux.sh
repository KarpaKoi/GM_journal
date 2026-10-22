#!/usr/bin/env bash
# Costruisce GM Journal per Linux: un solo file autoestraente installer/out/GMJournal-<versione>-linux-<arch>.run
# (dentro: il programma, install.sh e uninstall.sh). Serve Python 3.11+ con il modulo venv, e xz.
set -euo pipefail
cd "$(dirname "$0")/.."
OUT=installer/out

echo "[1/4] Preparo gli strumenti necessari..."
python3 -m venv "$OUT/venv"
# PySide6_Essentials ha tutti i moduli che il programma usa (QtCore, QtGui, QtWidgets, QtSvg): il pacchetto PySide6 completo ne aggiunge altri, pesantissimi e inutili qui
"$OUT/venv/bin/pip" install --quiet --upgrade pip pyinstaller "PySide6_Essentials>=6.6" "spylls>=0.1.7"

echo "[2/4] Costruisco il programma (ci vuole qualche minuto)..."
"$OUT/venv/bin/pyinstaller" --noconfirm --clean --distpath "$OUT/dist" --workpath "$OUT/build" installer/gmjournal.spec

echo "[3/4] Tolgo ciò che il programma non usa..."
python3 installer/linux/prune.py "$OUT/dist/GMJournal"

echo "[4/4] Impacchetto in un solo file..."
VERSION=$("$OUT/venv/bin/python" -c "import gmjournal; print(gmjournal.__version__)")
NAME="GMJournal-$VERSION-linux-$(uname -m)"
PKG="$OUT/$NAME"
rm -rf "$PKG"; mkdir -p "$PKG"
cp -r "$OUT/dist/GMJournal" "$PKG/"
cp installer/linux/install.sh installer/linux/uninstall.sh installer/linux/gm-journal.desktop assets/gmjournal.png "$PKG/"
chmod 755 "$PKG/install.sh" "$PKG/uninstall.sh" "$PKG/GMJournal/GMJournal"
chmod 644 "$PKG/gmjournal.png" "$PKG/gm-journal.desktop"      # copiati dal progetto: senza il bit «eseguibile»
# l'intestazione dice da quale riga comincia l'archivio (il numero di righe non cambia sostituendo @SKIP@)
SKIP=$(( $(wc -l < installer/linux/run-header.sh) + 1 ))
sed "s/@SKIP@/$SKIP/" installer/linux/run-header.sh > "$OUT/$NAME.run"
tar -C "$OUT" --owner=0 --group=0 --numeric-owner -cf - "$NAME" | xz -9e -T0 >> "$OUT/$NAME.run"
chmod 755 "$OUT/$NAME.run"
echo "Fatto: $OUT/$NAME.run"
