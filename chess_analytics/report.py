"""
Everything that turns clean_df / sig_df into things a human looks at:
the Excel tables, the PNG charts, and the auto-updated README block. No
statistical logic lives here — this module only formats and writes.
"""

import re

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt


from . import config


def build_country_tables(clean_df):
    with pd.ExcelWriter(config.TABLES_PATH, engine="openpyxl") as writer:
        for tc in ["blitz", "rapid"]:
            sub = clean_df[(clean_df["time_class"] == tc) & (clean_df["country_name"].notna())]
            counts = sub.groupby(["country_name", "outcome"]).size().unstack(fill_value=0)
            for col in ["win", "draw", "loss"]:
                if col not in counts.columns:
                    counts[col] = 0
            counts = counts[["win", "draw", "loss"]]
            counts["total"] = counts.sum(axis=1)
            counts = counts[counts["total"] >= config.MIN_GAMES].sort_values("total", ascending=False)

            table = pd.DataFrame(index=counts.index)
            table["Total Games"] = counts["total"]
            for col, label in [("win", "Win"), ("draw", "Draw"), ("loss", "Loss")]:
                pct = (counts[col] / counts["total"] * 100).round(1)
                table[label] = counts[col].astype(str) + " (" + pct.astype(str) + "%)"
            table.index.name = "Country"
            table.to_excel(writer, sheet_name=tc)
    print(f"Saved {config.TABLES_PATH}")


def build_charts(clean_df):
    for tc in ["blitz", "rapid"]:
        sub = clean_df[(clean_df["time_class"] == tc) & (clean_df["country_name"].notna())]
        stats = (
            sub.groupby("country_name")["outcome"]
            .value_counts(normalize=True)
            .unstack(fill_value=0)
            .reindex(columns=["win", "draw", "loss"], fill_value=0)
        )
        counts = sub.groupby("country_name").size()
        stats = stats[counts >= config.MIN_GAMES]
        if stats.empty:
            print(f"{tc}: no countries meet the {config.MIN_GAMES}-game floor, skipping chart")
            continue
        stats = stats.loc[counts[stats.index].sort_values(ascending=False).index]

        n = len(stats)
        x = np.arange(n) * 1.6
        width = 0.4

        fig, ax = plt.subplots(figsize=(max(12, n * 1.4), 7))
        fig.patch.set_facecolor("black")
        ax.set_facecolor("black")

        ax.bar(x - width, stats["win"], width, label="Win", color="#00C853", edgecolor="white", linewidth=0.6)
        ax.bar(x, stats["draw"], width, label="Draw", color="#FFFFFF", edgecolor="white", linewidth=0.6)
        ax.bar(x + width, stats["loss"], width, label="Loss", color="#FF1744", edgecolor="white", linewidth=0.6)

        for i, country in enumerate(stats.index):
            ax.text(x[i], max(stats.iloc[i]) + 0.06, f"Total games: {counts[country]}",
                     ha="center", fontsize=9, color="white")

        ax.set_title(f"{tc.capitalize()} — win/draw/loss rate by opponent country (min {config.MIN_GAMES} games)",
                     color="white", fontsize=14, pad=20)
        ax.set_ylabel("Share of games (proportion, 0–1)", color="white", fontsize=11)
        ax.set_ylim(0, 1.15)
        ax.set_xticks(x)
        ax.set_xticklabels(stats.index, rotation=30, ha="right", color="white", fontsize=10)
        ax.tick_params(axis="y", colors="white", labelsize=10)
        ax.spines["bottom"].set_color("white")
        ax.spines["left"].set_color("white")
        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)

        legend = ax.legend(title="Outcome", facecolor="black", edgecolor="white", loc="upper right", fontsize=10)
        legend.get_title().set_color("white")
        for text in legend.get_texts():
            text.set_color("white")

        plt.tight_layout()
        plt.savefig(config.CHARTS_DIR / f"outcome_clustered_{tc}.png", dpi=150, facecolor="black")
        plt.close(fig)
    print(f"Saved charts to {config.CHARTS_DIR}/")

def build_session_fatigue_chart(summary):
    if summary.empty:
        print("Session fatigue: no positions meet the games-per-position floor, skipping chart")
        return

    fig, ax = plt.subplots(figsize=(max(8, len(summary) * 1.2), 6))
    fig.patch.set_facecolor("black")
    ax.set_facecolor("black")

    colors = ["#00C853" if v >= 0 else "#FF1744" for v in summary["mean_delta"]]
    ax.bar(summary["position_label"], summary["mean_delta"], color=colors, edgecolor="white", linewidth=0.6)
    ax.axhline(0, color="white", linewidth=1)

    for i, row in enumerate(summary.itertuples()):
        y = row.mean_delta
        ax.text(i, y + (0.01 if y >= 0 else -0.01), f"n={row.n_games}",
                 ha="center", va="bottom" if y >= 0 else "top", fontsize=8, color="white")

    ax.set_title("Performance vs. Elo expectation, by position in session", color="white", fontsize=13, pad=15)
    ax.set_xlabel("Game # within session (same-sitting, same time class)", color="white", fontsize=10)
    ax.set_ylabel("Mean performance delta (actual − expected score)", color="white", fontsize=10)
    ax.tick_params(colors="white")
    for spine in ["bottom", "left"]:
        ax.spines[spine].set_color("white")
    for spine in ["top", "right"]:
        ax.spines[spine].set_visible(False)

    plt.tight_layout()
    plt.savefig(config.CHARTS_DIR / "session_fatigue.png", dpi=150, facecolor="black")
    plt.close(fig)
    print("Saved charts/session_fatigue.png")

def build_peak_rating_charts(clean_df, peak_df):
    for tc in ["blitz", "rapid"]:
        sub = clean_df[clean_df["time_class"] == tc].sort_values("date").reset_index(drop=True)
        if sub.empty or peak_df.empty or tc not in peak_df["time_class"].values:
            print(f"{tc}: no data for rating progression chart, skipping")
            continue

        peak_row = peak_df[peak_df["time_class"] == tc].iloc[0]
        game_numbers = range(1, len(sub) + 1)

        fig, ax = plt.subplots(figsize=(12, 6))
        fig.patch.set_facecolor("black")
        ax.set_facecolor("black")

        ax.plot(game_numbers, sub["my_rating"], color="#00C853", linewidth=1.2)

        peak_x = peak_row["games_to_reach_peak"]
        peak_y = peak_row["peak_rating"]
        ax.scatter([peak_x], [peak_y], color="#FFFFFF", s=60, zorder=5, edgecolor="#00C853", linewidth=1.5)
        ax.annotate(
            f"Peak: {int(peak_y)}\n(game {int(peak_x)} of {int(peak_row['total_games_in_format'])})",
            xy=(peak_x, peak_y), xytext=(peak_x, peak_y + (sub["my_rating"].max() - sub["my_rating"].min()) * 0.08),
            color="white", fontsize=10, ha="center",
            arrowprops=dict(arrowstyle="->", color="white", lw=1),
        )

        ax.set_title(f"{tc.capitalize()} rating progression", color="white", fontsize=14, pad=15)
        ax.set_xlabel("Rated game # (chronological)", color="white", fontsize=10)
        ax.set_ylabel("Rating", color="white", fontsize=10)
        ax.tick_params(colors="white")
        for spine in ["bottom", "left"]:
            ax.spines[spine].set_color("white")
        for spine in ["top", "right"]:
            ax.spines[spine].set_visible(False)

        plt.tight_layout()
        plt.savefig(config.CHARTS_DIR / f"rating_progression_{tc}.png", dpi=150, facecolor="black")
        plt.close(fig)
    print("Saved rating progression charts")


def update_readme(clean_df, sig_df, session_summary=None, session_meta=None, peak_df=None):
    """
    Rewrites the auto-generated block in README.md between the markers
    below. Everything outside the markers (setup instructions, design
    notes) is left untouched.
    """
    if not config.README_PATH.exists():
        print("README.md not found, skipping README update")
        return

    content = config.README_PATH.read_text()
    start_marker = "<!-- STATS:START -->"
    end_marker = "<!-- STATS:END -->"

    if start_marker not in content or end_marker not in content:
        print("README markers not found — add <!-- STATS:START --> / <!-- STATS:END --> to enable auto-update")
        return

    total_games = len(clean_df)
    date_range = (
        f"{clean_df['date'].min().date()} to {clean_df['date'].max().date()}"
        if not clean_df.empty else "n/a"
    )

    if not sig_df.empty:
        flagged = sig_df[sig_df["significant_after_correction"]]
        if not flagged.empty:
            flagged_lines = "\n".join(
                f"- **{r.country}** ({r.time_class}): n={r.n_games}, mean delta={r.mean_delta:+.3f}, "
                f"p={r.p_raw} < corrected α={r.bonferroni_alpha} — *treat as a lead to re-check by hand, "
                f"not a confirmed effect. See caveats in `chess_analytics/stats.py`.*"
                for r in flagged.itertuples()
            )
        else:
            flagged_lines = (
                "_No country crosses the Bonferroni-corrected significance threshold this run — "
                "consistent with the earlier manual finding that country has no strong effect "
                "on your results once tested properly._"
            )
    else:
        flagged_lines = (
            "_Not enough data yet to run significance tests (need ≥15 non-repeat games in at "
            "least one country/format combo)._"
        )

    if session_meta is None or session_summary is None or session_summary.empty:
        fatigue_lines = "_Not enough session data yet to test for fatigue._"
    else:
        trend_p = session_meta.get("trend_p")
        step_p = session_meta.get("step_change_p")
        step_delta = session_meta.get("step_change_delta")

        parts = [f"Based on {session_meta['n_sessions']} inferred sessions, {session_meta['n_games_analyzed']} games."]

        if trend_p is not None:
            trend_verdict = "a statistically real trend" if trend_p < 0.05 else "not distinguishable from no trend"
            parts.append(f"Position-vs-performance correlation: ρ={session_meta['trend_rho']}, p={trend_p} — {trend_verdict}.")

        if step_p is not None:
            step_verdict = "a statistically real step-change" if step_p < 0.05 else "not distinguishable from noise"
            direction = "worse" if step_delta < 0 else "better"
            parts.append(f"First game of session vs. later games: later games score {direction} by "
                         f"{abs(step_delta):.3f} on average, p={step_p} — {step_verdict}.")

        parts.append("_Both tests use α=0.05 uncorrected for this specific comparison — treat a single "
                     "borderline p-value as a lead to watch over time, not a confirmed effect, same caveat "
                     "as the country analysis._")
        fatigue_lines = " ".join(parts)

    if peak_df is None or peak_df.empty:
        peak_lines = "_Not enough rated games yet in blitz/rapid to report a peak._"
    else:
        peak_parts = []
        for r in peak_df.itertuples():
            status = "— that's still your peak right now" if r.currently_at_peak else "— you've since come back down from it"
            peak_parts.append(
                f"- **{r.time_class.capitalize()}**: peak rating **{r.peak_rating}**, reached after "
                f"{r.games_to_reach_peak} of {r.total_games_in_format} rated games, on {r.peak_date.date()} {status}"
            )
        peak_lines = "\n".join(peak_parts)

    block = f"""{start_marker}
### Last updated: {pd.Timestamp.utcnow().strftime('%Y-%m-%d %H:%M UTC')}

**Dataset:** {total_games} rated games, {date_range}

**Statistically flagged countries this run** (Bonferroni-corrected within this run's test set —
does *not* correct across repeated daily runs; see notes in `chess_analytics/stats.py`):

{flagged_lines}

**Session fatigue** (does performance decline the longer you play in one sitting? —
sessions inferred from time gaps, see `chess_analytics/sessions.py`):

{fatigue_lines}

**Peak rating** (see `chess_analytics/milestones.py` — this is a moving target, updates as new games are added):

{peak_lines}


**Charts:**

![Blitz outcomes by country](charts/outcome_clustered_blitz.png)
![Rapid outcomes by country](charts/outcome_clustered_rapid.png)
![Session fatigue](charts/session_fatigue.png)
![Blitz rating progression](charts/rating_progression_blitz.png)
![Rapid rating progression](charts/rating_progression_rapid.png)

Full tables: [`data/country_outcome_tables.xlsx`](data/country_outcome_tables.xlsx) ·
Significance tests: [`data/significance_report.csv`](data/significance_report.csv) ·
Session fatigue data: [`data/session_fatigue_report.csv`](data/session_fatigue_report.csv) ·
Peak rating data: [`data/peak_rating_report.csv`](data/peak_rating_report.csv)
{end_marker}"""

    new_content = re.sub(
        f"{re.escape(start_marker)}.*?{re.escape(end_marker)}",
        block,
        content,
        flags=re.DOTALL,
    )
    config.README_PATH.write_text(new_content)
    print("Updated README.md stats block")