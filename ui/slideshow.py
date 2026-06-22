"""Cinematic slide-by-slide analysis presentation."""

import random
import requests as _requests

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame,
    QPushButton, QSizePolicy, QGraphicsOpacityEffect,
)
from PyQt6.QtCore import (
    Qt, QPropertyAnimation, QEasingCurve, pyqtSignal,
    QRunnable, QObject, QThreadPool, QTimer,
)
from PyQt6.QtGui import QColor, QPainter, QPainterPath, QPixmap

import pandas as pd
from config import COLORS
from ui.widgets import AvatarLabel, rating_to_stars


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _label(text: str, size: int, color: str, weight: str = "normal",
           align=Qt.AlignmentFlag.AlignCenter, wrap: bool = True) -> QLabel:
    lbl = QLabel(text)
    lbl.setAlignment(align)
    lbl.setWordWrap(wrap)
    lbl.setStyleSheet(
        f"color: {color}; font-size: {size}px; font-weight: {weight};"
        f" background: transparent;"
    )
    return lbl


_PLACEHOLDER_COLORS = [
    "#1a3a4a", "#2d1a4a", "#1a3d2d", "#4a2d1a",
    "#3d1a1a", "#1a2d4a", "#3a1a3a", "#1a3a3a",
]

POSTER_W = 120
POSTER_H = 180


# ---------------------------------------------------------------------------
# Async poster widget
# ---------------------------------------------------------------------------

class _FetchSig(QObject):
    done = pyqtSignal(bytes)


class _FetchRunnable(QRunnable):
    def __init__(self, url: str, sig: _FetchSig):
        super().__init__()
        self._url = url
        self._sig = sig

    def run(self):
        try:
            r = _requests.get(self._url, timeout=10)
            if r.ok:
                self._sig.done.emit(r.content)
        except Exception:
            pass


class PosterWidget(QWidget):
    """POSTER_W × POSTER_H rounded-corner poster; loads image asynchronously."""

    def __init__(self, title: str, poster_url: str | None = None, parent=None):
        super().__init__(parent)
        self.setFixedSize(POSTER_W, POSTER_H)
        self._pixmap: QPixmap | None = None
        self._bg = QColor(random.choice(_PLACEHOLDER_COLORS))
        self._letter = (title[0].upper() if title else "?")

        if poster_url:
            sig = _FetchSig(self)
            sig.done.connect(self._on_bytes)
            self._sig = sig   # keep reference alive
            QThreadPool.globalInstance().start(_FetchRunnable(poster_url, sig))

    def _on_bytes(self, data: bytes):
        pix = QPixmap()
        pix.loadFromData(data)
        if not pix.isNull():
            self._pixmap = pix.scaled(
                POSTER_W, POSTER_H,
                Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                Qt.TransformationMode.SmoothTransformation,
            )
            self.update()

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)

        path = QPainterPath()
        path.addRoundedRect(0, 0, self.width(), self.height(), 8, 8)
        p.setClipPath(path)

        if self._pixmap:
            sx = max(0, (self._pixmap.width()  - self.width())  // 2)
            sy = max(0, (self._pixmap.height() - self.height()) // 2)
            p.drawPixmap(0, 0, self._pixmap, sx, sy, self.width(), self.height())
        else:
            p.fillRect(self.rect(), self._bg)
            p.setPen(QColor(255, 255, 255, 55))
            font = p.font()
            font.setPointSize(32)
            font.setBold(True)
            p.setFont(font)
            p.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, self._letter)

        p.end()


# ---------------------------------------------------------------------------
# Film card (poster + title + ratings)
# ---------------------------------------------------------------------------

class SlideFilmCard(QFrame):
    def __init__(self, title: str, poster_url: str | None = None,
                 rating_u1=None, rating_u2=None,
                 u1_name: str = "You", u2_name: str = "Them",
                 gap: float | None = None,
                 parent=None):
        super().__init__(parent)
        self.setObjectName("SlideFilmCard")
        self.setFixedWidth(POSTER_W + 16)
        self.setStyleSheet(f"""
            #SlideFilmCard {{
                background: {COLORS['bg_card']};
                border-radius: 10px;
                border: 1px solid {COLORS['border']};
            }}
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 12)
        layout.setSpacing(8)
        layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        # Poster
        poster = PosterWidget(title, poster_url)
        layout.addWidget(poster, 0, Qt.AlignmentFlag.AlignHCenter)

        # Title
        t = QLabel(title)
        t.setAlignment(Qt.AlignmentFlag.AlignCenter)
        t.setWordWrap(True)
        t.setStyleSheet(
            f"color: {COLORS['text_primary']}; font-size: 12px;"
            f" font-weight: 600; background: transparent;"
        )
        layout.addWidget(t)

        # Ratings
        for name, val in [(u1_name, rating_u1), (u2_name, rating_u2)]:
            if val is not None:
                lbl = QLabel(f"{name}: {rating_to_stars(val)}")
                lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
                lbl.setStyleSheet(
                    f"color: {COLORS['green']}; font-size: 11px; background: transparent;"
                )
                layout.addWidget(lbl)

        # Gap badge (dealbreakers only)
        if gap is not None:
            g = QLabel(f"±{gap:.1f} stars")
            g.setAlignment(Qt.AlignmentFlag.AlignCenter)
            g.setStyleSheet(
                f"color: {COLORS['red']}; font-weight: bold;"
                f" font-size: 12px; background: transparent;"
            )
            layout.addWidget(g)


# ---------------------------------------------------------------------------
# "Next" button
# ---------------------------------------------------------------------------

class NextButton(QPushButton):
    def __init__(self, label: str = "Next", parent=None):
        super().__init__(label, parent)
        self.setFixedSize(180, 46)
        self.setStyleSheet(f"""
            QPushButton {{
                background: {COLORS['green']};
                color: #000;
                font-weight: bold;
                font-size: 15px;
                border-radius: 23px;
                border: none;
            }}
            QPushButton:hover  {{ background: #00c848; }}
            QPushButton:pressed {{ background: #009e3c; }}
        """)


# ---------------------------------------------------------------------------
# Base slide
# ---------------------------------------------------------------------------

class BaseSlide(QWidget):
    next_requested = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet("background: transparent;")
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(60, 40, 60, 40)
        outer.setSpacing(0)
        outer.addStretch(1)

        self._content = QVBoxLayout()
        self._content.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._content.setSpacing(24)
        outer.addLayout(self._content)

        outer.addStretch(1)

        btn_row = QHBoxLayout()
        self._next_btn = NextButton()
        self._next_btn.clicked.connect(self.next_requested)
        btn_row.addStretch()
        btn_row.addWidget(self._next_btn)
        btn_row.addStretch()
        outer.addLayout(btn_row)
        outer.addSpacing(28)

    def add(self, widget: QWidget):
        self._content.addWidget(widget)

    def add_layout(self, layout):
        self._content.addLayout(layout)

    def set_next_label(self, text: str):
        self._next_btn.setText(text)


# ---------------------------------------------------------------------------
# Slide 1: Co-watched count
# ---------------------------------------------------------------------------

class OverlapSlide(BaseSlide):
    def __init__(self, co_watched: int, u1_name: str, u2_name: str, parent=None):
        super().__init__(parent)
        self.add(_label("The two of you watched a total of", 40, COLORS["text_muted"], "700"))
        self.add(_label(str(co_watched), 96, COLORS["green"], "900"))
        self.add(_label("of the same movies!", 40, COLORS["text_muted"], "700"))


# ---------------------------------------------------------------------------
# Slide 2: Mutual Favorites
# ---------------------------------------------------------------------------

class MutualFavoritesSlide(BaseSlide):
    def __init__(self, df: pd.DataFrame, u1_name: str, u2_name: str, parent=None):
        super().__init__(parent)
        self.add(_label("Mutual Favorites", 36, COLORS["text_primary"], "800"))
        self.add(_label("Films you both loved", 15, COLORS["text_muted"], "400"))

        if df.empty:
            self.add(_label("No shared favorites yet — keep watching!", 16, COLORS["text_muted"]))
            return

        sample = df.sample(min(4, len(df))).reset_index(drop=True)
        row_layout = QHBoxLayout()
        row_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        row_layout.setSpacing(16)
        for _, row in sample.iterrows():
            poster_url = _get(row, "poster_url_u1") or _get(row, "poster_url_u2") or _get(row, "poster_url")
            card = SlideFilmCard(
                title=str(_get(row, "title") or ""),
                poster_url=poster_url,
                rating_u1=_get(row, "rating_u1"),
                rating_u2=_get(row, "rating_u2"),
                u1_name=u1_name,
                u2_name=u2_name,
            )
            row_layout.addWidget(card)
        self.add_layout(row_layout)


# ---------------------------------------------------------------------------
# Slide 3: Dealbreakers
# ---------------------------------------------------------------------------

class DealbreakersSlide(BaseSlide):
    def __init__(self, df: pd.DataFrame, u1_name: str, u2_name: str, parent=None):
        super().__init__(parent)

        if df.empty:
            self.add(_label(
                "It seems like there are no films that have left\n"
                "a completely different impression on you!\n"
                "We're off to a good start!",
                22, COLORS["text_primary"], "700",
            ))
            return

        self.add(_label(
            "Uh-oh! It seems some movies left you both\nwith very different impressions!",
            28, COLORS["text_primary"], "800",
        ))

        cards_row = QHBoxLayout()
        cards_row.setAlignment(Qt.AlignmentFlag.AlignCenter)
        cards_row.setSpacing(16)
        for _, row in df.head(4).iterrows():
            poster_url = _get(row, "poster_url_u1") or _get(row, "poster_url_u2") or _get(row, "poster_url")
            card = SlideFilmCard(
                title=str(_get(row, "title") or ""),
                poster_url=poster_url,
                rating_u1=_get(row, "rating_u1"),
                rating_u2=_get(row, "rating_u2"),
                u1_name=u1_name,
                u2_name=u2_name,
                gap=float(_get(row, "rating_gap") or 0),
            )
            cards_row.addWidget(card)
        self.add_layout(cards_row)


# ---------------------------------------------------------------------------
# Async avatar loader for slides
# ---------------------------------------------------------------------------

def _load_avatar_async(url: str, avatar: AvatarLabel):
    sig = _FetchSig(avatar)
    sig.done.connect(avatar.set_image_bytes)
    avatar._genre_sig = sig   # keep reference alive
    QThreadPool.globalInstance().start(_FetchRunnable(url, sig))


# ---------------------------------------------------------------------------
# Slide 4: Genre vibes — user panels first, overlap fades in after 2s
# ---------------------------------------------------------------------------

class GenreSlide(BaseSlide):
    def __init__(self, genre_data: dict, u1_name: str, u2_name: str,
                 u1_avatar_url: str | None = None, u2_avatar_url: str | None = None,
                 parent=None):
        super().__init__(parent)
        self.add(_label("Your Genre Vibes", 36, COLORS["text_primary"], "800"))

        cols = QHBoxLayout()
        cols.setSpacing(24)
        cols.setAlignment(Qt.AlignmentFlag.AlignCenter)

        cols.addWidget(self._user_panel(
            u1_name,
            genre_data.get("u1_top", "N/A"),
            genre_data.get("u1_top_pct", 0),
            u1_avatar_url,
            COLORS["orange"],
        ))

        self._overlap_widget = self._overlap_block(
            genre_data.get("overlap", "N/A"),
            genre_data.get("overlap_pct", 0),
        )
        self._overlap_widget.setVisible(False)
        cols.addWidget(self._overlap_widget)

        cols.addWidget(self._user_panel(
            u2_name,
            genre_data.get("u2_top", "N/A"),
            genre_data.get("u2_top_pct", 0),
            u2_avatar_url,
            COLORS["blue"],
        ))

        self.add_layout(cols)
        QTimer.singleShot(2000, self._reveal_overlap)

    def _user_panel(self, name: str, top_genre: str, pct: int,
                    avatar_url: str | None, color: str) -> QFrame:
        f = QFrame()
        f.setObjectName("UserPanel")
        f.setFixedWidth(200)
        # Object-name selector so the rule never leaks into child widgets
        f.setStyleSheet(f"#UserPanel {{ background: {COLORS['bg_card']}; border-radius: 16px; border: none; }}")
        v = QVBoxLayout(f)
        v.setContentsMargins(20, 28, 20, 28)
        v.setSpacing(12)
        v.setAlignment(Qt.AlignmentFlag.AlignCenter)

        avatar = AvatarLabel(size=64)
        if avatar_url:
            _load_avatar_async(avatar_url, avatar)
        v.addWidget(avatar, 0, Qt.AlignmentFlag.AlignHCenter)

        v.addWidget(_label(name, 14, color, "700"))
        v.addWidget(_label(top_genre if top_genre != "N/A" else "—", 22, COLORS["text_primary"], "800"))
        v.addWidget(_label(
            f"{pct}% of their films" if top_genre != "N/A" else "No genre data",
            24, COLORS["text_muted"], "700",
        ))
        return f

    def _overlap_block(self, genre: str, pct: int) -> QFrame:
        f = QFrame()
        f.setObjectName("OverlapBlock")
        f.setFixedWidth(220)
        f.setStyleSheet(f"#OverlapBlock {{ background: {COLORS['bg_secondary']}; border-radius: 16px; border: none; }}")
        v = QVBoxLayout(f)
        v.setAlignment(Qt.AlignmentFlag.AlignCenter)
        v.setContentsMargins(20, 32, 20, 32)
        v.setSpacing(14)
        v.addWidget(_label("You both love", 18, COLORS["text_muted"], "600"))
        v.addWidget(_label(genre if genre != "N/A" else "—", 44, COLORS["green"], "900"))
        if genre != "N/A" and pct:
            v.addWidget(_label(f"overlap", 24, COLORS["text_muted"], "700"))
        return f

    def _reveal_overlap(self):
        # Set effect to opacity=0 BEFORE making the widget visible —
        # prevents the single-frame flash that made it look like a "popup"
        eff = QGraphicsOpacityEffect(self._overlap_widget)
        eff.setOpacity(0.0)
        self._overlap_widget.setGraphicsEffect(eff)
        self._overlap_widget.setVisible(True)

        anim = QPropertyAnimation(eff, b"opacity", self._overlap_widget)
        anim.setDuration(4500)
        anim.setStartValue(0.0)
        anim.setEndValue(1.0)
        anim.setEasingCurve(QEasingCurve.Type.InOutSine)
        anim.start()
        self._overlap_widget._reveal_anim = anim


# ---------------------------------------------------------------------------
# Slide 5: Recommendations  (profile pic header + poster cards per user)
# ---------------------------------------------------------------------------

class RecsSlide(BaseSlide):
    def __init__(self, u1_recs: pd.DataFrame, u2_recs: pd.DataFrame,
                 u1_name: str, u2_name: str,
                 u1_avatar_url: str | None = None,
                 u2_avatar_url: str | None = None,
                 parent=None):
        super().__init__(parent)
        self.add(_label("Watch These Next", 36, COLORS["text_primary"], "800"))

        cols = QHBoxLayout()
        cols.setSpacing(32)
        cols.setAlignment(Qt.AlignmentFlag.AlignCenter)
        cols.addWidget(self._rec_column(
            u1_name, u2_name, u1_recs, u1_avatar_url, COLORS["orange"],
        ))
        cols.addWidget(self._rec_column(
            u2_name, u1_name, u2_recs, u2_avatar_url, COLORS["blue"],
        ))
        self.add_layout(cols)

    def _rec_column(self, from_name: str, to_name: str, df: pd.DataFrame,
                    avatar_url: str | None, color: str) -> QWidget:
        col = QWidget()
        col.setStyleSheet("background: transparent;")
        v = QVBoxLayout(col)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(28)

        # ── Header: avatar + "X recommends to Y" ──────────────────────────
        header = QHBoxLayout()
        header.setSpacing(12)
        header.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)

        avatar = AvatarLabel(size=42)
        if avatar_url:
            _load_avatar_async(avatar_url, avatar)
        header.addWidget(avatar, 0, Qt.AlignmentFlag.AlignVCenter)

        lbl = QLabel(f"{from_name} recommends")
        lbl.setWordWrap(True)
        lbl.setMaximumWidth(260)
        lbl.setStyleSheet(
            f"color: {color}; font-size: 14px; font-weight: 700; background: transparent;"
        )
        header.addWidget(lbl)
        v.addLayout(header)

        # ── Film cards ──────────────────────────────────────────────────────
        cards = QHBoxLayout()
        cards.setSpacing(12)
        cards.setAlignment(Qt.AlignmentFlag.AlignLeft)

        if df.empty:
            empty = QLabel("Nothing to recommend yet.")
            empty.setStyleSheet(
                f"color: {COLORS['text_muted']}; font-size: 13px; background: transparent;"
            )
            cards.addWidget(empty)
        else:
            for _, row in df.head(2).iterrows():
                rating = _get(row, "rating")
                liked  = _get(row, "is_liked")
                # Show star rating; fall back to heart for liked-but-unrated films
                display_rating = rating if rating is not None else (5.0 if liked else None)
                card = SlideFilmCard(
                    title=str(_get(row, "title") or ""),
                    poster_url=_get(row, "poster_url"),
                    rating_u1=display_rating,
                    u1_name=from_name,
                )
                cards.addWidget(card)

        v.addLayout(cards)
        return col


# ---------------------------------------------------------------------------
# Slide 6: Conclusion — MatchCut compatibility verdict
# ---------------------------------------------------------------------------

class ConclusionSlide(BaseSlide):
    def __init__(self, compat: dict, u1_name: str, u2_name: str,
                 u1_avatar_url: str | None = None,
                 u2_avatar_url: str | None = None,
                 parent=None):
        super().__init__(parent)
        score = compat.get("score", 0)
        tier  = compat.get("tier", "Cinema Companions")

        # ── Title ──────────────────────────────────────────────────────────
        self.add(_label("Your MatchCut", 28, COLORS["text_muted"], "600"))
        self.add(_label("Score", 28, COLORS["text_muted"], "600"))
        self._content.addSpacing(8)

        # ── Avatar pair ────────────────────────────────────────────────────
        pair_row = QHBoxLayout()
        pair_row.setSpacing(0)
        pair_row.setAlignment(Qt.AlignmentFlag.AlignCenter)

        av1 = AvatarLabel(size=80)
        if u1_avatar_url:
            _load_avatar_async(u1_avatar_url, av1)
        pair_row.addWidget(av1)

        sep = QLabel("×")
        sep.setStyleSheet(
            f"color: {COLORS['text_muted']}; font-size: 40px; font-weight: 300;"
            " background: transparent; padding: 0 16px;"
        )
        sep.setAlignment(Qt.AlignmentFlag.AlignCenter)
        pair_row.addWidget(sep)

        av2 = AvatarLabel(size=80)
        if u2_avatar_url:
            _load_avatar_async(u2_avatar_url, av2)
        pair_row.addWidget(av2)

        self.add_layout(pair_row)

        # ── Name row ───────────────────────────────────────────────────────
        name_row = QHBoxLayout()
        name_row.setAlignment(Qt.AlignmentFlag.AlignCenter)
        n1 = QLabel(u1_name)
        n1.setStyleSheet(
            f"color: {COLORS['orange']}; font-size: 14px; font-weight: 700;"
            " background: transparent;"
        )
        mid = QLabel("&")
        mid.setStyleSheet(
            f"color: {COLORS['text_muted']}; font-size: 14px;"
            " background: transparent; padding: 0 10px;"
        )
        n2 = QLabel(u2_name)
        n2.setStyleSheet(
            f"color: {COLORS['blue']}; font-size: 14px; font-weight: 700;"
            " background: transparent;"
        )
        name_row.addWidget(n1)
        name_row.addWidget(mid)
        name_row.addWidget(n2)
        self.add_layout(name_row)

        self._content.addSpacing(24)

        # ── Big score ──────────────────────────────────────────────────────
        self.add(_label(f"{score}%", 112, COLORS["green"], "900"))

        # ── Tagline replaces tier label ─────────────────────────────────────
        if score < 40:
            tagline = "Hope you love \u201cenemies to lovers\u201d because your tastes don't match at all"
        elif score < 70:
            tagline = "Well, you can agree to disagree"
        else:
            tagline = "Match from a movie scene!"

        tl = QLabel(tagline)
        tl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        tl.setWordWrap(True)
        tl.setMaximumWidth(520)
        tl.setStyleSheet(
            f"color: {COLORS['text_primary']}; font-size: 22px; font-weight: 600;"
            " background: transparent;"
        )
        self._content.addWidget(tl, 0, Qt.AlignmentFlag.AlignCenter)

        self.set_next_label("Start over  ↺")


# ---------------------------------------------------------------------------
# Utility: safe row value getter (handles both Series and dict)
# ---------------------------------------------------------------------------

def _get(row, key):
    try:
        val = row[key]
        if val is None or (isinstance(val, float) and __import__("math").isnan(val)):
            return None
        return val
    except (KeyError, TypeError):
        return None


# ---------------------------------------------------------------------------
# Slideshow orchestrator
# ---------------------------------------------------------------------------

class SlideshowWidget(QWidget):
    finished = pyqtSignal()

    def __init__(self, result: dict, u1_name: str, u2_name: str,
                 u1_avatar_url: str | None = None, u2_avatar_url: str | None = None,
                 parent=None):
        super().__init__(parent)
        self.setStyleSheet(f"background: {COLORS['bg']};")

        merged  = result["merged"]
        holy    = result["holy_trinity"]
        deal    = result["dealbreakers"]
        genre   = result["genre_data"]
        u1_recs = result["u1_recommends"]
        u2_recs = result["u2_recommends"]
        compat  = result.get("compat", {"score": 50, "tier": "Cinema Companions"})

        both = merged["title_u1"].notna() & merged["title_u2"].notna()
        co_watched = int(both.sum())

        self._slides = [
            OverlapSlide(co_watched, u1_name, u2_name),
            MutualFavoritesSlide(holy, u1_name, u2_name),
            DealbreakersSlide(deal, u1_name, u2_name),
            GenreSlide(genre, u1_name, u2_name, u1_avatar_url, u2_avatar_url),
            RecsSlide(u1_recs, u2_recs, u1_name, u2_name, u1_avatar_url, u2_avatar_url),
            ConclusionSlide(compat, u1_name, u2_name, u1_avatar_url, u2_avatar_url),
        ]

        self._index = 0
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)

        self._container = QWidget()
        self._container.setStyleSheet("background: transparent;")
        self._container_layout = QVBoxLayout(self._container)
        self._container_layout.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(self._container)

        for slide in self._slides:
            slide.next_requested.connect(self._advance)

        self._show_slide(0, animate=False)

    def _show_slide(self, index: int, animate: bool = True):
        slide = self._slides[index]
        while self._container_layout.count():
            item = self._container_layout.takeAt(0)
            if item.widget():
                item.widget().setParent(None)
        self._container_layout.addWidget(slide)
        slide.show()

        if animate:
            eff = QGraphicsOpacityEffect(slide)
            slide.setGraphicsEffect(eff)
            anim = QPropertyAnimation(eff, b"opacity", slide)
            anim.setDuration(800)
            anim.setStartValue(0.0)
            anim.setEndValue(1.0)
            anim.setEasingCurve(QEasingCurve.Type.OutSine)
            anim.start()
            slide._fade_anim = anim

    def _advance(self):
        current = self._slides[self._index]
        eff = QGraphicsOpacityEffect(current)
        current.setGraphicsEffect(eff)
        anim = QPropertyAnimation(eff, b"opacity", current)
        anim.setDuration(560)
        anim.setStartValue(1.0)
        anim.setEndValue(0.0)
        anim.setEasingCurve(QEasingCurve.Type.InSine)
        current._fade_out_anim = anim

        next_index = self._index + 1
        if next_index >= len(self._slides):
            anim.finished.connect(self.finished)
        else:
            def _show():
                self._index = next_index
                self._show_slide(next_index, animate=True)
            anim.finished.connect(_show)

        anim.start()
