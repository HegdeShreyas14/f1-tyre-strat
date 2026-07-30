# Tyre Degradation & Pit-Window Findings

Real FastF1 timing data from three 2023 races — Spain, Monaco, and Silverstone,
chosen for strategic variety — run through a cleaning pipeline, a degradation
model, and a pit-window optimiser. This is the plain-language summary; the
notebook has the full derivation.

## Headline

**Spain degrades roughly 2.5x faster than Silverstone, and the two circuits
separate compounds completely differently.** At Spain, soft/medium/hard tyres
lose time at distinguishably different rates. At Silverstone, all three lose
time at the *same* rate — there is no measurable compound separation at all.
That is a real result, not a modelling failure, and it is more interesting
than a textbook "softs degrade fastest" would have been.

| Circuit | SOFT | MEDIUM | HARD | Read |
|---|---:|---:|---:|---|
| Spain | 0.058 s/lap | 0.055 s/lap | 0.049 s/lap | clear separation |
| Silverstone | 0.023 s/lap | 0.022 s/lap | 0.022 s/lap | no separation |
| Monaco | — | 0.027 s/lap | 0.037 s/lap | soft unmeasurable (1 stint) |

## Why the raw data looked backwards

Plot lap time against tyre age with no correction and it *falls* as the tyre
wears — the opposite of what a tyre should do. The car sheds roughly 1.7 kg of
fuel per lap, worth about 0.05 s/lap, which is larger than the degradation
itself (0.02–0.06 s/lap) and points the other way. Every result here comes
from a model that separates the two — `driver + race-lap + tyre-age×compound`,
fit per circuit — before the degradation number is trustworthy at all. The
fitted fuel term lands on -0.056 / -0.050 / -0.054 s/lap for Spain / Monaco /
Silverstone, matching the textbook physical value, which is the check that the
separation actually worked.

Getting there took two attempts. Fitting fuel burn separately per compound
seemed like the natural first cut, but within a single stint race-lap and
tyre-age increment together every lap, so the two are collinear — one Monaco
stint (one driver, one set of softs) had them correlated at exactly 1.000,
and the fit returned a nonsense fuel coefficient of +3.3 s/lap. The fix was to
share one fuel term across all compounds per circuit and add per-driver
offsets, pooling the cross-stint variation that actually identifies it. Softs,
mediums, and hards don't burn fuel differently — treating fuel as a property
of the car rather than the tyre is what makes the numbers physical.

## The pit-window model

A stop trades a fixed cost (pit-lane time) against a recurring gain (fresh
tyres). Pit loss was measured from real green-flag stops — in-lap plus
out-lap against each driver's surrounding pace — at **23.8s (Spain), 20.0s
(Monaco), 19.8s (Silverstone)**. The model then searches every legal stop lap
and compound combination for the one that minimises total time lost.

| Circuit | Model optimum | Actual median | Verdict |
|---|---|---|---|
| Silverstone | 1-stop, lap 26 | 1-stop, lap 31 (14 drivers) | **matches** |
| Monaco | 1-stop, lap 25 | lap 53 — the rain stop, not tyre-driven | not a real comparison |
| Spain | 1-stop, lap 32, by only 5.3s | 2-stop at [16, 39] (17 of 17 finishers) | **model likely wrong** |

Silverstone is the clean validation: the model's recommendation lands within
five laps of what the entire front of the field actually did.

Spain does not confirm the model, and the reason is instructive rather than a
shrug. The model's 1-stop plan requires a 32-lap stint on softs — but the
longest soft stint ever run at Spain in this data is 27 laps. The model is
linearly extrapolating a degradation rate measured only up to 27 laps out to
32, on the compound that wears fastest, and its margin over the real strategy
(5.3 seconds) is smaller than the noise in the pit-loss estimate itself
(±3.7s). Every one of the 17 finishers ran a 2-stop instead. The honest read
is that the real teams are right and the model's answer is an artifact of
pushing a linear fit past the range it was measured on — tyres often degrade
non-linearly near the end of a long stint (a "cliff"), which this model cannot
see because it was never asked to fit one.

Monaco isn't a fair test either way: the race finished in the rain, so the
"actual" pit laps for most drivers are the switch to wet-weather tyres, not a
strategic tyre-life decision. The model's own Monaco plan also extrapolates
slightly (53 laps on hards vs. 51 ever observed), so this circuit is excluded
from the strategy comparison rather than treated as a disagreement.

## Limitations, stated plainly

- **Fresh-tyre pace was measured and found unmeasurable.** A soft should be
  several tenths quicker than a hard on a new set; the data shows nothing
  beyond noise (largest signal is 1.6 standard errors, and Spain's soft
  offset even comes out slower than the hard's). This is because compounds
  aren't driven comparably in a race — softs get lift-and-coast management,
  hards run long clean-air stints — so raw race pace never contains the
  equal-effort comparison a pace ranking would need. The model runs with this
  set to zero rather than guessed.
- **Degradation is fit as a straight line.** Real tyres can fall off a cliff
  near the end of their life; this model has no way to detect one, and
  Spain's mismatch above is a direct consequence.
- **Three races is a proof of method, not a season-wide claim.** The approach
  (separate fuel from wear, then optimise the stop) generalises; the specific
  numbers are read from three data points per circuit.
- **Public timing data only.** No car telemetry, no team-side tyre
  temperature or pressure data — this is what's visible from the outside,
  which is also what makes the pit-loss and degradation estimates fully
  reproducible from `extract.py` onward.

## The pitch

Raw lap times fall as a tyre wears, which looks backwards until you notice
fuel burn is bigger than degradation and pointing the other way. Separating
the two with a regression — after diagnosing and fixing a collinearity bug
that first gave a fuel coefficient of +3.3 s/lap — turns up a real finding:
Spain degrades 2.5x faster than Silverstone, and Silverstone shows no
separation between compounds at all. Feeding those rates into a pit-window
optimiser against a measured pit-loss cost recovers the paddock's actual
strategy at Silverstone, and at Spain correctly identifies *why* the model's
answer shouldn't be trusted — it silently extrapolates past the longest stint
ever recorded on that compound. That diagnosis is the deliverable as much as
the numbers are.
