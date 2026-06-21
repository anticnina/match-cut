"""Reusable styled widgets."""

from PyQt6.QtWidgets import (
    QLabel, QFrame, QHBoxLayout, QVBoxLayout, QWidget,
    QPushButton, QSizePolicy,
)
from PyQt6.QtGui import QPixmap, QPainter, QPainterPath, QColor, QFont, QFontMetrics
from PyQt6.QtCore import Qt, QSize, QByteArray

from config import COLORS


# ---------------------------------------------------------------------------
# Avatar
# ---------------------------------------------------------------------------

class AvatarLabel(QWidget):
    """Circular avatar from raw image bytes. Uses paintEvent (not QLabel)
    to avoid Qt's stylesheet/alignment interactions that cause visual artefacts."""

    def __init__(self, size: int = 72, parent=None):
        super().__init__(parent)
        self._size = size
        self.setFixedSize(size, size)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self._pixmap: QPixmap | None = None

    def paintEvent(self, _event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        if self._pixmap and not self._pixmap.isNull():
            p.drawPixmap(0, 0, self._pixmap)
        else:
            # Placeholder circle
            p.setBrush(QColor(COLORS["bg_card"]))
            p.setPen(QColor(COLORS["border"]))
            p.drawEllipse(1, 1, self._size - 2, self._size - 2)
        p.end()

    def set_image_bytes(self, data: bytes):
        raw = QPixmap()
        raw.loadFromData(QByteArray(data))
        if raw.isNull():
            return
        scaled = raw.scaled(
            self._size, self._size,
            Qt.AspectRatioMode.KeepAspectRatioByExpanding,
            Qt.TransformationMode.SmoothTransformation,
        )
        # Circular crop — center so we always clip around the middle of the image
        x_off = (scaled.width() - self._size) // 2
        y_off = (scaled.height() - self._size) // 2
        result = QPixmap(self._size, self._size)
        result.fill(Qt.GlobalColor.transparent)
        p = QPainter(result)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        path = QPainterPath()
        path.addEllipse(0, 0, self._size, self._size)
        p.setClipPath(path)
        p.drawPixmap(-x_off, -y_off, scaled)
        p.end()
        self._pixmap = result
        self.update()


# ---------------------------------------------------------------------------
# Star rating display
# ---------------------------------------------------------------------------

def rating_to_stars(rating: float | None) -> str:
    if rating is None:
        return "—"
    full = int(rating)
    half = 1 if (rating - full) >= 0.5 else 0
    return "★" * full + ("½" if half else "") or "—"


class RatingLabel(QLabel):
    def __init__(self, rating: float | None, parent=None):
        super().__init__(rating_to_stars(rating), parent)
        self.setStyleSheet(f"color: {COLORS['orange']}; font-size: 13px;")


# ---------------------------------------------------------------------------
# Film card
# ---------------------------------------------------------------------------

class FilmCard(QFrame):
    """Small card showing poster placeholder, title, and ratings."""

    def __init__(self, title: str, rating_u1=None, rating_u2=None,
                 genres: list | None = None, year=None, parent=None):
        super().__init__(parent)
        self.setObjectName("FilmCard")
        self.setStyleSheet(f"""
            #FilmCard {{
                background: {COLORS['bg_card']};
                border: 1px solid {COLORS['border']};
                border-radius: 8px;
            }}
        """)
        self.setFixedWidth(160)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(4)

        # Poster placeholder (green accent bar)
        poster = QFrame()
        poster.setFixedHeight(90)
        poster.setStyleSheet(f"background: {COLORS['bg_secondary']}; border-radius: 4px;")
        layout.addWidget(poster)

        # Title
        title_label = QLabel(title)
        title_label.setWordWrap(True)
        title_label.setStyleSheet(f"color: {COLORS['text_primary']}; font-weight: bold; font-size: 12px;")
        title_label.setFixedHeight(40)
        layout.addWidget(title_label)

        if year:
            yr = QLabel(str(int(year)))
            yr.setStyleSheet(f"color: {COLORS['text_muted']}; font-size: 11px;")
            layout.addWidget(yr)

        # Ratings row
        if rating_u1 is not None or rating_u2 is not None:
            row = QHBoxLayout()
            row.setSpacing(6)
            if rating_u1 is not None:
                row.addWidget(RatingLabel(rating_u1))
            if rating_u2 is not None:
                row.addWidget(RatingLabel(rating_u2))
            row.addStretch()
            layout.addLayout(row)

        if genres:
            genre_text = " · ".join(genres[:2])
            gl = QLabel(genre_text)
            gl.setStyleSheet(f"color: {COLORS['text_muted']}; font-size: 10px;")
            layout.addWidget(gl)

        layout.addStretch()


# ---------------------------------------------------------------------------
# Section header
# ---------------------------------------------------------------------------

class SectionHeader(QLabel):
    def __init__(self, text: str, parent=None):
        super().__init__(text, parent)
        self.setStyleSheet(f"""
            color: {COLORS['text_primary']};
            font-size: 18px;
            font-weight: bold;
            padding: 6px 0px;
            border-bottom: 2px solid {COLORS['green']};
        """)


# ---------------------------------------------------------------------------
# Genre badge
# ---------------------------------------------------------------------------

class GenreBadge(QLabel):
    def __init__(self, genre: str, color: str = COLORS["green"], parent=None):
        super().__init__(genre, parent)
        self.setStyleSheet(f"""
            background: transparent;
            border: 1px solid {color};
            border-radius: 10px;
            color: {color};
            font-size: 11px;
            padding: 2px 8px;
        """)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)


# ---------------------------------------------------------------------------
# Spinning loader
# ---------------------------------------------------------------------------

from PyQt6.QtCore import QTimer, QRect
from PyQt6.QtGui import QPen


class SpinnerWidget(QWidget):
    """Animated green arc spinner."""

    def __init__(self, size: int = 48, parent=None):
        super().__init__(parent)
        self._size = size
        self._angle = 0
        self.setFixedSize(size, size)
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)

    def start(self):
        self._timer.start(30)

    def stop(self):
        self._timer.stop()

    def _tick(self):
        self._angle = (self._angle + 12) % 360
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        pen = QPen(QColor(COLORS["green"]), 4)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        p.setPen(pen)
        margin = 6
        rect = QRect(margin, margin, self._size - margin * 2, self._size - margin * 2)
        p.drawArc(rect, self._angle * 16, 270 * 16)
        p.end()


# ---------------------------------------------------------------------------
# Separator
# ---------------------------------------------------------------------------

class HSeparator(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFrameShape(QFrame.Shape.HLine)
        self.setStyleSheet(f"color: {COLORS['border']}; margin: 8px 0;")


# ---------------------------------------------------------------------------
# Styled button
# ---------------------------------------------------------------------------

class GreenButton(QPushButton):
    def __init__(self, text: str, parent=None):
        super().__init__(text, parent)
        self.setStyleSheet(f"""
            QPushButton {{
                background: {COLORS['green']};
                color: #000;
                font-weight: bold;
                font-size: 14px;
                border-radius: 6px;
                padding: 8px 24px;
                border: none;
            }}
            QPushButton:hover {{
                background: #00c848;
            }}
            QPushButton:pressed {{
                background: #009e3c;
            }}
        """)
