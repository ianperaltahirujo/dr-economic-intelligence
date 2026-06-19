# Tests


## Running

```bash
pytest tests/ -v
```

## What's covered

**test_build_vulnerability.py** — synthetic unit tests against
`classify_indicator()` and `compute_zscores()` in isolation. Covers the
directional z-score logic, all three `LEVEL_THRESHOLDS` overrides
(ipc_yoy_pct, dop_usd, UMCSENT), the `gas_premium_dop` month-over-month
override added to fix the z-score artifact, contribution/weighted_score
arithmetic, the strict no-partial-coverage rule, and sanity checks on the
module-level threshold constants.

**test_regression_real_data.py** — end-to-end tests that run the actual
scoring pipeline (`compute_zscores` + the per-month scoring loop) against
`fixtures/vulnerability_history.csv`, a trimmed 135-month slice of real
project data (raw indicator values only, 2015-04 through the most recent
run). Pins down three specific, previously-verified scores (2020-04,
2025-09, 2026-05) so a future change to the engine that shifts any of them
fails loudly instead of being discovered on the published dashboard.

## Updating the fixture

`fixtures/vulnerability_history.csv` should be regenerated whenever
`VULNERABILITY_COMPONENTS` changes (a column added/removed) or when
extending the regression coverage to new target months. Build it from a
real `vulnerability_scored.csv` by slicing to the raw component columns
only (not the precomputed zscore/score columns, since the test recomputes
those) and keeping enough trailing history before any target month for
the longest rolling window (60 months, for `ipc_yoy_pct`/`dop_usd`) to
resolve correctly.

## Why build_vulnerability.py's ingestion imports moved inside the function

`run_vulnerability_pipeline()` used to import `ingest_bcrd`, `ingest_sb`,
and `ingest_fred_dr` at module level. Those modules need network access,
API keys, and `fredapi`, none of which should be required just to import
the module and test its pure scoring functions. The imports were moved
inside `run_vulnerability_pipeline()` itself, where they're actually used.
No behavior change; this is what makes `pytest` able to import
`build_vulnerability.py` at all without faking out the entire ingestion
layer.

## Known gap

`write_html.py`'s `count_indicator_statuses()` and `build_indicator_cards()`
still duplicate `classify_indicator()`'s logic by hand rather than calling
it directly (the gas MoM override was patched into both as a stopgap, but
the `LEVEL_THRESHOLDS` overrides for ipc_yoy_pct/dop_usd/UMCSENT are not
wired into either function). No test here currently exercises that gap
since none of the real data has crossed those absolute levels yet. This is
flagged as the next structural fix, not addressed in this test pass.