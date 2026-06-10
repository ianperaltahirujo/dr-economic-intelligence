"""
BCRD Data Ingestion Module
Parses BCRD Excel files into clean, monthly pandas DataFrames.
Each function returns a DataFrame with a DatetimeIndex and one or more value columns.

Usage:
    from pipeline.ingest_bcrd import load_remesas, load_imae, load_exchange_rate, load_ipc, load_tourism_air
"""

import pandas as pd
import numpy as np
from pathlib import Path

# Spanish month name to number mapping
MONTH_MAP_LONG = {
    'Enero': 1, 'Febrero': 2, 'Marzo': 3, 'Abril': 4,
    'Mayo': 5, 'Junio': 6, 'Julio': 7, 'Agosto': 8,
    'Septiembre': 9, 'Octubre': 10, 'Noviembre': 11, 'Diciembre': 12
}

MONTH_MAP_SHORT = {
    'Ene': 1, 'Feb': 2, 'Mar': 3, 'Abr': 4,
    'May': 5, 'Jun': 6, 'Jul': 7, 'Ago': 8,
    'Sep': 9, 'Oct': 10, 'Nov': 11, 'Dic': 12
}


def load_remesas(path: str) -> pd.DataFrame:
    """
    Parse Remesas familiares mensual (Remesas_6.xlsx).

    Format: Wide table. Row 7 = header (years as columns).
    Rows 8-19 = months (Enero-Diciembre).
    Values are in USD (not millions despite header text).
    We divide by 1,000,000 to convert to millions USD.

    Returns:
        DataFrame with DatetimeIndex, column 'remesas_usd_mm' (millions USD)
    """
    raw = pd.read_excel(path, sheet_name='Total', header=None)

    year_row = raw.iloc[7, 1:]
    month_col = raw.iloc[8:20, 0]

    data_block = raw.iloc[8:20, 1:]
    data_block.columns = year_row.values
    data_block.index = month_col.values

    records = []
    for year in data_block.columns:
        try:
            year_int = int(str(year).replace('*', '').strip().split('.')[0])
        except (ValueError, AttributeError):
            continue

        for month_name, value in data_block[year].items():
            month_num = MONTH_MAP_LONG.get(str(month_name).strip())
            if month_num is None or pd.isna(value):
                continue
            date = pd.Timestamp(year=year_int, month=month_num, day=1)
            records.append({'date': date, 'remesas_usd_mm': float(value) / 1_000_000})

    df = pd.DataFrame(records).set_index('date').sort_index()
    df = df[~df.index.duplicated(keep='last')]
    return df


def load_imae(path: str) -> pd.DataFrame:
    """
    Parse Indicador Mensual de Actividad Economica (imae_2018.xlsx).

    Format: Two structural sections in the same sheet:
    - Older section (2007-2022): Year appears as "Promedio YYYY" in col 0
    - Newer section (2023+): Year appears as plain integer in col 0
    Col 1 = month name. Col 2 = Serie Original index value.

    Returns:
        DataFrame with DatetimeIndex, column 'imae_index' (chained volume index, 2018=100)
    """
    import re
    raw = pd.read_excel(path, sheet_name='IMAE', header=None)

    records = []
    current_year = None

    for idx, row in raw.iterrows():
        cell_0 = str(row.iloc[0]).strip() if pd.notna(row.iloc[0]) else ''

        if cell_0.isdigit() and 2000 <= int(cell_0) <= 2030:
            current_year = int(cell_0)
            continue

        match = re.search(r'Promedio\s+(\d{4})', cell_0, re.IGNORECASE)
        if match:
            current_year = int(match.group(1))
            continue

        month_name = str(row.iloc[1]).strip() if pd.notna(row.iloc[1]) else ''
        month_num = MONTH_MAP_LONG.get(month_name)

        if month_num is None or current_year is None:
            continue

        value = row.iloc[2]
        if pd.isna(value):
            continue

        try:
            date = pd.Timestamp(year=current_year, month=month_num, day=1)
            records.append({'date': date, 'imae_index': float(value)})
        except (ValueError, OverflowError):
            continue

    df = pd.DataFrame(records).set_index('date').sort_index()
    df = df[~df.index.duplicated(keep='last')]
    return df


def load_exchange_rate(path: str) -> pd.DataFrame:
    """
    Parse Tasa de Cambio DOP/USD (TASA_DOLAR_REFERENCIA_MC.xlsx).

    Uses 'PromMensual' sheet (monthly average).
    Format: Ano | Mes | Compra | Venta (3 header rows).
    We use 'Venta' (sell rate) as the standard reference.

    Returns:
        DataFrame with DatetimeIndex, column 'dop_usd' (RD$ per US$1, sell rate)
    """
    raw = pd.read_excel(path, sheet_name='PromMensual', header=None)

    data = raw.iloc[3:, :4].copy()
    data.columns = ['year', 'month', 'compra', 'venta']

    data['year'] = pd.to_numeric(data['year'], errors='coerce')
    data['year'] = data['year'].ffill()

    records = []
    for _, row in data.iterrows():
        year = row['year']
        month_abbr = str(row['month']).strip()
        month_num = MONTH_MAP_SHORT.get(month_abbr)
        venta = row['venta']

        if pd.isna(year) or month_num is None or pd.isna(venta):
            continue

        try:
            date = pd.Timestamp(year=int(year), month=month_num, day=1)
            records.append({'date': date, 'dop_usd': float(venta)})
        except (ValueError, OverflowError):
            continue

    df = pd.DataFrame(records).set_index('date').sort_index()
    df = df[~df.index.duplicated(keep='last')]
    return df


def load_ipc(path: str) -> pd.DataFrame:
    """
    Parse Indice de Precios al Consumidor (ipc_base_2019-2020.xls).

    Returns:
        DataFrame with DatetimeIndex, columns:
            'ipc_index'      - price level index
            'ipc_mom_pct'    - month-over-month % change
            'ipc_yoy_pct'    - 12-month (year-over-year) % change
    """
    raw = pd.read_excel(path, header=None)

    records = []
    current_year = None

    for idx, row in raw.iterrows():
        cell_0 = row.iloc[0]

        if pd.notna(cell_0):
            try:
                year_val = int(float(str(cell_0).strip()))
                if 1980 <= year_val <= 2030:
                    current_year = year_val
            except (ValueError, OverflowError):
                pass

        month_name = str(row.iloc[1]).strip() if pd.notna(row.iloc[1]) else ''
        month_num = MONTH_MAP_LONG.get(month_name)

        if month_num is None or current_year is None:
            continue

        ipc_index = row.iloc[2]
        ipc_mom = row.iloc[3]
        ipc_yoy = row.iloc[5] if len(row) > 5 else np.nan

        if pd.isna(ipc_index):
            continue

        try:
            date = pd.Timestamp(year=current_year, month=month_num, day=1)
            records.append({
                'date': date,
                'ipc_index': float(ipc_index),
                'ipc_mom_pct': float(ipc_mom) if pd.notna(ipc_mom) else np.nan,
                'ipc_yoy_pct': float(ipc_yoy) if pd.notna(ipc_yoy) else np.nan
            })
        except (ValueError, OverflowError):
            continue

    df = pd.DataFrame(records).set_index('date').sort_index()
    df = df[~df.index.duplicated(keep='last')]
    return df


def load_tourism_air(path: str) -> pd.DataFrame:
    """
    Parse Llegada total de pasajeros no residentes via aerea (lleg_total.xls).

    Returns:
        DataFrame with DatetimeIndex, column 'tourist_arrivals_air' (monthly count)
    """
    raw = pd.read_excel(path, sheet_name='No Residentes 78 - 26', header=None)

    records = []
    current_year = None

    for idx, row in raw.iterrows():
        cell_0 = row.iloc[0]

        if pd.notna(cell_0):
            try:
                year_val = int(float(str(cell_0).strip()))
                if 1970 <= year_val <= 2030:
                    current_year = year_val
                    continue
            except (ValueError, OverflowError):
                pass

        month_name = str(cell_0).strip() if pd.notna(cell_0) else ''
        month_num = MONTH_MAP_LONG.get(month_name)

        if month_num is None or current_year is None:
            continue

        value = row.iloc[1]
        if pd.isna(value):
            continue

        try:
            date = pd.Timestamp(year=current_year, month=month_num, day=1)
            records.append({'date': date, 'tourist_arrivals_air': float(value)})
        except (ValueError, OverflowError):
            continue

    df = pd.DataFrame(records).set_index('date').sort_index()
    df = df[~df.index.duplicated(keep='last')]
    return df


def load_reserves(path: str) -> pd.DataFrame:
    """
    Parse Reservas Internacionales del Banco Central (reservas_internacionales.xlsx).

    Returns:
        DataFrame with DatetimeIndex, column 'reserves_usd_mm' (millions USD, gross)
    """
    raw = pd.read_excel(path, sheet_name='Reservas Mensuales', header=None)

    year_row  = raw.iloc[5, 1:]
    label_row = raw.iloc[7, 1:]

    col_meta = {}
    current_year = None
    for col_idx, (year_val, label_val) in enumerate(
        zip(year_row.values, label_row.values), start=1
    ):
        if pd.notna(year_val):
            try:
                clean = str(year_val).strip().split()[0].rstrip('/')
                current_year = int(float(clean))
            except (ValueError, AttributeError, IndexError):
                pass
        label_str = str(label_val).strip().upper()
        if current_year and label_str in ('BRUTAS', 'BRUTOS'):
            col_meta[col_idx] = current_year

    month_map_upper = {v.upper(): k for v, k in MONTH_MAP_LONG.items()}

    records = []
    for row_idx in range(8, 20):
        row = raw.iloc[row_idx]
        month_name = str(row.iloc[0]).strip().upper()
        month_num = month_map_upper.get(month_name)
        if month_num is None:
            continue

        for col_idx, year_int in col_meta.items():
            value = row.iloc[col_idx]
            if pd.isna(value):
                continue
            try:
                date = pd.Timestamp(year=year_int, month=month_num, day=1)
                records.append({'date': date, 'reserves_usd_mm': float(value)})
            except (ValueError, OverflowError):
                continue

    df = pd.DataFrame(records).set_index('date').sort_index()
    df = df[~df.index.duplicated(keep='last')]
    return df


def load_all(path_or_dir: str = 'data/raw') -> pd.DataFrame:
    """
    Load all BCRD indicators and merge into a single monthly DataFrame.
    Aligns everything to month-start frequency.

    Args:
        path_or_dir: Directory containing the BCRD Excel files.

    Returns:
        Merged monthly DataFrame with all available indicators.
    """
    p = Path(path_or_dir)

    frames = {}

    file_map = {
        'remesas':     ('Remesas_6.xlsx',                load_remesas),
        'imae':        ('imae_2018.xlsx',                load_imae),
        'exchange':    ('TASA_DOLAR_REFERENCIA_MC.xlsx', load_exchange_rate),
        'ipc':         ('ipc_base_2019-2020.xls',        load_ipc),
        'tourism_air': ('lleg_total.xls',                load_tourism_air),
        'reserves':    ('reservas_internacionales.xlsx', load_reserves),
    }

    for key, (filename, loader) in file_map.items():
        filepath = p / filename
        if not filepath.exists():
            print(f"  WARNING: {filename} not found in {path_or_dir}, skipping.")
            continue
        try:
            df = loader(str(filepath))
            df.index = df.index + pd.offsets.MonthBegin(0)
            frames[key] = df
            print(f"  Loaded {key}: {len(df)} rows "
                  f"({df.index.min().date()} to {df.index.max().date()})")
        except Exception as e:
            print(f"  ERROR loading {key}: {e}")

    if not frames:
        raise RuntimeError("No BCRD files loaded. Check data_dir path.")

    merged = pd.concat(frames.values(), axis=1, join='outer', sort=True).sort_index()
    return merged


if __name__ == '__main__':
    print("Testing BCRD ingestion with sample files...")
    import sys
    data_dir = sys.argv[1] if len(sys.argv) > 1 else 'data/raw'
    df = load_all(data_dir)
    print(f"\nMerged shape: {df.shape}")
    print(f"Columns: {list(df.columns)}")
    print(f"Date range: {df.index.min()} to {df.index.max()}")
    print("\nMost recent 3 rows:")
    print(df.tail(3).to_string())