"""
Context indicator file downloader.
Downloads gas prices from MICM and tourism files from BCRD CDN.
Called by run_pipeline.py before ingest_context.py runs.
"""

import sys
import time
import requests
from pathlib import Path

OUTPUT_DIR = Path("data/raw")

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/111.0.0.0 Safari/537.36"
    )
}

CONTEXT_FILES = {
    "precios-combustibles-2010-2026.csv": (
        "https://micm.gob.do/transparencias/datos-abiertos/"
        "precios-de-combustibles/precios-de-combustibles-2010-2026.csv"
    ),
    "turismo_gasto_estadia.xls": (
        "https://cdn.bancentral.gov.do/documents/estadisticas/"
        "sector-turismo/documents/turismo_gasto_estadia.xls"
    ),
    "turismo_fiscal.xls": (
        "https://cdn.bancentral.gov.do/documents/estadisticas/"
        "sector-turismo/documents/turismo_fiscal.xls"
    ),
    "turismo_fiscal_mensual.xlsx": (
        "https://cdn.bancentral.gov.do/documents/estadisticas/"
        "sector-turismo/documents/turismo_fiscal_mensual.xlsx"
    ),
}

REQUEST_DELAY = 1.0


def download_file(url: str, dest: Path) -> bool:
    try:
        r = requests.get(url, headers=HEADERS, timeout=60, stream=True)
        r.raise_for_status()
        with open(dest, "wb") as f:
            for chunk in r.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)
        size_kb = dest.stat().st_size / 1024
        print(f"  [OK] {dest.name} ({size_kb:.1f} KB)")
        return True
    except requests.HTTPError as e:
        print(f"  [HTTP ERROR] {dest.name}: {e}")
        return False
    except Exception as e:
        print(f"  [ERROR] {dest.name}: {e}")
        return False


def download_all(output_dir: Path = OUTPUT_DIR) -> dict:
    output_dir.mkdir(parents=True, exist_ok=True)
    print(f"Downloading {len(CONTEXT_FILES)} context files to {output_dir}/\n")

    success, failed = [], []
    for filename, url in CONTEXT_FILES.items():
        dest = output_dir / filename
        ok = download_file(url, dest)
        (success if ok else failed).append(filename)
        time.sleep(REQUEST_DELAY)

    print(f"\nContext download complete: {len(success)}/{len(CONTEXT_FILES)} succeeded.")
    if failed:
        print(f"Failed: {failed}")
    return {"success": success, "failed": failed}


if __name__ == "__main__":
    results = download_all()
    if results["failed"]:
        sys.exit(1)