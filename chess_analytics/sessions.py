"""
Session-fatigue analysis: does performance (relative to Elo expectation)
decline the longer you play in one sitting?

A "session" is defined purely by time gaps between games (see
config.SESSION_GAP_MINUTES) — chess.com doesn't expose any session concept,
so this is inferred, not given. That inference is the main assumption this
whole analysis rests on; it's stated explicitly here and in config.py rather
than buried, because it's the thing most likely to be wrong if the fatigue
finding doesn't replicate intuition.

Two independent tests are run, deliberately, not one:
- A trend test (Spearman correlation between position-in-session and
  performance_delta) — catches a gradual decline.
- A blunt first-game-vs-later-games t-test — catches a step-change effect
  (e.g. you're fine for the first couple games, then fall off a cliff) that
  a linear trend test could wash out or under-detect.
Same principle as the country work: don't rely on a single statistical lens
and assume it caught everything.
"""

import pandas as pd
from scipy.stats import spearmanr, ttest_ind

from . import config


def assign_sessions(df):
    """
    Adds `session_id` and `position_in_session` columns. Games are ordered
    by end time (`date`); a new session starts whenever the gap since the
    previous game's end exceeds SESSION_GAP_MINUTES, OR when the time_class
    changes (switching formats counts as a mental context switch, not a
    continuation of the same grind).
    """
    df = df.sort_values("date").copy()

    gap = df["date"].diff().dt.total_seconds() / 60
    time_class_changed = df["time_class"] != df["time_class"].shift()
    new_session = (gap > config.SESSION_GAP_MINUTES) | time_class_changed | gap.isna()

    df["session_id"] = new_session.cumsum()
    df["position_in_session"] = df.groupby("session_id").cumcount() + 1

    return df


def _bucket_position(pos):
    return pos if pos <= config.SESSION_POSITION_CAP else config.SESSION_POSITION_CAP + 1  # "N+" bucket, encoded numerically


def build_session_fatigue_report(clean_df):
    df = assign_sessions(clean_df)
    df["position_bucket"] = df["position_in_session"].apply(_bucket_position)

    summary = (
        df.groupby("position_bucket")
        .agg(n_games=("performance_delta", "count"), mean_delta=("performance_delta", "mean"))
        .reset_index()
    )
    summary = summary[summary["n_games"] >= config.MIN_GAMES_PER_POSITION]
    summary["position_label"] = summary["position_bucket"].apply(
        lambda p: f"{config.SESSION_POSITION_CAP}+" if p > config.SESSION_POSITION_CAP else str(p)
    )

    testable = df[df["position_bucket"].isin(summary["position_bucket"])]
    if len(testable) >= 30:
        rho, trend_p = spearmanr(testable["position_in_session"], testable["performance_delta"])
    else:
        rho, trend_p = float("nan"), float("nan")

    first_game = df[df["position_in_session"] == 1]["performance_delta"]
    later_games = df[df["position_in_session"] > 1]["performance_delta"]
    if len(first_game) >= 15 and len(later_games) >= 15:
        t, step_p = ttest_ind(first_game, later_games, equal_var=False)
        step_delta = later_games.mean() - first_game.mean()
    else:
        step_p, step_delta = float("nan"), float("nan")

    summary.to_csv(config.SESSION_FATIGUE_PATH, index=False)

    meta = {
        "trend_rho": round(rho, 4) if pd.notna(rho) else None,
        "trend_p": round(trend_p, 4) if pd.notna(trend_p) else None,
        "step_change_p": round(step_p, 4) if pd.notna(step_p) else None,
        "step_change_delta": round(step_delta, 4) if pd.notna(step_delta) else None,
        "n_sessions": df["session_id"].nunique(),
        "n_games_analyzed": len(df),
    }

    print(f"Session fatigue: {meta['n_sessions']} sessions, trend p={meta['trend_p']}, "
          f"first-vs-later step p={meta['step_change_p']}")

    return summary, meta