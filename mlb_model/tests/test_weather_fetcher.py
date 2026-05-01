import pytest
from datetime import datetime, timezone
from data.foundation.weather_fetcher import (
    fetch_weather_at, parse_open_meteo_response, project_wind,
    WeatherSnapshot, WeatherError,
)

_MOCK_ARCHIVE = {
    "hourly": {
        "time": ["2024-07-15T18:00", "2024-07-15T19:00", "2024-07-15T20:00"],
        "temperature_2m": [75.0, 78.0, 80.0],
        "wind_speed_10m": [10.0, 12.0, 15.0],
        "wind_direction_10m": [180.0, 200.0, 210.0],
    }
}

def test_parse_picks_closest_hour():
    snap = parse_open_meteo_response(_MOCK_ARCHIVE,
                                     target=datetime(2024, 7, 15, 19, 30, tzinfo=timezone.utc))
    # 19:30 equidistant to 19:00 and 20:00 — either valid
    assert snap.temp_f in (78.0, 80.0)

def test_project_wind_blowing_out():
    w = project_wind(wind_mph=10, wind_from_deg=0, outfield_orientation_deg=0)
    assert w == pytest.approx(10.0)

def test_project_wind_blowing_in():
    w = project_wind(wind_mph=10, wind_from_deg=180, outfield_orientation_deg=0)
    assert w == pytest.approx(-10.0)

def test_project_wind_crosswind():
    w = project_wind(wind_mph=10, wind_from_deg=90, outfield_orientation_deg=0)
    assert abs(w) < 0.1

def test_fetch_raises_on_http_error(monkeypatch):
    def boom(*a, **kw): raise OSError("network down")
    monkeypatch.setattr("data.foundation.weather_fetcher._http_get_json", boom)
    with pytest.raises(WeatherError):
        fetch_weather_at(latitude=40.0, longitude=-75.0,
                         target=datetime(2024, 7, 15, 19, 0, tzinfo=timezone.utc))

def test_fetch_returns_parsed(monkeypatch):
    monkeypatch.setattr("data.foundation.weather_fetcher._http_get_json", lambda url: _MOCK_ARCHIVE)
    snap = fetch_weather_at(latitude=40.0, longitude=-75.0,
                            target=datetime(2024, 7, 15, 19, 0, tzinfo=timezone.utc))
    assert snap.temp_f == 78.0
    assert snap.wind_mph == 12.0
    assert snap.wind_from_deg == 200.0
