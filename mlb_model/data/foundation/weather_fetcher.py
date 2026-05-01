"""
data/foundation/weather_fetcher.py

Open-Meteo archive + forecast API wrapper.

Archive (historical):  https://archive-api.open-meteo.com/v1/archive
Forecast (today/future): https://api.open-meteo.com/v1/forecast

Free tier: 10k requests/day. No API key needed.
"""
from __future__ import annotations
import json
import logging
import math
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional

logger = logging.getLogger(__name__)

ARCHIVE_BASE = "https://archive-api.open-meteo.com/v1/archive"
FORECAST_BASE = "https://api.open-meteo.com/v1/forecast"


class WeatherError(Exception):
    pass


@dataclass
class WeatherSnapshot:
    temp_f: float
    wind_mph: float
    wind_from_deg: float


def _http_get_json(url: str) -> dict:
    req = urllib.request.Request(url, headers={"User-Agent": "mlb_model/1.0"})
    with urllib.request.urlopen(req, timeout=15) as resp:
        return json.loads(resp.read().decode())


def project_wind(wind_mph: float, wind_from_deg: float,
                 outfield_orientation_deg: float) -> float:
    """
    Project wind onto the park's outfield axis.
    Returns +mph if blowing OUT toward CF, -mph if blowing IN from CF.
    Clamped to +/-30 mph.
    """
    angle_deg = wind_from_deg - outfield_orientation_deg
    angle_rad = math.radians(angle_deg)
    projected = wind_mph * math.cos(angle_rad)
    return max(-30.0, min(30.0, projected))


def parse_open_meteo_response(data: dict, target: datetime) -> WeatherSnapshot:
    """Pick the hourly reading closest to target datetime."""
    hourly = data.get("hourly") or {}
    times = hourly.get("time") or []
    temps = hourly.get("temperature_2m") or []
    winds = hourly.get("wind_speed_10m") or []
    dirs = hourly.get("wind_direction_10m") or []
    if not times:
        raise WeatherError("no hourly data in response")

    target_utc = target.astimezone(timezone.utc).replace(tzinfo=None)
    best_idx = 0
    best_diff = abs((datetime.fromisoformat(times[0]) - target_utc).total_seconds())
    for i, t_str in enumerate(times[1:], start=1):
        diff = abs((datetime.fromisoformat(t_str) - target_utc).total_seconds())
        if diff < best_diff:
            best_diff = diff
            best_idx = i

    return WeatherSnapshot(
        temp_f=float(temps[best_idx]) if best_idx < len(temps) else 70.0,
        wind_mph=float(winds[best_idx]) if best_idx < len(winds) else 0.0,
        wind_from_deg=float(dirs[best_idx]) if best_idx < len(dirs) else 0.0,
    )


def fetch_weather_at(latitude: float, longitude: float, target: datetime,
                     use_archive: bool = True) -> WeatherSnapshot:
    """Fetch hourly weather closest to target datetime."""
    base = ARCHIVE_BASE if use_archive else FORECAST_BASE
    date_str = target.strftime("%Y-%m-%d")
    url = (
        f"{base}?latitude={latitude}&longitude={longitude}"
        f"&start_date={date_str}&end_date={date_str}"
        f"&hourly=temperature_2m,wind_speed_10m,wind_direction_10m"
        f"&temperature_unit=fahrenheit&wind_speed_unit=mph&timezone=UTC"
    )
    try:
        data = _http_get_json(url)
    except Exception as e:
        raise WeatherError(f"Open-Meteo fetch failed: {e}") from e
    return parse_open_meteo_response(data, target)
