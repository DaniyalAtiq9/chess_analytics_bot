"""
All shared constants and paths live here, and only here. Every other module
imports from this file rather than redefining paths/thresholds locally — if
you ever need to change where data lands or what the significance floor is,
this is the only file you touch.
"""

import os
from pathlib import Path

USERNAME = os.environ.get("CHESS_USERNAME")
CONTACT_EMAIL = os.environ.get("CHESS_CONTACT_EMAIL")

if not USERNAME or not CONTACT_EMAIL:
    raise RuntimeError(
        "CHESS_USERNAME and CHESS_CONTACT_EMAIL must be set as GitHub Actions "
        "repo variables (Settings → Secrets and variables → Actions → Variables). "
        "See README.md setup instructions."
    )

HEADERS = {"User-Agent": f"chess-analytics-bot ({CONTACT_EMAIL})"}

DATA_DIR = Path("data")
CHARTS_DIR = Path("charts")
DATA_DIR.mkdir(exist_ok=True)
CHARTS_DIR.mkdir(exist_ok=True)

GAMES_PATH = DATA_DIR / "games.csv"
OPP_CACHE_PATH = DATA_DIR / "opponent_cache.json"
TABLES_PATH = DATA_DIR / "country_outcome_tables.xlsx"
SIGNIFICANCE_PATH = DATA_DIR / "significance_report.csv"
SESSION_FATIGUE_PATH = DATA_DIR / "session_fatigue_report.csv"
PEAK_RATING_PATH = DATA_DIR / "peak_rating_report.csv"
README_PATH = Path("README.md")

# floor for anything reported/charted per country — do not lower casually,
# this exists because smaller samples produced statistically meaningless
# rankings during manual analysis (see README design notes)
MIN_GAMES = 15

# chess.com placeholder codes, not real ISO countries — excluded, never
# guess-mapped to a real name
NON_COUNTRY_CODES = {"XS", "XO", "XB", "XA", "XG", "XC", "XE", "EU", "XX"}

# a new game starting more than this many minutes after the previous one
# ended is treated as the start of a NEW session, not a continuation
SESSION_GAP_MINUTES = 30

# cap on how far into a session position gets tracked individually — after
# this, positions bucket into a single "N+" group, since marathon sessions
# otherwise produce single-game buckets that are statistically meaningless.
SESSION_POSITION_CAP = 8


# minimum games required at a given session-position before it's included —
# same discipline as MIN_GAMES for countries, since late-session positions
# are inherently thin and are exactly where a false "fatigue effect" hides.
MIN_GAMES_PER_POSITION = 15

# an opponent played more than this many times is flagged as "repeat" —
# excluded from significance testing since repeated games against a known
# person aren't independent matchmaking draws
REPEAT_OPPONENT_THRESHOLD = 2

REQUEST_DELAY = 0.3   # seconds between archive/profile requests
MAX_RETRIES = 3
