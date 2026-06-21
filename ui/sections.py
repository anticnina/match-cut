"""Analysis section widgets rendered on the main window."""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame,
    QScrollArea, QSizePolicy, QGridLayout,
)
from PyQt6.QtCore import Qt

from config import COLORS
from ui.widgets import (
    FilmCard, SectionHeader, GenreBadge, HSeparator, rating_to_stars,
)
import pandas as pd


def _muted(text: str) -> QLabel:
    lbl = QLabel(text)
    lbl.setStyleSheet(f"color: {COLORS['text_muted']}; font-size: 12px;")
    lbl.setWordWrap(True)
    return lbl


def _body(text: str) -> QLabel:
    lbl = QLabel(text)
    lbl.setStyleSheet(f"color: {COLORS['text_primary']}; font-size: 13px;")
    lbl.setWordWrap(True)
    return lbl


def _card_row(df: pd.DataFrame, u1_name: str = "", u2_name: str = "") -> QHBoxLayout:
    row = QHBoxLayout()
    row.setSpacing(10)
    for _, r in df.iterrows():
        genres = r.get("genres", []) or []
        card = FilmCard(
            title=r.get("title", ""),
            rating_u1=r.get("rating_u1") if "rating_u1" in r else r.get("rating"),
            rating_u2=r.get("rating_u2") if "rating_u2" in r else None,
            genres=genres if isinstance(genres, list) else [],
            year=r.get("release_year"),
        )
        row.addWidget(card)
    row.addStretch()
    return row


# ---------------------------------------------------------------------------
# Section 1 – Holy Trinity
# ---------------------------------------------------------------------------

class HolyTrinitySection(QWidget):
    def __init__(self, df: pd.DataFrame, u1_name: str, u2_name: str, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)

        layout.addWidget(SectionHeader("✦ The Holy Trinity — Zajednički favoriti"))
        layout.addWidget(_muted(
            f"Filmovi koje su i {u1_name} i {u2_name} ocenili visoko ili voleli."
        ))

        if df.empty:
            layout.addWidget(_body("Nema zajedničkih favorita još uvek."))
        else:
            layout.addLayout(_card_row(df, u1_name, u2_name))

        layout.addWidget(HSeparator())


# ---------------------------------------------------------------------------
# Section 2 – Dealbreakers
# ---------------------------------------------------------------------------

class DealbreakersSection(QWidget):
    def __init__(self, df: pd.DataFrame, u1_name: str, u2_name: str, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)

        layout.addWidget(SectionHeader("⚡ The Dealbreakers — Najveća neslaganja"))
        layout.addWidget(_muted(
            "Filmovi gde se ukusi najviše razilaze."
        ))

        if df.empty:
            layout.addWidget(_body("Nema velikih neslaganja — savršeni ste match!"))
        else:
            for _, row in df.iterrows():
                item = _DealbreakRow(row, u1_name, u2_name)
                layout.addWidget(item)

        layout.addWidget(HSeparator())


class _DealbreakRow(QFrame):
    def __init__(self, row, u1_name: str, u2_name: str, parent=None):
        super().__init__(parent)
        self.setStyleSheet(f"""
            QFrame {{
                background: {COLORS['bg_card']};
                border-radius: 8px;
                border: 1px solid {COLORS['border']};
            }}
        """)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(14, 10, 14, 10)

        title = QLabel(str(row.get("title", "")))
        title.setStyleSheet(f"color: {COLORS['text_primary']}; font-weight: bold; font-size: 13px;")
        layout.addWidget(title, stretch=2)

        for name, col in [(u1_name, "rating_u1"), (u2_name, "rating_u2")]:
            val = row.get(col)
            stars = rating_to_stars(val)
            lbl = QLabel(f"{name}: {stars}")
            lbl.setStyleSheet(f"color: {COLORS['orange']}; font-size: 13px; min-width: 110px;")
            layout.addWidget(lbl)

        gap = row.get("rating_gap", 0)
        gap_lbl = QLabel(f"±{gap:.1f}")
        gap_lbl.setStyleSheet(f"color: {COLORS['red']}; font-weight: bold; font-size: 14px;")
        layout.addWidget(gap_lbl)


# ---------------------------------------------------------------------------
# Section 3 – Genre comparison
# ---------------------------------------------------------------------------

class GenreSection(QWidget):
    def __init__(self, genre_data: dict, u1_name: str, u2_name: str, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)

        layout.addWidget(SectionHeader("◈ Genre Vibes — Poređenje žanrova"))

        grid = QHBoxLayout()
        grid.setSpacing(16)

        grid.addWidget(self._genre_block(
            u1_name, genre_data.get("u1_top", "N/A"),
            genre_data.get("u1_counts"),
            COLORS["green"],
        ))

        # Middle: overlap
        mid = self._overlap_block(
            genre_data.get("overlap", "N/A"),
            genre_data.get("overlap_pct", 0),
        )
        grid.addWidget(mid)

        grid.addWidget(self._genre_block(
            u2_name, genre_data.get("u2_top", "N/A"),
            genre_data.get("u2_counts"),
            COLORS["orange"],
        ))

        layout.addLayout(grid)
        layout.addWidget(HSeparator())

    def _genre_block(self, name: str, top: str, counts, color: str) -> QFrame:
        frame = QFrame()
        frame.setStyleSheet(f"""
            QFrame {{
                background: {COLORS['bg_card']};
                border-radius: 8px;
                border: 1px solid {COLORS['border']};
            }}
        """)
        v = QVBoxLayout(frame)
        v.setContentsMargins(14, 14, 14, 14)
        v.setSpacing(6)

        name_lbl = QLabel(name)
        name_lbl.setStyleSheet(f"color: {color}; font-weight: bold; font-size: 13px;")
        name_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        v.addWidget(name_lbl)

        fav_lbl = QLabel(top)
        fav_lbl.setStyleSheet(f"color: {COLORS['text_primary']}; font-size: 18px; font-weight: bold;")
        fav_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        fav_lbl.setWordWrap(True)
        v.addWidget(fav_lbl)

        if counts:
            from collections import Counter
            for genre, cnt in counts.most_common(5):
                row = QHBoxLayout()
                g = QLabel(genre)
                g.setStyleSheet(f"color: {COLORS['text_muted']}; font-size: 11px;")
                c = QLabel(str(cnt))
                c.setStyleSheet(f"color: {color}; font-size: 11px;")
                row.addWidget(g)
                row.addStretch()
                row.addWidget(c)
                v.addLayout(row)

        return frame

    def _overlap_block(self, genre: str, pct: int) -> QFrame:
        frame = QFrame()
        frame.setStyleSheet(f"""
            QFrame {{
                background: {COLORS['bg_secondary']};
                border-radius: 8px;
                border: 2px solid {COLORS['green']};
            }}
        """)
        v = QVBoxLayout(frame)
        v.setContentsMargins(14, 14, 14, 14)
        v.setSpacing(6)
        v.setAlignment(Qt.AlignmentFlag.AlignCenter)

        lbl = QLabel("Zajednički žanr")
        lbl.setStyleSheet(f"color: {COLORS['text_muted']}; font-size: 11px;")
        lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        v.addWidget(lbl)

        genre_lbl = QLabel(genre)
        genre_lbl.setStyleSheet(f"color: {COLORS['green']}; font-size: 20px; font-weight: bold;")
        genre_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        genre_lbl.setWordWrap(True)
        v.addWidget(genre_lbl)

        pct_lbl = QLabel(f"{pct}% overlap")
        pct_lbl.setStyleSheet(f"color: {COLORS['text_muted']}; font-size: 12px;")
        pct_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        v.addWidget(pct_lbl)

        return frame


# ---------------------------------------------------------------------------
# Section 4 – Cross-recommendations
# ---------------------------------------------------------------------------

class RecommendationsSection(QWidget):
    def __init__(
        self, u1_recs: pd.DataFrame, u2_recs: pd.DataFrame,
        u1_name: str, u2_name: str, parent=None,
    ):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)

        layout.addWidget(SectionHeader("♦ Cross-preporuke"))

        cols = QHBoxLayout()
        cols.setSpacing(20)
        cols.addWidget(self._rec_block(u1_name, u2_name, u1_recs, COLORS["green"]))
        cols.addWidget(self._rec_block(u2_name, u1_name, u2_recs, COLORS["orange"]))
        layout.addLayout(cols)

    def _rec_block(
        self, from_name: str, to_name: str,
        df: pd.DataFrame, color: str,
    ) -> QFrame:
        frame = QFrame()
        frame.setStyleSheet(f"""
            QFrame {{
                background: {COLORS['bg_card']};
                border-radius: 8px;
                border: 1px solid {COLORS['border']};
            }}
        """)
        v = QVBoxLayout(frame)
        v.setContentsMargins(14, 14, 14, 14)
        v.setSpacing(8)

        header = QLabel(f"{from_name} preporučuje →")
        header.setStyleSheet(f"color: {color}; font-weight: bold; font-size: 13px;")
        v.addWidget(header)

        to_lbl = QLabel(f"za {to_name}")
        to_lbl.setStyleSheet(f"color: {COLORS['text_muted']}; font-size: 11px;")
        v.addWidget(to_lbl)

        if df.empty:
            v.addWidget(_muted("Nema preporuka."))
        else:
            for _, row in df.iterrows():
                title = str(row.get("title", ""))
                rating = row.get("rating")
                genres = row.get("genres", []) or []

                title_lbl = QLabel(f"▸  {title}")
                title_lbl.setStyleSheet(f"color: {COLORS['text_primary']}; font-size: 13px; font-weight: bold;")
                title_lbl.setWordWrap(True)
                v.addWidget(title_lbl)

                meta_parts = []
                if rating:
                    meta_parts.append(rating_to_stars(rating))
                if isinstance(genres, list) and genres:
                    meta_parts.append(" · ".join(genres[:2]))
                if meta_parts:
                    meta = QLabel("  " + "   ".join(meta_parts))
                    meta.setStyleSheet(f"color: {COLORS['orange']}; font-size: 12px;")
                    v.addWidget(meta)

        v.addStretch()
        return frame
