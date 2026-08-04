"""
Takes raw fetched games + the opponent cache and produces the two DataFrames
everything downstream depends on: `combined` (full history, unfiltered — the
saved source of truth) and `clean_df` (rated, valid-rating, delta-annotated —
what stats/report actually analyze).

If you ever add a new derived column, it goes here, not in report.py or
stats.py — keeps "what does this column mean" answerable from one file.
"""

import pandas as pd

from . import config

WIN_CODES = {"win"}
DRAW_CODES = {"agreed", "repetition", "stalemate", "insufficient", "50move", "timevsinsufficient"}


def load_existing_games():
    if config.GAMES_PATH.exists():
        df = pd.read_csv(config.GAMES_PATH, parse_dates=["date", "start_time"])
        print(f"Loaded {len(df)} existing games from {config.GAMES_PATH}")
        return df
    print("No existing games.csv found — starting fresh (full history pull)")
    return pd.DataFrame()


def merge_games(existing_df, new_games_df):
    if not existing_df.empty and not new_games_df.empty:
        combined = pd.concat([existing_df, new_games_df], ignore_index=True)
        combined = combined.drop_duplicates(subset="url", keep="last")
    elif not new_games_df.empty:
        combined = new_games_df
    else:
        combined = existing_df
    print(f"Total games after merge: {len(combined)} (was {len(existing_df)})")
    return combined


def attach_country(combined, opp_cache, code_to_name_fn):
    combined = combined.copy()
    combined["country"] = combined["opp_username"].map(lambda u: opp_cache.get(u, {}).get("country"))
    combined["country_name"] = combined["country"].apply(code_to_name_fn)
    return combined


def add_derived_columns(combined):
    combined = combined.copy()
    combined["outcome"] = combined["my_result"].apply(
        lambda r: "win" if r in WIN_CODES else ("draw" if r in DRAW_CODES else "loss")
    )
    combined["rating_diff"] = combined["my_rating"] - combined["opp_rating"]

    opp_counts = combined["opp_username"].value_counts()
    repeat_opponents = set(opp_counts[opp_counts > config.REPEAT_OPPONENT_THRESHOLD].index)
    combined["is_repeat_opponent"] = combined["opp_username"].isin(repeat_opponents)

    return combined


def build_clean_df(combined):
    """
    Rated games only, with a real (>0) rating — see README for why: unrated
    games and one zero-rating variant game were found to corrupt the
    Elo-expected-score calculation during manual analysis.
    """
    clean_df = combined[(combined["my_rating"] > 0) & (combined["rated"] == True)].copy()
    clean_df["expected_score"] = 1 / (1 + 10 ** ((clean_df["opp_rating"] - clean_df["my_rating"]) / 400))
    clean_df["actual_score"] = clean_df["outcome"].map({"win": 1, "draw": 0.5, "loss": 0})
    clean_df["performance_delta"] = clean_df["actual_score"] - clean_df["expected_score"]
    return clean_df
