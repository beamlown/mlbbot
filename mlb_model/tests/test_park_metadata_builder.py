import pytest
from data.foundation.park_metadata_builder import (
    build_park_metadata,
    PARK_METADATA,
)

def test_all_30_current_parks_present():
    df = build_park_metadata()
    assert len(df) == 30

def test_coors_is_outdoor():
    df = build_park_metadata()
    coors = df[df.park_id == "DEN02"].iloc[0]
    assert coors.has_roof == 0
    assert coors.is_indoor == 0

def test_tropicana_is_indoor():
    df = build_park_metadata()
    tropicana = df[df.park_id == "STP01"].iloc[0]
    assert tropicana.has_roof == 1
    assert tropicana.is_indoor == 1

def test_chase_field_has_retractable_roof():
    df = build_park_metadata()
    chase = df[df.park_id == "PHO01"].iloc[0]
    assert chase.has_roof == 1
    assert chase.is_retractable == 1

def test_every_park_has_lat_lon_orientation():
    df = build_park_metadata()
    assert df["latitude"].notna().all()
    assert df["longitude"].notna().all()
    assert df["outfield_orientation_deg"].notna().all()
