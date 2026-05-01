import pandas as pd
import pytest
from sports.mlb.park_metadata_live import lookup_park_metadata, _set_test_table, ParkMetadata

@pytest.fixture(autouse=True)
def reset():
    yield
    _set_test_table(None)

def test_lookup_known_outdoor():
    tbl = pd.DataFrame([{
        "park_id": "DEN02", "park_name": "Coors", "latitude": 39.75, "longitude": -104.99,
        "outfield_orientation_deg": 0, "has_roof": 0, "is_retractable": 0, "is_indoor": 0,
    }])
    _set_test_table(tbl)
    m = lookup_park_metadata("DEN02")
    assert m.latitude == pytest.approx(39.75)
    assert m.is_indoor is False
    assert m.has_roof is False

def test_lookup_unknown_returns_indoor_neutral():
    _set_test_table(pd.DataFrame(columns=[
        "park_id", "park_name", "latitude", "longitude",
        "outfield_orientation_deg", "has_roof", "is_retractable", "is_indoor",
    ]))
    m = lookup_park_metadata("XXX")
    assert m.is_indoor is True
    assert m.has_roof is True
