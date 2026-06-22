"""Main application window for MatchCut."""

import os
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QScrollArea, QFrame, QLineEdit, QSizePolicy, QStackedWidget,
    QGraphicsOpacityEffect,
)
from PyQt6.QtCore import Qt, QThreadPool, QTimer, pyqtSlot, QByteArray, QRect, QSize
from PyQt6.QtGui import QPixmap, QFont, QPainter, QColor, QPen

from config import COLORS
from ui.widgets import (
    AvatarLabel, GreenButton, SpinnerWidget, HSeparator,
)
from ui.animations import fade_in, staggered_entrance
from ui.popup import MatchPopup
from ui.sections import (
    HolyTrinitySection, DealbreakersSection,
    GenreSection, RecommendationsSection,
)
from workers import ProfileWorker, AnalysisWorker
from ui.slideshow import SlideshowWidget


GLOBAL_STYLE = f"""
    QMainWindow, QWidget {{
        background-color: {COLORS['bg']};
        color: {COLORS['text_primary']};
        font-family: 'Segoe UI', 'Helvetica Neue', Arial, sans-serif;
    }}
    QScrollArea {{
        border: none;
        background: transparent;
    }}
    QScrollBar:vertical {{
        background: {COLORS['bg_secondary']};
        width: 8px;
        border-radius: 4px;
    }}
    QScrollBar::handle:vertical {{
        background: {COLORS['border']};
        border-radius: 4px;
    }}
    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
    QLineEdit {{
        background: {COLORS['bg_card']};
        color: {COLORS['text_primary']};
        border: 1px solid {COLORS['border']};
        border-radius: 6px;
        padding: 8px 14px;
        font-size: 14px;
        min-height: 36px;
    }}
    QLineEdit:focus {{
        border-color: {COLORS['green']};
    }}
"""


# ---------------------------------------------------------------------------
# Letterboxd three-circles logo widget
# ---------------------------------------------------------------------------

class LetterboxdLogoWidget(QWidget):
    """
    Paints the three overlapping Letterboxd circles (green / orange / blue)
    followed by the 'Letterboxd' wordmark, at the requested scale.
    """
    def __init__(self, circle_r: int = 18, parent=None):
        super().__init__(parent)
        self._r = circle_r
        # The three circles overlap by ~35% of diameter
        overlap = int(circle_r * 0.7)
        total_w = circle_r * 2 + 2 * (circle_r * 2 - overlap) + 16
        self.setFixedHeight(circle_r * 2 + 4)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)

    def sizeHint(self) -> QSize:
        r = self._r
        overlap = int(r * 0.7)
        circles_w = r * 2 + 2 * (r * 2 - overlap)
        return QSize(circles_w + 4, r * 2 + 4)

    def paintEvent(self, _event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)

        r = self._r
        overlap = int(r * 0.7)
        step = r * 2 - overlap   # distance between circle centres horizontally
        y = 2                     # top margin

        colors = [COLORS["orange"], COLORS["green"], COLORS["blue"]]
        for i, hex_color in enumerate(colors):
            x = 2 + i * step
            color = QColor(hex_color)
            color.setAlphaF(0.85)
            p.setBrush(color)
            p.setPen(Qt.PenStyle.NoPen)
            p.drawEllipse(x, y, r * 2, r * 2)

        p.end()


# ---------------------------------------------------------------------------
# Welcome banner (shown above profile on the profile screen)
# ---------------------------------------------------------------------------

class WelcomeBanner(QFrame):
    """
    Welcome to
    [●●● Letterboxd]          ← three circles + wordmark
    compatibility analysis!
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet(f"background: transparent;")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 20)
        layout.setSpacing(0)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        def _lbl(text, size, color, weight="normal", spacing="0px"):
            l = QLabel(text)
            l.setAlignment(Qt.AlignmentFlag.AlignCenter)
            l.setStyleSheet(
                f"color: {color}; font-size: {size}px; font-weight: {weight};"
                f" letter-spacing: {spacing}; background: transparent;"
            )
            return l

        layout.addWidget(_lbl("Welcome to", 40, COLORS["text_primary"], weight="700"))
        layout.addSpacing(16)

        # Middle row: circles widget + "Letterboxd" text side by side, centred
        logo_row = QHBoxLayout()
        logo_row.setAlignment(Qt.AlignmentFlag.AlignCenter)
        logo_row.setSpacing(20)

        circles = LetterboxdLogoWidget(circle_r=40)
        logo_row.addWidget(circles)

        wordmark = QLabel("Letterboxd")
        wordmark.setStyleSheet(
            f"color: {COLORS['text_primary']}; font-size: 76px; font-weight: 900;"
            f" letter-spacing: -1px; background: transparent;"
        )
        logo_row.addWidget(wordmark)
        layout.addLayout(logo_row)

        layout.addSpacing(16)
        layout.addWidget(_lbl("compatibility analysis!", 40, COLORS["text_primary"], weight="700"))


# ---------------------------------------------------------------------------
# Login screen widget  (simple centered card)
# ---------------------------------------------------------------------------

class LoginScreen(QWidget):
    def __init__(self, on_submit, parent=None):
        super().__init__(parent)
        self._on_submit = on_submit
        self._build()

    def _build(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addStretch(2)

        card = QFrame()
        card.setFixedWidth(380)
        card.setStyleSheet(f"""
            QFrame {{
                background: {COLORS['bg_secondary']};
                border: 1px solid {COLORS['border']};
                border-radius: 14px;
            }}
        """)
        layout = QVBoxLayout(card)
        layout.setContentsMargins(36, 36, 36, 36)
        layout.setSpacing(16)

        logo = QLabel("MatchCut")
        logo.setAlignment(Qt.AlignmentFlag.AlignCenter)
        logo.setStyleSheet(
            f"color: {COLORS['green']}; font-size: 28px; font-weight: bold; border: none;"
        )
        layout.addWidget(logo)

        tagline = QLabel("Discover your Letterboxd compatibility")
        tagline.setAlignment(Qt.AlignmentFlag.AlignCenter)
        tagline.setStyleSheet(
            f"color: {COLORS['text_muted']}; font-size: 13px; border: none;"
        )
        layout.addWidget(tagline)

        layout.addSpacing(8)

        lbl = QLabel("Your Letterboxd username")
        lbl.setStyleSheet(f"color: {COLORS['text_muted']}; font-size: 12px; border: none;")
        layout.addWidget(lbl)

        self._input = QLineEdit()
        self._input.setPlaceholderText("e.g. ecipecipec")
        self._input.returnPressed.connect(self._submit)
        layout.addWidget(self._input)

        self._error_lbl = QLabel("")
        self._error_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._error_lbl.setWordWrap(True)
        self._error_lbl.setStyleSheet(
            f"color: {COLORS['red']}; font-size: 12px; border: none;"
        )
        self._error_lbl.hide()
        layout.addWidget(self._error_lbl)

        self._btn = GreenButton("Load Profile")
        self._btn.clicked.connect(self._submit)
        layout.addWidget(self._btn)

        spinner_row = QHBoxLayout()
        self._spinner = SpinnerWidget(24)
        self._loading_lbl = QLabel("Loading profile...")
        self._loading_lbl.setStyleSheet(
            f"color: {COLORS['text_muted']}; font-size: 12px; border: none;"
        )
        spinner_row.addStretch()
        spinner_row.addWidget(self._spinner)
        spinner_row.addSpacing(8)
        spinner_row.addWidget(self._loading_lbl)
        spinner_row.addStretch()
        layout.addLayout(spinner_row)
        self._spinner.hide()
        self._loading_lbl.hide()

        center_row = QHBoxLayout()
        center_row.addStretch()
        center_row.addWidget(card)
        center_row.addStretch()
        outer.addLayout(center_row)
        outer.addStretch(3)

    def show_loading(self, loading: bool):
        self._btn.setEnabled(not loading)
        if loading:
            self._spinner.show()
            self._loading_lbl.show()
            self._spinner.start()
            self._error_lbl.hide()
        else:
            self._spinner.stop()
            self._spinner.hide()
            self._loading_lbl.hide()

    def show_error(self, msg: str):
        self._error_lbl.setText(msg)
        self._error_lbl.show()
        self.show_loading(False)

    def _submit(self):
        username = self._input.text().strip().lstrip("@")
        if not username:
            return
        self._error_lbl.hide()
        self.show_loading(True)
        self._on_submit(username)


# ---------------------------------------------------------------------------
# Profile header widget (shown after login)
# ---------------------------------------------------------------------------

class ProfileHeader(QFrame):
    def __init__(self, profile: dict, on_matchcut, parent=None):
        super().__init__(parent)
        self.setStyleSheet(f"""
            QFrame {{
                background: {COLORS['bg_secondary']};
                border-radius: 12px;
            }}
        """)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 24, 28, 24)
        layout.setSpacing(12)

        # Top row: avatar + info
        top = QHBoxLayout()
        top.setSpacing(20)

        self.avatar = AvatarLabel(size=80)
        top.addWidget(self.avatar, 0, Qt.AlignmentFlag.AlignTop)

        info = QVBoxLayout()
        info.setSpacing(4)

        display = QLabel(profile.get("display_name", profile["username"]))
        display.setStyleSheet(f"color: {COLORS['text_primary']}; font-size: 22px; font-weight: bold;")
        info.addWidget(display)

        uname = QLabel(f"@{profile['username']}")
        uname.setStyleSheet(f"color: {COLORS['text_muted']}; font-size: 13px;")
        info.addWidget(uname)

        stats = profile.get("stats", {})
        parts = []
        for key in ("films", "following", "followers"):
            if key in stats:
                parts.append(f"{stats[key]:,} {key.capitalize()}")
        if parts:
            stats_lbl = QLabel("  ·  ".join(parts))
            stats_lbl.setStyleSheet(f"color: {COLORS['text_muted']}; font-size: 12px;")
            info.addWidget(stats_lbl)

        top.addLayout(info, stretch=1)
        layout.addLayout(top)

        layout.addWidget(HSeparator())

        # MatchCut button + description
        btn = GreenButton("MatchCut")
        btn.setFixedWidth(150)
        btn.clicked.connect(on_matchcut)
        layout.addWidget(btn, 0, Qt.AlignmentFlag.AlignLeft)

        desc = QLabel(
            '"In the film industry, a \'Match Cut\' represents a perfect and seamless '
            'transition from one scene to another based on their visual similarities."'
        )
        desc.setStyleSheet(f"color: {COLORS['text_muted']}; font-size: 12px; font-style: italic;")
        desc.setWordWrap(True)
        desc.setMaximumWidth(540)
        layout.addWidget(desc)


# ---------------------------------------------------------------------------
# Profile screen (header + analysis area)
# ---------------------------------------------------------------------------

class ProfileScreen(QWidget):
    def __init__(self, profile: dict, on_matchcut, parent=None):
        super().__init__(parent)
        self._u2_profile: dict = {}
        self._analysis_sections: list[QWidget] = []

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        root.addWidget(scroll)

        body = QWidget()
        self._body_layout = QVBoxLayout(body)
        self._body_layout.setContentsMargins(40, 32, 40, 40)
        self._body_layout.setSpacing(0)
        scroll.setWidget(body)

        # Welcome banner above profile
        self._body_layout.addWidget(WelcomeBanner())

        self._header = ProfileHeader(profile, on_matchcut)
        self._body_layout.addWidget(self._header)

        # Loading row
        self._loading_widget = QWidget()
        lrow = QHBoxLayout(self._loading_widget)
        lrow.setContentsMargins(0, 24, 0, 24)
        self._spinner = SpinnerWidget(44)
        self._loading_lbl = QLabel("Loading data…")
        self._loading_lbl.setStyleSheet(f"color: {COLORS['text_muted']}; font-size: 14px;")
        lrow.addStretch()
        lrow.addWidget(self._spinner)
        lrow.addSpacing(14)
        lrow.addWidget(self._loading_lbl)
        lrow.addStretch()
        self._loading_widget.hide()
        self._body_layout.addWidget(self._loading_widget)

        self._analysis_area = QWidget()
        self._analysis_layout = QVBoxLayout(self._analysis_area)
        self._analysis_layout.setContentsMargins(0, 24, 0, 0)
        self._analysis_layout.setSpacing(24)
        self._body_layout.addWidget(self._analysis_area)

        self._body_layout.addStretch()

    def avatar_widget(self):
        return self._header.avatar

    def set_loading(self, on: bool, msg: str = "Loading data…"):
        self._loading_lbl.setText(msg)
        if on:
            self._loading_widget.show()
            self._spinner.start()
        else:
            self._spinner.stop()
            self._loading_widget.hide()

    def update_loading_msg(self, msg: str):
        self._loading_lbl.setText(msg)

    def clear_analysis(self):
        while self._analysis_layout.count():
            item = self._analysis_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self._analysis_sections = []

    def show_analysis(self, result: dict, u1_name: str, u2_name: str):
        self.clear_analysis()
        sections = [
            HolyTrinitySection(result["holy_trinity"], u1_name, u2_name),
            DealbreakersSection(result["dealbreakers"], u1_name, u2_name),
            GenreSection(result["genre_data"], u1_name, u2_name),
            RecommendationsSection(
                result["u1_recommends"], result["u2_recommends"],
                u1_name, u2_name,
            ),
        ]
        for s in sections:
            eff = QGraphicsOpacityEffect(s)
            eff.setOpacity(0)
            s.setGraphicsEffect(eff)
            self._analysis_layout.addWidget(s)

        self._analysis_sections = sections
        QTimer.singleShot(60, lambda: staggered_entrance(sections, step=220))

    def show_error(self, msg: str):
        err = QLabel(f"Error: {msg[:400]}")
        err.setStyleSheet(f"color: {COLORS['red']}; font-size: 12px;")
        err.setWordWrap(True)
        self._analysis_layout.addWidget(err)


# ---------------------------------------------------------------------------
# Main Window
# ---------------------------------------------------------------------------

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("MatchCut — Letterboxd Compatibility")
        self.setMinimumSize(900, 600)
        self.resize(1060, 760)
        self.setStyleSheet(GLOBAL_STYLE)

        self._u1_profile: dict = {}
        self._u2_profile: dict = {}
        self._pending_u2_username: str = ""
        # Prefer env var; the login screen field can override at analysis time
        self._tmdb_key: str = os.environ.get("TMDB_API_KEY", "")
        self._pool = QThreadPool.globalInstance()
        self._pool.setMaxThreadCount(4)

        self._stack = QStackedWidget()
        self.setCentralWidget(self._stack)

        self._login_screen = LoginScreen(on_submit=self._load_user1)
        self._stack.addWidget(self._login_screen)   # index 0

        # Profile screen added dynamically at index 1
        self._profile_screen: ProfileScreen | None = None
        self._slideshow_screen: SlideshowWidget | None = None

        fade_in(self, duration=400)

    # ------------------------------------------------------------------

    def _load_user1(self, username: str):
        worker = ProfileWorker(username)
        worker.signals.result.connect(self._on_profile_loaded)
        worker.signals.error.connect(self._on_profile_error)
        self._pool.start(worker)

    @pyqtSlot(object)
    def _on_profile_loaded(self, data: dict):
        if not data.get("valid", True):
            self._login_screen.show_error(
                f'No Letterboxd account found for "{data["username"]}". '
                "Check the spelling and try again."
            )
            return

        self._u1_profile = data
        self._login_screen.show_loading(False)

        # Build profile screen
        screen = ProfileScreen(data, on_matchcut=self._open_popup)
        if self._profile_screen is not None:
            self._stack.removeWidget(self._profile_screen)
            self._profile_screen.deleteLater()

        self._profile_screen = screen
        self._stack.addWidget(screen)
        self._stack.setCurrentWidget(screen)

        # Fetch avatar in background
        if data.get("avatar_url"):
            self._fetch_avatar(data["avatar_url"], screen.avatar_widget())

    @pyqtSlot(str)
    def _on_profile_error(self, msg: str):
        self._login_screen.show_error("Could not reach Letterboxd. Check your connection.")

    def _fetch_avatar(self, url: str, avatar_widget):
        from scraper import fetch_image_bytes
        from PyQt6.QtCore import QRunnable, QObject, pyqtSignal

        class _Sig(QObject):
            done = pyqtSignal(bytes)

        class _Run(QRunnable):
            def __init__(self_, sig):
                super().__init__()
                self_.sig = sig

            def run(self_):
                data = fetch_image_bytes(url)
                if data:
                    self_.sig.done.emit(data)

        sig = _Sig()
        sig.done.connect(avatar_widget.set_image_bytes)
        self._pool.start(_Run(sig))

    # ------------------------------------------------------------------

    def _open_popup(self):
        username1 = self._u1_profile.get("username", "")
        if not username1:
            return

        popup = MatchPopup(username1, self._tmdb_key, parent=self)
        popup.confirmed.connect(self._on_user2_selected)

        geo = self.geometry()
        popup.adjustSize()
        popup.move(
            geo.center().x() - popup.width() // 2,
            geo.center().y() - popup.height() // 2,
        )
        popup.exec()

    @pyqtSlot(str, str)
    def _on_user2_selected(self, username2: str, tmdb_key: str):
        if not self._profile_screen:
            return

        self._tmdb_key = tmdb_key
        self._pending_u2_username = username2
        self._u2_profile = {}   # clear stale data from any previous run
        self._profile_screen.clear_analysis()
        self._profile_screen.set_loading(True, "Loading data…")

        self._analysis_worker = AnalysisWorker(
            self._u1_profile.get("username", ""),
            username2,
            tmdb_key,
        )
        self._analysis_worker.signals.progress.connect(self._profile_screen.update_loading_msg)
        self._analysis_worker.signals.result.connect(self._on_analysis_done)
        self._analysis_worker.signals.error.connect(self._on_analysis_error)
        self._pool.start(self._analysis_worker)

        w2 = ProfileWorker(username2)
        w2.signals.result.connect(lambda d: setattr(self, "_u2_profile", d))
        self._pool.start(w2)

    @pyqtSlot(object)
    def _on_analysis_done(self, result: dict):
        if not self._profile_screen:
            return
        self._profile_screen.set_loading(False)

        u1 = self._u1_profile.get("display_name") or self._u1_profile.get("username", "User 1")
        # _u2_profile may not have loaded yet (race condition) — fall back to the username
        u2 = (self._u2_profile.get("display_name")
              or self._u2_profile.get("username")
              or self._pending_u2_username
              or "User 2")

        # Remove old slideshow if one exists
        if self._slideshow_screen is not None:
            self._stack.removeWidget(self._slideshow_screen)
            self._slideshow_screen.deleteLater()
            self._slideshow_screen = None

        slideshow = SlideshowWidget(
            result, u1, u2,
            u1_avatar_url=self._u1_profile.get("avatar_url"),
            u2_avatar_url=self._u2_profile.get("avatar_url"),
        )
        slideshow.finished.connect(self._on_slideshow_done)
        self._slideshow_screen = slideshow
        self._stack.addWidget(slideshow)
        self._stack.setCurrentWidget(slideshow)

    def _on_slideshow_done(self):
        """User clicked 'Start over' on the last slide — go back to profile."""
        if self._slideshow_screen is not None:
            self._stack.removeWidget(self._slideshow_screen)
            self._slideshow_screen.deleteLater()
            self._slideshow_screen = None
        if self._profile_screen:
            self._stack.setCurrentWidget(self._profile_screen)

    @pyqtSlot(str)
    def _on_analysis_error(self, msg: str):
        if self._profile_screen:
            self._profile_screen.set_loading(False)
            self._profile_screen.show_error(msg)
