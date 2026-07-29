# extract.py
import fastf1
import pandas as pd

fastf1.Cache.enable_cache('f1_cache')   
#   Spain 2023   - high tyre degradation, classic 2-stop
#   Monaco 2023  - low deg, track position king, 1-stop
#   Silverstone 2023 - high deg + a safety car that scrambled strategy
RACES = [
    (2023, 'Spain'),
    (2023, 'Monaco'),
    (2023, 'Great Britain'),
]

def get_race_laps(year, gp):
    session = fastf1.get_session(year, gp, 'R')   # 'R' = Race
    session.load()                                # downloads timing + tyre data
    laps = session.laps

    # Keep only the columns relevant to a degradation / pit-window study.
    cols = [
        'Driver', 'LapNumber', 'LapTime', 'Stint',
        'Compound', 'TyreLife',        # TyreLife = laps on the current tyre set
        'PitInTime', 'PitOutTime',     # non-null only on in/out laps
        'TrackStatus',                 # '1' = green; other codes = SC/VSC/yellow
        'IsAccurate',                  # FastF1's own flag for a clean-measured lap
    ]
    df = laps[cols].copy()
    df['Year'] = year
    df['GP'] = gp
    return df

if __name__ == '__main__':
    all_races = []
    for year, gp in RACES:
        print(f'Loading {year} {gp}...')
        all_races.append(get_race_laps(year, gp))
    data = pd.concat(all_races, ignore_index=True)

    # LapTime comes as a pandas Timedelta; convert to seconds (float) for modelling.
    data['LapTimeSeconds'] = data['LapTime'].dt.total_seconds()

    data.to_csv('raw_laps.csv', index=False)   # or .to_csv if you prefer
    print(f'\nSaved {len(data)} laps across {len(RACES)} races.')
    print(data[['Driver','GP','LapNumber','Compound','TyreLife','LapTimeSeconds']].head(15))