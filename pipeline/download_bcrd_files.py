"""
BCRD Excel File Downloader
Downloads the latest BCRD statistical Excel files from the CDN.
Each download overwrites the existing file — no versioning, no accumulation.

Run this at the start of the weekly pipeline to ensure fresh data before
ingest_bcrd.py parses the files.

Usage:
    python pipeline/download_bcrd_files.py
"""

import os
import sys
import time
import requests
from pathlib import Path

# Output directory — must match the path expected by ingest_bcrd.load_all()
OUTPUT_DIR = Path("data/raw")

# CDN URLs mapped to local filenames.
# Order doesn't matter — all are downloaded independently.
BCRD_FILES = {
    "Remesas_6.xlsx": (
        "https://cdn.bancentral.gov.do/documents/estadisticas/"
        "sector-externo/documents/Remesas_6.xlsx"
    ),
    "imae_2018.xlsx": (
        "https://cdn.bancentral.gov.do/documents/estadisticas/"
        "sector-real/documents/imae_2018.xlsx"
    ),
    "TASA_DOLAR_REFERENCIA_MC.xlsx": (
        "https://cdn.bancentral.gov.do/documents/estadisticas/"
        "mercado-cambiario/documents/TASA_DOLAR_REFERENCIA_MC.xlsx"
    ),
    "ipc_base_2019-2020.xls": (
        "https://cdn.bancentral.gov.do/documents/estadisticas/"
        "precios/documents/ipc_base_2019-2020.xls"
    ),
    "lleg_total.xls": (
        "https://cdn.bancentral.gov.do/documents/estadisticas/"
        "sector-turismo/documents/lleg_total.xls"
    ),
    "reservas_internacionales.xlsx": (
        "https://cdn.bancentral.gov.do/documents/estadisticas/"
        "sector-externo/documents/reservas_internacionales.xlsx"
    ),
}

# HTTP headers — the BCRD CDN requires a realistic User-Agent
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/111.0.0.0 Safari/537.36"
    )
}

# Seconds to wait between requests — polite crawling
REQUEST_DELAY = 1.0


def download_file(url: str, dest: Path) -> bool:
    """
    Download a single file from url and save to dest.
    Overwrites dest if it already exists.

    Returns True on success, False on failure.
    """
    try:
        response = requests.get(url, headers=HEADERS, timeout=60, stream=True)
        response.raise_for_status()

        # Write in chunks to handle large files without loading into memory
        with open(dest, "wb") as f:
            for chunk in response.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)

        size_kb = dest.stat().st_size / 1024
        print(f"  [OK] {dest.name} ({size_kb:.1f} KB)")
        return True

    except requests.HTTPError as e:
        print(f"  [HTTP ERROR] {dest.name}: {e}")
        return False
    except requests.Timeout:
        print(f"  [TIMEOUT] {dest.name}: request exceeded 60s")
        return False
    except Exception as e:
        print(f"  [ERROR] {dest.name}: {e}")
        return False


def download_all(output_dir: Path = OUTPUT_DIR) -> dict:
    """
    Download all BCRD Excel files to output_dir.

    Returns:
        dict with keys 'success' and 'failed' listing filenames.
    """
    output_dir.mkdir(parents=True, exist_ok=True)

    print(f"Downloading {len(BCRD_FILES)} BCRD files to {output_dir}/\n")

    success = []
    failed  = []

    for filename, url in BCRD_FILES.items():
        dest = output_dir / filename
        ok = download_file(url, dest)
        if ok:
            success.append(filename)
        else:
            failed.append(filename)
        time.sleep(REQUEST_DELAY)

    print(f"\nDownload complete: {len(success)}/{len(BCRD_FILES)} succeeded.")

    if failed:
        print(f"Failed files ({len(failed)}):")
        for f in failed:
            print(f"  - {f}")
        print("Pipeline will use existing cached versions for failed files.")

    return {"success": success, "failed": failed}


if __name__ == "__main__":
    results = download_all()
    # Exit with error code if any downloads failed, so the pipeline
    # orchestrator (Prefect/GitHub Actions) can detect and alert.
    if results["failed"]:
        sys.exit(1)