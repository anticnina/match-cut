"""Letterboxd scraping and TMDB genre enrichment."""

import os
import re
import time
import logging
from typing import Optional
from urllib.parse import urljoin

import re
import requests
import pandas as pd
from bs4 import BeautifulSoup

from config import (
    LETTERBOXD_BASE, TMDB_BASE, TMDB_IMAGE_BASE,
    HEADERS, HIGH_RATING_THRESHOLD,
    MAX_RATINGS_PAGES, REQUEST_DELAY, TMDB_API_KEY,
)

logger = logging.getLogger(__name__)

_session = requests.Session()
_session.headers.update(HEADERS)


# ---------------------------------------------------------------------------
# Low-level helpers
# ---------------------------------------------------------------------------

def _get(url: str, params: dict | None = None) -> BeautifulSoup | None:
    try:
        r = _session.get(url, params=params, timeout=15)
        r.raise_for_status()
        time.sleep(REQUEST_DELAY)
        return BeautifulSoup(r.text, "lxml")
    except Exception as exc:
        logger.warning("GET %s failed: %s", url, exc)
        return None


def _tmdb_get(path: str, params: dict | None = None) -> dict:
    api_key = os.environ.get("TMDB_API_KEY", TMDB_API_KEY)
    base_params = {"api_key": api_key}
    if params:
        base_params.update(params)
    try:
        r = _session.get(f"{TMDB_BASE}{path}", params=base_params, timeout=10)
        r.raise_for_status()
        return r.json()
    except Exception as exc:
        logger.warning("TMDB %s failed: %s", path, exc)
        return {}


# ---------------------------------------------------------------------------
# Profile
# ---------------------------------------------------------------------------

def scrape_profile(username: str) -> dict:
    """Return display name, avatar URL, bio, and stat counts.
    Sets valid=False if the profile page cannot be found."""
    try:
        r = _session.get(f"{LETTERBOXD_BASE}/{username}/", timeout=15)
        if r.status_code == 404:
            return {"username": username, "valid": False}
        r.raise_for_status()
        time.sleep(REQUEST_DELAY)
        soup = BeautifulSoup(r.text, "lxml")
    except Exception as exc:
        logger.warning("Profile fetch failed for %s: %s", username, exc)
        return {"username": username, "valid": False}

    # Letterboxd 404 pages still return 200 in some cases — detect by missing profile section
    if not soup.select_one("section.profile-header, div.profile-summary, div#person"):
        # Try alternate check: look for the person table or header body
        if not soup.select_one("h1.title-1, .profile-name"):
            return {"username": username, "valid": False}

    display_name = username
    name_tag = soup.select_one("h1.title-1, span.title-3, .profile-name")
    if name_tag:
        display_name = name_tag.get_text(strip=True)

    avatar_url = None
    img = soup.select_one("div.profile-avatar img, .avatar img, .profile-avatar img")
    if img:
        avatar_url = img.get("src") or img.get("data-src")

    stats = {}
    for item in soup.select("ul.stats li a"):
        label_el = item.select_one(".definition")
        value_el = item.select_one(".value")
        if label_el and value_el:
            key = label_el.get_text(strip=True).lower()
            val = value_el.get_text(strip=True).replace(",", "")
            try:
                stats[key] = int(val)
            except ValueError:
                stats[key] = val

    return {
        "username": username,
        "display_name": display_name,
        "avatar_url": avatar_url,
        "stats": stats,
        "valid": True,
    }


# ---------------------------------------------------------------------------
# Following list
# ---------------------------------------------------------------------------

def scrape_following(username: str, progress_cb=None) -> list[dict]:
    """Return list of {username, display_name, avatar_url} dicts.

    Letterboxd HTML (verified June 2026):
      <td class="col-member table-person">
        <div class="person-summary">
          <a class="avatar -a40" href="/username/"><img alt="..." src="..."></a>
          <a class="name" href="/username/"> Display Name </a>
        </div>
      </td>
    First page: /following/  (no page number)
    Subsequent: /following/page/2/, /following/page/3/, ...
    """
    following = []
    page = 1
    while True:
        if page == 1:
            url = f"{LETTERBOXD_BASE}/{username}/following/"
        else:
            url = f"{LETTERBOXD_BASE}/{username}/following/page/{page}/"

        soup = _get(url)
        if soup is None:
            break

        persons = soup.select("div.person-summary")
        if not persons:
            break

        for div in persons:
            name_a = div.select_one("a.name")
            avatar_img = div.select_one("a.avatar img")
            if name_a:
                uname = name_a["href"].strip("/").split("/")[-1]
                dname = name_a.get_text(strip=True) or uname
                av = avatar_img.get("src") if avatar_img else None
                following.append({"username": uname, "display_name": dname, "avatar_url": av})

        if progress_cb:
            progress_cb(f"Loading following list… page {page} ({len(following)} found)")

        next_btn = soup.select_one("a.next")
        if not next_btn:
            break
        page += 1

    return following


# ---------------------------------------------------------------------------
# Ratings — via RSS feed (Cloudflare allows this; paginated sub-paths are blocked)
# ---------------------------------------------------------------------------

_RSS_NS = {
    "letterboxd": "https://letterboxd.com",
    "tmdb":       "https://themoviedb.org",
}

_EMPTY_COLS = ["movie_id", "title", "rating", "is_liked", "genres", "release_year", "tmdb_id", "poster_url"]


def scrape_ratings(username: str, progress_cb=None) -> pd.DataFrame:
    """
    Fetch film history from /{username}/rss/ — the only endpoint Cloudflare
    does not challenge.  Includes memberRating, memberLike, filmYear, and
    the TMDB movie ID so genre enrichment requires no title-search round-trips.

    Duplicates (rewatches) are collapsed: highest rating wins, liked=True
    if any entry is liked.
    """
    from xml.etree import ElementTree as ET

    url = f"{LETTERBOXD_BASE}/{username}/rss/"
    if progress_cb:
        progress_cb(f"Fetching {username}'s film diary...")
    try:
        r = _session.get(url, timeout=20)
        r.raise_for_status()
    except Exception as exc:
        logger.warning("RSS fetch failed for %s: %s", username, exc)
        return pd.DataFrame(columns=_EMPTY_COLS)

    try:
        root = ET.fromstring(r.content)
    except Exception as exc:
        logger.warning("RSS parse failed for %s: %s", username, exc)
        return pd.DataFrame(columns=_EMPTY_COLS)

    rows: dict[str, dict] = {}   # slug → row (deduplicated)

    for item in root.findall(".//item"):
        link = item.findtext("link") or ""
        # Link: https://letterboxd.com/user/film/SLUG/  or  …/film/SLUG/N/
        parts = [p for p in link.rstrip("/").split("/") if p]
        try:
            fi = parts.index("film")
            slug = parts[fi + 1]
        except (ValueError, IndexError):
            continue

        def _text(tag: str) -> Optional[str]:
            el = item.find(tag, _RSS_NS)
            return el.text if el is not None else None

        title    = _text("letterboxd:filmTitle") or slug
        year_s   = _text("letterboxd:filmYear")
        rating_s = _text("letterboxd:memberRating")
        like_s   = _text("letterboxd:memberLike")
        tmdb_s   = _text("tmdb:movieId")

        # Poster URL from <description> CDATA — always present, no API key needed
        desc_text = item.findtext("description") or ""
        m = re.search(r'<img[^>]+src="([^"]+)"', desc_text)
        rss_poster = m.group(1) if m else None

        year   = int(year_s)          if year_s   else None
        rating = float(rating_s)      if rating_s else None
        liked  = (like_s or "").strip().lower() == "yes"
        tmdb_id = int(tmdb_s)         if tmdb_s   else None

        if slug in rows:
            existing = rows[slug]
            if rating is not None:
                if existing["rating"] is None or rating > existing["rating"]:
                    existing["rating"] = rating
            if liked:
                existing["is_liked"] = True
        else:
            rows[slug] = {
                "movie_id":     slug,
                "title":        title,
                "rating":       rating,
                "is_liked":     liked,
                "genres":       [],
                "release_year": year,
                "tmdb_id":      tmdb_id,
                "poster_url":   rss_poster,
            }

    if progress_cb:
        progress_cb(f"Found {len(rows)} films for {username}")

    if not rows:
        return pd.DataFrame(columns=_EMPTY_COLS)

    return pd.DataFrame(list(rows.values()))


# ---------------------------------------------------------------------------
# Genre enrichment — scraped from Letterboxd film pages (no API key needed)
# ---------------------------------------------------------------------------

_genre_cache: dict[str, list[str]] = {}


def _scrape_film_genres(slug: str) -> list[str]:
    """Fetch genre names from https://letterboxd.com/film/{slug}/"""
    import json as _json

    if slug in _genre_cache:
        return _genre_cache[slug]

    try:
        r = _session.get(f"{LETTERBOXD_BASE}/film/{slug}/", timeout=12)
        if not r.ok:
            _genre_cache[slug] = []
            return []
        soup = BeautifulSoup(r.text, "lxml")

        # 1) JSON-LD block is most reliable
        for script in soup.find_all("script", type="application/ld+json"):
            try:
                data = _json.loads(script.string or "")
                g = data.get("genre")
                if g:
                    genres = ([x.strip() for x in g.split(",") if x.strip()]
                              if isinstance(g, str) else [str(x) for x in g if x])
                    _genre_cache[slug] = genres
                    return genres
            except Exception:
                pass

        # 2) Genre links in the sidebar
        seen: set[str] = set()
        genres = []
        for a in soup.select("a[href*='/films/genre/']"):
            text = a.get_text(strip=True)
            if text and text.lower() not in seen:
                seen.add(text.lower())
                genres.append(text)

        _genre_cache[slug] = genres
        return genres
    except Exception as exc:
        logger.debug("Genre scrape failed for slug=%s: %s", slug, exc)
        _genre_cache[slug] = []
        return []


def enrich_genres(df: pd.DataFrame, progress_cb=None) -> pd.DataFrame:
    """
    Add genres by scraping Letterboxd film pages concurrently.
    No API key required — individual film pages are not Cloudflare-blocked.
    """
    from concurrent.futures import ThreadPoolExecutor, as_completed

    if df.empty:
        return df

    to_enrich = [
        (idx, str(row["movie_id"]))
        for idx, row in df.iterrows()
        if not (isinstance(row.get("genres"), list) and row["genres"])
    ]

    if not to_enrich:
        return df

    if progress_cb:
        progress_cb(f"Loading genres for {len(to_enrich)} films…")

    done = 0
    with ThreadPoolExecutor(max_workers=8) as pool:
        futures = {pool.submit(_scrape_film_genres, slug): idx
                   for idx, slug in to_enrich}
        for future in as_completed(futures):
            idx = futures[future]
            genres = future.result()
            if genres:
                df.at[idx, "genres"] = genres
            done += 1
            if progress_cb and done % 5 == 0:
                progress_cb(f"Loading genres… {done}/{len(to_enrich)}")

    return df


# ---------------------------------------------------------------------------
# Image download
# ---------------------------------------------------------------------------

def fetch_image_bytes(url: str) -> Optional[bytes]:
    if not url:
        return None
    try:
        r = _session.get(url, timeout=10)
        r.raise_for_status()
        return r.content
    except Exception:
        return None


def tmdb_poster_url(title: str, year: Optional[int] = None) -> Optional[str]:
    result = _tmdb_search(title, year)
    path = result.get("poster_path")
    if path:
        return f"{TMDB_IMAGE_BASE}{path}"
    return None
