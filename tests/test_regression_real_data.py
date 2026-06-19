"""
End-to-end regression tests against real (trimmed) production data.

Unlike test_build_vulnerability.py's synthetic unit tests, these run the
actual compute_zscores() + scoring loop against a real 135-month slice of
the project's vulnerability_scored.csv (raw indicator values only -- the
zscore/score columns are dropped and recomputed fresh here, so this proves
the pipeline reproduces itself, not that stored numbers equal stored
numbers).

The three target months were chosen deliberately:

    2020-04-01  COVID collapse, also the month gas_premium_dop crashed
                -38.5 DOP in a single month -- the gas MoM override should
                fire and the fixed score (72.13) should differ materially
                from what the pre-fix engine produced (67.13), confirming
                the fix changes real history correctly, not just synthetic
                cases.
    2025-09-01  Part of the Aug-Nov 2025 deterioration window that the old
                50/65 thresholds buried under "Moderate" alongside ordinary
                months. Under the new percentile bands this must classify
                as HIGH.
    2026-05-01  The month that originally surfaced the gas z-score bug
                (z=+4.98). The gas fix is a no-op here specifically because
                the old z-score had already saturated contribution to 1.0 --
                this test guards against someone "fixing" the gas rule
                again later in a way that accidentally changes this number.

If a future change to compute_zscores(), classify_indicator(), or the
component weights/thresholds shifts ANY of these three values, this test
fails. That's the point: these are the load-bearing facts the rest of the
project's published numbers depend on.

Run with:
    pytest tests/test_regression_real_data.py -v
"""

import sys
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from pipeline.build_vulnerability import (
    VULNERABILITY_COMPONENTS,
    MODERATE_STRESS_THRESHOLD,
    HIGH_STRESS_THRESHOLD,
    compute_zscores,
    classify_indicator,
)

FIXTURE_PATH = Path(__file__).parent / "fixtures" / "vulnerability_history.csv"


@pytest.fixture(scope="module")
def scored_history():
    """
    Load the trimmed real-data fixture and run it through the actual
    scoring pipeline (compute_zscores + the same per-month scoring loop
    run_vulnerability_pipeline uses), returning a dict of {Timestamp: score}
    for every month with full 12-indicator coverage.
    """
    raw = pd.read_csv(FIXTURE_PATH, index_col=0, parse_dates=True)
    components = list(VULNERABILITY_COMPONENTS.keys())
    assert set(components).issubset(raw.columns), (
        "Fixture is missing expected component columns -- "
        "was it regenerated against an outdated VULNERABILITY_COMPONENTS?"
    )

    scored = compute_zscores(raw)
    zscore_cols = [f"{c}_zscore" for c in components]
    missing_mask = scored[zscore_cols].isna().any(axis=1)

    scores = {}
    for idx, row in scored.iterrows():
        if missing_mask.loc[idx]:
            continue
        total = 0.0
        for col in components:
            z = row[f"{col}_zscore"]
            if pd.notna(z):
                mom = row.get("gas_premium_dop_mom") if col == "gas_premium_dop" else None
                classification = classify_indicator(col, row[col], z, mom_delta=mom)
                total += classification["weighted_score"]
        scores[idx] = total
    return scores


class TestKnownMonthScores:

    def test_2020_04_covid_gas_shock_score(self, scored_history):
        # COVID month with a -38.5 DOP gas crash. The gas MoM override
        # should be saturating this contribution, pushing the score above
        # what the old z-score-only engine produced (67.13).
        ts = pd.Timestamp("2020-04-01")
        assert ts in scored_history, "2020-04 missing from fixture coverage"
        assert scored_history[ts] == pytest.approx(72.13, abs=0.05)

    def test_2020_04_classifies_as_high_stress(self, scored_history):
        ts = pd.Timestamp("2020-04-01")
        assert scored_history[ts] >= HIGH_STRESS_THRESHOLD

    def test_2025_09_deterioration_window_score(self, scored_history):
        ts = pd.Timestamp("2025-09-01")
        assert ts in scored_history, "2025-09 missing from fixture coverage"
        assert scored_history[ts] == pytest.approx(61.88, abs=0.05)

    def test_2025_09_classifies_as_high_under_new_bands(self, scored_history):
        # This is the month that justified moving off the old 50/65 bands:
        # under the OLD bands this was merely "Moderate" alongside calm
        # months. Under the new percentile bands it must read HIGH.
        ts = pd.Timestamp("2025-09-01")
        assert scored_history[ts] >= HIGH_STRESS_THRESHOLD
        # And document explicitly that the OLD bands would have called
        # this Moderate, not High -- a frozen fact about why the rebanding
        # mattered, independent of whatever the current thresholds are.
        OLD_HIGH_THRESHOLD = 65.0
        assert scored_history[ts] < OLD_HIGH_THRESHOLD

    def test_2026_05_gas_artifact_month_unchanged_by_fix(self, scored_history):
        # The month that surfaced the original z=+4.98 bug. The gas fix is
        # a deliberate no-op here (the z-score had already saturated
        # contribution to 1.0 before the fix existed) -- this pins that
        # fact down so a future change to the gas rule can't silently
        # alter this specific, already-published number without the test
        # noticing.
        ts = pd.Timestamp("2026-05-01")
        assert ts in scored_history, "2026-05 missing from fixture coverage"
        assert scored_history[ts] == pytest.approx(51.50, abs=0.05)

    def test_2026_05_classifies_as_moderate_not_high(self, scored_history):
        ts = pd.Timestamp("2026-05-01")
        score = scored_history[ts]
        assert MODERATE_STRESS_THRESHOLD <= score < HIGH_STRESS_THRESHOLD


class TestFixtureIntegrity:
    """Guards against the fixture itself silently rotting or being edited."""

    def test_fixture_has_expected_date_range(self):
        raw = pd.read_csv(FIXTURE_PATH, index_col=0, parse_dates=True)
        assert raw.index.min() <= pd.Timestamp("2015-04-01")
        assert raw.index.max() >= pd.Timestamp("2026-05-01")

    def test_fixture_has_all_twelve_components(self):
        raw = pd.read_csv(FIXTURE_PATH, index_col=0, parse_dates=True)
        for col in VULNERABILITY_COMPONENTS:
            assert col in raw.columns, f"Fixture missing component column: {col}"
