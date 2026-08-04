"""
All shared constants and paths live here, and only here. Every other module
imports from this file rather than redefining paths/thresholds locally — if
you ever need to change where data lands or what the significance floor is,
this is the only file you touch.
"""

import os
from pathlib import Path

USERNAME = os.environ.get("CHESS_USERNAME", "daniyaltered")
CONTACT_EMAIL = os.environ.get("CHESS_CONTACT_EMAIL", "daniyalatiqrao.com")
HEADERS = {"User-Agent": f"chess-analytics-bot ({CONTACT_EMAIL})"}

DATA_DIR = Path("data")
CHARTS_DIR = Path("charts")
DATA_DIR.mkdir(exist_ok=True)
CHARTS_DIR.mkdir(exist_ok=True)

GAMES_PATH = DATA_DIR / "games.csv"
OPP_CACHE_PATH = DATA_DIR / "opponent_cache.json"
TABLES_PATH = DATA_DIR / "country_outcome_tables.xlsx"
SIGNIFICANCE_PATH = DATA_DIR / "significance_report.csv"
README_PATH = Path("README.md")

# floor for anything reported/charted per country — do not lower casually,
# this exists because smaller samples produced statistically meaningless
# rankings during manual analysis (see README design notes)
MIN_GAMES = 15

# chess.com placeholder codes, not real ISO countries — excluded, never
# guess-mapped to a real name
NON_COUNTRY_CODES = {"XS", "XO", "XB", "XA", "XG", "XC", "XE", "EU", "XX"}

# an opponent played more than this many times is flagged as "repeat" —
# excluded from significance testing since repeated games against a known
# person aren't independent matchmaking draws
REPEAT_OPPONENT_THRESHOLD = 2

REQUEST_DELAY = 0.3   # seconds between archive/profile requests
MAX_RETRIES = 3
