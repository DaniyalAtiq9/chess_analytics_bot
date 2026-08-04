"""
Everything that talks to the chess.com games/archives API. Owns retry logic,
the incremental-month-selection rule, and flattening raw game JSON into rows.
Does NOT know about opponent country resolution (that's cache.py) or about
stats/output (that's stats.py / report.py) — this module's only job is
"turn chess.com archive URLs into a DataFrame of games."
"""

import re
import time

import pandas as pd
import requests

from . import config


def get_with_retry(url, headers=None, max_retries=config.MAX_RETRIES):
    headers = headers or config.HEADERS
    for attempt in range(max_retries):
        try:
            r = requests.get(url, headers=headers, timeout=20)
            if r.status_code == 200:
                return r
            if r.status_code == 404:
                return r  # caller decides how to handle
            if r.status_code == 429:
                wait = 5 * (attempt + 1)
                print(f"Rate limited on {url}, waiting {wait}s")
                time.sleep(wait)
                continue
        except requests.RequestException as e:
            print(f"Request failed ({e}) on {url}, attempt {attempt+1}/{max_retries}")
            time.sleep(2 * (attempt + 1))
    raise RuntimeError(f"Failed to fetch {url} after {max_retries} retries")


def get_archive_urls():
    resp = get_with_retry(f"https://api.chess.com/pub/player/{config.USERNAME}/games/archives")
    return resp.json()["archives"]


def months_to_refetch(archive_urls, existing_df):
    """
    Always refetch the current and previous month (they can still change).
    Refetch any month not represented at all in existing_df (first run, or a
    gap from a prior failed run). Older finalized months are never
    re-pulled — chess.com doesn't retroactively change them, and re-pulling
    2+ years of history every day would be pure waste.
    """
    if existing_df.empty:
        return archive_urls  # first run — pull everything

    existing_months = set(existing_df["date"].dt.to_period("M").astype(str))
    all_months = [u.rstrip("/").split("/")[-2] + "-" + u.rstrip("/").split("/")[-1] for u in archive_urls]

    to_fetch = [url for url, ym in zip(archive_urls, all_months) if ym not in existing_months]

    for url in archive_urls[-2:]:
        if url not in to_fetch:
            to_fetch.append(url)

    return to_fetch


def fetch_games_for_months(urls):
    rows = []
    for url in urls:
        resp = get_with_retry(url)
        if resp.status_code != 200:
            print(f"Skipping {url} (status {resp.status_code})")
            continue
        for g in resp.json().get("games", []):
            rows.append(_flatten_game(g))
        time.sleep(config.REQUEST_DELAY)
    return pd.DataFrame(rows)


def _flatten_game(g):
    white, black = g.get("white", {}), g.get("black", {})
    is_white = white.get("username", "").lower() == config.USERNAME.lower()
    me, opp = (white, black) if is_white else (black, white)

    pgn = g.get("pgn", "")
    clocks = re.findall(r"\[%clk (\d+:\d+:\d+(?:\.\d+)?)\]", pgn)

    return {
        "date": pd.to_datetime(g.get("end_time"), unit="s"),
        "time_control": g.get("time_control"),
        "time_class": g.get("time_class"),
        "rated": g.get("rated"),
        "rules": g.get("rules"),
        "color": "white" if is_white else "black",
        "my_rating": me.get("rating"),
        "opp_rating": opp.get("rating"),
        "opp_username": opp.get("username"),
        "my_result": me.get("result"),
        "eco": g.get("eco"),
        "num_ply": len(re.findall(r"\d+\.", pgn)),
        "num_clock_tags": len(clocks),
        "first_clk": clocks[0] if clocks else None,
        "last_clk": clocks[-1] if clocks else None,
        "pgn": pgn,
        "url": g.get("url"),
        "fen": g.get("fen"),
        "start_time": pd.to_datetime(g.get("start_time"), unit="s") if g.get("start_time") else None,
    }
