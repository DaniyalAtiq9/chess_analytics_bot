"""
Per-country, per-format test of whether performance deviates from your
overall baseline — automates the exact manual check that caught the PK
false lead (repeat-opponent contamination) and the MX false lead
(uncorrected multiple comparisons).

What this DOES automate:
- Excludes repeat-opponent games from the tested sample (matches the
  manual finding: those games aren't independent matchmaking draws).
- Runs an independent two-sample t-test of each country's performance
  delta against the delta of everyone else, not against an assumed 50%.
- Applies a Bonferroni correction sized to however many countries are
  actually being tested that day, not a fixed number.

What this does NOT automate — read this every time you look at the
output, don't just trust the "significant_after_correction" column blindly:
- Running this daily means you're implicitly testing the same hypotheses
  over and over across time. A country that flags once in 200 daily runs
  is not the same evidential weight as one that flags once in a single
  run. This module does not correct across runs, only within a single
  run's set of countries. If a country starts flagging repeatedly over
  weeks, that's worth a manual look, not an automatic "confirmed."
- Small-but-growing samples (just past MIN_GAMES) are exactly where false
  positives concentrate. A flag on a country at n=16 deserves more
  suspicion, not less, than one at n=200.
"""

import pandas as pd
from scipy.stats import ttest_ind

from . import config


def build_significance_report(clean_df):
    rows = []
    for tc in ["blitz", "rapid"]:
        sub = clean_df[
            (clean_df["time_class"] == tc)
            & (clean_df["country_name"].notna())
            & (~clean_df["is_repeat_opponent"])
        ]
        counts = sub.groupby("country_name").size()
        eligible = counts[counts >= config.MIN_GAMES].index.tolist()

        if not eligible:
            continue

        n_tests = len(eligible)
        bonferroni_alpha = 0.05 / n_tests if n_tests > 0 else 0.05

        for country in eligible:
            country_delta = sub.loc[sub["country_name"] == country, "performance_delta"]
            other_delta = sub.loc[sub["country_name"] != country, "performance_delta"]
            if len(other_delta) < 2 or len(country_delta) < 2:
                continue
            t, p = ttest_ind(country_delta, other_delta, equal_var=False)
            rows.append({
                "time_class": tc,
                "country": country,
                "n_games": len(country_delta),
                "mean_delta": round(country_delta.mean(), 4),
                "p_raw": round(p, 4),
                "n_tests_this_run": n_tests,
                "bonferroni_alpha": round(bonferroni_alpha, 5),
                "significant_after_correction": p < bonferroni_alpha,
            })

    sig_df = pd.DataFrame(rows)
    if not sig_df.empty:
        sig_df = sig_df.sort_values(["time_class", "p_raw"])
    sig_df.to_csv(config.SIGNIFICANCE_PATH, index=False)

    n_flagged = sig_df["significant_after_correction"].sum() if not sig_df.empty else 0
    print(f"Saved significance report: {len(sig_df)} country/format tests, {n_flagged} flagged after correction")
    return sig_df
