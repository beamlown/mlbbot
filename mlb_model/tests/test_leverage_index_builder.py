import pandas as pd
import pytest
from data.foundation.leverage_index_builder import (
    build_leverage_table,
    _score_bucket,
)

def test_score_bucket():
    assert _score_bucket(0) == 0
    assert _score_bucket(2) == 2
    assert _score_bucket(-2) == -2
    assert _score_bucket(10) == 5
    assert _score_bucket(-10) == -5

def test_build_produces_complete_table():
    """Synthetic game data -> LI table covers all state combos seen."""
    rows = [
        {"inning": 1, "outs": 0, "base_state": 0, "score_diff": 0, "wp_swing_sq": 0.05},
        {"inning": 9, "outs": 2, "base_state": 7, "score_diff": 0, "wp_swing_sq": 0.80},
        {"inning": 5, "outs": 1, "base_state": 3, "score_diff": 1, "wp_swing_sq": 0.15},
    ]
    df = pd.DataFrame(rows)
    tbl = build_leverage_table(df)
    li_late = tbl[(tbl.inning == 9) & (tbl.outs == 2) & (tbl.base_state == 7) &
                  (tbl.score_bucket == 0)].iloc[0].leverage_index
    li_early = tbl[(tbl.inning == 1) & (tbl.outs == 0) & (tbl.base_state == 0) &
                   (tbl.score_bucket == 0)].iloc[0].leverage_index
    assert li_late > li_early
