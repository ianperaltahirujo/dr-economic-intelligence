"""
FRED Data Ingestion for DR Economic Intelligence Pipeline
Pulls U.S. economic indicators that drive Dominican economic conditions
via remittances, tourism, and trade channels.
"""

import os
import pandas as pd
from fredapi import Fred
from dotenv import load_dotenv

load_dotenv()


def get_fred_client():
    api_key = os.getenv("FRED_API_KEY")
    if not api_key:
        raise ValueError("FRED_API_KEY not found in .env file.")
    return Fred(api_key=api_key)


# U.S. indicators relevant to DR economic conditions
FRED_SERIES = {
    "UNRATE":   "U.S. Unemployment Rate",
    "UMCSENT":  "U.S. Consumer Sentiment (U of Michigan)",
    "PAYEMS":   "U.S. Nonfarm Payrolls",
    "T10Y2Y":   "U.S. Yield Curve Spread (10Y-2Y)",
    "BAA10Y":   "U.S. BAA Corporate Bond Spread",
    "INDPRO":   "U.S. Industrial Production Index",
}


def fetch_us_indicators(start_date: str = "2007-01-01") -> pd.DataFrame:
    """
    Pull U.S. macroeconomic indicators from FRED.
    Start date defaults to 2007 to align with IMAE coverage.

    Returns:
        Monthly DataFrame with one column per FRED series.
    """
    fred = get_fred_client()
    frames = []

    for series_id, description in FRED_SERIES.items():
        print(f"  Fetching {series_id}: {description}...")
        raw = fred.get_series(series_id, observation_start=start_date)
        df = raw.to_frame(name=series_id)
        frames.append(df)

    merged = pd.concat(frames, axis=1, sort=True)

    # Resample to monthly (PAYEMS and others may be monthly already,
    # but daily series like T10Y2Y need averaging)
    merged.index = pd.to_datetime(merged.index)
    monthly = merged.resample("MS").mean()

    return monthly


def save_us_indicators(df: pd.DataFrame,
                       path: str = "data/processed/us_indicators.csv"):
    df.to_csv(path)
    print(f"  U.S. indicators saved to {path}")
    print(f"  Shape: {df.shape}")
    print(f"  Date range: {df.index.min().date()} to {df.index.max().date()}")


def load_us_indicators(path: str = "data/processed/us_indicators.csv"
                       ) -> pd.DataFrame:
    """Load cached U.S. indicators from CSV."""
    df = pd.read_csv(path, index_col=0, parse_dates=True)
    return df


def main():
    print("Fetching U.S. indicators from FRED...")
    df = fetch_us_indicators(start_date="2007-01-01")
    save_us_indicators(df)
    print("\nMost recent 3 rows:")
    print(df.tail(3).to_string())


if __name__ == "__main__":
    main()