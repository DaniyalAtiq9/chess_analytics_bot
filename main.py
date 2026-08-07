"""
Entrypoint. Run as: python main.py

This file should stay thin — if you're adding logic here instead of in the
relevant chess_analytics/ module, you're probably putting it in the wrong
place. Read this file to understand *what* the pipeline does, in order; read
the individual modules to understand *how*.
"""

from chess_analytics import cache, config, fetch, report, sessions, stats, transform


def main():
    print(f"=== Chess.com stats refresh for {config.USERNAME} ===")

    # 1. load what we already have
    existing_df = transform.load_existing_games()
    opp_cache = cache.load_cache()

    # 2. fetch only what's new (current + previous month, or everything on first run)
    archive_urls = fetch.get_archive_urls()
    refetch_urls = fetch.months_to_refetch(archive_urls, existing_df)
    print(f"Refetching {len(refetch_urls)} of {len(archive_urls)} months")
    new_games_df = fetch.fetch_games_for_months(refetch_urls)

    # 3. merge, resolve opponent countries (cached), derive columns
    combined = transform.merge_games(existing_df, new_games_df)

    unique_opponents = combined["opp_username"].dropna().unique().tolist()
    opp_cache = cache.resolve_new_opponents(unique_opponents, opp_cache)
    cache.save_cache(opp_cache)

    combined = transform.attach_country(combined, opp_cache, cache.code_to_name)
    combined = transform.add_derived_columns(combined)
    clean_df = transform.build_clean_df(combined)

    # 4. persist the full dataset as next run's starting point
    combined.to_csv(config.GAMES_PATH, index=False)
    print(f"Saved {len(combined)} games to {config.GAMES_PATH}")

    # 5. analyze + write outputs
    report.build_country_tables(clean_df)
    report.build_charts(clean_df)
    sig_df = stats.build_significance_report(clean_df)

    session_summary, session_meta = sessions.build_session_fatigue_report(clean_df)
    report.build_session_fatigue_chart(session_summary)

    report.update_readme(clean_df, sig_df, session_summary, session_meta)

    print("=== Done ===")


if __name__ == "__main__":
    main()
