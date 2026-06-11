"""
DR Economic Intelligence - Context Indicators Ingestion
Fetches display-only context indicators that enrich the weekly report
without contributing to the vulnerability score.

Indicators:
    Gas prices (MICM)          — weekly, averaged to monthly
    Tourism income (BCRD)      — monthly spending by foreign visitors
    Tourism fiscal revenue      — monthly tax revenue from tourism
    National debt % GDP (FRED)  — annual IMF series DOMGGXWDGGDP

These are display-only. They appear on the website and Excel workbook
but do NOT feed into VULNERABILITY_COMPONENTS or the composite score.

Usage:
    from pipeline.ingest_context import load_context_all
    ctx = load_context_all()
"""

import os
import io
from pathlib import Path

import numpy as np
import pandas as pd
import requests
from dotenv import load_dotenv

load_dotenv()

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/111.0.0.0 Safari/537.36"
    )
}

SPANISH_MONTHS = {
    "enero": 1, "febrero": 2, "marzo": 3, "abril": 4,
    "mayo": 5, "junio": 6, "julio": 7, "agosto": 8,
    "septiembre": 9, "octubre": 10, "noviembre": 11, "diciembre": 12,
    # Short forms
    "ene": 1, "feb": 2, "mar": 3, "abr": 4,
    "may": 5, "jun": 6, "jul": 7, "ago": 8,
    "sep": 9, "oct": 10, "nov": 11, "dic": 12,
}


# ── Gas prices (MICM) ─────────────────────────────────────────────────────────

MICM_GAS_URL = (
    "https://micm.gob.do/transparencias/datos-abiertos/"
    "precios-de-combustibles/precios-de-combustibles-2010-2026.csv"
)


def load_gas_prices(path: str = None) -> pd.DataFrame:
    """
    Load weekly fuel prices from MICM and average to monthly.

    Source: MICM open data CSV — semicolon delimited, weekly rows since 2010.
    Columns of interest: GASOLINA PREMIUM, GASOLINA REGULAR, GASOIL REGULAR,
                         GASOIL OPTIMO, GLP

    Returns:
        DataFrame with DatetimeIndex (month-start), columns:
            gas_premium_dop    — Gasolina Premium (DOP/gallon)
            gas_regular_dop    — Gasolina Regular (DOP/gallon)
            gasoil_regular_dop — Gasoil Regular (DOP/gallon)
            glp_dop            — GLP (DOP/gallon)
    """
    if path and Path(path).exists():
        # Read from local cached file
        with open(path, "rb") as f:
            raw_bytes = f.read()
    else:
        print("  Fetching gas prices from MICM...")
        try:
            r = requests.get(MICM_GAS_URL, headers=HEADERS, timeout=30)
            r.raise_for_status()
            raw_bytes = r.content
        except Exception as e:
            print(f"  ERROR fetching gas prices: {e}")
            return pd.DataFrame()

    # Try latin-1 encoding first (common for DR government files)
    for enc in ["latin-1", "utf-8", "cp1252"]:
        try:
            text = raw_bytes.decode(enc)
            break
        except UnicodeDecodeError:
            continue
    else:
        print("  ERROR: Could not decode gas prices CSV")
        return pd.DataFrame()

    try:
        df = pd.read_csv(io.StringIO(text), sep=";", decimal=",")
    except Exception:
        try:
            df = pd.read_csv(io.StringIO(text), sep=";")
        except Exception as e:
            print(f"  ERROR parsing gas prices CSV: {e}")
            return pd.DataFrame()

    # Normalize column names — strip whitespace and accents
    df.columns = (
        df.columns.str.strip()
        .str.upper()
        .str.replace("Ñ", "N")
        .str.replace("Á", "A").str.replace("É", "E")
        .str.replace("Í", "I").str.replace("Ó", "O").str.replace("Ú", "U")
    )

    # Build date from AÑO (or AO) and MES columns
    year_col = next((c for c in df.columns if c in ["AO", "ANO", "AÑO", "YEAR"]), None)
    mes_col  = next((c for c in df.columns if c in ["MES", "MONTH", "MES "]), None)
    dia_col  = next((c for c in df.columns if "DIA DESDE" in c or "DIA_DESDE" in c), None)

    if year_col is None or mes_col is None:
        print(f"  WARNING: Could not find year/month columns. Got: {list(df.columns[:8])}")
        return pd.DataFrame()

    # Map Spanish month names to numbers if needed
    def parse_month(val):
        if pd.isna(val):
            return None
        try:
            return int(val)
        except (ValueError, TypeError):
            return SPANISH_MONTHS.get(str(val).strip().lower())

    df["_month_num"] = df[mes_col].apply(parse_month)
    df["_year"] = pd.to_numeric(df[year_col], errors="coerce")
    df = df.dropna(subset=["_month_num", "_year"])

    df["date"] = df.apply(
        lambda r: pd.Timestamp(year=int(r["_year"]), month=int(r["_month_num"]), day=1),
        axis=1
    )

    # Column name mapping — try common variants
    col_map = {
        "gas_premium_dop":    ["GASOLINA PREMIUM", "GAS PREMIUM", "PREMIUM"],
        "gas_regular_dop":    ["GASOLINA REGULAR", "GAS REGULAR", "REGULAR"],
        "gasoil_regular_dop": ["GASOIL REGULAR", "GASOIL REG"],
        "glp_dop":            ["GLP", "GLP 2", "GAS LICUADO"],
    }

    result_cols = {"date": df["date"]}
    for out_col, candidates in col_map.items():
        found = next((c for c in candidates if c in df.columns), None)
        if found:
            result_cols[out_col] = pd.to_numeric(df[found], errors="coerce")
        else:
            # Try partial match
            partial = next((c for c in df.columns if any(cand in c for cand in candidates)), None)
            if partial:
                result_cols[out_col] = pd.to_numeric(df[partial], errors="coerce")

    result = pd.DataFrame(result_cols).set_index("date")

    # Average weekly readings to monthly
    result = result.resample("MS").mean()
    result = result.sort_index()
    result = result[~result.index.duplicated(keep="last")]

    if not result.empty:
        print(f"  Gas prices: {len(result)} months "
              f"({result.index.min().date()} to {result.index.max().date()})")

    return result


# ── Tourism income (BCRD) ─────────────────────────────────────────────────────

def load_tourism_spending(path: str = "data/raw/turismo_gasto_estadia.xls") -> pd.DataFrame:
    """
    Parse tourist daily spending and average stay by foreign non-resident visitors.
    (turismo_gasto_estadia.xls)

    Actual format: Quarterly data (t1-t4) and annual averages.
    Col 0 = period (year int or 't1'-'t4'), Col 1 = daily spending (USD), Col 2 = avg stay (nights)
    Annual rows give the yearly average; quarterly rows give sub-annual detail.

    We use annual figures and forward-fill to monthly frequency.
    Note: daily spending (USD/day) x avg stay (nights) = total spend per visitor.

    Returns:
        DataFrame with DatetimeIndex (month-start), columns:
            tourism_daily_spend_usd  — avg daily spending per foreign visitor (USD)
            tourism_avg_stay_nights  — avg length of stay (nights)
    """
    if not Path(path).exists():
        print(f"  WARNING: {path} not found, skipping tourism spending.")
        return pd.DataFrame()

    try:
        raw = pd.read_excel(path, sheet_name="1993 - 2026", header=None)
    except Exception as e:
        print(f"  ERROR reading tourism spending file: {e}")
        return pd.DataFrame()

    records = []
    current_year = None

    for idx, row in raw.iterrows():
        cell_0 = str(row.iloc[0]).strip() if pd.notna(row.iloc[0]) else ""

        # Detect year row — appears as plain integer e.g. 1993, 2025
        try:
            year_val = int(float(cell_0))
            if 1990 <= year_val <= 2030:
                current_year = year_val
                # The annual average value is on the same row as the year
                spending = row.iloc[1]
                avg_stay = row.iloc[2]
                if pd.notna(spending) and current_year is not None:
                    date = pd.Timestamp(year=current_year, month=1, day=1)
                    records.append({
                        "date":                  date,
                        "tourism_daily_spend_usd": float(spending),
                        "tourism_avg_stay_nights": float(avg_stay) if pd.notna(avg_stay) else np.nan,
                    })
                continue
        except (ValueError, TypeError):
            pass

        # Skip quarterly sub-rows (t1, t2, t3, t4) and header rows
        # We only use annual averages for simplicity

    if not records:
        print("  WARNING: No records parsed from tourism spending file.")
        return pd.DataFrame()

    # Build annual series
    df_annual = pd.DataFrame(records).set_index("date").sort_index()
    df_annual = df_annual[~df_annual.index.duplicated(keep="last")]

    # Forward-fill annual values to monthly frequency
    monthly_idx = pd.date_range(
        start=df_annual.index.min(),
        end=df_annual.index.max() + pd.DateOffset(months=11),
        freq="MS"
    )
    df_monthly = df_annual.reindex(monthly_idx).ffill()

    print(f"  Tourism spending: {len(df_monthly)} months "
          f"({df_monthly.index.min().date()} to {df_monthly.index.max().date()})")
    return df_monthly


def load_tourism_fiscal(
    path_hist:  str = "data/raw/turismo_fiscal.xls",
    path_2026:  str = "data/raw/turismo_fiscal_mensual.xlsx",
) -> pd.DataFrame:
    """
    Parse fiscal revenue from tourism (tax receipts from the DR treasury).

    Historical file (turismo_fiscal.xls):
        21 sheets, each covering a fiscal year range e.g. '2024-2025'.
        Wide format: years as columns (cols 2+), TOTAL row identifiable by label.
        Units vary: early sheets in miles de RD$, later in RD$.

    Current year file (turismo_fiscal_mensual.xlsx):
        Sheet 'Ene-Mar 2026'. Wide: months as columns (Enero=col2, Febrero=col3, Marzo=col4).
        TOTAL row is at row index 16 (0-based).
        Units: RD$ (not thousands).

    Returns:
        DataFrame with DatetimeIndex, column:
            tourism_fiscal_rdm  — monthly total fiscal revenue from tourism (RD$ millions)
    """
    records = []

    # ── Historical file: annual data from each sheet ──
    if Path(path_hist).exists():
        try:
            xl = pd.ExcelFile(path_hist)
            for sheet in xl.sheet_names:
                try:
                    raw = pd.read_excel(path_hist, sheet_name=sheet, header=None)

                    # Find TOTAL row — look for cell containing "TOTAL" (case-insensitive)
                    total_row_idx = None
                    for i, row in raw.iterrows():
                        cell = str(row.iloc[0]).strip().upper()
                        if cell == "TOTAL":
                            total_row_idx = i
                            break

                    if total_row_idx is None:
                        continue

                    total_row = raw.iloc[total_row_idx]

                    # Find year columns — years appear as floats like 2024.0 in row 3 or 5
                    # Look for the header row with year values
                    year_row = None
                    for i in range(min(8, len(raw))):
                        candidate = raw.iloc[i]
                        years_found = []
                        for val in candidate:
                            try:
                                y = int(float(str(val)))
                                if 1995 <= y <= 2030:
                                    years_found.append((candidate.index.get_loc(candidate[candidate == val].index[0]) if hasattr(candidate.index, 'get_loc') else list(candidate).index(val), y))
                            except (ValueError, TypeError):
                                pass
                        if years_found:
                            year_row = (i, years_found)
                            break

                    if year_row is None:
                        # Try simpler: look for year values in cols 2+
                        header = raw.iloc[3]
                        year_map = {}
                        for col_idx, val in enumerate(header):
                            try:
                                y = int(float(str(val)))
                                if 1995 <= y <= 2030:
                                    year_map[col_idx] = y
                            except (ValueError, TypeError):
                                pass
                    else:
                        year_map = {}
                        header = raw.iloc[year_row[0]]
                        for col_idx, val in enumerate(header):
                            try:
                                y = int(float(str(val)))
                                if 1995 <= y <= 2030:
                                    year_map[col_idx] = y
                            except (ValueError, TypeError):
                                pass

                    # Determine unit scaling
                    # Early sheets say "miles de RD$", later say "RD$" or "En RD$"
                    is_miles = any(
                        "miles" in str(raw.iloc[i, 0]).lower()
                        for i in range(min(5, len(raw)))
                        if pd.notna(raw.iloc[i, 0])
                    )
                    scale = 1_000 if is_miles else 1  # convert to RD$

                    for col_idx, year in year_map.items():
                        val = total_row.iloc[col_idx]
                        if pd.isna(val):
                            continue
                        try:
                            # Convert to RD$ millions
                            rdm = float(val) * scale / 1_000_000
                            date = pd.Timestamp(year=year, month=1, day=1)
                            records.append({"date": date, "tourism_fiscal_rdm": rdm})
                        except (ValueError, TypeError):
                            continue

                except Exception:
                    continue

        except Exception as e:
            print(f"  ERROR reading historical fiscal file: {e}")

    # ── 2026 file: monthly data, wide format ──
    if Path(path_2026).exists():
        try:
            raw = pd.read_excel(path_2026, sheet_name="Ene-Mar 2026", header=None)

            # TOTAL is at row 16, months are cols 2 (Enero), 3 (Febrero), 4 (Marzo)
            total_row = raw.iloc[16]

            month_cols = {2: 1, 3: 2, 4: 3}  # col_idx -> month_number
            year = 2026

            for col_idx, month_num in month_cols.items():
                val = total_row.iloc[col_idx]
                if pd.isna(val):
                    continue
                try:
                    rdm = float(val) / 1_000_000
                    date = pd.Timestamp(year=year, month=month_num, day=1)
                    records.append({"date": date, "tourism_fiscal_rdm": rdm})
                except (ValueError, TypeError):
                    continue

        except Exception as e:
            print(f"  ERROR reading 2026 fiscal file: {e}")

    if not records:
        print("  WARNING: No tourism fiscal data loaded.")
        return pd.DataFrame()

    df = pd.DataFrame(records)
    df["date"] = pd.to_datetime(df["date"])

    # Deduplicate BEFORE any reindex -- keep last (most recent sheet wins for same year)
    df = df.sort_values("date").drop_duplicates(subset="date", keep="last")
    df = df.set_index("date").sort_index()

    # Forward-fill annual records to monthly frequency
    monthly_idx = pd.date_range(
        start=df.index.min(),
        end=df.index.max() + pd.DateOffset(months=11),
        freq="MS"
    )
    df = df.reindex(monthly_idx).ffill()
    df.index.name = "date"

    print(f"  Tourism fiscal revenue: {len(df)} rows "
          f"({df.index.min().date()} to {df.index.max().date()})")
    return df


# ── National debt (FRED) ──────────────────────────────────────────────────────

DEBT_FRED_URL = (
    "https://fred.stlouisfed.org/graph/fredgraph.csv"
    "?id=DOMGGXWDGGDP"
    "&cosd=1997-01-01&coed=2031-01-01"
    "&vintage_date=2026-06-11&revision_date=2026-06-11"
)


def load_national_debt() -> pd.DataFrame:
    """
    Load Dominican Republic general government debt (% of GDP) from FRED.
    Series: DOMGGXWDGGDP (IMF World Economic Outlook)
    Frequency: Annual. Includes IMF projections to 2031.

    Returns:
        DataFrame with DatetimeIndex (year-start), column:
            debt_pct_gdp — general government gross debt as % of GDP
    """
    api_key = os.getenv("FRED_API_KEY", "")
    if api_key:
        url = f"https://api.stlouisfed.org/fred/series/observations?series_id=DOMGGXWDGGDP&api_key={api_key}&file_type=json"
        try:
            r = requests.get(url, timeout=30)
            r.raise_for_status()
            data = r.json()
            observations = data.get("observations", [])
            records = []
            for obs in observations:
                if obs["value"] == ".":
                    continue
                records.append({
                    "date":         pd.Timestamp(obs["date"]),
                    "debt_pct_gdp": float(obs["value"])
                })
            if records:
                df = pd.DataFrame(records).set_index("date").sort_index()
                print(f"  National debt: {len(df)} years "
                      f"({df.index.min().year} to {df.index.max().year})")
                return df
        except Exception as e:
            print(f"  FRED API failed ({e}), trying direct CSV...")

    # Fallback: direct CSV download (no API key needed)
    try:
        r = requests.get(DEBT_FRED_URL, headers=HEADERS, timeout=30)
        r.raise_for_status()
        df = pd.read_csv(io.StringIO(r.text))
        df.columns = ["date", "debt_pct_gdp"]
        df["date"] = pd.to_datetime(df["date"])
        df = df[df["debt_pct_gdp"] != "."]
        df["debt_pct_gdp"] = pd.to_numeric(df["debt_pct_gdp"], errors="coerce")
        df = df.dropna().set_index("date").sort_index()
        print(f"  National debt: {len(df)} years "
              f"({df.index.min().year} to {df.index.max().year})")
        return df
    except Exception as e:
        print(f"  ERROR loading national debt: {e}")
        return pd.DataFrame()


# ── Unified loader ────────────────────────────────────────────────────────────

def load_context_all(data_dir: str = "data/raw") -> dict:
    """
    Load all context indicators.

    Returns dict with keys:
        'gas'           — monthly gas prices DataFrame
        'tourism_spend' — monthly tourism spending DataFrame
        'tourism_fiscal'— monthly tourism fiscal revenue DataFrame
        'debt'          — annual national debt DataFrame

    All DataFrames have DatetimeIndex. Missing files return empty DataFrames
    gracefully — context indicators never crash the pipeline.
    """
    print("\nLoading context indicators...")

    gas = pd.DataFrame()
    try:
        gas_path = Path(data_dir) / "precios-combustibles-2010-2026.csv"
        gas = load_gas_prices(str(gas_path) if gas_path.exists() else None)
    except Exception as e:
        print(f"  ERROR loading gas prices: {e}")

    tourism_spend = pd.DataFrame()
    try:
        tourism_spend = load_tourism_spending(
            str(Path(data_dir) / "turismo_gasto_estadia.xls")
        )
    except Exception as e:
        print(f"  ERROR loading tourism spending: {e}")

    tourism_fiscal = pd.DataFrame()
    try:
        tourism_fiscal = load_tourism_fiscal(
            path_hist = str(Path(data_dir) / "turismo_fiscal.xls"),
            path_2026 = str(Path(data_dir) / "turismo_fiscal_mensual.xlsx"),
        )
    except Exception as e:
        print(f"  ERROR loading tourism fiscal: {e}")

    debt = pd.DataFrame()
    try:
        debt = load_national_debt()
    except Exception as e:
        print(f"  ERROR loading national debt: {e}")

    return {
        "gas":            gas,
        "tourism_spend":  tourism_spend,
        "tourism_fiscal": tourism_fiscal,
        "debt":           debt,
    }


# ── CLI ───────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    ctx = load_context_all()

    for key, df in ctx.items():
        if df.empty:
            print(f"\n{key}: NO DATA")
        else:
            print(f"\n{key}: {df.shape}")
            print(df.tail(3).to_string())   