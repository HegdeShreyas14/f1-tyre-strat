# sql/build_db.py
"""Load the cleaned lap data into SQLite so the analysis can also be queried in SQL.

Three tables:
  laps       one row per clean green-flag lap (the output of clean.py)
  stints     one row per (race, driver, stint) -- a derived summary table
  pit_stops  one row per pit stop, with the in-lap/out-lap times and a
             clean_for_pace flag (0 under SC/VSC or after Monaco's rain arrived)

Run from the repo root:  python sql/build_db.py
"""
import sqlite3
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
DB = ROOT / 'sql' / 'f1.db'

laps = pd.read_csv(ROOT / 'clean_laps.csv')
laps = laps[['GP', 'Year', 'Driver', 'LapNumber', 'Stint', 'Compound',
             'TyreLife', 'LapTimeSeconds']]
laps.columns = ['gp', 'year', 'driver', 'lap', 'stint', 'compound',
                'tyre_life', 'lap_time']

# --- stints: one row per tyre set actually run -----------------------------
stints = (laps.groupby(['gp', 'driver', 'stint', 'compound'], as_index=False)
              .agg(laps_run=('lap', 'size'),
                   start_lap=('lap', 'min'),
                   end_lap=('lap', 'max'),
                   start_age=('tyre_life', 'min'),
                   end_age=('tyre_life', 'max'),
                   median_time=('lap_time', 'median'),
                   best_time=('lap_time', 'min')))

# --- pit_stops: in-lap/out-lap pairs, from the untouched data --------------
# clean.py discards in-laps and out-laps, so these have to come from raw_laps.csv.
# Every real stop is kept -- a strategy count should include stops made under a
# safety car -- but each row is flagged `clean_for_pace`, since an in/out lap
# timed under SC or in Monaco's late rain measures the caution period or the
# weather, not the pit lane, and would wildly overstate pit loss if averaged in.
raw = pd.read_csv(ROOT / 'raw_laps.csv')
raw = raw[raw.LapTimeSeconds.notna()].copy()
raw['TrackStatus'] = raw['TrackStatus'].astype(str)

WET_COMPOUNDS = ['INTERMEDIATE', 'WET']
wet_onset = raw[raw.Compound.isin(WET_COMPOUNDS)].groupby('GP')['LapNumber'].min()

inlaps = raw[raw.PitInTime.notna()][
    ['GP', 'Driver', 'LapNumber', 'LapTimeSeconds', 'TrackStatus']]
inlaps.columns = ['gp', 'driver', 'lap', 'in_lap_time', 'in_status']
outlaps = raw[raw.PitOutTime.notna()][
    ['GP', 'Driver', 'LapNumber', 'LapTimeSeconds', 'TrackStatus']]
outlaps.columns = ['gp', 'driver', 'out_lap', 'out_lap_time', 'out_status']
outlaps['lap'] = outlaps['out_lap'] - 1          # the stop's in-lap
pit_stops = inlaps.merge(outlaps, on=['gp', 'driver', 'lap'], how='inner')

before_rain = pit_stops['lap'] < pit_stops['gp'].map(wet_onset).fillna(float('inf'))
pit_stops['clean_for_pace'] = (
    (pit_stops.in_status == '1') & (pit_stops.out_status == '1') & before_rain
).astype(int)
pit_stops = pit_stops.drop(columns=['in_status', 'out_status'])

DB.unlink(missing_ok=True)
with sqlite3.connect(DB) as con:
    laps.to_sql('laps', con, index=False)
    stints.to_sql('stints', con, index=False)
    pit_stops.to_sql('pit_stops', con, index=False)
    con.executescript("""
        CREATE INDEX idx_laps_stint  ON laps (gp, driver, stint);
        CREATE INDEX idx_laps_comp   ON laps (gp, compound);
        CREATE INDEX idx_stints_gp   ON stints (gp, compound);
    """)

print(f'wrote {DB.relative_to(ROOT)}')
for name, df in [('laps', laps), ('stints', stints), ('pit_stops', pit_stops)]:
    print(f'  {name:10s} {len(df):5d} rows')
