#!/usr/bin/env bash
# Toglie GM Journal. Le campagne (cartella «GM Journal» in Documenti) NON vengono toccate.
set -euo pipefail
rm -rf "$HOME/.local/opt/GMJournal"
rm -f "$HOME/.local/bin/gm-journal" \
      "$HOME/.local/share/applications/gm-journal.desktop" \
      "$HOME/.local/share/icons/hicolor/256x256/apps/gm-journal.png"
command -v update-desktop-database >/dev/null && update-desktop-database "$HOME/.local/share/applications" || true
echo "GM Journal rimosso. Le tue campagne sono rimaste dove sono."
