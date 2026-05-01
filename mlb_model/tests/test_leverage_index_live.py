import pandas as pd
import pytest
from sports.mlb.leverage_index_live import lookup_leverage_index, _set_test_table

@pytest.fixture(autouse=True)
def reset():
    yield
    _set_test_table(None)

def test_lookup_exact():
    tbl = pd.DataFrame([{
        "inning": 9, "outs": 2, "base_state": 7, "score_bucket": 0,
        "leverage_index": 4.5,
    }])
    _set_test_table(tbl)
    li = lookup_leverage_index(inning=9, outs=2, base_state=7, score_diff=0)
    assert li == pytest.approx(4.5)

def test_lookup_unknown_state_returns_1():
    _set_test_table(pd.DataFrame(columns=["inning", "outs", "base_state",
                                          "score_bucket", "leverage_index"]))
    assert lookup_leverage_index(1, 0, 0, 0) == 1.0

def test_clamps_extreme_score_diff():
    tbl = pd.DataFrame([{
        "inning": 9, "outs": 2, "base_state": 7, "score_bucket": 5,
        "leverage_index": 0.1,
    }])
    _set_test_table(tbl)
    li = lookup_leverage_index(inning=9, outs=2, base_state=7, score_diff=20)
    assert li == pytest.approx(0.1)

def test_extras_falls_back_to_inning_9():
    tbl = pd.DataFrame([{
        "inning": 9, "outs": 0, "base_state": 0, "score_bucket": 0,
        "leverage_index": 3.2,
    }])
    _set_test_table(tbl)
    li = lookup_leverage_index(inning=11, outs=0, base_state=0, score_diff=0)
    assert li == pytest.approx(3.2)
