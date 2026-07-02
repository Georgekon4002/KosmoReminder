"""
Application stylesheet – Catppuccin Mocha dark theme.
Import STYLE_MAIN and apply via QApplication.setStyleSheet().
"""

# ── Palette ────────────────────────────────────────────────────────────────
CRUST    = "#11111b"
MANTLE   = "#181825"
BASE     = "#1e1e2e"
SURFACE0 = "#313244"
SURFACE1 = "#45475a"
SURFACE2 = "#585b70"
OVERLAY0 = "#6c7086"
OVERLAY1 = "#7f849c"
TEXT     = "#cdd6f4"
SUBTEXT1 = "#bac2de"
SUBTEXT0 = "#a6adc8"
BLUE     = "#89b4fa"
SAPPHIRE = "#74c7ec"
GREEN    = "#a6e3a1"
YELLOW   = "#f9e2af"
PEACH    = "#fab387"
RED      = "#f38ba8"
MAUVE    = "#cba6f7"
PINK     = "#f5c2e7"

# ── Status badge colours ───────────────────────────────────────────────────
COLOR_PENDING  = YELLOW
COLOR_SENDING  = SAPPHIRE
COLOR_SENT     = GREEN
COLOR_ERROR    = RED

STATUS_COLORS = {
    "ΠΡΟΣ ΑΠΟΣΤΟΛΗ": (YELLOW,   "#2a2206"),
    "ΣΕ ΑΠΟΣΤΟΛΗ":   (SAPPHIRE, "#061c2a"),
    "ΑΠΕΣΤΑΛΛΕΙ":    (GREEN,    "#062a0e"),
    "ΣΦΑΛΜΑ":        (RED,      "#2a060a"),
}

# ── Main stylesheet ────────────────────────────────────────────────────────
STYLE_MAIN = f"""
/* ── Base ──────────────────────────────────────────────────────────────── */
QMainWindow, QDialog {{
    background-color: {BASE};
    color: {TEXT};
}}
QWidget {{
    background-color: transparent;
    color: {TEXT};
    font-family: "Segoe UI", "Inter", "Helvetica Neue", Arial, sans-serif;
    font-size: 13px;
}}
QFrame {{
    background-color: transparent;
    border: none;
}}

/* ── Sidebar ────────────────────────────────────────────────────────────── */
#sidebar {{
    background-color: {MANTLE};
    border-right: 1px solid {SURFACE0};
    min-width: 220px;
    max-width: 220px;
}}
#sidebar QLabel#logo {{
    color: {BLUE};
    font-size: 18px;
    font-weight: 700;
    padding: 8px 0;
}}
#sidebar QLabel#logo_sub {{
    color: {OVERLAY0};
    font-size: 10px;
    letter-spacing: 1.5px;
}}
QPushButton#nav_btn {{
    background-color: transparent;
    color: {SUBTEXT1};
    border: none;
    border-radius: 8px;
    text-align: left;
    padding: 10px 16px;
    font-size: 13px;
    font-weight: 500;
    margin: 2px 8px;
}}
QPushButton#nav_btn:hover {{
    background-color: {SURFACE0};
    color: {TEXT};
}}
QPushButton#nav_btn[active="true"] {{
    background-color: {SURFACE0};
    color: {BLUE};
    font-weight: 600;
    border-left: 3px solid {BLUE};
}}

/* ── Header bar ─────────────────────────────────────────────────────────── */
#header_bar {{
    background-color: {MANTLE};
    border-bottom: 1px solid {SURFACE0};
    min-height: 56px;
    max-height: 56px;
    padding: 0 20px;
}}
#header_title {{
    color: {TEXT};
    font-size: 16px;
    font-weight: 600;
}}
#status_dot {{
    width: 10px; height: 10px;
    border-radius: 5px;
    background: {RED};
}}
#status_dot[connected="true"] {{
    background: {GREEN};
}}
#status_label {{
    color: {OVERLAY1};
    font-size: 12px;
}}

/* ── Content area ──────────────────────────────────────────────────────── */
#content_area {{
    background-color: {BASE};
    padding: 20px;
}}

/* ── Stat cards ────────────────────────────────────────────────────────── */
#stat_card {{
    background-color: {MANTLE};
    border: 1px solid {SURFACE0};
    border-radius: 12px;
    padding: 16px 20px;
    min-width: 140px;
}}
#stat_number {{
    font-size: 32px;
    font-weight: 700;
    color: {TEXT};
}}
#stat_label {{
    font-size: 11px;
    color: {OVERLAY1};
    text-transform: uppercase;
    letter-spacing: 0.8px;
}}
#stat_card[variant="pending"]  #stat_number {{ color: {YELLOW};   }}
#stat_card[variant="sent"]     #stat_number {{ color: {GREEN};    }}
#stat_card[variant="error"]    #stat_number {{ color: {RED};      }}
#stat_card[variant="total"]    #stat_number {{ color: {BLUE};     }}

/* ── Section titles ─────────────────────────────────────────────────────── */
QLabel#section_title {{
    font-size: 15px;
    font-weight: 600;
    color: {TEXT};
    padding-bottom: 4px;
}}
QFrame#divider {{
    background-color: {SURFACE0};
    max-height: 1px;
    min-height: 1px;
}}

/* ── Table ──────────────────────────────────────────────────────────────── */
QTableWidget {{
    background-color: {MANTLE};
    alternate-background-color: {BASE};
    gridline-color: {SURFACE0};
    border: 1px solid {SURFACE0};
    border-radius: 8px;
    selection-background-color: {SURFACE1};
    selection-color: {TEXT};
    outline: 0;
}}
QTableWidget::item {{
    padding: 6px 12px;
    border: none;
    color: {TEXT};
}}
QTableWidget::item:hover {{
    background-color: {SURFACE0};
}}
QTableWidget::item:selected {{
    background-color: {SURFACE1};
    color: {TEXT};
}}
QHeaderView::section {{
    background-color: {CRUST};
    color: {SUBTEXT0};
    font-size: 11px;
    font-weight: 600;
    letter-spacing: 0.5px;
    text-transform: uppercase;
    padding: 10px 12px;
    border: none;
    border-bottom: 1px solid {SURFACE0};
    border-right: 1px solid {SURFACE0};
}}
QHeaderView::section:last {{
    border-right: none;
}}
QHeaderView::section:checked {{
    background-color: {SURFACE0};
}}
QTableCornerButton::section {{
    background-color: {CRUST};
    border: none;
    border-bottom: 1px solid {SURFACE0};
    border-right: 1px solid {SURFACE0};
}}

/* ── Inputs ─────────────────────────────────────────────────────────────── */
QLineEdit, QTextEdit, QPlainTextEdit {{
    background-color: {MANTLE};
    color: {TEXT};
    border: 1px solid {SURFACE1};
    border-radius: 6px;
    padding: 8px 12px;
    selection-background-color: {SURFACE2};
}}
QLineEdit:focus, QTextEdit:focus, QPlainTextEdit:focus {{
    border-color: {BLUE};
}}
QLineEdit[readOnly="true"] {{
    background-color: {CRUST};
    color: {OVERLAY1};
}}

/* ── ComboBox ───────────────────────────────────────────────────────────── */
QComboBox {{
    background-color: {MANTLE};
    color: {TEXT};
    border: 1px solid {SURFACE1};
    border-radius: 6px;
    padding: 8px 12px;
    min-width: 120px;
}}
QComboBox:focus {{ border-color: {BLUE}; }}
QComboBox::drop-down {{
    border: none;
    width: 20px;
}}
QComboBox QAbstractItemView {{
    background-color: {SURFACE0};
    color: {TEXT};
    border: 1px solid {SURFACE1};
    selection-background-color: {SURFACE1};
    padding: 4px;
}}

/* ── Spinbox ────────────────────────────────────────────────────────────── */
QSpinBox {{
    background-color: {MANTLE};
    color: {TEXT};
    border: 1px solid {SURFACE1};
    border-radius: 6px;
    padding: 8px 12px;
}}
QSpinBox:focus {{ border-color: {BLUE}; }}
QSpinBox::up-button, QSpinBox::down-button {{
    background: {SURFACE0};
    border: none;
    width: 18px;
}}

/* ── Checkbox ───────────────────────────────────────────────────────────── */
QCheckBox {{
    color: {TEXT};
    spacing: 8px;
}}
QCheckBox::indicator {{
    width: 16px; height: 16px;
    border: 1.5px solid {SURFACE2};
    border-radius: 4px;
    background-color: {MANTLE};
}}
QCheckBox::indicator:checked {{
    background-color: {BLUE};
    border-color: {BLUE};
    image: none;
}}
QCheckBox::indicator:hover {{
    border-color: {BLUE};
}}

/* ── Buttons ────────────────────────────────────────────────────────────── */
QPushButton {{
    background-color: {SURFACE1};
    color: {TEXT};
    border: 1px solid {SURFACE2};
    border-radius: 7px;
    padding: 8px 18px;
    font-weight: 500;
    min-height: 34px;
}}
QPushButton:hover {{
    background-color: {SURFACE2};
    border-color: {OVERLAY0};
}}
QPushButton:pressed {{
    background-color: {SURFACE0};
}}
QPushButton:disabled {{
    background-color: {SURFACE0};
    color: {OVERLAY0};
    border-color: {SURFACE1};
}}
QPushButton#btn_primary {{
    background-color: {BLUE};
    color: {CRUST};
    border: none;
    font-weight: 700;
}}
QPushButton#btn_primary:hover {{
    background-color: #9ec5fb;
}}
QPushButton#btn_primary:pressed {{
    background-color: #6fa8f8;
}}
QPushButton#btn_danger {{
    background-color: {RED};
    color: {CRUST};
    border: none;
    font-weight: 700;
}}
QPushButton#btn_danger:hover {{
    background-color: #f8a8b6;
}}
QPushButton#btn_success {{
    background-color: {GREEN};
    color: {CRUST};
    border: none;
    font-weight: 700;
}}
QPushButton#btn_success:hover {{
    background-color: #b8ecb2;
}}
QPushButton#btn_ghost {{
    background-color: transparent;
    border: 1px solid {SURFACE1};
    color: {SUBTEXT1};
}}
QPushButton#btn_ghost:hover {{
    background-color: {SURFACE0};
    color: {TEXT};
}}

/* ── Progress bar ───────────────────────────────────────────────────────── */
QProgressBar {{
    background-color: {SURFACE0};
    border: none;
    border-radius: 5px;
    height: 10px;
    text-align: center;
    color: transparent;
}}
QProgressBar::chunk {{
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                                stop:0 {BLUE}, stop:1 {MAUVE});
    border-radius: 5px;
}}

/* ── Scrollbars ─────────────────────────────────────────────────────────── */
QScrollBar:vertical {{
    background: {MANTLE};
    width: 8px;
    margin: 0;
    border-radius: 4px;
}}
QScrollBar::handle:vertical {{
    background: {SURFACE2};
    min-height: 30px;
    border-radius: 4px;
}}
QScrollBar::handle:vertical:hover {{ background: {OVERLAY0}; }}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
QScrollBar:horizontal {{
    background: {MANTLE};
    height: 8px;
    margin: 0;
    border-radius: 4px;
}}
QScrollBar::handle:horizontal {{
    background: {SURFACE2};
    min-width: 30px;
    border-radius: 4px;
}}
QScrollBar::handle:horizontal:hover {{ background: {OVERLAY0}; }}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{ width: 0; }}

/* ── TabWidget ──────────────────────────────────────────────────────────── */
QTabWidget::pane {{
    border: 1px solid {SURFACE0};
    border-radius: 0 8px 8px 8px;
    background-color: {MANTLE};
    padding: 16px;
}}
QTabBar::tab {{
    background-color: {CRUST};
    color: {SUBTEXT0};
    border: 1px solid {SURFACE0};
    border-bottom: none;
    border-radius: 6px 6px 0 0;
    padding: 8px 20px;
    margin-right: 2px;
    font-size: 12px;
    font-weight: 500;
}}
QTabBar::tab:selected {{
    background-color: {MANTLE};
    color: {TEXT};
    border-bottom: 2px solid {BLUE};
}}
QTabBar::tab:hover:!selected {{ background-color: {SURFACE0}; color: {TEXT}; }}

/* ── GroupBox ───────────────────────────────────────────────────────────── */
QGroupBox {{
    font-weight: 600;
    color: {SUBTEXT1};
    border: 1px solid {SURFACE0};
    border-radius: 8px;
    margin-top: 14px;
    padding: 12px;
}}
QGroupBox::title {{
    subcontrol-origin: margin;
    subcontrol-position: top left;
    padding: 2px 8px;
    background-color: {MANTLE};
    color: {BLUE};
    font-size: 12px;
    font-weight: 600;
}}

/* ── Log viewer ─────────────────────────────────────────────────────────── */
#log_view {{
    background-color: {CRUST};
    color: {SUBTEXT1};
    font-family: "Cascadia Code", "Consolas", "Courier New", monospace;
    font-size: 12px;
    border: 1px solid {SURFACE0};
    border-radius: 8px;
    padding: 8px;
}}

/* ── Tooltip ────────────────────────────────────────────────────────────── */
QToolTip {{
    background-color: {SURFACE1};
    color: {TEXT};
    border: 1px solid {SURFACE2};
    border-radius: 4px;
    padding: 4px 8px;
    font-size: 12px;
}}

/* ── Status bar ─────────────────────────────────────────────────────────── */
QStatusBar {{
    background-color: {CRUST};
    color: {OVERLAY1};
    font-size: 11px;
    border-top: 1px solid {SURFACE0};
}}

/* ── Dialog buttons ─────────────────────────────────────────────────────── */
QDialogButtonBox QPushButton {{
    min-width: 80px;
}}

/* ── Label variants ─────────────────────────────────────────────────────── */
QLabel#label_info  {{ color: {BLUE};    }}
QLabel#label_ok    {{ color: {GREEN};   }}
QLabel#label_warn  {{ color: {YELLOW};  }}
QLabel#label_error {{ color: {RED};     }}
"""
