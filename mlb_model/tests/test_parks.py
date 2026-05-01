import pytest
from sports.mlb.parks import TEAM_TO_PARK, lookup_park_id, ALL_TEAMS

def test_every_team_has_park():
    for team in ALL_TEAMS:
        assert team in TEAM_TO_PARK, f"{team} missing from TEAM_TO_PARK"
        assert TEAM_TO_PARK[team], f"{team} has empty park_id"

def test_lookup_known_team():
    assert lookup_park_id("COL") == "DEN02"
    assert lookup_park_id("LAD") == "LOS03"
    assert lookup_park_id("BOS") == "BOS07"

def test_lookup_unknown_team_returns_unknown_string():
    assert lookup_park_id("XYZ") == "unknown"
    assert lookup_park_id("") == "unknown"

def test_lookup_normalizes_case():
    assert lookup_park_id("col") == "DEN02"
    assert lookup_park_id("Lad") == "LOS03"
