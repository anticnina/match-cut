"""MatchCut pop-up window — follower selection with circular avatars."""

import os
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QListWidget,
    QListWidgetItem, QPushButton, QFrame, QAbstractItemView,
    QWidget, QSizePolicy,
)
from PyQt6.QtCore import Qt, QThreadPool, pyqtSignal, QObject, QRunnable, pyqtSlot, QByteArray
from PyQt6.QtGui import QPixmap, QPainter, QPainterPath

from config import COLORS
from ui.widgets import GreenButton, SpinnerWidget, AvatarLabel
from ui.animations import fade_in
from workers import FollowingWorker


POPUP_STYLE = f"""
    QDialog {{
        background: {COLORS['bg_secondary']};
    }}
    QLabel {{
        background: transparent;
        color: {COLORS['text_primary']};
    }}
    QListWidget {{
        background: {COLORS['bg']};
        border: none;
        outline: none;
    }}
    QListWidget::item {{
        border-bottom: 1px solid {COLORS['bg_card']};
        padding: 0px;
    }}
    QListWidget::item:selected {{
        background: rgba(0, 224, 84, 0.12);
        border-left: 3px solid {COLORS['green']};
    }}
    QListWidget::item:hover:!selected {{
        background: {COLORS['bg_card']};
    }}
    QScrollBar:vertical {{
        background: {COLORS['bg']};
        width: 5px;
        border-radius: 2px;
    }}
    QScrollBar::handle:vertical {{
        background: {COLORS['border']};
        border-radius: 2px;
    }}
    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
    QPushButton#CancelBtn {{
        background: transparent;
        color: {COLORS['text_muted']};
        border: 1px solid {COLORS['border']};
        border-radius: 6px;
        padding: 9px 24px;
        font-size: 13px;
    }}
    QPushButton#CancelBtn:hover {{
        color: {COLORS['text_primary']};
        border-color: {COLORS['text_muted']};
    }}
"""


# ---------------------------------------------------------------------------
# Per-row person widget
# ---------------------------------------------------------------------------

class PersonRowWidget(QWidget):
    def __init__(self, display_name: str, username: str, parent=None):
        super().__init__(parent)
        self.username = username
        self.setFixedHeight(60)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(14, 10, 14, 10)
        layout.setSpacing(14)

        self.avatar = AvatarLabel(size=38)
        layout.addWidget(self.avatar)

        text_col = QVBoxLayout()
        text_col.setSpacing(2)
        text_col.setContentsMargins(0, 0, 0, 0)

        name_lbl = QLabel(display_name)
        name_lbl.setStyleSheet(
            f"color: {COLORS['text_primary']}; font-size: 13px; font-weight: 600;"
        )
        text_col.addWidget(name_lbl)

        uname_lbl = QLabel(f"@{username}")
        uname_lbl.setStyleSheet(
            f"color: {COLORS['text_muted']}; font-size: 11px;"
        )
        text_col.addWidget(uname_lbl)

        layout.addLayout(text_col)
        layout.addStretch()


# ---------------------------------------------------------------------------
# Background avatar loader
# ---------------------------------------------------------------------------

class _AvatarSignals(QObject):
    loaded = pyqtSignal(str, bytes)   # (username, image_bytes)


class _AvatarBatchWorker(QRunnable):
    """Fetches avatars sequentially and emits one signal per image."""
    def __init__(self, people: list[dict]):
        super().__init__()
        self.people = people
        self.signals = _AvatarSignals()
        self._cancelled = False

    def cancel(self):
        self._cancelled = True

    @pyqtSlot()
    def run(self):
        from scraper import fetch_image_bytes
        for p in self.people:
            if self._cancelled:
                break
            url = p.get("avatar_url")
            if url:
                data = fetch_image_bytes(url)
                if data:
                    self.signals.loaded.emit(p["username"], data)


# ---------------------------------------------------------------------------
# Main popup
# ---------------------------------------------------------------------------

class MatchPopup(QDialog):
    """Modal — pick a follower to compare with."""
    confirmed = pyqtSignal(str, str)   # (username2, tmdb_key)

    def __init__(self, username1: str, tmdb_key: str, parent=None):
        super().__init__(parent)
        self.username1 = username1
        self.tmdb_key = tmdb_key
        self._row_widgets: dict[str, PersonRowWidget] = {}
        self._avatar_worker: _AvatarBatchWorker | None = None

        self.setWindowTitle("MatchCut")
        self.setWindowFlags(Qt.WindowType.Dialog | Qt.WindowType.WindowStaysOnTopHint)
        self.setModal(True)
        self.setFixedWidth(460)
        self.setMinimumHeight(480)
        self.setStyleSheet(POPUP_STYLE)

        self._build_ui()
        self._load_following()
        fade_in(self, duration=260)

    def closeEvent(self, event):
        if self._avatar_worker:
            self._avatar_worker.cancel()
        super().closeEvent(event)

    # ------------------------------------------------------------------
    # UI
    # ------------------------------------------------------------------

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # ── Header ──────────────────────────────────────────────────────
        header = QFrame()
        header.setStyleSheet(f"background: {COLORS['bg_secondary']};")
        header_layout = QVBoxLayout(header)
        header_layout.setContentsMargins(28, 24, 28, 20)
        header_layout.setSpacing(10)

        q = QLabel("Want to find out if\nyou two are a perfect match?")
        q.setAlignment(Qt.AlignmentFlag.AlignCenter)
        q.setStyleSheet(
            f"color: {COLORS['text_primary']}; font-size: 17px; font-weight: bold;"
        )
        header_layout.addWidget(q)

        # Spinner status (hidden once loaded)
        self._status_row = QHBoxLayout()
        self._spinner = SpinnerWidget(22)
        self._status_lbl = QLabel("Loading your following list…")
        self._status_lbl.setStyleSheet(f"color: {COLORS['text_muted']}; font-size: 12px;")
        self._status_row.addStretch()
        self._status_row.addWidget(self._spinner)
        self._status_row.addSpacing(6)
        self._status_row.addWidget(self._status_lbl)
        self._status_row.addStretch()
        header_layout.addLayout(self._status_row)
        self._spinner.start()

        root.addWidget(header)

        # ── "Choose user:" label ─────────────────────────────────────────
        lbl_frame = QFrame()
        lbl_frame.setStyleSheet(f"background: {COLORS['bg']}; border-bottom: 1px solid {COLORS['bg_card']};")
        lbl_row = QHBoxLayout(lbl_frame)
        lbl_row.setContentsMargins(14, 8, 14, 8)
        choose_lbl = QLabel("Choose user:")
        choose_lbl.setStyleSheet(
            f"color: {COLORS['text_muted']}; font-size: 11px; font-weight: 600; letter-spacing: 0.5px;"
        )
        lbl_row.addWidget(choose_lbl)
        root.addWidget(lbl_frame)

        # ── Person list ──────────────────────────────────────────────────
        self._list = QListWidget()
        self._list.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self._list.setMinimumHeight(260)
        self._list.itemDoubleClicked.connect(self._confirm)
        self._list.setVerticalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        root.addWidget(self._list)

        # ── Buttons ──────────────────────────────────────────────────────
        btn_frame = QFrame()
        btn_frame.setStyleSheet(
            f"background: {COLORS['bg_secondary']}; border-top: 1px solid {COLORS['border']};"
        )
        btn_layout = QHBoxLayout(btn_frame)
        btn_layout.setContentsMargins(20, 16, 20, 16)

        cancel = QPushButton("Cancel")
        cancel.setObjectName("CancelBtn")
        cancel.clicked.connect(self.reject)

        self._confirm_btn = GreenButton("Find My Match!")
        self._confirm_btn.clicked.connect(self._confirm)

        btn_layout.addWidget(cancel)
        btn_layout.addStretch()
        btn_layout.addWidget(self._confirm_btn)
        root.addWidget(btn_frame)

    # ------------------------------------------------------------------
    # Data loading
    # ------------------------------------------------------------------

    def _load_following(self):
        worker = FollowingWorker(self.username1)
        worker.signals.result.connect(self._on_following_loaded)
        worker.signals.error.connect(self._on_following_error)
        worker.signals.progress.connect(self._status_lbl.setText)
        QThreadPool.globalInstance().start(worker)

    def _on_following_loaded(self, following: list):
        self._spinner.stop()
        self._spinner.hide()

        if not following:
            self._status_lbl.setText("No following list found.")
            return

        self._status_lbl.setText(f"{len(following)} people you follow")
        self._populate_list(following)
        self._start_avatar_loading(following)

    def _on_following_error(self, _: str):
        self._spinner.stop()
        self._spinner.hide()
        self._status_lbl.setText("Could not load following list.")

    def _populate_list(self, people: list[dict]):
        self._list.clear()
        self._row_widgets.clear()

        for p in people:
            display = p.get("display_name") or p["username"]
            uname = p["username"]

            row_widget = PersonRowWidget(display, uname)
            self._row_widgets[uname] = row_widget

            item = QListWidgetItem()
            item.setData(Qt.ItemDataRole.UserRole, uname)
            item.setSizeHint(row_widget.sizeHint())
            self._list.addItem(item)
            self._list.setItemWidget(item, row_widget)

    def _start_avatar_loading(self, people: list[dict]):
        worker = _AvatarBatchWorker(people)
        worker.signals.loaded.connect(self._on_avatar_loaded)
        self._avatar_worker = worker
        QThreadPool.globalInstance().start(worker)

    @pyqtSlot(str, bytes)
    def _on_avatar_loaded(self, username: str, data: bytes):
        widget = self._row_widgets.get(username)
        if widget:
            widget.avatar.set_image_bytes(data)

    # ------------------------------------------------------------------
    # Confirm
    # ------------------------------------------------------------------

    def _confirm(self):
        selected = self._list.selectedItems()
        if not selected:
            self._status_lbl.setText("Please select someone from the list first.")
            self._status_lbl.setStyleSheet(f"color: {COLORS['orange']}; font-size: 12px;")
            return

        username2 = selected[0].data(Qt.ItemDataRole.UserRole)
        self.confirmed.emit(username2, self.tmdb_key)
        self.accept()
