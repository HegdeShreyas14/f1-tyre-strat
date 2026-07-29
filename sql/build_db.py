# sql/build_db.py
"""Load the cleaned lap data into SQLite so the analysis can also be queried in SQL.

Three tables:
  laps       one row per clean green-flag lap (the output of clean.py)
  stints     one row per (race, driver, stint) -- a derived summary table
  pit_stops  one row per pit stop, with the in-lap and out-lap times

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
raw = pd.read_csv(ROOT / 'raw_laps.csv')
raw = raw[raw.LapTimeSeconds.notna()]
inlaps = raw[raw.PitInTime.notna()][['GP', 'Driver', 'LapNumber', 'LapTimeSeconds']]
inlaps.columns = ['gp', 'driver', 'lap', 'in_lap_time']
outlaps = raw[raw.PitOutTime.notna()][['GP', 'Driver', 'LapNumber', 'LapTimeSeconds']]
outlaps.columns = ['gp', 'driver', 'out_lap', 'out_lap_time']
outlaps['lap'] = outlaps['out_lap'] - 1          # the stop's in-lap
pit_stops = inlaps.merge(outlaps, on=['gp', 'driver', 'lap'], how='inner')

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
