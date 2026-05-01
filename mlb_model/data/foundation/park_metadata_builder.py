"""
data/foundation/park_metadata_builder.py

Static 30-row table of MLB park metadata.

Orientations: compass bearing of home plate -> center field axis (degrees).
A wind blowing FROM that direction blows the ball OUT (positive wind_out).

Hand-coded from public stadium data. Update if a team relocates.
"""
from __future__ import annotations
from pathlib import Path
import pandas as pd

OUTPUT_PATH = Path("data/features/park_metadata.parquet")

PARK_METADATA = [
    ("BAL12", "Oriole Park at Camden Yards",  39.2838,  -76.6217,  37, 0, 0, 0),
    ("BOS07", "Fenway Park",                   42.3467,  -71.0972,  45, 0, 0, 0),
    ("NYC21", "Yankee Stadium",                40.8296,  -73.9262,  74, 0, 0, 0),
    ("STP01", "Tropicana Field",               27.7682,  -82.6534,  46, 1, 0, 1),
    ("TOR02", "Rogers Centre",                 43.6414,  -79.3894,   0, 1, 1, 0),
    ("CHI12", "Guaranteed Rate Field",         41.8300,  -87.6338,  40, 0, 0, 0),
    ("CLE08", "Progressive Field",             41.4958,  -81.6852,   0, 0, 0, 0),
    ("DET05", "Comerica Park",                 42.3390,  -83.0485, 150, 0, 0, 0),
    ("KAN06", "Kauffman Stadium",              39.0517,  -94.4803,  45, 0, 0, 0),
    ("MIN04", "Target Field",                  44.9817,  -93.2776,  90, 0, 0, 0),
    ("OAK01", "Oakland Coliseum",              37.7515, -122.2006,  60, 0, 0, 0),
    ("HOU03", "Minute Maid / Daikin Park",     29.7572,  -95.3550,  20, 1, 1, 0),
    ("ANA01", "Angel Stadium",                 33.8003, -117.8827,  45, 0, 0, 0),
    ("SEA03", "T-Mobile Park",                 47.5914, -122.3325,  45, 1, 1, 0),
    ("ARL02", "Globe Life Field",              32.7473,  -97.0817,   0, 1, 1, 0),
    ("ATL03", "Truist Park",                   33.8908,  -84.4678, 150, 0, 0, 0),
    ("MIA02", "loanDepot park",                25.7781,  -80.2197,  40, 1, 1, 0),
    ("NYC20", "Citi Field",                    40.7571,  -73.8458,   0, 0, 0, 0),
    ("PHI13", "Citizens Bank Park",            39.9061,  -75.1665,  15, 0, 0, 0),
    ("WAS11", "Nationals Park",                38.8729,  -77.0074,   0, 0, 0, 0),
    ("CHI11", "Wrigley Field",                 41.9484,  -87.6553,  30, 0, 0, 0),
    ("CIN09", "Great American Ball Park",      39.0975,  -84.5069, 100, 0, 0, 0),
    ("MIL06", "American Family Field",         43.0280,  -87.9712,  60, 1, 1, 0),
    ("PIT08", "PNC Park",                      40.4469,  -80.0057, 120, 0, 0, 0),
    ("STL10", "Busch Stadium",                 38.6226,  -90.1928,  60, 0, 0, 0),
    ("PHO01", "Chase Field",                   33.4453, -112.0667,  15, 1, 1, 0),
    ("DEN02", "Coors Field",                   39.7559, -104.9942,   0, 0, 0, 0),
    ("LOS03", "Dodger Stadium",                34.0739, -118.2400,  25, 0, 0, 0),
    ("SAN02", "Petco Park",                    32.7073, -117.1566,  30, 0, 0, 0),
    ("SFO03", "Oracle Park",                   37.7786, -122.3893,  90, 0, 0, 0),
]


def build_park_metadata() -> pd.DataFrame:
    return pd.DataFrame(PARK_METADATA, columns=[
        "park_id", "park_name", "latitude", "longitude",
        "outfield_orientation_deg", "has_roof", "is_retractable", "is_indoor",
    ])


def main() -> None:
    df = build_park_metadata()
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(OUTPUT_PATH, index=False)
    print(f"Wrote {len(df)} rows to {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
