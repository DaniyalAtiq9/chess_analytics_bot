"""
Everything that turns clean_df / sig_df into things a human looks at:
the Excel tables, the PNG charts, and the auto-updated README block. No
statistical logic lives here — this module only formats and writes.
"""

import re

import numpy as np
import pandas as pd

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
    import matplotlib
    matplotlib.use("Agg")  # headless — no display available in CI
    import matplotlib.pyplot as plt

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


def update_readme(clean_df, sig_df):
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

    block = f"""{start_marker}
### Last updated: {pd.Timestamp.utcnow().strftime('%Y-%m-%d %H:%M UTC')}

**Dataset:** {total_games} rated games, {date_range}

**Statistically flagged countries this run** (Bonferroni-corrected within this run's test set —
does *not* correct across repeated daily runs; see notes in `chess_analytics/stats.py`):

{flagged_lines}

**Charts:**

![Blitz outcomes by country](charts/outcome_clustered_blitz.png)
![Rapid outcomes by country](charts/outcome_clustered_rapid.png)

Full tables: [`data/country_outcome_tables.xlsx`](data/country_outcome_tables.xlsx) ·
Raw significance test output: [`data/significance_report.csv`](data/significance_report.csv)
{end_marker}"""

    new_content = re.sub(
        f"{re.escape(start_marker)}.*?{re.escape(end_marker)}",
        block,
        content,
        flags=re.DOTALL,
    )
    config.README_PATH.write_text(new_content)
    print("Updated README.md stats block")
