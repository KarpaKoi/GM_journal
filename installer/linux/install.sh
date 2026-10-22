#!/usr/bin/env bash
# Installa GM Journal per l'utente corrente (nessun permesso di amministratore).
# Programma in ~/.local/opt/GMJournal, voce nel menu delle applicazioni, comando «gm-journal».
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
DEST="$HOME/.local/opt/GMJournal"
BIN="$HOME/.local/bin"
APPS="$HOME/.local/share/applications"
ICONS="$HOME/.local/share/icons/hicolor/256x256/apps"

rm -rf "$DEST"
mkdir -p "$(dirname "$DEST")" "$BIN" "$APPS" "$ICONS"
cp -r "$HERE/GMJournal" "$DEST"
cp "$HERE/uninstall.sh" "$DEST/uninstall.sh"        # per toglierlo: ~/.local/opt/GMJournal/uninstall.sh
ln -sf "$DEST/GMJournal" "$BIN/gm-journal"
cp "$HERE/gmjournal.png" "$ICONS/gm-journal.png"
sed "s|@EXEC@|$DEST/GMJournal|" "$HERE/gm-journal.desktop" > "$APPS/gm-journal.desktop"
command -v update-desktop-database >/dev/null && update-desktop-database "$APPS" || true
command -v gtk-update-icon-cache >/dev/null && gtk-update-icon-cache -q -t "$HOME/.local/share/icons/hicolor" || true

echo "GM Journal installato: lo trovi nel menu delle applicazioni, oppure scrivi «gm-journal» nel terminale."
echo "Le campagne si salvano in ~/Documenti/GM Journal (o ~/Documents/GM Journal)."
echo "Per toglierlo: $DEST/uninstall.sh (le campagne non si toccano)."

# Qt apre la finestra con il suo plugin «xcb», che usa alcune librerie di sistema: se ne manca una, il programma lanciato
# dal menu non si aprirebbe e senza dire perché. Le cerchiamo ora, chiedendo al sistema quali non trova
# (con `set -o pipefail` un `grep` che non trova nulla farebbe fallire la riga: per questo `|| true`)
MANCANTI="$(ldd "$DEST/_internal/PySide6/Qt/plugins/platforms/libqxcb.so" 2>/dev/null | awk '/not found/ {print $1}' | sort -u || true)"
if [ -n "$MANCANTI" ]; then
    echo
    echo "ATTENZIONE: mancano queste librerie di sistema, che Qt usa per aprire la finestra:"
    echo "$MANCANTI" | sed 's/^/  /'
    echo "Installale con il comando della tua distribuzione, poi il programma parte:"
    echo "  Debian/Ubuntu:  sudo apt install libxcb-cursor0 libxcb-icccm4 libxcb-image0 libxcb-keysyms1 libxcb-render-util0 libxcb-util1 libxcb-xkb1 libxkbcommon-x11-0"
    echo "  Fedora:         sudo dnf install xcb-util-cursor xcb-util-wm xcb-util-image xcb-util-keysyms xcb-util-renderutil xcb-util libxcb libxkbcommon-x11"
    echo "  Arch:           sudo pacman -S xcb-util-cursor xcb-util-wm xcb-util-image xcb-util-keysyms xcb-util-renderutil xcb-util libxcb libxkbcommon-x11"
fi
