"""
BCRD API Data Ingestion Module
Fetches macroeconomic indicators from the Banco Central de la Republica
Dominicana REST API.

IMPORTANT: All endpoints are POST, not GET.
Auth: API key passed in request body as "token" field.
Base URL: https://api.bancentral.gov.do

Endpoints:
    POST /api/services/app/MacroVariables/Inflacion       -> inflation/IPC
    POST /api/services/app/MacroVariables/SectorReal      -> IMAE, GDP
    POST /api/services/app/MacroVariables/SectorExterno   -> remesas, trade
    POST /api/services/app/MacroVariables/Monetarias      -> monetary aggregates
    POST /api/services/app/MacroVariables/HistoricoTasas  -> exchange rate history
    POST /api/v2/HistoricoIPC                             -> IPC with date range filter

Response schema for all endpoints:
    { "name": "string", "values": [ {...}, ... ] }

Usage:
    python pipeline/ingest_bcrd_api.py --discover   # probe all endpoints, print raw structure
    python pipeline/ingest_bcrd_api.py              # run full ingestion
"""

import os
import sys
import json
import argparse
import requests
import pandas as pd
import numpy as np
from dotenv import load_dotenv
from pathlib import Path

load_dotenv()

BASE_URL = "https://api.bancentral.gov.do"

# Token is passed in the POST body, not as a header.
# Headers are standard content-type only.
REQUEST_HEADERS = {
    "Content-Type": "application/json",
    "Accept": "text/plain",
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/111.0.0.0 Safari/537.36"
    ),
}

TOKEN = os.getenv("BCRD_API_KEY", "")


# ── Core POST helper ──────────────────────────────────────────────────────────

def _post(endpoint: str, extra_body: dict = None) -> dict | None:
    """
    POST to a BCRD API endpoint with the token in the request body.

    Args:
        endpoint:   Path after BASE_URL, e.g. '/api/services/app/MacroVariables/Inflacion'
        extra_body: Additional fields beyond 'token' (e.g. date range params)

    Returns:
        Parsed JSON response dict, or None on failure.
    """
    if not TOKEN:
        raise EnvironmentError(
            "BCRD_API_KEY not found. Add BCRD_API_KEY=your_key to .env"
        )

    body = {"token": TOKEN}
    if extra_body:
        body.update(extra_body)

    url = BASE_URL + endpoint
    try:
        r = requests.post(url, headers=REQUEST_HEADERS, json=body, timeout=30)
        if r.status_code == 200:
            return r.json()
        else:
            print(f"  HTTP {r.status_code} for {endpoint}: {r.text[:200]}")
            return None
    except requests.Timeout:
        print(f"  TIMEOUT: {endpoint}")
        return None
    except Exception as e:
        print(f"  ERROR: {endpoint}: {e}")
        return None


# ── Endpoint discovery ────────────────────────────────────────────────────────

CANDIDATE_ENDPOINTS = [
    "/api/services/app/MacroVariables/Inflacion",
    "/api/services/app/MacroVariables/SectorReal",
    "/api/services/app/MacroVariables/SectorExterno",
    "/api/services/app/MacroVariables/Monetarias",
    "/api/services/app/MacroVariables/HistoricoTasas",
    "/api/v2/HistoricoIPC",
]


def discover_endpoints() -> None:
    """
    POST to all known endpoints with just the token and print the raw response
    structure. This tells us the actual field names inside 'values' so we can
    write correct parsers.
    """
    if not TOKEN:
        print("ERROR: BCRD_API_KEY not set in .env")
        return

    print(f"Probing {len(CANDIDATE_ENDPOINTS)} BCRD endpoints (POST)...\n")

    for endpoint in CANDIDATE_ENDPOINTS:
        print(f"Endpoint: {endpoint}")

        # HistoricoTasas requires date range — use a 30-day window as probe
        extra = {}
        if "HistoricoTasas" in endpoint:
            extra = {
                "fromDate": "2026-05-01T00:00:00.000Z",
                "toDate":   "2026-05-31T00:00:00.000Z",
                "skipCount": 0,
                "maxResultCount": 5,
            }
        elif "HistoricoIPC" in endpoint:
            extra = {
                "monthFrom": 1, "yearFrom": 2026,
                "monthTo":   5, "yearTo":   2026,
                "skipCount": 0, "maxResultCount": 5,
            }

        data = _post(endpoint, extra)

        if data is None:
            print("  [FAILED]\n")
            continue

        print(f"  [OK 200]")
        print(f"  Top-level keys: {list(data.keys()) if isinstance(data, dict) else type(data)}")

        if isinstance(data, dict) and "values" in data:
            values = data["values"]
            print(f"  values: list of {len(values)} items")
            if values:
                first = values[0]
                if isinstance(first, dict):
                    print(f"  First item keys: {list(first.keys())}")
                    print(f"  First item: {json.dumps(first, ensure_ascii=False, default=str)[:300]}")
                else:
                    print(f"  First item type: {type(first)}")
                    print(f"  First item: {str(first)[:300]}")
        elif isinstance(data, list):
            print(f"  Response is list of {len(data)}")
            if data:
                print(f"  First item: {json.dumps(data[0], ensure_ascii=False, default=str)[:300]}")
        else:
            print(f"  Raw response: {json.dumps(data, ensure_ascii=False, default=str)[:400]}")

        print()


# ── Response parser ───────────────────────────────────────────────────────────

def _parse_values(data: dict, date_key: str, value_key: str,
                  output_col: str) -> pd.DataFrame:
    """
    Parse a standard BCRD API response into a monthly DatetimeIndex DataFrame.

    Standard response format:
        { "name": "...", "values": [ {"fecha": "...", "valor": ...}, ... ] }

    Args:
        data:       Raw API response dict
        date_key:   Field name for the date inside each values item
        value_key:  Field name for the numeric value inside each values item
        output_col: Column name in the output DataFrame

    Returns:
        DataFrame with DatetimeIndex and one column named output_col.
    """
    if not isinstance(data, dict) or "values" not in data:
        print(f"  WARNING: Unexpected response structure. Keys: {list(data.keys()) if isinstance(data, dict) else type(data)}")
        return pd.DataFrame()

    values = data["values"]
    if not values:
        print(f"  WARNING: Empty values list in response.")
        return pd.DataFrame()

    records = []
    for item in values:
        if not isinstance(item, dict):
            continue
        raw_date  = item.get(date_key)
        raw_value = item.get(value_key)
        if raw_date is None or raw_value is None:
            continue
        try:
            date  = pd.to_datetime(raw_date, errors="coerce")
            value = float(raw_value)
            if pd.notna(date):
                records.append({"date": date, output_col: value})
        except (ValueError, TypeError):
            continue

    if not records:
        print(f"  WARNING: No valid records parsed. "
              f"Check date_key='{date_key}' and value_key='{value_key}'.")
        return pd.DataFrame()

    df = pd.DataFrame(records).set_index("date")
    # Align to month-start to match ingest_bcrd.py and ingest_sb.py convention
    df.index = df.index + pd.offsets.MonthBegin(0)
    df = df.sort_index()
    df = df[~df.index.duplicated(keep="last")]
    return df


# ── Individual loaders ────────────────────────────────────────────────────────
# Column names below are placeholders pending discovery output.
# After running --discover, update date_key and value_key to match
# the actual field names returned by each endpoint.

def load_ipc_api() -> pd.DataFrame:
    """
    Fetch IPC inflation data.
    Tries HistoricoIPC (date-filtered) first, falls back to Inflacion.
    """
    # Pull full available history
    data = _post("/api/v2/HistoricoIPC", {
        "monthFrom": 1,  "yearFrom": 2007,
        "monthTo":   12, "yearTo":   2026,
        "skipCount": 0,  "maxResultCount": 10000,
    })
    if data is None:
        data = _post("/api/services/app/MacroVariables/Inflacion")
    if data is None:
        return pd.DataFrame()

    # UPDATE date_key and value_key after running --discover
    return _parse_values(data, date_key="fecha", value_key="valor",
                         output_col="ipc_yoy_pct")


def load_exchange_rate_api() -> pd.DataFrame:
    """
    Fetch DOP/USD exchange rate historical series.
    Uses HistoricoTasas with full date range.
    """
    data = _post("/api/services/app/MacroVariables/HistoricoTasas", {
        "fromDate": "2007-01-01T00:00:00.000Z",
        "toDate":   "2026-12-31T00:00:00.000Z",
        "skipCount": 0,
        "maxResultCount": 10000,
    })
    if data is None:
        return pd.DataFrame()

    # UPDATE date_key and value_key after running --discover
    return _parse_values(data, date_key="fecha", value_key="venta",
                         output_col="dop_usd")


def load_sector_externo_api() -> pd.DataFrame:
    """
    Fetch SectorExterno which should contain remittances and trade data.
    Returns raw merged DataFrame — caller selects the remesas column.
    """
    data = _post("/api/services/app/MacroVariables/SectorExterno")
    if data is None:
        return pd.DataFrame()

    # SectorExterno likely returns multiple variables — parse after discovery
    return _parse_values(data, date_key="fecha", value_key="valor",
                         output_col="sector_externo_valor")


def load_sector_real_api() -> pd.DataFrame:
    """
    Fetch SectorReal which should contain IMAE and GDP data.
    """
    data = _post("/api/services/app/MacroVariables/SectorReal")
    if data is None:
        return pd.DataFrame()

    return _parse_values(data, date_key="fecha", value_key="valor",
                         output_col="sector_real_valor")


def load_monetarias_api() -> pd.DataFrame:
    """
    Fetch monetary aggregates including reserves.
    """
    data = _post("/api/services/app/MacroVariables/Monetarias")
    if data is None:
        return pd.DataFrame()

    return _parse_values(data, date_key="fecha", value_key="valor",
                         output_col="monetarias_valor")


# ── Unified loader ────────────────────────────────────────────────────────────

def load_all_api() -> pd.DataFrame:
    """
    Fetch all BCRD indicators via API and merge into a single monthly DataFrame.
    NOTE: column name mappings need verification after running --discover.
    """
    loaders = {
        "ipc":           load_ipc_api,
        "exchange_rate": load_exchange_rate_api,
        "sector_externo":load_sector_externo_api,
        "sector_real":   load_sector_real_api,
        "monetarias":    load_monetarias_api,
    }

    frames = {}
    for key, loader in loaders.items():
        print(f"  Fetching BCRD {key}...")
        try:
            df = loader()
            if not df.empty:
                frames[key] = df
                print(f"    {key}: {len(df)} rows "
                      f"({df.index.min().date()} to {df.index.max().date()})")
            else:
                print(f"    {key}: no data returned")
        except Exception as e:
            print(f"    ERROR loading {key}: {e}")

    if not frames:
        raise RuntimeError(
            "No BCRD API data loaded. Run with --discover to check endpoints."
        )

    merged = pd.concat(frames.values(), axis=1, join="outer", sort=True)
    merged = merged.sort_index()
    return merged


# ── CLI ───────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="BCRD API ingestion")
    parser.add_argument(
        "--discover",
        action="store_true",
        help="Probe all endpoints and print raw response structure"
    )
    args = parser.parse_args()

    if args.discover:
        discover_endpoints()
    else:
        print("Fetching BCRD indicators via API...\n")
        df = load_all_api()
        print(f"\nMerged shape: {df.shape}")
        print(f"Date range: {df.index.min().date()} to {df.index.max().date()}")
        print("\nMost recent 3 rows:")
        print(df.tail(3).to_string())