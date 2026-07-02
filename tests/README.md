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

**test_ms_graph.py** — tests for the OneDrive upload / Outlook email addon
(`pipeline/ms_graph.py`). All Graph/Azure AD calls are mocked, so no
network access or credentials are needed: covers token-request shaping,
the OneDrive upload request shape, `sendMail` payload shape (recipients,
body, base64 attachment), and the 5xx retry/backoff helper.

**test_write_excel.py** — tests for `write_workbook()`'s `headline`
parameter in `pipeline/write_excel.py`, which lets the weekly OneDrive
snapshot show the current in-progress month's projected score instead of
the last confirmed month. Covers: default behavior is byte-for-byte
unchanged when `headline` is omitted, the projected month/score render
correctly and use a distinct label from the confirmed-month "Avance
Estimado" tag, and the override never mutates the caller's results dict.

**test_monthly_report_state.py** — tests for
`pipeline/monthly_report_state.py`, which tracks which months already have
a finalized Monthly Report uploaded to OneDrive. Covers: a never-uploaded
month always needs upload, an unchanged month is skipped, a provisional
status flip (e.g. `tourism_daily_spend_usd`'s real value finally arriving)
triggers a re-upload, and graceful handling of a missing/corrupt state file.

**test_write_html.py** — locks in the fix for the dashboard-card
classification gap: `count_indicator_statuses()` and
`build_indicator_cards()` in `pipeline/write_html.py` now call
`classify_indicator()` instead of hand-rolling their own is_stress/is_watch
logic. Covers: the `LEVEL_THRESHOLDS` absolute overrides (ipc_yoy_pct,
dop_usd, UMCSENT) and the `gas_premium_dop` MoM override are honored by
both functions, the z-score bar width renders correctly for
"negative"-direction indicators, and `count_indicator_statuses()`'s totals
agree with independently calling `classify_indicator()` on every
component.

**test_current_month_estimate.py** — tests for
`build_vulnerability.py::estimate_current_month()`, the deliberate,
explicitly-separate relaxation of the strict full-coverage rule used only
to give the dashboard hero an honest reading for the current in-progress
calendar month. Covers: missing current-month components are forward-filled
and reported in `filled_components`, an explicit override value (e.g. a
`dop_usd` month-to-date average) counts as real data rather than a fill,
the function returns `None` instead of fabricating a number when there's
no row for the current month or every component would need filling, the
input DataFrame is never mutated, and the per-component `value`/`zscore`/
`is_filled`/`mom` breakdown used by the weekly OneDrive Excel snapshot.

**test_current_month_tracker.py** — tests for
`pipeline/current_month_tracker.py`, which persists the weekly snapshots of
`estimate_current_month()`'s projection in
`data/state/current_month_snapshots.json`. Covers: week-of-month math,
append-vs-update-by-week dedup (so a manual re-run doesn't skew the
average), reset on month rollover, and graceful handling of a
missing/corrupt snapshot file.

**test_ingest_bcrd.py** — tests for
`pipeline/ingest_bcrd.py::load_exchange_rate_mtd()`, the one place the
pipeline computes its own monthly average exchange rate from daily rates
instead of using BCRD's official `PromMensual` figure, because BCRD only
publishes that once the month closes. Uses a small synthetic `Diaria`-shaped
workbook rather than the real cached file. Covers: averaging only rows in
the target month, `None` when the target month has no rows, a missing
sheet, a missing file, and skipping rows with a blank `Venta` value.

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
