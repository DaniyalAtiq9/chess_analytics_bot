"""
Milestone metrics: descriptive facts about your rating trajectory. No
significance testing here (there's nothing to test — "how many games did
it take to reach your peak" is a fact about history, not a hypothesis about
a population), which is why this doesn't live in stats.py.

Note on what "rating" means per game: chess.com's per-game rating field
reflects your rating at that game, and this dataset only has one rating
value per game — there's no separate pre/post distinction available from
the public API. Treat "games to peak" as approximate to within one game,
not exact to the move.

This is a live, moving metric: as new games get added by the daily cron,
"peak rating" and "games to reach it" can both change. That's expected
behavior, not a bug — don't be surprised if the numbers shift between runs,
especially if you're actively climbing right now.
"""

import pandas as pd

from . import config


def build_peak_rating_report(clean_df):
    rows = []
    for tc in ["blitz", "rapid"]:
        sub = clean_df[clean_df["time_class"] == tc].sort_values("date").reset_index(drop=True)
        if sub.empty:
            continue

        peak_rating = sub["my_rating"].max()
        first_peak_idx = sub.index[sub["my_rating"] == peak_rating][0]
        currently_at_peak = sub["my_rating"].iloc[-1] >= peak_rating

        rows.append({
            "time_class": tc,
            "peak_rating": int(peak_rating),
            "games_to_reach_peak": int(first_peak_idx + 1),
            "peak_date": sub.loc[first_peak_idx, "date"],
            "total_games_in_format": len(sub),
            "currently_at_peak": bool(currently_at_peak),
        })

    df = pd.DataFrame(rows)
    df.to_csv(config.PEAK_RATING_PATH, index=False)

    for r in df.itertuples():
        status = "you're at it right now" if r.currently_at_peak else "you've since dropped below it"
        print(f"{r.time_class}: peak rating {r.peak_rating}, reached after {r.games_to_reach_peak}/"
              f"{r.total_games_in_format} games, on {r.peak_date.date()} — {status}")

    return df