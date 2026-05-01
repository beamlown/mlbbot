import pytest
from sports.mlb.lineup_live import (
    fetch_live_lineup, parse_live_response, LineupSnapshot, LineupError,
)

_MOCK_LIVE = {
    "gameData": {
        "teams": {
            "home": {"abbreviation": "LAA"},
            "away": {"abbreviation": "SDP"},
        },
    },
    "liveData": {
        "linescore": {
            "offense": {"batter": {"id": 600001}, "battingOrder": "5"},
            "defense": {"pitcher": {"id": 700001}},
        },
        "boxscore": {
            "teams": {
                "home": {
                    "battingOrder": [600100, 600101, 600102, 600103, 600104,
                                     600001, 600106, 600107, 600108],
                    "players": {
                        "ID600001": {"person": {"id": 600001}, "stats": {}, "batSide": {"code": "L"}},
                    },
                },
                "away": {
                    "battingOrder": [600200, 600201, 600202, 600203, 600204,
                                     600205, 600206, 600207, 600208],
                    "players": {
                        "ID700001": {"person": {"id": 700001}, "pitchHand": {"code": "R"}},
                    },
                },
            },
        },
    },
}

def test_parse_extracts_current_batter_and_lineups():
    snap = parse_live_response(_MOCK_LIVE)
    assert isinstance(snap, LineupSnapshot)
    assert snap.current_batter_id == 600001
    assert snap.current_pitcher_id == 700001
    assert snap.current_batter_stand == "L"
    assert snap.current_pitcher_throws == "R"
    assert snap.current_lineup_position == 6   # 0-indexed 5 -> 1-indexed 6
    assert snap.home_lineup == [600100, 600101, 600102, 600103, 600104,
                                 600001, 600106, 600107, 600108]

def test_parse_returns_none_on_missing_fields():
    bad = {"gameData": {}, "liveData": {}}
    assert parse_live_response(bad) is None

def test_fetch_raises_on_http_error(monkeypatch):
    def boom(*a, **kw):
        raise OSError("network down")
    monkeypatch.setattr("sports.mlb.lineup_live._http_get_json", boom)
    with pytest.raises(LineupError):
        fetch_live_lineup(game_pk=999)

def test_fetch_returns_parsed(monkeypatch):
    # Clear cache first (in case an earlier test seeded it)
    from sports.mlb import lineup_live as ll
    ll._CACHE.clear()
    monkeypatch.setattr("sports.mlb.lineup_live._http_get_json", lambda url: _MOCK_LIVE)
    snap = fetch_live_lineup(game_pk=999)
    assert snap.current_batter_id == 600001
