"""Aspetto dell'app: l'unico posto con colori, misure, caratteri e foglio di stile."""

import logging
from pathlib import Path
from string import Template

from PySide6.QtGui import QColor, QFont, QFontDatabase, QPalette
from PySide6.QtWidgets import QApplication

ASSETS_DIR = Path(__file__).resolve().parents[1] / "assets"

# --- Colori -----------------------------------------------------------------
BG = "#14161a"            # sfondo generale
SURFACE = "#1b1e24"       # barre, pannelli, card
HOVER = "#262a33"         # elemento selezionato / premuto
HOVER_SOFT = "#20232a"    # elemento sotto il mouse
BORDER = "#2a2e37"
BORDER_STRONG = "#343a46"
DISABLED = "#4a4f5a"
TEXT = "#d8dbe2"
TEXT_ACTIVE = "#eef0f4"   # voce attiva nelle liste
TEXT_SOFT = "#b4b9c4"     # voce non attiva nelle liste
MUTED = "#8a909c"
ACCENT = "#9db7e8"
ACCENT_HOVER = "#b1c5ec"
DANGER = "#e39aa6"        # azioni che eliminano
DANGER_TEXT = "#f2bcc6"
POPUP_BG = "#1d2128"
MENU_BG = "#222630"
MENU_HOVER = "#2d3340"
OVERLAY = "#a30a0b0e"     # velo scuro dietro i popup (ARGB)

# Editor di testo
TOOLBAR_BG = "#171a1f"        # barra degli strumenti
CONTROL_BG = "#1f232a"        # menu a tendina e gruppo dimensioni nella barra
SEGMENT_ACTIVE = "#323845"    # dimensione del testo attiva
EDITOR_TEXT = "#d3d6de"       # testo della pagina
FIELD_TEXT = "#cfd3dc"        # testo dei campi di una scheda
SELECTION_BG = "#3a4b73"      # testo selezionato
SPELL_ERROR = "#ef7b8a"       # onda sotto le parole sbagliate
FIND_MATCH = "#e0cfa0"        # cerca nella pagina: le occorrenze (sabbia, con trasparenza)
# La scheda tecnica di una creatura, come sui manuali: carta beige, titoli e filetti rossi, bordi arancio.
STAT_PAPER = "#fdf1dc"
STAT_INK = "#1f1b16"
STAT_RED = "#7a200d"
STAT_EDGE = "#e69a28"
# Evidenziatore: nome nel testo salvato -> (nome mostrato, colore). Sotto il testo il colore è trasparente.
HIGHLIGHT_COLORS = {
    "sabbia": ("Sabbia", "#e0cfa0"),
    "verde": ("Verde", "#8fcca0"),
    "azzurro": ("Azzurro", "#8cb8e8"),
    "rosa": ("Rosa", "#e39aa6"),
    "viola": ("Viola", "#b4a4e6"),
    "ambra": ("Ambra", "#e3b878"),
}
TABLE_CELL_ACTIVE = "#232833"   # cella di tabella in cui si scrive
TABLE_GRID_LINE = "#3a4050"     # quadratini della griglia per scegliere la misura di una tabella
# Box nel testo: tipo -> (sfondo, colore dell'etichetta e dell'icona, colore del testo).
BOX_COLORS = {
    "voice": ("#28251d", "#e0cfa0", "#e6dfc9"),    # Da leggere a voce
    "master": ("#25222f", "#b4a4e6", "#d4cfe6"),   # Nota del Master
}
ENCOUNTER_BOX = ("#2b2326", "#e39aa6", "#e6d3d6")  # il box «Incontro» nel testo: (sfondo, etichetta e icone, nomi)

# Colori delle sezioni: solo per icone, pallini e tinte.
SECTION_COLORS = {
    "scrittura": "#e0cfa0",
    "personaggi": "#8cb8e8",
    "luoghi": "#8fcca0",
    "organizzazioni": "#e3b878",
    "culture": "#c8d98c",
    "incontri": "#e39aa6",
    "immagini": "#d9a0c4",
    "mappe": "#7fcfc8",
    "grafi": "#b4a4e6",
    "impostazioni": MUTED,
}

# Come si colora la difficoltà di un incontro (chiavi di dnd.DIFFICULTY_LABELS).
DIFFICULTY_COLORS = {"trivial": MUTED, "easy": "#8fcca0", "medium": "#e3b878", "hard": "#e8946a", "deadly": "#e39aa6"}

# Colori selezionabili per le categorie (e i pin): chiave -> (nome, colore).
CATEGORY_COLORS = {
    "blue": ("Blu", "#8cb8e8"),
    "teal": ("Verde acqua", "#7fcfc8"),
    "green": ("Verde", "#8fcca0"),
    "amber": ("Ambra", "#e3b878"),
    "pink": ("Rosa", "#e39aa6"),
    "violet": ("Viola", "#b4a4e6"),
    "mauve": ("Malva", "#d9a0c4"),
    "gray": ("Grigio", "#a3a8b5"),
}

# Colori della copertina di una campagna: chiave -> (nome, colore dell'icona, tinta di sfondo).
CAMPAIGN_COLORS = {
    "blue": ("Blu", "#8cb8e8", "#1f2a3a"),
    "green": ("Verde", "#8fcca0", "#1f2e27"),
    "amber": ("Ambra", "#e3b878", "#33291c"),
    "pink": ("Rosa", "#e39aa6", "#33222a"),
    "violet": ("Viola", "#b4a4e6", "#2a2535"),
    "gray": ("Grigio", "#a3a8b5", "#272a31"),
}

# --- Misure (pixel logici: Qt le adatta alla scala dello schermo) ----------------
TOPBAR_HEIGHT = 52
SIDEBAR_WIDTH = 208
SIDEBAR_WIDTH_COLLAPSED = 64
PANEL_WIDTH = 320
RADIUS_CONTROL = 8

# --- Caratteri --------------------------------------------------------------
UI_FAMILY = "Figtree"
SERIF_FAMILY = "Newsreader"
_FALLBACK_FAMILIES = {UI_FAMILY: "Segoe UI", SERIF_FAMILY: "Georgia"}
_FONT_FILES = (
    "Figtree-Regular.ttf", "Figtree-Medium.ttf", "Figtree-SemiBold.ttf",
    "Newsreader-Regular.ttf", "Newsreader-Medium.ttf", "Newsreader-SemiBold.ttf",
    "Newsreader-Italic.ttf", "Newsreader-SemiBoldItalic.ttf",
)

_STYLESHEET = Template("""
QToolTip { background: $surface; color: $text; border: 1px solid $border; padding: 4px 8px; }

/* Barre principali */
#TopBar     { background: $surface; border-bottom: 1px solid $border; }
#Sidebar    { background: $surface; border-right: 1px solid $border; }
#RightPanel { background: $surface; border-left: 1px solid $border; }
#RightPanel QAbstractScrollArea { background: $surface; }     /* le aree a scorrimento dei pannelli non coprono il colore del pannello */

/* Pulsanti a icona della barra superiore */
QToolButton#BarButton { background: transparent; border: none; border-radius: ${radius}px; }
QToolButton#BarButton:hover, QToolButton#BarButton:checked { background: $hover; }

/* Campi con un'icona a sinistra: ricerca globale, «cerca nella pagina», «aggiungi una cosa da fare» */
#SearchBox, #FindField, #TodoField { background: $bg; border: 1px solid $border; border-radius: ${radius}px; }
#SearchBox[focused="true"], #FindField[focused="true"], #TodoField[focused="true"] { border-color: $accent; }
#SearchBox QLineEdit, #FindField QLineEdit, #TodoField QLineEdit { background: transparent; border: none; padding: 0; font-size: 13px; }
QTextEdit#TodoEdit { background: transparent; border: none; padding: 0; font-size: 14px; }
#SearchHint { color: $muted; font-size: 11px; border: 1px solid $border; border-radius: 4px; padding: 2px 6px; }

/* Testi */
QLabel#Muted, QLabel#GroupLabel { color: $muted; }
QLabel#FieldLabel { font-size: 13px; font-weight: 500; }

QFrame#Divider { background: $border_strong; }

/* Editor di testo */
QTextEdit#RichEditor { background: $bg; border: none; selection-background-color: $selection; selection-color: $text_active; }
QTextEdit#FieldText { background: transparent; border: none; color: $field_text; selection-background-color: $selection; selection-color: $text_active; }
#TargetPopup { background: $menu_bg; border: 1px solid $border_strong; border-radius: 12px; }
QListWidget#TargetList { background: transparent; border: none; outline: none; }

/* Pagina aperta: titolo e albero dei capitoli */
QLineEdit#PageTitle { background: transparent; border: none; padding: 0; }
QTreeWidget#PageTree { background: transparent; border: none; outline: none; selection-background-color: transparent; }

/* Barra dell'editor */
#FormatToolbar { background: $toolbar; border-bottom: 1px solid $border; }
QToolButton#FormatButton { background: transparent; border: none; border-radius: ${radius}px; }
QToolButton#FormatButton:hover { background: $hover_soft; }
QToolButton#FormatButton:checked { background: $hover; }
QToolButton#FormatButton[split="left"] { border-top-right-radius: 0; border-bottom-right-radius: 0; padding-bottom: 4px; }
QToolButton#FormatButton[split="right"] { border-top-left-radius: 0; border-bottom-left-radius: 0; }
QToolButton#LanguageButton { background: transparent; border: none; border-radius: ${radius}px; padding: 0 8px; color: $text_soft; }
QToolButton#LanguageButton:hover { background: $hover_soft; }
QToolButton#LanguageButton:checked { color: $accent; }
QToolButton#LanguageButton:disabled { color: $disabled; }
#TableBar { background: $menu_bg; border: 1px solid $border_strong; border-radius: 10px; }
QToolButton#TableBarButton { background: transparent; border: none; border-radius: 6px; padding: 0 10px 0 8px; }
QToolButton#TableBarButton:hover { background: $menu_hover; }
QToolButton#TablePlus { background: $menu_hover; border: none; border-radius: 12px; }
QToolButton#TablePlus:hover { background: $disabled; }
QFrame#ToolbarDivider { background: $border_strong; }
#FindBar { background: $menu_bg; border: 1px solid $border_strong; border-radius: 12px; }
QToolButton#FindButton { background: transparent; border: none; border-radius: 6px; }
QToolButton#FindButton:hover { background: $menu_hover; }
QFrame#SheetCard { background: $surface; border-radius: 12px; }
QFrame#SheetCard[gm="true"] { background: $master_bg; }
QLineEdit#InlineEdit { background: transparent; border: 1px solid transparent; border-radius: 7px; padding: 0 8px; color: $text_soft; }
QLineEdit#InlineEdit:hover { border-color: $border; }
QLineEdit#InlineEdit:focus { background: $bg; border-color: $accent; color: $text_active; }
QToolButton#BackLink { background: transparent; border: none; color: $muted; padding: 0 4px 0 0; font-size: 13px; }
QToolButton#BackLink:hover { color: $text; }
#NoteEditor #FormatToolbar { border-top-left-radius: 11px; border-top-right-radius: 11px; }

/* Campi di testo */
QLineEdit, QPlainTextEdit {
    background: $bg; border: 1px solid $border_strong; border-radius: 10px;
    padding: 0 14px; color: $text_active; selection-background-color: $accent; selection-color: $bg;
}
QPlainTextEdit { padding: 8px 10px; }
QLineEdit:focus, QPlainTextEdit:focus { border-color: $accent; }

/* Popup */
#PopupCard { background: $popup_bg; border: 1px solid $border_strong; border-radius: 16px; }
#MenuPanel { background: $menu_bg; border: 1px solid $border_strong; border-radius: 12px; }
QPushButton#PrimaryButton { background: $accent; color: $bg; border: none; font-weight: 600; padding: 0 22px; }
QPushButton#PrimaryButton:hover { background: $accent_hover; }
QPushButton#PrimaryButton:disabled { background: $hover; color: $disabled; }
QPushButton#SuggestionChip {
    border: 1px dashed $disabled; border-radius: 14px; padding: 0 12px; min-height: 28px; font-size: 13px; color: $text_soft;
}
QPushButton#SuggestionChip:hover { background: $hover; border-style: solid; color: $text_active; }
QPushButton#DashedButton {
    border: 1px dashed $disabled; border-radius: 8px; padding: 0 12px; min-height: 30px; font-size: 13px;
}
QPushButton#LinkButton {
    border: none; background: transparent; padding: 0 8px; min-height: 30px;
    font-size: 13px; font-weight: 600; text-decoration: underline;
}
QFrame#Chip { background: $hover; border-radius: 8px; }
QFrame#InfoBox { background: $bg; border: 1px solid $border_strong; border-radius: 10px; }
QToolButton#ChipButton { background: transparent; border: none; border-radius: 5px; }
QToolButton#ChipButton:hover { background: $border; }
QToolButton#CloseButton { background: transparent; border: none; border-radius: ${radius}px; }
QToolButton#CloseButton:hover { background: $hover; }
QToolButton#CardMenuButton { background: rgba(20, 22, 26, 153); border: none; border-radius: ${radius}px; }
QToolButton#CardMenuButton:hover { background: rgba(20, 22, 26, 217); }

/* Barra di avanzamento (backup e ripristino) */
QProgressBar { background: $bg; border: none; border-radius: 4px; }
QProgressBar::chunk { background: $accent; border-radius: 4px; }

/* Pulsanti con contorno */
QPushButton {
    background: transparent; border: 1px solid $border_strong; border-radius: 10px;
    padding: 0 16px; min-height: 36px; font-weight: 500;
}
QPushButton:hover { background: $hover; }

/* Mappa: le barre che galleggiano sopra */
QFrame#FloatingBar { background: rgba(27, 30, 36, 240); border: 1px solid $border; border-radius: 10px; }

/* Barre di scorrimento */
QScrollBar:vertical { background: transparent; width: 10px; margin: 2px; }
QScrollBar::handle:vertical { background: $border; border-radius: 3px; min-height: 30px; }
QScrollBar::handle:vertical:hover { background: $disabled; }
QScrollBar:horizontal { background: transparent; height: 10px; margin: 2px; }
QScrollBar::handle:horizontal { background: $border; border-radius: 3px; min-width: 30px; }
QScrollBar::handle:horizontal:hover { background: $disabled; }
QScrollBar::add-line, QScrollBar::sub-line { width: 0; height: 0; }
""")


def category_color(key: str) -> str:
    """Il colore di una categoria (se la chiave non esiste più, il grigio)."""
    return CATEGORY_COLORS.get(key, CATEGORY_COLORS["gray"])[1]


def tint(color: str, alpha: float = 0.14) -> QColor:
    """Una tinta leggera di `color`, per gli sfondi dietro iniziali e icone."""
    result = QColor(color)
    result.setAlphaF(alpha)
    return result


def solid_button_style(color: str) -> str:
    """Foglio di stile per un pulsante pieno nel colore di una sezione («Nuovo personaggio»)."""
    return (f"QPushButton {{ background: {color}; color: {BG}; border: none; font-weight: 600; padding: 0 16px 0 12px; }}"
            f"QPushButton:hover {{ background: {QColor(color).lighter(112).name()}; }}")


def _font(family: str, px: int, weight: int, spacing: float) -> QFont:
    font = QFont()
    font.setFamilies([family, _FALLBACK_FAMILIES[family]])
    font.setPixelSize(px)
    font.setWeight(QFont.Weight(weight))
    if spacing:  # spacing è espresso in frazioni del corpo (0.08 = 0,08 em)
        font.setLetterSpacing(QFont.AbsoluteSpacing, spacing * px)
    return font


def ui_font(px: int = 14, weight: int = 400, spacing: float = 0.0) -> QFont:
    """Carattere dell'interfaccia (Figtree)."""
    return _font(UI_FAMILY, px, weight, spacing)


def serif_font(px: int, weight: int = 500, spacing: float = 0.0) -> QFont:
    """Carattere per titoli ed editor di testo (Newsreader)."""
    return _font(SERIF_FAMILY, px, weight, spacing)


def load_fonts() -> None:
    """Registra i caratteri in assets/fonts. Se manca un file l'app usa quello di riserva."""
    for name in _FONT_FILES:
        if QFontDatabase.addApplicationFont(str(ASSETS_DIR / "fonts" / name)) < 0:
            logging.warning("Carattere non caricato: %s", name)


def apply(app: QApplication) -> None:
    """Applica tema scuro, caratteri e foglio di stile a tutta l'applicazione."""
    app.setStyle("Fusion")
    app.setFont(ui_font())

    palette = QPalette()
    for role, color in {
        QPalette.Window: BG,
        QPalette.Base: BG,
        QPalette.AlternateBase: SURFACE,
        QPalette.WindowText: TEXT,
        QPalette.Text: TEXT,
        QPalette.ButtonText: TEXT,
        QPalette.Button: SURFACE,
        QPalette.PlaceholderText: MUTED,
        QPalette.ToolTipBase: SURFACE,
        QPalette.ToolTipText: TEXT,
        QPalette.Highlight: ACCENT,
        QPalette.HighlightedText: BG,
    }.items():
        palette.setColor(role, QColor(color))
    palette.setColor(QPalette.Disabled, QPalette.ButtonText, QColor(DISABLED))
    palette.setColor(QPalette.Disabled, QPalette.WindowText, QColor(DISABLED))
    palette.setColor(QPalette.Disabled, QPalette.Text, QColor(DISABLED))
    app.setPalette(palette)

    app.setStyleSheet(_STYLESHEET.substitute(
        bg=BG, surface=SURFACE, hover=HOVER, border=BORDER, border_strong=BORDER_STRONG,
        text=TEXT, text_active=TEXT_ACTIVE, muted=MUTED, disabled=DISABLED, accent=ACCENT,
        accent_hover=ACCENT_HOVER, popup_bg=POPUP_BG, menu_bg=MENU_BG, menu_hover=MENU_HOVER, radius=RADIUS_CONTROL, selection=SELECTION_BG,
        toolbar=TOOLBAR_BG, hover_soft=HOVER_SOFT, field_text=FIELD_TEXT,
        text_soft=TEXT_SOFT, master_bg=BOX_COLORS["master"][0],
    ))
