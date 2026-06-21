TMDB_API_KEY = ""  # Set via UI or environment variable TMDB_API_KEY

LETTERBOXD_BASE = "https://letterboxd.com"
TMDB_BASE = "https://api.themoviedb.org/3"
TMDB_IMAGE_BASE = "https://image.tmdb.org/t/p/w185"

COLORS = {
    "bg":           "#14181c",
    "bg_secondary": "#1c2228",
    "bg_card":      "#2c3440",
    "border":       "#456",
    "text_primary": "#ffffff",
    "text_muted":   "#9ab",
    "green":        "#00e054",
    "orange":       "#ff8000",
    "blue":         "#40bcf4",
    "red":          "#e9413e",
}

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
}

HIGH_RATING_THRESHOLD = 4.0
TOP_RECOMMENDATIONS = 3
MAX_RATINGS_PAGES = 8
REQUEST_DELAY = 0.4
