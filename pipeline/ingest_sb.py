"""
Superintendencia de Bancos (SB) Data Ingestion Module
Fetches financial system statistics from the SB API v2.

Authentication: Ocp-Apim-Subscription-Key header (loaded from .env)
Base URL: https://apis.sb.gob.do/estadisticas/v2/
Pagination: API returns pages; we loop until HasNext == False in x-pagination header.

Each public function returns a DataFrame with a DatetimeIndex and clean column names.
All period strings are converted to month-start DatetimeIndex to match ingest_bcrd.py.

Usage:
    from pipeline.ingest_sb import load_principales_indicadores, load_sb_all
"""

import json
import os
import time
from urllib.parse import urljoin, urlencode
from dotenv import load_dotenv
import pandas as pd
import requests

load_dotenv()

# ── Auth and base config ──────────────────────────────────────────────────────

BASE_URL = "https://apis.sb.gob.do/estadisticas/v2/"

# The SB API authenticates via a custom header, not a URL parameter.
# The key is stored in .env as SB_API_KEY to avoid committing credentials.
HEADERS = {
    "Ocp-Apim-Subscription-Key": os.getenv("SB_API_KEY", ""),
    # User-Agent is required by the SB API — requests without it get blocked.
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/111.0.0.0 Safari/537.36"
    ),
}

# How many records to request per page. 50000 is effectively "give me everything
# in one page" for most endpoints, which avoids unnecessary pagination loops.
DEFAULT_RECORDS_PER_PAGE = 50_000

# Polite delay between paginated requests to avoid hammering the server.
REQUEST_DELAY_SECONDS = 0.5


# ── Core HTTP helper ──────────────────────────────────────────────────────────

# Maximum number of retries on 500 errors before giving up on an endpoint.
MAX_RETRIES = 3

def _fetch_paginated(endpoint: str, params: dict) -> pd.DataFrame:
    """
    Fetch all pages from a SB API endpoint and return a single merged DataFrame.

    The SB API v2 uses page-based pagination. Each response includes an
    x-pagination header (JSON string) with HasNext (bool) and TotalPages (int).
    We start at page 1 and keep incrementing until HasNext is False.

    500 errors are retried up to MAX_RETRIES times with exponential backoff
    (2s, 4s, 8s). The SB API intermittently returns 500 on valid requests
    due to server load — retrying resolves this in practice.

    Args:
        endpoint: Path after BASE_URL, e.g. 'indicadores/principales'
        params: Query parameters dict. 'paginas' and 'registros' will be
                added/overridden internally.

    Returns:
        pd.DataFrame with all records concatenated, or empty DataFrame on failure.
    """
    if not HEADERS["Ocp-Apim-Subscription-Key"]:
        raise EnvironmentError(
            "SB_API_KEY not found in environment. "
            "Add SB_API_KEY=your_key to your .env file."
        )

    params = params.copy()
    params["paginas"] = 1
    params["registros"] = DEFAULT_RECORDS_PER_PAGE

    url = urljoin(BASE_URL, endpoint)
    pages: list[pd.DataFrame] = []
    has_next = True

    while has_next:
        full_url = url + "?" + urlencode(params)
        attempt = 0

        while attempt <= MAX_RETRIES:
            try:
                response = requests.get(full_url, headers=HEADERS, timeout=30)
                response.raise_for_status()
                break  # success — exit retry loop

            except requests.HTTPError as e:
                if response.status_code == 500 and attempt < MAX_RETRIES:
                    wait = 2 ** (attempt + 1)  # 2s, 4s, 8s
                    print(f"  500 error on {endpoint} "
                          f"(attempt {attempt + 1}/{MAX_RETRIES}), "
                          f"retrying in {wait}s...")
                    time.sleep(wait)
                    attempt += 1
                    continue
                # Non-500 error or retries exhausted — give up on this endpoint
                print(f"  HTTP error fetching {endpoint}: {e}")
                raise

            except requests.Timeout:
                if attempt < MAX_RETRIES:
                    wait = 2 ** (attempt + 1)
                    print(f"  Timeout on {endpoint} "
                          f"(attempt {attempt + 1}/{MAX_RETRIES}), "
                          f"retrying in {wait}s...")
                    time.sleep(wait)
                    attempt += 1
                    continue
                print(f"  Timeout fetching {endpoint} after {MAX_RETRIES} retries.")
                raise

            except Exception as e:
                print(f"  Unexpected error for {endpoint}: {e}")
                raise

        try:
            data = response.json()
        except json.JSONDecodeError as e:
            print(f"  JSON decode error for {endpoint}: {e}")
            raise

        if not data:
            # 204 No Content or empty list — no more records.
            break

        pages.append(pd.DataFrame(data))

        # Parse pagination metadata from response header.
        # The header value is a JSON string, not a dict.
        pagination_raw = response.headers.get("x-pagination", "{}")
        pagination = json.loads(pagination_raw)
        has_next = pagination.get("HasNext", False)
        total_pages = pagination.get("TotalPages", 1)

        print(f"  [{endpoint}] Page {params['paginas']}/{total_pages} "
              f"({len(data)} records)")

        params["paginas"] += 1
        time.sleep(REQUEST_DELAY_SECONDS)

    if not pages:
        return pd.DataFrame()

    return pd.concat(pages, ignore_index=True)


def _periodo_to_timestamp(series: pd.Series) -> pd.Series:
    """
    Convert SB API period strings ('YYYY-MM') to month-start Timestamps.
    This aligns with the DatetimeIndex convention used in ingest_bcrd.py.
    """
    return pd.to_datetime(series, format="%Y-%m") + pd.offsets.MonthBegin(0)


# ── Public loaders ────────────────────────────────────────────────────────────

def load_principales_indicadores(
    periodo_inicial: str,
    periodo_final: str | None = None,
) -> pd.DataFrame:
    """
    Fetch 'Principales indicadores del sistema' from SB API.

    This is the most important endpoint for the DR Vulnerability Score.
    It returns system-wide monthly aggregates:
        activos              — total banking system assets (DOP)
        solvencia            — capital adequacy ratio (%)
        montoCarteraCredito  — total credit portfolio (DOP)
        morosidad            — NPL (non-performing loan) ratio (%)
        roa                  — return on assets (%)
        tasaActiva           — weighted average lending rate (%)
        tasaPasiva           — weighted average deposit rate (%)
        margen               — interest margin (%)

    Args:
        periodo_inicial: Start period 'YYYY-MM', e.g. '2010-01'
        periodo_final:   End period 'YYYY-MM'. Defaults to current month.

    Returns:
        DataFrame with DatetimeIndex, columns named as above (snake_case).
    """
    if periodo_final is None:
        periodo_final = pd.Timestamp.now().strftime("%Y-%m")

    params = {
        "periodoInicial": periodo_inicial,
        "periodoFinal": periodo_final,
    }

    print(f"Fetching principales indicadores ({periodo_inicial} to {periodo_final})...")
    raw = _fetch_paginated("indicadores/principales", params)

    if raw.empty:
        print("  WARNING: No data returned for principales indicadores.")
        return pd.DataFrame()

    # Rename columns to snake_case for consistency with ingest_bcrd.py
    rename_map = {
        "periodo":             "periodo",
        "activos":             "sb_activos",
        "solvencia":           "sb_solvencia_pct",
        "montoCarteraCredito": "sb_cartera_total",
        "morosidad":           "sb_morosidad_pct",
        "roa":                 "sb_roa_pct",
        "tasaActiva":          "sb_tasa_activa_pct",
        "tasaPasiva":          "sb_tasa_pasiva_pct",
        "margen":              "sb_margen_pct",
    }
    raw = raw.rename(columns=rename_map)
    raw = raw[[c for c in rename_map.values() if c in raw.columns]]

    raw.index = _periodo_to_timestamp(raw["periodo"])
    raw.index.name = "date"
    raw = raw.drop(columns=["periodo"])
    raw = raw.sort_index()
    raw = raw[~raw.index.duplicated(keep="last")]

    print(f"  Loaded: {len(raw)} rows "
          f"({raw.index.min().date()} to {raw.index.max().date()})")
    return raw


    # load_cartera_total was removed. The carteras/creditos endpoint times out
    # at 30s due to response size, and principales indicadores already provides
    # sb_cartera_total (total credit portfolio) and sb_morosidad_pct (NPL ratio),
    # which covers everything we need from that endpoint.


def load_morosidad_estresada(
    periodo_inicial: str,
    periodo_final: str | None = None,
) -> pd.DataFrame:
    """
    Fetch 'Indicador de morosidad estresada' from SB API.

    Stress-tested delinquency rate — a forward-looking measure of credit risk
    that includes loans at risk of going bad, not just those already delinquent.
    More sensitive than the headline morosidad figure.

    Returns:
        DataFrame with DatetimeIndex and available morosidad estresada columns
        prefixed 'sb_mor_'.
    """
    if periodo_final is None:
        periodo_final = pd.Timestamp.now().strftime("%Y-%m")

    params = {
        "periodoInicial": periodo_inicial,
        "periodoFinal": periodo_final,
        "tipoEntidad": "BM",
    }

    print(f"Fetching morosidad estresada ({periodo_inicial} to {periodo_final})...")
    raw = _fetch_paginated("indicadores/morosidad-estresada", params)

    if raw.empty:
        print("  WARNING: No data returned for morosidad estresada.")
        return pd.DataFrame()

    # The API returns one row per entity per period.
    # entidad == 'TODOS' is the system-wide aggregate — that's the only row
    # we want. Individual institution rows would double-count when summed.
    if "entidad" in raw.columns:
        raw = raw[raw["entidad"].str.upper().str.strip() == "TODOS"].copy()

    if raw.empty:
        print("  WARNING: No 'TODOS' aggregate row found in morosidad estresada.")
        return pd.DataFrame()

    raw.index = _periodo_to_timestamp(raw["periodo"])
    raw.index.name = "date"
    raw = raw.drop(columns=["periodo", "tipoEntidad", "entidad"], errors="ignore")

    # Rename to meaningful snake_case columns
    rename_map = {
        "vencido":                  "sb_mor_vencido",
        "cobranza":                 "sb_mor_cobranza",
        "tc31a60":                  "sb_mor_tc31a60",
        "reestructuradoRea":        "sb_mor_reest_real",
        "reestructuradoTemporal":   "sb_mor_reest_temp",
        "castigos":                 "sb_mor_castigos",
        "adjudicado":               "sb_mor_adjudicado",
        "carteraTotal":             "sb_mor_cartera_total",
    }
    raw = raw.rename(columns=rename_map)
    raw = raw.sort_index()
    raw = raw[~raw.index.duplicated(keep="last")]

    print(f"  Loaded: {len(raw)} rows "
          f"({raw.index.min().date()} to {raw.index.max().date()})")
    return raw


def load_indicadores_financieros(
    periodo_inicial: str,
    periodo_final: str | None = None,
) -> pd.DataFrame:
    """
    Fetch 'Indicadores financieros' from SB API.

    Broader set of financial ratios: liquidity, efficiency, leverage.
    Complements principales indicadores with more granular metrics.

    Returns:
        DataFrame with DatetimeIndex, all columns prefixed 'sb_fin_'.
    """
    if periodo_final is None:
        periodo_final = pd.Timestamp.now().strftime("%Y-%m")

    # Hard cap at 36 months regardless of what periodo_inicial is passed in.
    # This endpoint returns ~50k records per page and times out on large ranges.
    capped_start = (pd.Timestamp.now() - pd.DateOffset(months=36)).strftime("%Y-%m")
    periodo_inicial = max(periodo_inicial, capped_start)

    params = {
        "periodoInicial": periodo_inicial,
        "periodoFinal": periodo_final,
        "tipoEntidad": "BM",
    }

    print(f"Fetching indicadores financieros ({periodo_inicial} to {periodo_final})...")
    raw = _fetch_paginated("indicadores/financieros", params)

    if raw.empty:
        print("  WARNING: No data returned for indicadores financieros.")
        return pd.DataFrame()

    # This endpoint returns long-format data: one row per (periodo, entidad,
    # indicador). We need entidad == 'TODOS' for system aggregates, then pivot
    # so each unique indicator name becomes its own column.
    if "entidad" in raw.columns:
        raw = raw[raw["entidad"].str.upper().str.strip() == "TODOS"].copy()

    if raw.empty:
        print("  WARNING: No 'TODOS' aggregate row found in indicadores financieros.")
        return pd.DataFrame()

    raw["date"] = _periodo_to_timestamp(raw["periodo"])

    # 'indicador' holds the indicator name, 'valor' holds the numeric value.
    # Pivot so each indicator becomes a column, indexed by date.
    if "indicador" not in raw.columns or "valor" not in raw.columns:
        print(f"  WARNING: Expected 'indicador'/'valor' columns. Got: {list(raw.columns)}")
        return pd.DataFrame()

    # Clean indicator names for use as column names:
    # lowercase, replace spaces with underscores, strip special chars
    raw["indicador_clean"] = (
        raw["indicador"]
        .str.strip()
        .str.lower()
        .str.replace(r"[^a-z0-9]+", "_", regex=True)
        .str.strip("_")
    )

    pivoted = (
        raw.pivot_table(
            index="date",
            columns="indicador_clean",
            values="valor",
            aggfunc="mean",   # average if duplicate indicator/date combos exist
        )
        .rename_axis(None, axis=1)
    )
    pivoted.index.name = "date"

    # Prefix all columns to namespace them clearly
    pivoted = pivoted.add_prefix("sb_fin_")
    pivoted = pivoted.sort_index()
    pivoted = pivoted[~pivoted.index.duplicated(keep="last")]

    raw = pivoted

    print(f"  Loaded: {len(raw)} rows "
          f"({raw.index.min().date()} to {raw.index.max().date()})")
    return raw


# ── Unified loader ────────────────────────────────────────────────────────────

def load_sb_all(
    periodo_inicial: str = "2010-01",
    periodo_final: str | None = None,
) -> pd.DataFrame:
    """
    Load all SB indicators and merge into a single monthly DataFrame.
    Mirrors the load_all() pattern from ingest_bcrd.py for consistency.

    Args:
        periodo_inicial: Earliest period to fetch (default '2010-01').
        periodo_final:   Latest period (default: current month).

    Returns:
        Merged monthly DataFrame with all SB indicators.
    """
    if periodo_final is None:
        periodo_final = pd.Timestamp.now().strftime("%Y-%m")

    loaders = {
        "principales":    lambda: load_principales_indicadores(periodo_inicial, periodo_final),
        "morosidad_est":  lambda: load_morosidad_estresada(periodo_inicial, periodo_final),
        "fin_indicators": lambda: load_indicadores_financieros(periodo_inicial, periodo_final),
    }

    frames = {}
    for key, loader in loaders.items():
        try:
            df = loader()
            if not df.empty:
                frames[key] = df
        except Exception as e:
            print(f"  ERROR loading SB [{key}]: {e}")
            # Non-fatal: skip this indicator and continue with the rest.
            continue

    if not frames:
        raise RuntimeError(
            "No SB data loaded. Check SB_API_KEY in .env and network access."
        )

    merged = pd.concat(frames.values(), axis=1, join="outer", sort=True).sort_index()
    print(f"\nSB merged shape: {merged.shape}")
    print(f"Columns: {list(merged.columns)}")
    return merged


# ── CLI test ──────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("Testing SB API ingestion...")
    print("Fetching last 24 months of data...\n")

    # Only fetch 24 months for the test run to keep it fast
    start = (pd.Timestamp.now() - pd.DateOffset(months=24)).strftime("%Y-%m")

    df = load_sb_all(periodo_inicial=start)

    print(f"\nMerged shape: {df.shape}")
    print(f"Date range: {df.index.min()} to {df.index.max()}")
    print("\nMost recent 3 rows:")
    print(df.tail(3).to_string())