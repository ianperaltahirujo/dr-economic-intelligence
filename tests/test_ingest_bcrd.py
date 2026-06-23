"""
Tests for pipeline/ingest_bcrd.py's load_exchange_rate_mtd().

This is the one place the pipeline computes its own monthly average from
daily rates, instead of using BCRD's own official 'PromMensual' figure --
specifically because BCRD only publishes that monthly figure once the
month closes, and the dashboard needs an honest reading for the current,
still-open month. These tests use a small synthetic 'Diaria'-shaped
workbook rather than the real cached file, so they don't depend on
whatever happens to be in data/raw/ on a given day.

Run with:
    pytest tests/test_ingest_bcrd.py -v
"""

import sys
from pathlib import Path

import openpyxl
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from pipeline.ingest_bcrd import load_exchange_rate_mtd


def _write_diaria_fixture(path, rows):
    """rows: list of (year, month_abbr_es, day, compra, venta)."""
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Diaria"
    ws.append(["Tasas de Cambio del dólar de Referencia del Mercado Spot"])
    ws.append([])
    ws.append(["Año", "Mes", "Día", "Compra", "Venta"])
    for row in rows:
        ws.append(list(row))
    wb.save(path)


class TestMonthToDateAverage:
    def test_averages_only_rows_in_the_target_month(self, tmp_path):
        path = tmp_path / "fx.xlsx"
        _write_diaria_fixture(path, [
            (2026, "May", 30, 58.0, 58.5),   # prior month, excluded
            (2026, "Jun", 1, 58.0, 58.6),
            (2026, "Jun", 2, 58.2, 58.8),
            (2026, "Jun", 3, 58.4, 59.0),
        ])
        avg = load_exchange_rate_mtd(str(path), as_of=pd.Timestamp("2026-06-15"))
        assert avg == pytest.approx((58.6 + 58.8 + 59.0) / 3)

    def test_returns_none_when_target_month_has_no_rows(self, tmp_path):
        path = tmp_path / "fx.xlsx"
        _write_diaria_fixture(path, [(2026, "May", 30, 58.0, 58.5)])
        avg = load_exchange_rate_mtd(str(path), as_of=pd.Timestamp("2026-06-15"))
        assert avg is None

    def test_returns_none_for_missing_sheet(self, tmp_path):
        path = tmp_path / "fx.xlsx"
        wb = openpyxl.Workbook()
        wb.active.title = "SomethingElse"
        wb.save(path)
        avg = load_exchange_rate_mtd(str(path), as_of=pd.Timestamp("2026-06-15"))
        assert avg is None

    def test_returns_none_for_missing_file(self, tmp_path):
        avg = load_exchange_rate_mtd(str(tmp_path / "does_not_exist.xlsx"),
                                      as_of=pd.Timestamp("2026-06-15"))
        assert avg is None

    def test_skips_rows_with_blank_venta(self, tmp_path):
        path = tmp_path / "fx.xlsx"
        _write_diaria_fixture(path, [
            (2026, "Jun", 1, 58.0, 58.6),
            (2026, "Jun", 2, 58.2, None),
            (2026, "Jun", 3, 58.4, 59.0),
        ])
        avg = load_exchange_rate_mtd(str(path), as_of=pd.Timestamp("2026-06-15"))
        assert avg == pytest.approx((58.6 + 59.0) / 2)
