"""
Tests for the `headline` parameter on pipeline/write_excel.py's write_workbook().

`headline` lets a caller (the weekly OneDrive snapshot) render the current
in-progress calendar month's projected score as the workbook's headline,
instead of the last confirmed month in results['scored']. These tests pin
down:

1. Default behavior (headline=None) is unchanged -- still renders the
   confirmed month from results['scored'].
2. Passing headline overrides the Dashboard's date/score to the projected
   month, labeled distinctly from the existing "Avance Estimado" tag.
3. The override never mutates the caller's original results dict.

Run with:
    pytest tests/test_write_excel.py -v
"""

import sys
from pathlib import Path

import openpyxl
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from pipeline.build_vulnerability import VULNERABILITY_COMPONENTS
from pipeline.write_excel import write_workbook


_CALM_VALUES = {
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


def _make_scored(n_months=6, confirmed_date=None):
    confirmed_date = confirmed_date or pd.Timestamp("2026-05-01")
    idx = pd.date_range(end=confirmed_date, periods=n_months, freq="MS")
    data = {"vulnerability_score": [45.0] * n_months, "is_provisional": [False] * n_months}
    for col, val in _CALM_VALUES.items():
        data[col] = [val] * n_months
        data[f"{col}_zscore"] = [0.0] * n_months
    return pd.DataFrame(data, index=idx)


def _make_results(confirmed_date=None):
    confirmed_date = confirmed_date or pd.Timestamp("2026-05-01")
    scored = _make_scored(confirmed_date=confirmed_date)
    return {
        "current_score": 45.0,
        "score_date": confirmed_date,
        "scored": scored,
        "alerts": pd.DataFrame(),
        "tourism_fiscal": pd.DataFrame(),
        "debt_detail": pd.DataFrame(),
    }


def _make_headline(date=None):
    date = date or pd.Timestamp("2026-06-01")
    components = {}
    for col, val in _CALM_VALUES.items():
        components[col] = {"value": val, "zscore": 0.0, "is_filled": col == "tourism_daily_spend_usd", "mom": None}
    return {
        "date": date,
        "score": 52.3,
        "filled_components": ["tourism_daily_spend_usd"],
        "components_real": 11,
        "components_total": 12,
        "components": components,
    }


def _dashboard_rows(path):
    wb = openpyxl.load_workbook(path, data_only=True)
    ws = wb["Dashboard"]
    return {row[1]: row[2] for row in ws.iter_rows(min_row=1, max_row=10, values_only=True) if row[1]}


class TestDefaultBehaviorUnchanged:
    def test_no_headline_shows_confirmed_month(self, tmp_path):
        results = _make_results()
        path = write_workbook(results, path=str(tmp_path / "out.xlsx"))
        rows = _dashboard_rows(path)
        assert rows["Score:"] == 45.0
        assert rows["Fecha:"] == "May 2026"


class TestHeadlineOverride:
    def test_headline_shows_projected_month_and_score(self, tmp_path):
        results = _make_results()
        headline = _make_headline()
        path = write_workbook(results, path=str(tmp_path / "out.xlsx"), headline=headline)
        rows = _dashboard_rows(path)
        assert rows["Score:"] == 52.3
        assert "June 2026" in rows["Fecha:"]
        assert "Estimación del Mes en Curso" in rows["Fecha:"]

    def test_headline_does_not_use_avance_estimado_label(self, tmp_path):
        # The projection gets its own label, distinct from the confirmed-
        # month "Avance Estimado" tag, even though is_provisional is also
        # True under the hood for the synthetic row.
        results = _make_results()
        headline = _make_headline()
        path = write_workbook(results, path=str(tmp_path / "out.xlsx"), headline=headline)
        rows = _dashboard_rows(path)
        assert "Avance Estimado" not in rows["Fecha:"]

    def test_does_not_mutate_caller_results(self, tmp_path):
        results = _make_results()
        original_score_date = results["score_date"]
        original_scored_len = len(results["scored"])
        headline = _make_headline()
        write_workbook(results, path=str(tmp_path / "out.xlsx"), headline=headline)
        assert results["score_date"] == original_score_date
        assert len(results["scored"]) == original_scored_len
        assert "is_current_month_projection" not in results
