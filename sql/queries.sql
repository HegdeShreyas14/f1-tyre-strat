-- sql/queries.sql
--
-- Five queries against sql/f1.db (built by sql/build_db.py from clean_laps.csv
-- and raw_laps.csv). Run with:  sqlite3 sql/f1.db < sql/queries.sql
--
-- These are a SQL-side complement to the Stage 3 regression in the notebook, not
-- a replacement for it. A GROUP BY average cannot separate fuel burn from tyre
-- wear or add driver fixed effects, so query 2 below is a coarse three-bucket
-- approximation, not the real degradation rate. The regression is the source
-- of truth; these show the same data sliced with SQL primitives (GROUP BY /
-- HAVING, window functions, CTEs, multi-table joins).


-- 1. Which compound/circuit pairs actually have enough stints to trust?
-- GROUP BY + HAVING, mirroring the MIN_STINTS >= 5 identification rule from
-- Stage 3 -- Monaco SOFT is exactly the row this excludes (1 stint).
SELECT gp,
       compound,
       COUNT(*)                    AS n_stints,
       SUM(laps_run)                AS n_laps,
       ROUND(AVG(median_time), 2)   AS avg_median_lap_time
FROM stints
GROUP BY gp, compound
HAVING COUNT(*) >= 5
ORDER BY gp, compound;


-- 2. Coarse degradation signal: split each stint into thirds by tyre age
-- (NTILE window function) and compare average pace in the first third against
-- the last third. This is confounded by fuel burn, the same failure mode
-- Stage 3's Spec A hit, and it shows: at Great Britain and Monaco,
-- late_minus_early comes out NEGATIVE, i.e. even within a single stint the
-- car looks like it is getting faster with tyre age. That is not a query bug
-- -- it is the regression's own numbers reproduced. Fuel burn there
-- (~-0.05 s/lap) is larger than degradation (~0.02-0.03 s/lap), so it wins
-- even over one stint. Spain is the only circuit where late_minus_early is
-- positive, because its degradation (~0.05-0.06 s/lap) is large enough to
-- roughly match fuel burn.
WITH bucketed AS (
    SELECT gp, driver, stint, compound, lap_time,
           NTILE(3) OVER (PARTITION BY gp, driver, stint ORDER BY tyre_life) AS third
    FROM laps
)
SELECT gp,
       compound,
       ROUND(AVG(CASE WHEN third = 1 THEN lap_time END), 3) AS avg_early_third,
       ROUND(AVG(CASE WHEN third = 3 THEN lap_time END), 3) AS avg_late_third,
       ROUND(AVG(CASE WHEN third = 3 THEN lap_time END)
           - AVG(CASE WHEN third = 1 THEN lap_time END), 3) AS late_minus_early
FROM bucketed
GROUP BY gp, compound
HAVING COUNT(DISTINCT driver || stint) >= 5
ORDER BY gp, compound;


-- 3. Fastest stint per compound per circuit, ranked by median lap time.
-- RANK() window function rather than a plain MIN so ties are visible and every
-- stint's standing is inspectable, not just the winner.
WITH ranked AS (
    SELECT gp, driver, stint, compound, laps_run, median_time,
           RANK() OVER (PARTITION BY gp, compound ORDER BY median_time ASC) AS pace_rank
    FROM stints
    WHERE laps_run >= 5
)
SELECT gp, compound, driver, stint, laps_run, median_time, pace_rank
FROM ranked
WHERE pace_rank = 1
ORDER BY gp, compound;


-- 4. Pit-loss estimate per circuit, computed in SQL as a check against the
-- pandas estimate in the notebook (Spain 23.8s / Monaco 20.0s / GB 19.8s).
-- Reference pace is each driver's own average clean lap time for that race
-- (the `laps` table already excludes in/out/non-green laps), so the estimate
-- is relative to how that driver was actually running, not the field average.
-- Restricted to clean_for_pace = 1: without it, Silverstone's safety-car
-- pile of stops and Monaco's rain stops (in-laps over 100s slower than normal)
-- dominate the average and roughly double the estimate.
-- SQLite has no built-in MEDIAN, and the notebook's per-stop windowed median
-- is not expressible in plain SQL, so this is coarser than the Python figure --
-- close agreement is the point, not an exact match.
WITH ref_pace AS (
    SELECT gp, driver, AVG(lap_time) AS ref_time
    FROM laps
    GROUP BY gp, driver
)
SELECT p.gp,
       COUNT(*)                                                     AS n_stops,
       ROUND(AVG(p.in_lap_time + p.out_lap_time - 2 * r.ref_time), 2) AS est_pit_loss_s
FROM pit_stops p
JOIN ref_pace r ON r.gp = p.gp AND r.driver = p.driver
WHERE p.clean_for_pace = 1
GROUP BY p.gp
ORDER BY p.gp;


-- 5. Per-driver strategy summary for one race: stint count, total laps,
-- average stint length, and pit stops. n_pit_stops is a correlated subquery,
-- not a JOIN, on purpose: stints and pit_stops both have several rows per
-- driver, so a plain JOIN on (gp, driver) fans out to every stint x stop
-- combination and silently inflates SUM(laps_run) by however many stops that
-- driver made. The subquery keeps the stints aggregation and the stop count
-- independent.
SELECT s.driver,
       COUNT(DISTINCT s.stint)                       AS n_stints,
       SUM(s.laps_run)                                AS clean_laps_run,
       ROUND(AVG(s.laps_run), 1)                      AS avg_stint_length,
       GROUP_CONCAT(DISTINCT s.compound)               AS compounds_used,
       (SELECT COUNT(*) FROM pit_stops p
         WHERE p.gp = s.gp AND p.driver = s.driver)    AS n_pit_stops
FROM stints s
WHERE s.gp = 'Spain'
GROUP BY s.driver
ORDER BY n_stints DESC, clean_laps_run DESC;
