# clean.py
import numpy as np
import pandas as pd

df = pd.read_csv('raw_laps.csv')
start = len(df)
print(f"Starting laps: {start}")

# First lap of each race on a wet tyre. Taken from the untouched data on purpose:
# the stop onto wets is itself an in-lap, so measuring this after the in/out-lap
# filter below reports the onset a lap late and leaves rain-affected laps in.
WET_COMPOUNDS = ['INTERMEDIATE', 'WET']
wet_onset = (df[df['Compound'].isin(WET_COMPOUNDS)]
               .groupby('GP')['LapNumber'].min())

# -- -laps with no recorded lap time have been dropped  ---
df = df[df['LapTimeSeconds'].notna()]
print(f"After dropping null lap times: {len(df)}")

# --- drop in-laps and out-laps  ---
# A lap is an out-lap if PitOutTime is set; an in-lap if PitInTime is set.
df = df[df['PitInTime'].isna() & df['PitOutTime'].isna()]
print(f"After dropping in/out laps: {len(df)}")

# --- drop laps 1-2 (standing start is not representative pace) ---
# Lap 1 is the start itself. Lap 2 is still the bunched pack with DRS not yet
# enabled: in Spain seven drivers sit at 81.8-83.1s on lap 2 vs ~81.6s on lap 3,
# which shows up as a spurious spike at the low-tyre-age end of every curve.
df = df[df['LapNumber'] > 2]
print(f"After dropping laps 1-2: {len(df)}")

# --- drop non-green-flag laps (safety car / VSC / yellow flag) ---
# TrackStatus '1' == all-clear green. Anything else means the field was slowed.
df['TrackStatus'] = df['TrackStatus'].astype(str)
df = df[df['TrackStatus'] == '1']
print(f"After dropping non-green laps: {len(df)}")

# --- drop laps run in changing conditions ---
# Once it starts raining, lap time stops measuring the tyre and starts measuring
# the track. The giveaway is cars still on slicks: in Monaco 2023 the dry-compound
# median goes 78.57s on lap 50 -> 84.18 -> 89.00 -> 93.26, while the first wet-tyre
# stop is lap 52. So the track is already gone a lap before anyone reacts: cut from
# (first wet-tyre lap - 1) to the end of that race, wet and dry laps alike.
BUFFER = 1

for gp, lap in (wet_onset - BUFFER).items():
    n = len(df)
    df = df[(df['GP'] != gp) | (df['LapNumber'] < lap)]
    print(f"  {gp}: wet from lap {lap:.0f}, dropped {n - len(df)} laps")
print(f"After dropping mixed-condition laps: {len(df)}")

# --- per-stint outlier removal (traffic, mistakes, lock-ups) ---
# Cutting only SLOW laps relative to a flat stint median is wrong: lap time
# TRENDS within a stint (fuel burn makes it fall, tyre wear makes it rise), so a
# flat baseline systematically flags whichever end of the stint is slower and
# eats the degradation signal we are trying to measure.
#
# Instead, detrend each stint against its own linear fit and cut SYMMETRICALLY on
# the residual, scaled by that stint's own noise (MAD). Stints differ a lot in
# consistency, so a per-stint scale beats one global threshold in seconds.

K = 3.0             # keep residuals within K robust sigma
FLOOR = 0.5         # ...but never cut anything inside +/- 0.5s (very tidy stints)
MIN_FIT = 5         # stints shorter than this get a flat median baseline


def stint_residual(g):
    """Lap time minus that stint's own trend line."""
    y = g['LapTimeSeconds'].values
    if len(g) >= MIN_FIT:
        x = g['TyreLife'].values
        baseline = np.polyval(np.polyfit(x, y, 1), x)
    else:
        baseline = np.median(y)
    return pd.Series(y - baseline, index=g.index)


keys = ['GP', 'Driver', 'Stint']
res = (df.groupby(keys, group_keys=False)
         .apply(stint_residual)
         .reindex(df.index))            # groupby.apply may reorder; realign to df
mad = res.groupby([df[k] for k in keys]).transform(
    lambda r: np.median(np.abs(r - np.median(r))))
scale = np.maximum(1.4826 * mad, 0.15)      # MAD -> sigma, with a sanity floor

df = df[(res.abs() <= np.maximum(K * scale, FLOOR)).values]
print(f"After per-stint outlier removal: {len(df)}")

print(f"\nTotal removed: {start - len(df)} laps ({100*(start-len(df))/start:.1f}%)")

df.to_csv('clean_laps.csv', index=False)
print("Saved clean_laps.csv")