"""
Tests for build_vulnerability.estimate_current_month().

This is a deliberate, explicitly-separate relaxation of the strict
full-coverage rule, used only to give the dashboard hero an honest reading
for the current in-progress calendar month (which the strict historical
loop in run_vulnerability_pipeline() will correctly leave unscored until
every component has real data). These tests pin down:

1. Missing current-month components get forward-filled from their last
   known reading, and are reported in `filled_components`.
2. An explicit `overrides` value (e.g. a dop_usd month-to-date average)
   counts as real data, not a fill.
3. The function returns None rather than fabricating a number when there
   is no row at all for the current month, or when every single
   component would have to be filled (no genuine current-month signal).
4. The input DataFrame is never mutated -- this must never leak into the
   caller's `merged`/`scored` frames that feed vulnerability_scored.csv.

Run with:
    pytest tests/test_current_month_estimate.py -v
"""

import sys
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from pipeline.build_vulnerability import (
    VULNERABILITY_COMPONENTS,
    estimate_current_month,
)


_CALM_BASE = {
    "remesas_usd_mm": 1000.0,
    "ipc_yoy_pct": 4.0,
    "dop_usd": 60.0,
    "reserves_usd_mm": 5000.0,
    "imae_index": 3.0,
    "sb_morosidad_pct": 2.0,
    "sb_solvencia_pct": 15.0,
    "UNRATE": 4.0,
    "UMCSENT": 70.0,
    "sb_tasa_activa_pct": 10.0,
    "gas_premium_dop": 290.0,
    "tourism_daily_spend_usd": 150.0,
}


def _make_history(n_months=15, drop_current=None, current_period=None):
    """
    `n_months` of calm synthetic history (enough for compute_zscores'
    rolling window to produce real numbers) ending at `current_period`.
    Columns named in `drop_current` are left NaN for the current month,
    simulating data that hasn't been published yet.
    """
    current_period = current_period or pd.Timestamp("2026-06-01")
    drop_current = set(drop_current or [])
    idx = pd.date_range(end=current_period, periods=n_months + 1, freq="MS")

    data = {}
    for col, base in _CALM_BASE.items():
        # small wiggle so rolling std isn't exactly zero
        data[col] = [base + (i % 3) * 0.3 for i in range(len(idx))]
    df = pd.DataFrame(data, index=idx)

    for col in drop_current:
        df.loc[current_period, col] = float("nan")
    return df, current_period


class TestForwardFillsMissingComponents:
    def test_missing_components_are_filled_and_reported(self):
        df, period = _make_history(drop_current=["ipc_yoy_pct", "reserves_usd_mm"])
        result = estimate_current_month(df, as_of=period)
        assert result is not None
        assert set(result["filled_components"]) == {"ipc_yoy_pct", "reserves_usd_mm"}
        assert result["components_real"] == len(VULNERABILITY_COMPONENTS) - 2
        assert result["components_total"] == len(VULNERABILITY_COMPONENTS)
        assert result["date"] == period
        assert isinstance(result["score"], float)

    def test_no_missing_components_yields_empty_fill_list(self):
        df, period = _make_history()
        result = estimate_current_month(df, as_of=period)
        assert result["filled_components"] == []
        assert result["components_real"] == len(VULNERABILITY_COMPONENTS)


class TestOverridesCountAsReal:
    def test_override_value_is_not_reported_as_filled(self):
        df, period = _make_history(drop_current=["dop_usd"])
        result = estimate_current_month(df, as_of=period, overrides={"dop_usd": 61.2})
        assert "dop_usd" not in result["filled_components"]
        assert result["components_real"] == len(VULNERABILITY_COMPONENTS)

    def test_override_for_already_present_column_is_ignored_by_fill_logic(self):
        # overrides only matters when the column would otherwise be missing;
        # this just confirms supplying one doesn't break the normal path.
        df, period = _make_history()
        result = estimate_current_month(df, as_of=period, overrides={"dop_usd": 999.0})
        assert result["filled_components"] == []


class TestRefusesToFabricate:
    def test_returns_none_when_no_row_for_current_month(self):
        df, period = _make_history()
        df = df.drop(index=period)
        assert estimate_current_month(df, as_of=period) is None

    def test_returns_none_when_every_component_would_be_filled(self):
        df, period = _make_history(drop_current=list(VULNERABILITY_COMPONENTS.keys()))
        assert estimate_current_month(df, as_of=period) is None

    def test_empty_dataframe_returns_none(self):
        assert estimate_current_month(pd.DataFrame()) is None


class TestDoesNotMutateInput:
    def test_caller_dataframe_is_unchanged(self):
        df, period = _make_history(drop_current=["UMCSENT"])
        before = df.copy()
        estimate_current_month(df, as_of=period)
        pd.testing.assert_frame_equal(df, before)
