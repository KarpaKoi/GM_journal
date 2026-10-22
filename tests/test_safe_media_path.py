"""`safe_media_path`: i percorsi delle immagini non devono mai portare fuori dalla cartella della campagna."""

import os

import pytest

from gmjournal.data.image_refs import drop_unsafe, safe_media_path


def test_accetta_un_percorso_nella_cartella_immagini(tmp_path):
    assert safe_media_path(tmp_path, "immagini/a.png") == (tmp_path / "immagini" / "a.png").resolve()


def test_accetta_le_sottocartelle_e_i_nomi_con_spazi_e_accenti(tmp_path):
    assert safe_media_path(tmp_path, "immagini/sotto/Città è.png") == (tmp_path / "immagini" / "sotto" / "Città è.png").resolve()


@pytest.mark.parametrize("relative", [
    "../x.png",                     # esce dalla cartella
    "/etc/x",                       # assoluto
    "C:\\x.png",                    # unità di Windows
    "\\\\srv\\sh\\x.png",           # rete (UNC): farebbe partire una connessione SMB
    "immagini\\..\\..\\x",          # backslash con ..
    "immagini/C:x.png",             # unità dentro il percorso
    "immagini/../../x.png",         # .. dentro il percorso
    "immagini/../campagna.db",      # .. che resta nella campagna ma esce da immagini/
    "campagna.db",                  # non è un'immagine
    "immagini",                     # la cartella stessa
    "immagini/",
    "",
    None,
    "immagini/a\x00.png",           # carattere nullo
    "file:///C:/x.png",             # un indirizzo
    "//srv/sh/x.png",
])
def test_rifiuta_i_percorsi_non_fidati(tmp_path, relative):
    assert safe_media_path(tmp_path, relative) is None


def test_rifiuta_un_collegamento_simbolico_che_esce_dalla_campagna(tmp_path):
    outside = tmp_path / "fuori"
    outside.mkdir()
    (outside / "segreto.png").write_bytes(b"x")
    campaign = tmp_path / "campagna"
    (campaign / "immagini").mkdir(parents=True)
    try:
        os.symlink(outside / "segreto.png", campaign / "immagini" / "link.png")
    except (OSError, NotImplementedError):
        pytest.skip("i collegamenti simbolici non sono disponibili qui")
    assert safe_media_path(campaign, "immagini/link.png") is None


def test_rifiuta_una_cartella_immagini_che_e_un_collegamento_fuori(tmp_path):
    outside = tmp_path / "fuori"
    outside.mkdir()
    campaign = tmp_path / "campagna"
    campaign.mkdir()
    try:
        os.symlink(outside, campaign / "immagini", target_is_directory=True)
    except (OSError, NotImplementedError):
        pytest.skip("i collegamenti simbolici non sono disponibili qui")
    assert safe_media_path(campaign, "immagini/a.png") is None


def test_drop_unsafe_toglie_solo_le_immagini_non_valide(tmp_path):
    text = ('<p>a<img src="immagini/ok.png" width="5">b<img src="../../x.png">c<img width="3" src=\'C:\\y.png\'>'
            'd<IMG SRC="\\\\srv\\sh\\z.png">e<img alt="&gt;" src="/etc/passwd"></p>')
    assert drop_unsafe(text, tmp_path) == '<p>a<img src="immagini/ok.png" width="5">bcde</p>'


def test_drop_unsafe_capisce_le_entita_html(tmp_path):
    assert drop_unsafe('<img src="immagini&#47;..&#47;..&#47;x.png">', tmp_path) == ""
    assert drop_unsafe('<img src="immagini/a&amp;b.png">', tmp_path) == '<img src="immagini/a&amp;b.png">'
