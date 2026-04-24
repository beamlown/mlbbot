"""Tazz URL derivation from ESPN game dict (tazztv.io format)."""
import pytest

from dugout_dash.blueprints.game import _tazz_url


def test_tazz_url_home_team_default(monkeypatch):
    from dugout_dash import config as cfg
    monkeypatch.setattr(cfg, "TAZZ_BASE_URL", "https://tazztv.io/?league=MLB&name={slug}")
    monkeypatch.setattr(cfg, "TAZZ_TEAM_SIDE", "home")
    game = {"home": "Colorado Rockies", "away": "New York Yankees"}
    assert _tazz_url(game) == "https://tazztv.io/?league=MLB&name=colorado_rockies"


def test_tazz_url_away_team_override(monkeypatch):
    from dugout_dash import config as cfg
    monkeypatch.setattr(cfg, "TAZZ_BASE_URL", "https://tazztv.io/?league=MLB&name={slug}")
    monkeypatch.setattr(cfg, "TAZZ_TEAM_SIDE", "away")
    game = {"home": "Colorado Rockies", "away": "New York Yankees"}
    assert _tazz_url(game) == "https://tazztv.io/?league=MLB&name=new_york_yankees"


def test_tazz_url_none_when_missing_team():
    assert _tazz_url(None) is None
    assert _tazz_url({"home": "", "away": "Yankees"}) is None
