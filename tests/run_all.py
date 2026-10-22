"""Lancia tutte le prove automatiche (senza schermo) e stampa un riepilogo.

    python tests/run_all.py            # tutte
    python tests/run_all.py t_img_ui   # una sola

Ogni prova stampa PASS/FAIL per controllo e, in fondo, «N/N» (o «N/N prove superate»). Se una prova resta ferma, di solito
si è aperto un popup modale che nessuno chiude: nelle prove si pilota con `drive(...)` (vedi t_img_ui.py).
"""
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
ORDER = ["t_data4", "t_img_data", "t_field", "t_mention_reg", "t_scrittura", "t_preview", "t_leader", "t_final",
         "t_sheet_flow", "t_search", "t_img_ui", "t_img_more", "t_maps_data", "t_maps_ui", "t_graphs_data", "t_graphs_ui", "t_graph_edge_links",
         "t_settings_data", "t_settings_ui",
         "t_backup_data", "t_backup_ui", "t_thumbs", "t_tables_data", "t_tables_ui", "t_spelling", "t_spell_ui", "t_find_ui",
         "t_writing_data", "t_writing_ui", "t_link_preview", "t_creatures_data", "t_creatures_ui", "t_encounters_data", "t_encounters_ui", "t_stat_block", "t_encounter_box", "t_crumbs", "t_relation_text", "t_bookmarks", "t_preview_long", "t_portable", "t_culture"]


def run(name: str) -> tuple[str, bool]:
    env = {**os.environ, "QT_QPA_PLATFORM": "offscreen"}
    try:
        with tempfile.TemporaryDirectory() as scratch:        # alcune prove salvano screenshot nella cartella corrente
            out = subprocess.run([sys.executable, str(HERE / f"{name}.py")], capture_output=True, text=True, env=env,
                                 timeout=240, cwd=scratch).stdout
    except subprocess.TimeoutExpired:
        return "ferma (popup non chiuso?)", False
    failed = [line for line in out.splitlines() if line.startswith("FAIL")]
    found = re.findall(r"^(\d+)/(\d+)", out, re.M)
    if not found:
        return "nessun riepilogo (errore?)", False
    done, total = map(int, found[-1])
    return f"{done}/{total}" + ("".join(f"\n    {line}" for line in failed)), done == total and not failed


if __name__ == "__main__":
    names = sys.argv[1:] or ORDER
    results = {name: run(name) for name in names}
    for name, (text, good) in results.items():
        print(f"{'OK  ' if good else 'KO  '}{name}: {text}")
    sys.exit(0 if all(good for _, good in results.values()) else 1)
