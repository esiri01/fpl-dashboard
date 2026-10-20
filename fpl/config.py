"""Settings and constants for the dashboard."""

from __future__ import annotations

import os

DEFAULT_LEAGUE_ID = "799250"  # Mech Peeps
BASE_URL = "https://fantasy.premierleague.com/api"

# FPL sometimes rejects the default python-requests user agent.
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0 Safari/537.36 fpl-dashboard"
)
TIMEOUT_SECONDS = 10
MAX_WORKERS = 8  # keep concurrency polite
MAX_STANDINGS_PAGES = 20  # 50 managers per page -> 1,000 managers max

# Cache lifetimes (seconds)
TTL_LIVE = 5 * 60  # current / unfinished gameweek data
TTL_FINISHED = 24 * 60 * 60  # finished gameweeks never change
TTL_BOOTSTRAP = 15 * 60  # gameweek list + player names

# Optional: point the app at a folder of saved API responses (offline/demo mode).
FIXTURES_ENV = "FPL_FIXTURES_DIR"

CHIP_NAMES = {
    "wildcard": "Wildcard",
    "freehit": "Free Hit",
    "bboost": "Bench Boost",
    "3xc": "Triple Captain",
    "manager": "Assistant Manager",
}

# Palette (matches .streamlit/config.toml)
ACCENT = "#1F7A4D"
HIGHLIGHT_COLORS = ["#1F7A4D", "#2F6DB5", "#C27C0E", "#7A3E9D"]
MUTED_LINE = "#CDD2CC"
INK = "#15201A"


def get_league_id() -> str:
    """League ID from Streamlit secrets, then env var FPL_LEAGUE_ID, then the default."""
    try:
        import streamlit as st

        value = st.secrets.get("LEAGUE_ID")
        if value:
            return str(value)
    except Exception:  # no secrets file, or not running under Streamlit
        pass
    return os.environ.get("FPL_LEAGUE_ID", DEFAULT_LEAGUE_ID)


def get_fixtures_dir() -> str | None:
    """Folder of saved API responses to read instead of the live API, if set."""
    return os.environ.get(FIXTURES_ENV) or None


def chip_label(code: str | None) -> str:
    """Human-readable chip name ('3xc' -> 'Triple Captain')."""
    if not isinstance(code, str) or not code:  # None / NaN
        return ""
    return CHIP_NAMES.get(code, code.replace("_", " ").title())
