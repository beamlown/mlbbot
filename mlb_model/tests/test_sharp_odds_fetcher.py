import json
from datetime import datetime, timezone
from unittest.mock import patch, MagicMock
import pytest
from data.foundation.sharp_odds_fetcher import (
    fetch_pinnacle_mlb_moneylines,
    parse_response,
    snapshot,
    SharpOddsError,
)

_MOCK_RESPONSE = [{
    "id": "abc123",
    "sport_key": "baseball_mlb",
    "commence_time": "2026-04-19T23:05:00Z",
    "home_team": "Los Angeles Angels",
    "away_team": "San Diego Padres",
    "bookmakers": [{
        "key": "pinnacle",
        "markets": [{
            "key": "h2h",
            "outcomes": [
                {"name": "Los Angeles Angels", "price": 2.10},
                {"name": "San Diego Padres", "price": 1.85},
            ],
        }],
    }],
}]

def test_parse_extracts_home_implied_prob():
    rows = parse_response(_MOCK_RESPONSE, fetched_at=datetime(2026, 4, 19, 22, 0, tzinfo=timezone.utc))
    assert len(rows) == 1
    r = rows[0]
    assert r["home_team"] == "Los Angeles Angels"
    assert r["away_team"] == "San Diego Padres"
    assert 0.45 < r["home_prob"] < 0.49

def test_parse_skips_event_without_pinnacle():
    bad = [{"id": "x", "home_team": "A", "away_team": "B",
            "commence_time": "2026-04-19T23:00:00Z",
            "bookmakers": [{"key": "draftkings", "markets": []}]}]
    rows = parse_response(bad, fetched_at=datetime(2026, 4, 19, tzinfo=timezone.utc))
    assert rows == []

def test_fetch_raises_on_http_error(monkeypatch):
    def boom(*a, **kw):
        raise OSError("network down")
    monkeypatch.setattr("data.foundation.sharp_odds_fetcher._http_get_json", boom)
    with pytest.raises(SharpOddsError):
        fetch_pinnacle_mlb_moneylines(api_key="dummy")

def test_fetch_returns_parsed_rows(monkeypatch):
    monkeypatch.setattr("data.foundation.sharp_odds_fetcher._http_get_json",
                        lambda url: _MOCK_RESPONSE)
    rows = fetch_pinnacle_mlb_moneylines(api_key="dummy")
    assert len(rows) == 1
    assert "home_prob" in rows[0]
