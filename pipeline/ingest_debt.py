"""
DR Economic Intelligence - Public Debt Ingestion
Fetches consolidated public debt data from BCRD CDN.

Source:
    Deuda Publica Consolidada Por Fuente de Financiamiento Trimestral
    cdn.bancentral.gov.do/documents/estadisticas/sector-externo/documents/
        Deuda_Consolidada_Por_Fuente_Trimestral.xlsx

Sheets:
    'Fuente (US$)'   -- Millions of USD, quarterly 2013-present
    'Fuente (%PIB)'  -- Same as % of GDP (also contains GDP in USD)

Indicators extracted:
    debt_total_usd_mm     -- Total consolidated public debt (USD millions)
    debt_external_usd_mm  -- External debt component (USD millions)
    debt_internal_usd_mm  -- Net internal debt component (USD millions)
    debt_total_pct_gdp    -- Total debt as % of GDP
    debt_external_pct_gdp -- External debt as % of GDP
    gdp_usd_mm            -- GDP in USD millions (from %PIB sheet)

Frequency: Quarterly, forward-filled to monthly for pipeline alignment.
Latest available: Q1 2026 (Mar-26). Future quarters are zeros -- excluded.

Usage:
    from pipeline.ingest_debt import load_debt_all
    df = load_debt_all()
"""

import io
from pathlib import Path

import numpy as np
import pandas as pd
import requests

DEBT_URL = (
    "https://cdn.bancentral.gov.do/documents/estadisticas/sector-externo"
    "/documents/Deuda_Consolidada_Por_Fuente_Trimestral.xlsx"
)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/111.0.0.0 Safari/537.36"
    )
}

# Spanish quarter-end month names -> (month_number, quarter_label)
QUARTER_MONTHS = {
    "mar": 3, "jun": 6, "sep": 9, "dic": 12,
}


def _parse_quarter_dates(header_row: pd.Series) -> list:
    """
    Parse a row of quarter labels like 'Mar-13', 'Jun-13', etc.
    Returns list of (col_index, pd.Timestamp) tuples for valid quarters only.
    Excludes future placeholder zeros (Jun-26 onward currently unpublished).
    """
    dates = []
    for col_idx, val in enumerate(header_row):
        if pd.isna(val):
            continue
        s = str(val).strip().lower()
        # Expected format: 'mar-13', 'jun-26', etc.
        parts = s.split("-")
        if len(parts) != 2:
            continue
        month_str, year_str = parts
        month_num = QUARTER_MONTHS.get(month_str)
        if month_num is None:
            continue
        try:
            year = int(year_str)
            year = year + 2000 if year < 100 else year
        except ValueError:
            continue
        dates.append((col_idx, pd.Timestamp(year=year, month=month_num, day=1)))
    return dates


def _extract_row(raw: pd.DataFrame, row_idx: int, date_cols: list) -> pd.Series:
    """Extract numeric values from a specific row at the given column indices."""
    row = raw.iloc[row_idx]
    result = {}
    for col_idx, date in date_cols:
        try:
            val = float(row.iloc[col_idx])
            # Exclude zeros -- future unpublished quarters
            if val == 0.0:
                continue
            result[date] = val
        except (ValueError, TypeError):
            continue
    return pd.Series(result)


def load_debt_usd(path: str = None) -> pd.DataFrame:
    """
    Load debt in USD millions from 'Fuente (US$)' sheet.

    Returns DataFrame with DatetimeIndex (quarter-end dates), columns:
        debt_total_usd_mm     -- Total consolidated public debt
        debt_external_usd_mm  -- External debt (A)
        debt_internal_usd_mm  -- Net internal debt (B)
    """
    raw_bytes = _fetch_bytes(path)
    if raw_bytes is None:
        return pd.DataFrame()

    try:
        raw = pd.read_excel(io.BytesIO(raw_bytes), sheet_name="Fuente (US$)", header=None)
    except Exception as e:
        print(f"  ERROR reading debt USD sheet: {e}")
        return pd.DataFrame()

    # Row 9 (0-indexed) contains quarter labels: Mar-13, Jun-13, ...
    date_cols = _parse_quarter_dates(raw.iloc[9])
    if not date_cols:
        print("  ERROR: Could not parse quarter dates from debt file")
        return pd.DataFrame()

    # Row 10: DEUDA PUBLICA CONSOLIDADA (A+B) -- total
    # Row 12: A. DEUDA EXTERNA -- external
    # Row 16: B. DEUDA INTERNA NETA -- internal
    total    = _extract_row(raw, 10, date_cols)
    external = _extract_row(raw, 12, date_cols)
    internal = _extract_row(raw, 16, date_cols)

    df = pd.DataFrame({
        "debt_total_usd_mm":    total,
        "debt_external_usd_mm": external,
        "debt_internal_usd_mm": internal,
    }).sort_index()

    df = df[~df.index.duplicated(keep="last")]
    df = df.dropna(how="all")

    return df


def load_debt_pct_gdp(path: str = None) -> pd.DataFrame:
    """
    Load debt as % of GDP and GDP in USD from 'Fuente (%PIB)' sheet.

    Returns DataFrame with DatetimeIndex (quarter-end dates), columns:
        debt_total_pct_gdp    -- Total debt as % of GDP (decimal, e.g. 0.58)
        debt_external_pct_gdp -- External debt as % of GDP
        gdp_usd_mm            -- Nominal GDP in USD millions
    """
    raw_bytes = _fetch_bytes(path)
    if raw_bytes is None:
        return pd.DataFrame()

    try:
        raw = pd.read_excel(io.BytesIO(raw_bytes), sheet_name="Fuente (%PIB)", header=None)
    except Exception as e:
        print(f"  ERROR reading debt %PIB sheet: {e}")
        return pd.DataFrame()

    date_cols = _parse_quarter_dates(raw.iloc[9])
    if not date_cols:
        print("  ERROR: Could not parse quarter dates from %PIB sheet")
        return pd.DataFrame()

    # Row 10: total debt % GDP
    # Row 12: external debt % GDP
    # Row 21: GDP in USD millions
    total_pct    = _extract_row(raw, 10, date_cols)
    external_pct = _extract_row(raw, 12, date_cols)
    gdp          = _extract_row(raw, 21, date_cols)

    df = pd.DataFrame({
        "debt_total_pct_gdp":    total_pct,
        "debt_external_pct_gdp": external_pct,
        "gdp_usd_mm":            gdp,
    }).sort_index()

    df = df[~df.index.duplicated(keep="last")]
    df = df.dropna(how="all")

    return df


def load_debt_all(path: str = None, monthly: bool = True) -> pd.DataFrame:
    """
    Load and merge all debt indicators.

    Args:
        path:    Optional local file path (fetches from CDN if None)
        monthly: If True, forward-fill quarterly data to monthly frequency

    Returns:
        DataFrame with columns:
            debt_total_usd_mm, debt_external_usd_mm, debt_internal_usd_mm,
            debt_total_pct_gdp, debt_external_pct_gdp, gdp_usd_mm
    """
    usd = load_debt_usd(path)
    pct = load_debt_pct_gdp(path)

    if usd.empty and pct.empty:
        print("  ERROR: No debt data loaded.")
        return pd.DataFrame()

    df = usd.join(pct, how="outer") if not usd.empty and not pct.empty else (usd if not usd.empty else pct)
    df = df.sort_index()

    latest = df.index.max()
    earliest = df.index.min()

    if monthly:
        today_floor = pd.Timestamp.today().to_period("M").to_timestamp()
        monthly_idx = pd.date_range(start=earliest, end=min(latest, today_floor), freq="MS")
        df = df.reindex(monthly_idx).ffill()
        df.index.name = "date"

    print(f"  Debt data: {len(df)} {'months' if monthly else 'quarters'} "
          f"({earliest.strftime('%Y-Q%q') if not monthly else earliest.date()} "
          f"to {latest.date()})")
    print(f"  Latest total debt: USD {df['debt_total_usd_mm'].iloc[-1]:,.0f}M "
          f"({df['debt_total_pct_gdp'].iloc[-1]*100:.1f}% of GDP)")

    return df


# Cache for raw bytes so we only fetch once per session
_raw_bytes_cache: bytes = None


def _fetch_bytes(path: str = None) -> bytes:
    """Fetch raw Excel bytes from local path or CDN, with session cache."""
    global _raw_bytes_cache

    if path and Path(path).exists():
        with open(path, "rb") as f:
            return f.read()

    if _raw_bytes_cache is not None:
        return _raw_bytes_cache

    try:
        r = requests.get(DEBT_URL, headers=HEADERS, timeout=30)
        r.raise_for_status()
        _raw_bytes_cache = r.content
        return _raw_bytes_cache
    except Exception as e:
        print(f"  ERROR fetching debt file: {e}")
        return None


# -- CLI --
if __name__ == "__main__":
    print("Loading BCRD consolidated debt data...\n")
    df = load_debt_all()

    if df.empty:
        print("No data loaded.")
    else:
        print(f"\nShape: {df.shape}")
        print(f"Columns: {list(df.columns)}")
        print(f"\nLast 6 months:")
        print(df.tail(6).to_string())