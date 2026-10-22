"""Passo 11a, dati: tabelle ed evidenziatore nel testo salvato (lettura, scrittura, collegamenti nelle celle)."""
from harness import *
app()
import html
import random
import re
import time
from PySide6.QtGui import QTextDocument
from gmjournal.data import links
from gmjournal.data.models import ElementInput
from gmjournal.ui.editor import markup, styles

ok = []
def check(name, cond):
    ok.append(bool(cond)); print(("PASS " if cond else "FAIL ") + name)

def roundtrip(content):
    doc = QTextDocument(); markup.fill_document(doc, content)
    return markup.export_html(doc)

def cell_contexts(content):
    doc = QTextDocument(); markup.fill_document(doc, content)
    out, block = [], doc.firstBlock()
    while block.isValid():
        out.append((block.text(), styles.context_of(block))); block = block.next()
    return out, doc

a = lambda kind, i, text: f'<a href="gmj://{kind}/{i}">{text}</a>'

# --- Forma canonica: ciò che si salva si rilegge identico ------------------------------------------
design = ('<p>Prima</p><table><tr><th>d6</th><th>Voce</th><th>Vera?</th></tr>'
          f'<tr><td>1–2</td><td>{a("character", 3, "Mira")} nasconde una <span class="hl hl-sabbia"><b>lettera</b></span>.</td><td>Sì</td></tr>'
          '<tr><td>3–4</td><td>Riga uno<br>riga due</td><td></td></tr></table><p>Dopo</p>')
check("tabella con link, evidenziatore e «a capo» nelle celle: si rilegge identica", roundtrip(design) == design)
for content in ('<table><tr><th>a</th></tr></table>',
                '<h2>Titolo</h2><table><tr><th>x</th><th>y</th></tr><tr><td>1</td><td>2</td></tr></table>',
                '<table><tr><th>a</th></tr></table><p></p><table><tr><th>b</th></tr></table>',
                '<ul><li>voce</li></ul><table><tr><th>dopo un elenco</th></tr></table><ol><li>altra</li></ol>',
                '<p>A <span class="hl hl-verde">verde</span> e <span class="hl hl-rosa"><a href="gmj://place/2">link</a></span></p>',
                '<h1><span class="hl hl-ambra">Titolo evidenziato</span></h1>',
                '<div class="box master"><p><span class="hl hl-viola"><i>nota</i></span></p></div>',
                '<ul><li><span class="hl hl-azzurro"><span class="lg">grande</span></span></li></ul>'):
    check(f"forma canonica stabile: {content[:60]}", roundtrip(content) == content)

# --- Letture tolleranti --------------------------------------------------------------------------
check("la prima riga è sempre l'intestazione (anche se scritta con <td>)",
      roundtrip('<table><tr><td>a</td></tr><tr><td>b</td></tr></table>') == '<table><tr><th>a</th></tr><tr><td>b</td></tr></table>')
check("righe di lunghezza diversa: si completano con celle vuote",
      roundtrip('<table><tr><th>a</th><th>b</th></tr><tr><td>1</td></tr></table>') == '<table><tr><th>a</th><th>b</th></tr><tr><td>1</td><td></td></tr></table>')
check("<thead>/<tbody> si leggono",
      roundtrip('<table><thead><tr><th>a</th></tr></thead><tbody><tr><td>b</td></tr></tbody></table>') == '<table><tr><th>a</th></tr><tr><td>b</td></tr></table>')
check("tabella senza righe: si ignora", roundtrip('<p>x</p><table></table><p>y</p>') == '<p>x</p><p>y</p>')
check("nelle celle niente immagini, titoli o elenchi (solo il loro testo)",
      roundtrip('<table><tr><th><img src="immagini/a.png">T</th></tr><tr><td><h2>tit</h2></td></tr><tr><td><ul><li>voce</li></ul></td></tr></table>')
      == '<table><tr><th>T</th></tr><tr><td>tit</td></tr><tr><td>voce</td></tr></table>')
check("una tabella dentro un box: il box si divide attorno alla tabella",
      roundtrip('<div class="box voice"><p>A</p><table><tr><th>x</th></tr></table><p>B</p></div>')
      == '<div class="box voice"><p>A</p></div><table><tr><th>x</th></tr></table><div class="box voice"><p>B</p></div>')
check("evidenziatore di colore sconosciuto: si ignora", roundtrip('<p><span class="hl hl-fucsia">x</span></p>') == '<p>x</p>')
check("dimensione ed evidenziatore nello stesso <span>",
      roundtrip('<p><span class="sm hl hl-verde">x</span></p>') == '<p><span class="hl hl-verde"><span class="sm">x</span></span></p>')
check("grassetto nell'intestazione: l'intestazione è già in grassetto, non si salva due volte",
      roundtrip('<table><tr><th><b>x</b></th></tr></table>') == '<table><tr><th>x</th></tr></table>')
check("le dimensioni non valgono nelle celle", roundtrip('<table><tr><th>a</th></tr><tr><td><span class="lg">b</span></td></tr></table>')
      == '<table><tr><th>a</th></tr><tr><td>b</td></tr></table>')

# --- Struttura nel documento -----------------------------------------------------------------------
blocks, doc = cell_contexts(design)
contexts = [c for t, c in blocks]
check("contesti: intestazione, celle, testo prima e dopo",
      contexts[0] == "body" and contexts[1:4] == ["head"] * 3 and contexts[4:10] == ["cell"] * 6 and contexts[-1] == "body")
head_fmt = next(f for s, e, f in styles.fragments(doc.findBlock(7)))
check("aspetto dell'intestazione: Figtree 12, maiuscolo, grigio", head_fmt.font().pixelSize() == 12
      and head_fmt.font().capitalization().name == "AllUppercase" and head_fmt.foreground().color().name() == "#8a909c")
cell_block = [b for b in [doc.findBlock(p) for p in range(doc.characterCount())] if b.text().startswith("Mira")][0]
fmt = styles.fragments(cell_block)[0][2]
check("aspetto delle celle: Figtree 14", fmt.font().pixelSize() == 14 and fmt.font().families()[0] == "Figtree")
check("margini delle celle applicati al caricamento (14 px dal bordo: 8 della cella + 6 del paragrafo)",
      cell_block.blockFormat().leftMargin() == styles.TABLE_PAD_X - styles.TABLE_PAD_Y)
hl = [f for s, e, f in styles.fragments(cell_block) if f.stringProperty(styles.HIGHLIGHT)]
check("evidenziatore: sfondo trasparente del colore e testo del suo colore normale",
      hl and hl[0].background().color().alpha() < 90 and hl[0].foreground().color().name() == "#d8dbe2")
table = doc.rootFrame().childFrames()[0]
check("la tabella è larga quanto il testo e senza bordi di Qt",
      table.format().width().rawValue() == 100 and table.format().border() == 0)
_, doc2 = cell_contexts('<table><tr><th>a</th></tr></table>')
check("tabella in fondo: dopo c'è un paragrafo per scrivere sotto", styles.table_of(doc2.lastBlock()) is None)
check("…e il paragrafo che Qt tiene prima non si salva", markup.export_html(doc2) == '<table><tr><th>a</th></tr></table>')

# --- Collegamenti nelle celle: indice e «Citata da» ----------------------------------------------------
repo = new_repo("Tabelle")
cats = repo.categories("character")
mira = repo.create_element(ElementInput("character", "Mira Vesperi", cats[0].id, None, "", ""))
page = repo.create_page("Voci")
repo.save_content(page, f'<table><tr><th>Chi</th></tr><tr><td><span class="hl hl-rosa">{a("character", mira, "Mira")}</span></td></tr></table>')
check("un link dentro una cella (anche evidenziato) entra nell'indice dei collegamenti",
      [t.id for t in repo.cited_by("character", mira)] == [page] and links.extract_targets(repo.page(page).content) == [("character", mira)])
repo.delete_element(mira)
check("eliminando l'elemento il link nella cella diventa testo", repo.page(page).content == '<table><tr><th>Chi</th></tr><tr><td><span class="hl hl-rosa">Mira</span></td></tr></table>')

# --- 1500 documenti casuali: salvati, riletti e risalvati danno lo stesso testo --------------------
rng = random.Random(11)
WORDS = ["la", "locanda", "del", "Corvo", "è", "più", "silenziosa", "d'Ombra", "<x>", "&", "perché", "1–2", "Sì"]

def inline(depth=0, allow_size=True):
    parts = []
    for _ in range(rng.randint(0, 4)):
        text = html.escape(" ".join(rng.choice(WORDS) for _ in range(rng.randint(1, 3))), quote=False)
        roll = rng.random()
        if roll < 0.1:
            parts.append("<br>")
        if depth < 2 and roll < 0.55:
            tag = rng.choice(["b", "i", "u", "hl", "a", "size"] if allow_size else ["b", "i", "u", "hl", "a"])
            inner = text + inline(depth + 1, allow_size)
            if tag == "hl":
                parts.append(f'<span class="hl hl-{rng.choice(styles.HIGHLIGHTS)}">{inner}</span>')
            elif tag == "a":
                parts.append(a(rng.choice(["character", "place", "page"]), rng.randint(1, 9), inner))
            elif tag == "size":
                parts.append(f'<span class="{rng.choice(["sm", "lg"])}">{inner}</span>')
            else:
                parts.append(f"<{tag}>{inner}</{tag}>")
        else:
            parts.append(text)
    return "".join(parts)

def table():
    rows, cols = rng.randint(1, 4), rng.randint(1, 4)
    out = []
    for r in range(rows):
        tag = "th" if r == 0 else "td"
        out.append("<tr>" + "".join(f"<{tag}>{inline(allow_size=False)}</{tag}>" for _ in range(rng.randint(1, cols))) + "</tr>")
    return "<table>" + "".join(out) + "</table>"

def document():
    parts = []
    for _ in range(rng.randint(0, 7)):
        kind = rng.choice(["p", "p", "h", "ul", "ol", "box", "table", "table"])
        if kind == "p":
            parts.append(f"<p>{inline()}</p>")
        elif kind == "h":
            level = rng.randint(1, 3)
            parts.append(f"<h{level}>{inline(allow_size=False)}</h{level}>")
        elif kind in ("ul", "ol"):
            parts.append(f"<{kind}>" + "".join(f"<li>{inline()}</li>" for _ in range(rng.randint(1, 3))) + f"</{kind}>")
        elif kind == "box":
            inner = "".join(f"<p>{inline()}</p>" if rng.random() < 0.8 else table() for _ in range(rng.randint(1, 3)))
            parts.append(f'<div class="box {rng.choice(styles.BOX_KINDS)}">{inner}</div>')
        else:
            parts.append(table())
    return "".join(parts)

def plain(content):
    return html.unescape(re.sub(r"<[^>]+>", "", content))

stable = same_text = 0
first_bad = None
start = time.perf_counter()
for i in range(1500):
    source = document()
    once = roundtrip(source)
    twice = roundtrip(once)
    stable += once == twice
    same_text += plain(once) == plain(source)
    if (once != twice or plain(once) != plain(source)) and first_bad is None:
        first_bad = (source, once, twice)
print(f"  (1500 documenti in {time.perf_counter() - start:.1f} s)")
if first_bad:
    print("  primo caso diverso:\n   ", first_bad[0], "\n   ", first_bad[1], "\n   ", first_bad[2])
check("1500 documenti casuali con tabelle ed evidenziatore: risalvati danno lo stesso testo", stable == 1500)
check("…e nessuna parola si perde", same_text == 1500)

print(f"\n{sum(ok)}/{len(ok)}")
