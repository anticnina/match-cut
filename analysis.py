"""Data analysis logic for MatchCut."""

from collections import Counter
from typing import Optional

import pandas as pd

from config import HIGH_RATING_THRESHOLD, TOP_RECOMMENDATIONS


# ---------------------------------------------------------------------------
# Merge helper
# ---------------------------------------------------------------------------

def merge_dataframes(df1: pd.DataFrame, df2: pd.DataFrame) -> pd.DataFrame:
    """
    Outer-join both users' DataFrames on movie_id.
    Columns suffixed _u1 / _u2.
    """
    df1 = df1.copy()
    df2 = df2.copy()
    for df in (df1, df2):
        if "genres" not in df.columns:
            df["genres"] = [[] for _ in range(len(df))]

    merged = pd.merge(
        df1, df2,
        on="movie_id",
        how="outer",
        suffixes=("_u1", "_u2"),
    )
    # Coalesce shared columns
    for col in ("title", "release_year"):
        if f"{col}_u1" in merged.columns:
            merged[col] = merged[f"{col}_u1"].combine_first(merged[f"{col}_u2"])
    merged["genres"] = merged.apply(
        lambda r: r["genres_u1"] if isinstance(r.get("genres_u1"), list) and r["genres_u1"]
        else r.get("genres_u2", []),
        axis=1,
    )
    return merged


# ---------------------------------------------------------------------------
# Section 1: Holy Trinity
# ---------------------------------------------------------------------------

def holy_trinity(merged: pd.DataFrame) -> pd.DataFrame:
    """
    Movies where both users gave >= HIGH_RATING_THRESHOLD OR both liked.
    Returns rows sorted by average rating desc.
    """
    both_rated = (
        merged["rating_u1"].notna() & merged["rating_u2"].notna() &
        (merged["rating_u1"] >= HIGH_RATING_THRESHOLD) &
        (merged["rating_u2"] >= HIGH_RATING_THRESHOLD)
    )
    both_liked = merged["is_liked_u1"].eq(True) & merged["is_liked_u2"].eq(True)
    result = merged[both_rated | both_liked].copy()
    result["avg_rating"] = (
        result["rating_u1"].fillna(0) + result["rating_u2"].fillna(0)
    ) / 2
    return result.sort_values("avg_rating", ascending=False).head(20)


# ---------------------------------------------------------------------------
# Section 2: Dealbreakers
# ---------------------------------------------------------------------------

DEALBREAKER_THRESHOLD = 1.5

def dealbreakers(merged: pd.DataFrame) -> pd.DataFrame:
    """
    Movies both watched with a rating gap of at least DEALBREAKER_THRESHOLD.
    Returns empty DataFrame (not None) when none qualify.
    """
    both_watched = merged["rating_u1"].notna() & merged["rating_u2"].notna()
    result = merged[both_watched].copy()
    result["rating_gap"] = abs(result["rating_u1"] - result["rating_u2"])
    result = result[result["rating_gap"] >= DEALBREAKER_THRESHOLD]
    return result.sort_values("rating_gap", ascending=False).head(5)


# ---------------------------------------------------------------------------
# Section 3: Genre comparison
# ---------------------------------------------------------------------------

def _count_genres(df: pd.DataFrame) -> Counter:
    c: Counter = Counter()
    for genres in df["genres"].dropna():
        if isinstance(genres, list):
            c.update(genres)
    return c


def _films_with_genres(df: pd.DataFrame) -> int:
    return sum(1 for g in df["genres"].dropna() if isinstance(g, list) and g)


def analyze_genre_compatibility(user1_df: pd.DataFrame, user2_df: pd.DataFrame) -> pd.DataFrame:
    """
    Proportional Jaccard-style genre compatibility.

    Steps:
      1. Normalize each user's genre counts into a 0–1 percentage distribution.
      2. Outer-join both distributions into a single DataFrame (missing → 0).
      3. For each genre compute:
           overlap         = min(p1, p2)
           jaccard_balance = min(p1, p2) / max(p1, p2)   (0 when one side is 0)
           shared_vibe     = overlap × jaccard_balance    = min² / max

      shared_vibe rewards genres that are simultaneously common AND balanced
      in both users' libraries, so "Horror@47% vs Horror@70%" beats
      "Drama@48% vs Drama@30%" even though Drama has more raw overlap.
    """
    c1 = _count_genres(user1_df)
    c2 = _count_genres(user2_df)
    total1 = sum(c1.values()) or 1
    total2 = sum(c2.values()) or 1

    all_genres = set(c1) | set(c2)
    rows = []
    for g in all_genres:
        p1 = c1[g] / total1
        p2 = c2[g] / total2
        mn, mx = min(p1, p2), max(p1, p2)
        overlap         = mn
        jaccard_balance = (mn / mx) if mx > 0 else 0.0
        shared_vibe     = overlap * jaccard_balance   # = mn² / mx
        rows.append({
            "genre":          g,
            "user1_pct":      p1,
            "user2_pct":      p2,
            "overlap":        overlap,
            "jaccard_balance": jaccard_balance,
            "shared_vibe":    shared_vibe,
        })

    return pd.DataFrame(rows).sort_values("shared_vibe", ascending=False).reset_index(drop=True)


def genre_comparison(df1: pd.DataFrame, df2: pd.DataFrame) -> dict:
    c1 = _count_genres(df1)
    c2 = _count_genres(df2)
    total1 = _films_with_genres(df1) or 1
    total2 = _films_with_genres(df2) or 1

    u1_top = c1.most_common(1)[0][0] if c1 else "N/A"
    u2_top = c2.most_common(1)[0][0] if c2 else "N/A"
    u1_top_pct = round(c1[u1_top] / total1 * 100) if c1 else 0
    u2_top_pct = round(c2[u2_top] / total2 * 100) if c2 else 0

    compat = analyze_genre_compatibility(df1, df2)

    if compat.empty:
        best_genre = "N/A"
        best_overlap_pct = 0
    else:
        best = compat.iloc[0]
        best_genre = best["genre"]
        # Display the real overlap (min of both percentages) as an integer %
        best_overlap_pct = round(best["overlap"] * 100)

    return {
        "u1_top":      u1_top,
        "u1_top_pct":  u1_top_pct,
        "u2_top":      u2_top,
        "u2_top_pct":  u2_top_pct,
        "overlap":     best_genre,
        "overlap_pct": best_overlap_pct,
        "u1_counts":   c1,
        "u2_counts":   c2,
    }


# ---------------------------------------------------------------------------
# Section 4: Cross-Recommendations
# ---------------------------------------------------------------------------

def _recommend(
    source_df: pd.DataFrame,
    target_df: pd.DataFrame,
    priority_genres: list[str],
    n: int = TOP_RECOMMENDATIONS,
) -> pd.DataFrame:
    """
    High-rated / liked films from source that target has NOT watched.
    Priority given to films in priority_genres.
    """
    source_ids = set(source_df["movie_id"])
    target_ids = set(target_df["movie_id"].dropna())
    unwatched_by_target = source_ids - target_ids

    candidates = source_df[source_df["movie_id"].isin(unwatched_by_target)].copy()
    candidates = candidates[
        (candidates["rating"].fillna(0) >= HIGH_RATING_THRESHOLD) |
        candidates["is_liked"].fillna(False)
    ]

    def priority(row):
        genres = row["genres"] if isinstance(row["genres"], list) else []
        return any(g in priority_genres for g in genres)

    if priority_genres:
        candidates["_priority"] = candidates.apply(priority, axis=1)
        candidates = candidates.sort_values(
            ["_priority", "rating"], ascending=[False, False]
        )
    else:
        candidates = candidates.sort_values("rating", ascending=False)

    cols = ["movie_id", "title", "rating", "is_liked", "genres", "release_year"]
    if "poster_url" in candidates.columns:
        cols.append("poster_url")
    return candidates.head(n)[cols]


def cross_recommendations(
    df1: pd.DataFrame,
    df2: pd.DataFrame,
    genre_data: dict,
) -> dict:
    """
    Returns {"u1_recommends": DataFrame, "u2_recommends": DataFrame}.
    """
    priority = [genre_data.get("overlap", ""), genre_data.get("u2_top", "")]
    priority = [g for g in priority if g and g != "N/A"]

    u1_recs = _recommend(df1, df2, priority_genres=priority)

    priority2 = [genre_data.get("overlap", ""), genre_data.get("u1_top", "")]
    priority2 = [g for g in priority2 if g and g != "N/A"]
    u2_recs = _recommend(df2, df1, priority_genres=priority2)

    return {"u1_recommends": u1_recs, "u2_recommends": u2_recs}


# ---------------------------------------------------------------------------
# Compatibility score
# ---------------------------------------------------------------------------

def compatibility_score(
    holy_trinity_df: pd.DataFrame,
    dealbreakers_df: pd.DataFrame,
    genre_data: dict,
) -> dict:
    """
    Returns a 0-100 score and a tier label.

    Scoring:
      Base:       50  (they already follow each other)
      +5 per shared favorite, capped at +30
      +genre overlap_pct * 0.3, capped at +30
      -7 per dealbreaker film, capped at -30
    """
    shared_favs   = min(len(holy_trinity_df), 6)
    genre_bonus   = min(genre_data.get("overlap_pct", 0) * 0.3, 30)
    breaker_count = min(len(dealbreakers_df), 4)

    score = 50 + shared_favs * 5 + genre_bonus - breaker_count * 7
    score = max(0, min(100, round(score)))

    if score >= 80:
        tier = "Cinematic Soulmates"
    elif score >= 65:
        tier = "Film Allies"
    elif score >= 45:
        tier = "Cinema Companions"
    else:
        tier = "Different Wavelengths"

    return {"score": score, "tier": tier}


# ---------------------------------------------------------------------------
# Orchestrator
# ---------------------------------------------------------------------------

def run_analysis(df1: pd.DataFrame, df2: pd.DataFrame) -> dict:
    merged      = merge_dataframes(df1, df2)
    ht          = holy_trinity(merged)
    db          = dealbreakers(merged)
    genre_data  = genre_comparison(df1, df2)
    recs        = cross_recommendations(df1, df2, genre_data)
    compat      = compatibility_score(ht, db, genre_data)

    return {
        "merged":        merged,
        "holy_trinity":  ht,
        "dealbreakers":  db,
        "genre_data":    genre_data,
        "u1_recommends": recs["u1_recommends"],
        "u2_recommends": recs["u2_recommends"],
        "compat":        compat,
    }
