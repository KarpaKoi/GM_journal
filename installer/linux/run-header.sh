#!/bin/sh
# GM Journal per Linux: installatore in un solo file. Si lancia con  sh GMJournal-<versione>-linux-<arch>.run
# (o, dopo averlo reso eseguibile, con un doppio clic o ./GMJournal-….run). Non servono permessi di amministratore.
# Dopo questa riga di testo c'è il programma compresso: lo script lo estrae in una cartella provvisoria, lancia install.sh e la elimina.
set -eu
command -v xz >/dev/null 2>&1 || { echo "Manca il comando «xz» (pacchetto xz-utils, o xz): installalo e riprova." >&2; exit 1; }
command -v bash >/dev/null 2>&1 || { echo "Manca «bash»: installalo e riprova." >&2; exit 1; }
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT
echo "Estraggo GM Journal…"
tail -n +@SKIP@ "$0" | tar -xJf - -C "$TMP"
bash "$TMP"/*/install.sh
exit 0
