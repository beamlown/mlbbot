"""Cron entry: roll yesterday's results into elo_table.parquet."""
from data.foundation.elo_daily_updater import main

if __name__ == "__main__":
    main()
