"""
Main application window.

Layout:
  ┌──────────┬────────────────────────────────────┐
  │ Sidebar  │  Header bar                         │
  │          ├────────────────────────────────────┤
  │  [nav]   │  Content (stacked pages)            │
  │          │   • Dashboard                       │
  │          │   • Μηνύματα                         │
  │          │   • Αρχεία                           │
  │          │   • Ρυθμίσεις                        │
  └──────────┴────────────────────────────────────┘
"""
import logging
from typing import Optional

from PySide6.QtCore import Qt, QTimer, QThread, Signal, Slot
from PySide6.QtGui import QFont, QIcon
from PySide6.QtWidgets import (
    QFrame, QHBoxLayout, QLabel, QMainWindow,
    QPushButton, QSizePolicy, QStackedWidget,
    QStatusBar, QVBoxLayout, QWidget,
)

from ..config import AppConfig
from ..database import DatabaseManager
from .message_grid import MessageGridWidget
from .settings_dialog import SettingsDialog
from .styles import (
    BASE, BLUE, CRUST, GREEN, MANTLE, OVERLAY1, RED, STYLE_MAIN,
    SUBTEXT0, SURFACE0, TEXT, YELLOW,
    STATUS_COLORS,
)

logger = logging.getLogger(__name__)


# ── Stat card widget ───────────────────────────────────────────────────────

class StatCard(QWidget):
    def __init__(self, label: str, variant: str = "total", parent=None):
        super().__init__(parent)
        self.setObjectName("stat_card")
        self.setProperty("variant", variant)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(4)

        self._number = QLabel("–")
        self._number.setObjectName("stat_number")
        self._number.setAlignment(Qt.AlignLeft)

        self._label = QLabel(label.upper())
        self._label.setObjectName("stat_label")

        layout.addWidget(self._number)
        layout.addWidget(self._label)
        self.setFixedHeight(90)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

    def set_value(self, value: int):
        self._number.setText(f"{value:,}")


# ── Dashboard page ─────────────────────────────────────────────────────────

class DashboardPage(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(16)

        # ── Title
        title = QLabel("Πίνακας Ελέγχου")
        title.setObjectName("section_title")
        layout.addWidget(title)

        divider = QFrame()
        divider.setObjectName("divider")
        layout.addWidget(divider)

        # ── Stat cards row
        cards_row = QHBoxLayout()
        cards_row.setSpacing(12)

        self.card_total   = StatCard("Σύνολο",          "total")
        self.card_pending = StatCard("Προς Αποστολή",   "pending")
        self.card_sent    = StatCard("Απεστάλησαν",     "sent")
        self.card_error   = StatCard("Σφάλματα",        "error")

        for card in (self.card_total, self.card_pending, self.card_sent, self.card_error):
            cards_row.addWidget(card)
        cards_row.addStretch()

        layout.addLayout(cards_row)
        layout.addStretch()

    def update_stats(self, stats: dict):
        from ..database import STATUS_PENDING, STATUS_SENT, STATUS_ERROR
        pending = stats.get(STATUS_PENDING, 0)
        sent    = stats.get(STATUS_SENT,    0)
        error   = stats.get(STATUS_ERROR,   0)
        total   = sum(stats.values())

        self.card_total.set_value(total)
        self.card_pending.set_value(pending)
        self.card_sent.set_value(sent)
        self.card_error.set_value(error)


# ── Log page ───────────────────────────────────────────────────────────────

class LogPage(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(12)

        from PySide6.QtWidgets import QPlainTextEdit, QHBoxLayout
        title = QLabel("Αρχεία Καταγραφής")
        title.setObjectName("section_title")
        layout.addWidget(title)

        # Clear button
        btn_row = QHBoxLayout()
        btn_clear = QPushButton("🗑  Καθαρισμός")
        btn_clear.setObjectName("btn_ghost")
        btn_clear.setMaximumWidth(150)
        btn_row.addStretch()
        btn_row.addWidget(btn_clear)
        layout.addLayout(btn_row)

        self.log_view = QPlainTextEdit()
        self.log_view.setObjectName("log_view")
        self.log_view.setReadOnly(True)
        layout.addWidget(self.log_view)

        btn_clear.clicked.connect(self.log_view.clear)

    def append_log(self, message: str, level: str = "INFO"):
        colors = {"INFO": TEXT, "WARNING": YELLOW, "ERROR": RED, "DEBUG": OVERLAY1}
        color = colors.get(level.upper(), TEXT)
        from datetime import datetime
        ts = datetime.now().strftime("%H:%M:%S")
        self.log_view.appendHtml(
            f'<span style="color:{OVERLAY1}">[{ts}]</span> '
            f'<span style="color:{color}">{message}</span>'
        )
        sb = self.log_view.verticalScrollBar()
        sb.setValue(sb.maximum())


# ── DB refresh worker ──────────────────────────────────────────────────────

class RefreshWorker(QThread):
    stats_ready = Signal(dict)
    error = Signal(str)

    def __init__(self, db: DatabaseManager):
        super().__init__()
        self.db = db

    def run(self):
        try:
            stats = self.db.get_statistics()
            self.stats_ready.emit(stats)
        except Exception as exc:
            self.error.emit(str(exc))


# ── Main window ────────────────────────────────────────────────────────────

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.config = AppConfig.load()
        self.db = DatabaseManager(self.config.database)
        self._db_connected = False
        self._nav_buttons: list[QPushButton] = []

        self.setWindowTitle("SMS / Viber Sender")
        self.setMinimumSize(1100, 680)
        self.resize(1280, 760)
        self.setStyleSheet(STYLE_MAIN)

        self._build_ui()
        self._setup_status_bar()
        self._setup_auto_refresh()

        # Try initial connection
        QTimer.singleShot(200, self._check_db_connection)

    # ── UI construction ────────────────────────────────────────────────────

    def _build_ui(self):
        root = QWidget()
        root_layout = QHBoxLayout(root)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        # Left sidebar
        sidebar = self._build_sidebar()
        root_layout.addWidget(sidebar)

        # Right side (header + content)
        right = QWidget()
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(0)

        right_layout.addWidget(self._build_header())

        # Page stack
        self.stack = QStackedWidget()
        self.stack.setObjectName("content_area")

        self.page_dashboard = DashboardPage()
        self.page_messages  = MessageGridWidget(self.config, self)
        self.page_logs      = LogPage()

        self.stack.addWidget(self.page_dashboard)   # 0
        self.stack.addWidget(self.page_messages)    # 1
        self.stack.addWidget(self.page_logs)        # 2

        right_layout.addWidget(self.stack, stretch=1)
        root_layout.addWidget(right, stretch=1)

        self.setCentralWidget(root)

        # Wire log callback
        self.page_messages.set_log_callback(self.page_logs.append_log)

    def _build_sidebar(self) -> QWidget:
        sidebar = QWidget()
        sidebar.setObjectName("sidebar")
        sidebar.setFixedWidth(220)

        layout = QVBoxLayout(sidebar)
        layout.setContentsMargins(0, 0, 0, 16)
        layout.setSpacing(0)

        # ── Logo area
        logo_frame = QWidget()
        logo_frame.setFixedHeight(72)
        logo_layout = QVBoxLayout(logo_frame)
        logo_layout.setContentsMargins(20, 16, 20, 8)
        logo_layout.setSpacing(2)

        logo = QLabel("📱 SMS/Viber")
        logo.setObjectName("logo")
        logo_layout.addWidget(logo)

        sub = QLabel("SENDER v1.0")
        sub.setObjectName("logo_sub")
        logo_layout.addWidget(sub)
        layout.addWidget(logo_frame)

        # ── Divider
        div = QFrame()
        div.setObjectName("divider")
        div.setMaximumHeight(1)
        layout.addWidget(div)
        layout.addSpacing(12)

        # ── Nav buttons
        nav_items = [
            ("🏠  Αρχική",           0),
            ("📨  Μηνύματα",         1),
            ("📋  Αρχεία",           2),
        ]
        for label, page_idx in nav_items:
            btn = QPushButton(label)
            btn.setObjectName("nav_btn")
            btn.setCheckable(False)
            btn.clicked.connect(lambda _, idx=page_idx: self._navigate(idx))
            self._nav_buttons.append(btn)
            layout.addWidget(btn)

        layout.addStretch()

        # ── Bottom: Settings button
        btn_settings = QPushButton("⚙  Ρυθμίσεις")
        btn_settings.setObjectName("nav_btn")
        btn_settings.clicked.connect(self._open_settings)
        layout.addWidget(btn_settings)

        # ── Connection indicator
        conn_frame = QWidget()
        conn_frame.setFixedHeight(44)
        conn_layout = QHBoxLayout(conn_frame)
        conn_layout.setContentsMargins(20, 0, 20, 0)
        conn_layout.setSpacing(8)

        self.dot = QLabel()
        self.dot.setObjectName("status_dot")
        self.dot.setFixedSize(10, 10)
        self.dot.setProperty("connected", "false")

        self.conn_label = QLabel("Αποσυνδεδεμένο")
        self.conn_label.setObjectName("status_label")

        conn_layout.addWidget(self.dot)
        conn_layout.addWidget(self.conn_label)
        conn_layout.addStretch()
        layout.addWidget(conn_frame)

        self._navigate(0)
        return sidebar

    def _build_header(self) -> QWidget:
        bar = QWidget()
        bar.setObjectName("header_bar")
        bar.setFixedHeight(56)

        layout = QHBoxLayout(bar)
        layout.setContentsMargins(24, 0, 24, 0)
        layout.setSpacing(12)

        self.header_title = QLabel("Αρχική")
        self.header_title.setObjectName("header_title")
        layout.addWidget(self.header_title)
        layout.addStretch()

        # Reconnect button
        btn_reconnect = QPushButton("🔌  Σύνδεση")
        btn_reconnect.setObjectName("btn_ghost")
        btn_reconnect.setMaximumWidth(120)
        btn_reconnect.setToolTip("Επανασύνδεση στη βάση δεδομένων")
        btn_reconnect.clicked.connect(self._check_db_connection)
        layout.addWidget(btn_reconnect)

        # Refresh button
        btn_refresh = QPushButton("🔄  Ανανέωση")
        btn_refresh.setObjectName("btn_ghost")
        btn_refresh.setMaximumWidth(130)
        btn_refresh.clicked.connect(self._manual_refresh)
        layout.addWidget(btn_refresh)

        return bar

    def _setup_status_bar(self):
        sb = QStatusBar()
        self.setStatusBar(sb)
        self.status_msg = QLabel("Έτοιμο")
        sb.addWidget(self.status_msg, 1)
        self.status_db = QLabel("⬤  Χωρίς σύνδεση")
        sb.addPermanentWidget(self.status_db)

    def _setup_auto_refresh(self):
        self._refresh_timer = QTimer(self)
        self._refresh_timer.setInterval(30_000)  # every 30 s
        self._refresh_timer.timeout.connect(self._refresh_stats)
        self._refresh_timer.start()

    # ── Navigation ─────────────────────────────────────────────────────────

    def _navigate(self, page_idx: int):
        page_names = ["Αρχική", "Μηνύματα", "Αρχεία Καταγραφής"]
        self.stack.setCurrentIndex(page_idx)
        self.header_title.setText(page_names[page_idx])

        for i, btn in enumerate(self._nav_buttons):
            btn.setProperty("active", "true" if i == page_idx else "false")
            btn.style().unpolish(btn)
            btn.style().polish(btn)

    # ── DB connection ──────────────────────────────────────────────────────

    def _check_db_connection(self):
        self.status_msg.setText("Σύνδεση στη βάση…")
        ok, msg = self.db.test_connection()
        self._db_connected = ok
        self._update_connection_ui(ok, msg)
        if ok:
            self._refresh_stats()
            self.page_messages.reload_data()

    def _update_connection_ui(self, connected: bool, message: str = ""):
        color = GREEN if connected else RED
        self.dot.setProperty("connected", "true" if connected else "false")
        self.dot.style().unpolish(self.dot)
        self.dot.style().polish(self.dot)
        self.conn_label.setText("Συνδεδεμένο" if connected else "Αποσυνδεδεμένο")
        status_text = f"⬤  {message}" if message else ("⬤  Συνδεδεμένο" if connected else "⬤  Αποσυνδεδεμένο")
        self.status_db.setStyleSheet(f"color: {color}; padding-right: 8px;")
        self.status_db.setText(status_text[:60])
        self.status_msg.setText(message if not connected else "Έτοιμο")

    # ── Stats refresh ──────────────────────────────────────────────────────

    def _refresh_stats(self):
        if not self._db_connected:
            return
        worker = RefreshWorker(self.db)
        worker.stats_ready.connect(self.page_dashboard.update_stats)
        worker.error.connect(lambda e: logger.warning(f"Stats refresh error: {e}"))
        worker.start()
        self._keep_alive_worker = worker

    def _manual_refresh(self):
        self._refresh_stats()
        if self._db_connected:
            self.page_messages.reload_data()

    # ── Settings ───────────────────────────────────────────────────────────

    def _open_settings(self):
        dlg = SettingsDialog(self.config, self)
        if dlg.exec():
            self.config = dlg.get_config()
            self.config.save()
            self.db = DatabaseManager(self.config.database)
            self.page_messages.update_config(self.config)
            self.status_msg.setText("Ρυθμίσεις αποθηκεύτηκαν ✓")
            QTimer.singleShot(500, self._check_db_connection)

    # ── Log helper ─────────────────────────────────────────────────────────

    def log(self, message: str, level: str = "INFO"):
        self.page_logs.append_log(message, level)

    def closeEvent(self, event):
        event.accept()
